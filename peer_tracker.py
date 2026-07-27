"""해외 선행(Lead) Peer 그룹과 국내 후행(Lag) Peer 그룹의 주가 괴리율 추적.

2020년 이후 종가를 한 번 받아 두 가지를 계산한다.
1. 최근 6개월 정규화 인덱스의 Lag - Lead 스프레드와 20일 Z-Score
2. 장기 표본 기준 커플링 강도 (동행 상관, 시차 1일 전달 상관, 연도별 안정성)

커플링이 약한 그룹에서는 스프레드가 평균회귀할 근거가 없으므로,
Z-Score 신호의 신뢰도를 커플링 등급으로 함께 내려보낸다.

결과는 dashboard_data.json으로 저장한다.
"""

from __future__ import annotations

import json
import time
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf

from sheet_groups import SHEET_GROUPS

# 그룹 정의는 관심종목 시트를 옮긴 sheet_groups.py가 단일 출처다.
# lag(국내)가 없는 표는 스프레드를 계산할 수 없어 제외한다.
PEER_GROUPS: dict[str, dict[str, object]] = {
    key: {
        "sector": cfg["sector"],
        "desc": cfg["desc"],
        "lead_tickers": cfg["lead"],
        "lag_tickers": cfg["lag"],
    }
    for key, cfg in SHEET_GROUPS.items()
    if cfg["lag"]
}


LOOKBACK_DAYS = 183          # 최근 6개월

# 국내 티커 표시용 종목명. analysis/fetch_kr_names.py가 yfinance 조회명으로 생성한다.
# 한글명은 손으로 확정한 값이고, 나머지는 조회된 영문 상장명이다.
_NAMES_PATH = Path(__file__).parent / "kr_names.json"
KR_NAMES: dict[str, str] = (
    json.loads(_NAMES_PATH.read_text(encoding="utf-8")) if _NAMES_PATH.exists() else {}
)


Z_WINDOW = 20                # Z-Score 이동 윈도우 (거래일)
ALERT_THRESHOLD = 1.5
SLEEP_SEC = 0.2              # API 차단 방지
HISTORY_POINTS = 60          # 프론트 스파크라인용 최근 구간

COUPLING_START = date(2020, 1, 1)   # 장기 커플링 측정 시작
MIN_COUPLING_DAYS = 250             # 최소 1년치는 있어야 상관을 신뢰
COUPLING_TIERS = (                  # (등급, 최소 커플링 상관)
    ("strong", 0.30),
    ("moderate", 0.15),
    ("weak", 0.0),
)

OUTPUT_PATH = Path(__file__).parent / "frontend" / "public" / "dashboard_data.json"


def label_of(ticker: str) -> str:
    """국내 티커는 종목명으로, 해외 티커는 티커 그대로 표시한다."""
    return KR_NAMES.get(ticker, ticker)


def fetch_close(ticker: str, start: date, end: date) -> pd.Series | None:
    """단일 티커의 수정 종가 시리즈. 실패하거나 데이터가 없으면 None."""
    try:
        df = yf.download(
            ticker,
            start=start.isoformat(),
            end=end.isoformat(),
            auto_adjust=True,
            progress=False,
            actions=False,
            threads=False,
        )
    except Exception as exc:  # 네트워크/티커 오류는 그룹 전체를 죽이지 않는다
        print(f"  [warn] {ticker} 다운로드 실패: {exc}")
        return None
    finally:
        time.sleep(SLEEP_SEC)

    if df is None or df.empty:
        print(f"  [warn] {ticker} 데이터 없음")
        return None

    close = df["Close"]
    if isinstance(close, pd.DataFrame):  # yfinance가 MultiIndex 컬럼을 주는 경우
        close = close.iloc[:, 0]
    close = close.dropna()
    close.index = pd.to_datetime(close.index).tz_localize(None).normalize()
    return close.rename(ticker) if not close.empty else None


def build_group_frame(closes: list[pd.Series]) -> pd.DataFrame:
    """티커 종가들을 날짜 union으로 정렬 후 ffill. 전 종목 데이터가 갖춰진 날부터 반환."""
    frame = pd.concat(closes, axis=1, sort=True).ffill()
    return frame.dropna()


def chain_index(closes: list[pd.Series]) -> pd.Series:
    """구성 종목 상장 시점이 달라도 끊기지 않는 그룹 인덱스.

    각 날짜에 데이터가 있는 종목의 일간 수익률만 평균해 누적한다.
    신규 종목은 편입 시점의 인덱스 레벨을 이어받으므로 점프가 생기지 않는다.
    """
    frame = pd.concat(closes, axis=1, sort=True).ffill()
    frame = frame.loc[frame.notna().any(axis=1)]
    tradable = frame.notna() & frame.shift(1).notna()
    daily = frame.pct_change().where(tradable).mean(axis=1).fillna(0.0)
    return 100 * (1 + daily).cumprod()


def coupling_stats(lead: pd.Series, lag: pd.Series) -> dict | None:
    """장기 표본의 커플링 강도. 표본이 짧으면 None."""
    common = lead.index.intersection(lag.index)
    if len(common) < MIN_COUPLING_DAYS:
        return None

    lead_ret = lead.loc[common].pct_change()
    lag_ret = lag.loc[common].pct_change()

    same = pd.concat([lead_ret, lag_ret], axis=1).dropna()
    lagged = pd.concat([lead_ret.shift(1), lag_ret], axis=1).dropna()
    corr = float(same.iloc[:, 0].corr(same.iloc[:, 1]))
    corr_lag1 = float(lagged.iloc[:, 0].corr(lagged.iloc[:, 1]))

    # 연도별 상관: 특정 국면에만 성립하는 관계인지 구분한다.
    by_year = {}
    for year, chunk in same.groupby(same.index.year):
        if len(chunk) > 30:
            by_year[int(year)] = round(float(chunk.iloc[:, 0].corr(chunk.iloc[:, 1])), 2)

    # 등급은 동행과 시차1일 중 강한 쪽으로 정한다.
    # 미국 장이 먼저 닫히는 그룹은 전달이 다음 거래일에 나타나므로
    # 동행 상관만 보면 실제 연결을 놓친다 (예: 미국 방산 corr 0.13, lag1 0.28).
    strength = max(corr, corr_lag1)
    tier = next(name for name, floor in COUPLING_TIERS if strength >= floor)
    lead_channel = "same_day" if corr >= corr_lag1 else "next_day"
    values = list(by_year.values())

    return {
        "tier": tier,
        "strength": round(strength, 2),
        "lead_channel": lead_channel,
        "corr": round(corr, 2),
        "corr_lag1": round(corr_lag1, 2),
        "sample_days": len(common),
        "sample_from": common[0].date().isoformat(),
        "by_year": by_year,
        "year_min": min(values) if values else None,
        "year_max": max(values) if values else None,
        # 음수 연도가 있으면 관계가 뒤집힌 국면이 있었다는 뜻
        "negative_years": sum(v < 0 for v in values),
    }


def normalize_to_100(frame: pd.DataFrame) -> pd.Series:
    """기준일(첫 행)을 100으로 정규화한 뒤 종목 평균 = 그룹 인덱스."""
    return (frame / frame.iloc[0] * 100).mean(axis=1)


def analyze_group(key: str, cfg: dict, spread_start: date, end: date) -> dict | None:
    print(f"[{key}] {cfg['desc']}")
    leads: list[pd.Series] = []
    lags: list[pd.Series] = []
    missing: list[str] = []

    for bucket, tickers in ((leads, cfg["lead_tickers"]), (lags, cfg["lag_tickers"])):
        for ticker in tickers:
            # 장기 구간을 한 번만 받아 커플링과 스프레드에 함께 쓴다.
            series = fetch_close(ticker, COUPLING_START, end)
            if series is None:
                missing.append(ticker)
            else:
                bucket.append(series)

    if not leads or not lags:
        print(f"  [skip] Lead/Lag 한쪽 데이터가 비어 계산 불가 (missing={missing})")
        return None

    coupling = coupling_stats(chain_index(leads), chain_index(lags))

    # 스프레드는 최근 6개월만 본다. 그룹별로 정렬한 뒤 공통 거래일로 맞춘다.
    recent = [s.loc[s.index >= pd.Timestamp(spread_start)] for s in leads]
    recent_lag = [s.loc[s.index >= pd.Timestamp(spread_start)] for s in lags]
    lead_frame = build_group_frame(recent)
    lag_frame = build_group_frame(recent_lag)
    common = lead_frame.index.intersection(lag_frame.index)
    if len(common) < Z_WINDOW + 1:
        print(f"  [skip] 공통 거래일 {len(common)}일로 Z-Score({Z_WINDOW}일) 계산 불가")
        return None

    lead_index = normalize_to_100(lead_frame.loc[common])
    lag_index = normalize_to_100(lag_frame.loc[common])

    spread = lag_index - lead_index
    rolling = spread.rolling(Z_WINDOW)
    zscore = ((spread - rolling.mean()) / rolling.std()).dropna()
    if zscore.empty:
        print("  [skip] Z-Score 산출 실패 (표준편차 0)")
        return None

    latest_z = float(zscore.iloc[-1])
    history = pd.DataFrame({"spread": spread, "z": zscore}).dropna().tail(HISTORY_POINTS)

    tier = coupling["tier"] if coupling else "unknown"
    if coupling:
        corr_text = (
            f"corr={coupling['corr']:+.2f} lag1={coupling['corr_lag1']:+.2f}"
            f" ({coupling['lead_channel']})"
        )
    else:
        corr_text = "corr=n/a"
    print(
        f"  lead={lead_index.iloc[-1]:.1f} lag={lag_index.iloc[-1]:.1f} "
        f"spread={spread.iloc[-1]:+.2f} z={latest_z:+.2f} {corr_text} [{tier}]"
    )

    return {
        "key": key,
        "sector": cfg.get("sector", "기타"),
        "desc": cfg["desc"],
        "lead_tickers": [
            {"ticker": t, "label": label_of(t), "missing": t in missing}
            for t in cfg["lead_tickers"]
        ],
        "lag_tickers": [
            {"ticker": t, "label": label_of(t), "missing": t in missing}
            for t in cfg["lag_tickers"]
        ],
        "base_date": common[0].date().isoformat(),
        "last_date": common[-1].date().isoformat(),
        "lead_index": round(float(lead_index.iloc[-1]), 2),
        "lag_index": round(float(lag_index.iloc[-1]), 2),
        "spread": round(float(spread.iloc[-1]), 2),
        "zscore": round(latest_z, 2),
        # 커플링이 약하면 스프레드가 좁혀질 근거가 없으므로 경고로 올리지 않는다.
        "z_extreme": abs(latest_z) >= ALERT_THRESHOLD,
        "alert": abs(latest_z) >= ALERT_THRESHOLD and tier in ("strong", "moderate"),
        "coupling": coupling,
        "direction": "overshoot" if latest_z > 0 else "undershoot",
        "history": [
            {
                "date": idx.date().isoformat(),
                "spread": round(float(row.spread), 2),
                "z": round(float(row.z), 2),
            }
            for idx, row in history.iterrows()
        ],
    }


def main() -> None:
    today = date.today()
    end = today + timedelta(days=1)          # yfinance의 end는 exclusive
    start = today - timedelta(days=LOOKBACK_DAYS)
    print(f"스프레드 구간: {start} ~ {today}")
    print(f"커플링 표본: {COUPLING_START} ~ {today} (그룹 {len(PEER_GROUPS)}개)\n")

    groups = [
        result
        for key, cfg in PEER_GROUPS.items()
        if (result := analyze_group(key, cfg, start, end)) is not None
    ]
    # 커플링이 강한 그룹을 먼저, 그 안에서 괴리가 큰 순서로 세운다.
    tier_rank = {"strong": 0, "moderate": 1, "weak": 2, "unknown": 3}
    groups.sort(
        key=lambda g: (
            tier_rank[g["coupling"]["tier"] if g["coupling"] else "unknown"],
            -abs(g["zscore"]),
        )
    )

    payload = {
        "generated_at": pd.Timestamp.now().isoformat(timespec="seconds"),
        "period": {"start": start.isoformat(), "end": today.isoformat()},
        "z_window": Z_WINDOW,
        "alert_threshold": ALERT_THRESHOLD,
        "coupling_start": COUPLING_START.isoformat(),
        "coupling_tiers": {name: floor for name, floor in COUPLING_TIERS},
        "groups": groups,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    alerts = sum(g["alert"] for g in groups)
    muted = sum(g["z_extreme"] and not g["alert"] for g in groups)
    print(f"\n저장: {OUTPUT_PATH}")
    print(f"그룹 {len(groups)}개 / 경고 {alerts}개 (|Z| >= {ALERT_THRESHOLD} 이면서 커플링 유효)")
    print(f"커플링 약해 보류된 극단 Z: {muted}개")


if __name__ == "__main__":
    main()
