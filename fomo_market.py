"""국내 시장 공포탐욕 지수. CNN Fear & Greed Index를 한국 시장에 맞춰 옮겼다.

CNN은 7개 지표를 0~100으로 정규화해 평균한다. 지표 대부분이 미국 전용 데이터
(정크본드 스프레드, Put/Call 비율, S&P500 신고가 수)라 국내에서 받을 수 있는
것으로 대응 지표를 골랐다.

| CNN 원본 | 국내 대응 | 근거 |
|---|---|---|
| Market Momentum | 코스피 vs 125일선 | 20일 수익률과 상관 +0.86 |
| Market Volatility | 코스피 20일 실현변동성(역) | +0.33 |
| Stock Price Breadth | 상승 종목 비율 | 그 자체가 0~100 척도 |
| 52-Week High/Low | 코스피 52주 레인지 내 위치 | +0.91 |
| (신규) | RSI(14) | +0.76 |

**환율과 금, VIX는 넣지 않았다.** CNN의 Safe Haven Demand를 원달러로 옮기려 했지만
실측에서 코스피와 원달러 일간 수익률 상관이 **+0.457**로 같은 방향이었다. 교과서와
반대다(외국인 자금이 들어오면 지수와 환율이 함께 움직인 국면). 금(+0.19),
TLT(+0.07), VIX(-0.07)도 유효한 역상관이 없었다. 이론상 맞는 지표라도 데이터가
뒷받침하지 않으면 넣지 않는다. 실제로 이 지표를 넣었을 때 급락장(코스피 -18%,
변동성 1년 최고)에서 환율이 100점을 찍어 전체 점수를 끌어올렸다.

그래서 국내 가격 데이터로만 5개 지표를 만들고, 전부 지수 등락과 같은 방향임을
상관계수로 확인했다. 정규화는 과거 1년 분포의 백분위를 쓴다. 절대 임계값을 두면
국면이 바뀔 때마다 기준을 손봐야 하지만, 백분위는 "최근 1년 중 어느 수준인가"를
그대로 말해준다.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

LOOKBACK_DAYS = 400          # 백분위 계산용 과거 구간 (거래일 약 250일 확보)
MOMENTUM_WINDOW = 125        # CNN과 같은 이평 구간
VOL_WINDOW = 20
RANGE_WINDOW = 250           # 52주 (거래일 기준)
RSI_WINDOW = 14

_CACHE_PATH = Path(__file__).parent / ".cache" / "market_gauge.json"
_CACHE_TTL_SEC = 60 * 60     # 시장 데이터는 1시간 캐시


@dataclass
class Component:
    key: str
    label: str
    score: float | None      # 0(극단적 공포) ~ 100(극단적 탐욕)
    detail: str              # 화면에 그대로 보여줄 원값 설명


def _percentile(series, value: float) -> float:
    """과거 분포에서 현재값의 위치(0~100)."""
    clean = series.dropna()
    if len(clean) < 30:
        return 50.0
    return round(float((clean < value).mean() * 100), 1)


def _momentum(fdr, start: str) -> Component:
    """코스피가 125일선 위인지. CNN Market Momentum과 같은 방식이다."""
    close = fdr.DataReader("KS11", start)["Close"].dropna()
    ma = close.rolling(MOMENTUM_WINDOW).mean()
    gap = (close / ma - 1) * 100
    current = float(gap.iloc[-1])
    return Component(
        "momentum",
        "모멘텀",
        _percentile(gap, current),
        f"125일선 대비 {current:+.1f}%",
    )


def _volatility(fdr, start: str) -> Component:
    """코스피 실현변동성. 변동성이 높을수록 공포이므로 백분위를 뒤집는다.

    VKOSPI가 조회되지 않아 일간 수익률로 직접 계산한다.
    """
    import numpy as np

    close = fdr.DataReader("KS11", start)["Close"].dropna()
    vol = close.pct_change().rolling(VOL_WINDOW).std() * np.sqrt(252) * 100
    current = float(vol.iloc[-1])
    return Component(
        "volatility",
        "변동성",
        round(100 - _percentile(vol, current), 1),
        f"20일 변동성 {current:.0f}%",
    )


def _breadth(fdr) -> Component:
    """상승 종목 비율. 지수는 대형주에 끌려가므로 폭을 따로 본다."""
    import pandas as pd

    listing = fdr.StockListing("KRX")
    ratio = pd.to_numeric(listing["ChagesRatio"], errors="coerce").dropna()
    if not len(ratio):
        return Component("breadth", "시장 폭", None, "조회 실패")
    advancing = int((ratio > 0).sum())
    declining = int((ratio < 0).sum())
    share = advancing / len(ratio) * 100
    # 상승 비율은 그 자체가 0~100 척도다. 절반이 오르면 중립이다.
    return Component(
        "breadth",
        "시장 폭",
        round(share, 1),
        f"상승 {advancing} / 하락 {declining}",
    )


def _range_position(fdr, start: str) -> Component:
    """52주 레인지 안에서 코스피가 어디쯤인지.

    CNN의 신고가-신저가 지표를 지수 단위로 옮긴 것이다. 0이면 1년 최저, 100이면 최고다.
    백분위를 다시 씌우지 않는다. 이미 0~100 척도라 그대로가 더 읽기 쉽다.
    """
    close = fdr.DataReader("KS11", start)["Close"].dropna()
    window = close.tail(RANGE_WINDOW)
    low, high = float(window.min()), float(window.max())
    if high <= low:
        return Component("range", "52주 위치", None, "구간 없음")
    current = float(close.iloc[-1])
    position = (current - low) / (high - low) * 100
    return Component(
        "range",
        "52주 위치",
        round(position, 1),
        f"{low:,.0f} ~ {high:,.0f} 중 {current:,.0f}",
    )


def _rsi(fdr, start: str) -> Component:
    """코스피 RSI(14). 과매도(30 이하)가 공포, 과매수(70 이상)가 탐욕이다.

    RSI도 이미 0~100이라 백분위를 씌우지 않는다.
    """
    close = fdr.DataReader("KS11", start)["Close"].dropna()
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(RSI_WINDOW).mean()
    loss = (-delta.clip(upper=0)).rolling(RSI_WINDOW).mean()
    rs = gain / loss.replace(0, float("nan"))
    rsi = 100 - 100 / (1 + rs)
    current = float(rsi.iloc[-1])
    return Component("rsi", "RSI", round(current, 1), f"RSI(14) {current:.0f}")


def _interpret(score: float) -> tuple[str, str]:
    """CNN과 같은 5구간.

    구간 정의는 `fomo_core.interpret` 하나만 쓴다. 여기와 저기에 따로 두면 경계가
    어긋나 같은 점수가 다른 라벨을 받는다(실제로 42.1이 한쪽에서 중립, 다른 쪽에서
    공포로 갈렸다).
    """
    import fomo_core

    return fomo_core.interpret(score)


def market_gauge(force: bool = False) -> dict | None:
    """국내 시장 공포탐욕 지수. 조회 실패하면 None.

    지표 하나가 실패해도 나머지 평균으로 계산한다. 전부 실패하면 None이다.
    """
    if not force and _CACHE_PATH.exists():
        if time.time() - _CACHE_PATH.stat().st_mtime < _CACHE_TTL_SEC:
            try:
                return json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass

    try:
        import FinanceDataReader as fdr
    except ImportError:
        return None

    start = (date.today() - timedelta(days=LOOKBACK_DAYS)).isoformat()
    builders = (
        lambda: _momentum(fdr, start),
        lambda: _volatility(fdr, start),
        lambda: _breadth(fdr),
        lambda: _range_position(fdr, start),
        lambda: _rsi(fdr, start),
    )

    components: list[Component] = []
    for build in builders:
        try:
            components.append(build())
        except Exception:
            continue   # 지표 하나가 빠져도 나머지로 간다

    usable = [c for c in components if c.score is not None]
    if not usable:
        return None

    score = round(sum(c.score for c in usable) / len(usable), 1)
    zone, label = _interpret(score)
    payload = {
        "score": score,
        "zone": zone,
        "label": label,
        "as_of": date.today().isoformat(),
        "components": [
            {"key": c.key, "label": c.label, "score": c.score, "detail": c.detail}
            for c in components
        ],
    }

    try:
        _CACHE_PATH.parent.mkdir(exist_ok=True)
        _CACHE_PATH.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass
    return payload
