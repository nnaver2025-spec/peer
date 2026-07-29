"""지수 여론 감시 대상 정의.

지수는 종목과 다르게 다뤄야 한다.

1. 네이버 종목토론실이 없다. 6자리 코드가 없으니 그 소스는 자동으로 빠진다.
2. 부르는 말이 갈린다. S&P500은 `에센피`, `SPY`로도 불리고 한 이름만 검색하면
   표본의 대부분을 놓친다. 그래서 별칭을 묶어 검색하고 제목 기준으로 합친다.
3. 지수 전용 디시 갤러리(kospi, kosdaq, snp500index, dow100)는 대부분 죽어 있다.
   실측 결과 코스닥 갤러리는 2024-08, S&P 갤러리는 2025-04에 마지막 글이 올라왔다.
   그래서 별도 갤러리를 붙이지 않고 기존 8개 소스에 지수 키워드로 검색한다.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Index:
    key: str
    label: str
    market: str          # 국내 | 미국
    aliases: tuple[str, ...]
    fdr_symbol: str = ""     # 현재 지수 조회용 (FinanceDataReader)
    lookback_days: int = 0   # 0이면 종목과 같은 기간(fomo_core.LOOKBACK_DAYS)


# 미국 지수 수집 기간. 국내 커뮤니티에서 S&P500, 나스닥 언급은 국내 지수보다 훨씬
# 드물다. 3일로 자르면 S&P500이 25개(키워드 3회)만 남아 점수가 안 나왔다.
# 국내 지수(코스피/코스닥)는 표본이 충분해 종목과 같은 3일을 쓴다. 같은 기간이어야
# 시장 심리와 나란히 놓고 읽을 수 있다.
US_INDEX_LOOKBACK_DAYS = 7


# 별칭은 실제 검색 결과가 잡히는 표기만 넣는다. 짧은 약어(`국장`, `나닥`)는 다른
# 맥락에도 걸리므로 지수 이름과 함께 쓰이는 것만 골랐다.
#
# `스피`, `미장`, `서학`도 후보였지만 뺐다. 검색 결과는 많은데 특정 지수를 가리키지
# 않는다(`미장 언제 열어?`는 어느 지수 얘기도 아니다). 지수 지표에는 그 지수를
# 지목하는 말만 쓴다.
INDICES: tuple[Index, ...] = (
    Index("kospi", "코스피", "국내", ("코스피", "KOSPI"), "KS11"),
    Index("kosdaq", "코스닥", "국내", ("코스닥", "KOSDAQ"), "KQ11"),
    # S&P500은 부르는 말이 가장 많이 갈린다. 3일 기준에서 25개(키워드 3회)만
    # 잡혀 표본 부족이었고, 별칭을 늘려 실측으로 채웠다.
    Index(
        "sp500", "S&P500", "미국",
        ("S&P500", "S&P", "에센피", "에스앤피", "SPY", "SPX"), "US500",
        US_INDEX_LOOKBACK_DAYS,
    ),
    Index(
        "nasdaq", "나스닥", "미국",
        ("나스닥", "NASDAQ", "QQQ"), "IXIC", US_INDEX_LOOKBACK_DAYS,
    ),
)

_CACHE_PATH = Path(__file__).parent / ".cache" / "index_levels.json"
_LEVEL_TTL_SEC = 6 * 60 * 60


def index_levels() -> dict[str, float]:
    """지수별 최근 종가. 조회 실패하면 그 지수만 빠진다.

    `코스피 4천 가즈아`가 조롱인지 기대인지는 현재 지수를 알아야 판단된다.
    6시간 캐시를 두어 크론이 돌 때마다 4번씩 조회하지 않는다.
    """
    if _CACHE_PATH.exists() and time.time() - _CACHE_PATH.stat().st_mtime < _LEVEL_TTL_SEC:
        try:
            return json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    levels: dict[str, float] = {}
    try:
        import FinanceDataReader as fdr
        from datetime import date, timedelta

        start = (date.today() - timedelta(days=10)).isoformat()
        for index in INDICES:
            if not index.fdr_symbol:
                continue
            try:
                close = fdr.DataReader(index.fdr_symbol, start)["Close"].dropna()
                if len(close):
                    levels[index.key] = float(close.iloc[-1])
            except Exception:
                continue   # 한 지수가 실패해도 나머지는 쓴다
    except Exception:
        return {}

    try:
        _CACHE_PATH.parent.mkdir(exist_ok=True)
        _CACHE_PATH.write_text(json.dumps(levels), encoding="utf-8")
    except OSError:
        pass
    return levels
