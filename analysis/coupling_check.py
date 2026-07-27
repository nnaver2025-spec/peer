"""Lead-Lag 커플링 가설 검증 (일회성 분석 스크립트).

질문: "국내는 해외 선행 종목을 답지처럼 따라가야 한다"는 전제가 데이터에 있는가?

측정 세 가지
1. 시차 교차상관 - Lead 수익률이 며칠 앞서는가, 그때 상관은 얼마인가
2. Engle-Granger 공적분 - 두 인덱스가 장기적으로 묶여 있는가 (스프레드 평균회귀)
3. 스프레드 반감기 - 괴리가 좁혀지는 데 걸리는 거래일 (OU 프로세스 근사)

한국 시장은 미국보다 먼저 닫히므로, "전일 미국 -> 당일 한국" 전달은 lag=1에서 잡힌다.
"""

from __future__ import annotations

import sys
import time
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.tsa.stattools import adfuller, coint

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from peer_tracker import (  # noqa: E402
    LOOKBACK_DAYS,
    PEER_GROUPS,
    build_group_frame,
    fetch_close,
    normalize_to_100,
)

MAX_LAG = 5


def lead_lag_correlation(lead_ret: pd.Series, lag_ret: pd.Series) -> dict:
    """lag=k -> Lead의 k일 전 수익률과 국내 당일 수익률의 상관."""
    out = {}
    for k in range(0, MAX_LAG + 1):
        shifted = lead_ret.shift(k)
        pair = pd.concat([shifted, lag_ret], axis=1).dropna()
        out[k] = float(pair.iloc[:, 0].corr(pair.iloc[:, 1])) if len(pair) > 10 else np.nan
    return out


def half_life(spread: pd.Series) -> float:
    """AR(1) 계수로 평균회귀 반감기 추정. 발산하면 inf."""
    lagged = spread.shift(1).dropna()
    delta = (spread - spread.shift(1)).dropna()
    common = lagged.index.intersection(delta.index)
    model = sm.OLS(delta.loc[common], sm.add_constant(lagged.loc[common])).fit()
    beta = model.params.iloc[1]
    return float(-np.log(2) / np.log(1 + beta)) if beta < 0 else float("inf")


def main() -> None:
    today = date.today()
    start = today - timedelta(days=LOOKBACK_DAYS)
    end = today + timedelta(days=1)
    rows = []

    for key, cfg in PEER_GROUPS.items():
        leads, lags = [], []
        for bucket, tickers in ((leads, cfg["lead_tickers"]), (lags, cfg["lag_tickers"])):
            for t in tickers:
                s = fetch_close(t, start, end)
                if s is not None:
                    bucket.append(s)
                time.sleep(0)
        if not leads or not lags:
            continue

        lf, gf = build_group_frame(leads), build_group_frame(lags)
        common = lf.index.intersection(gf.index)
        if len(common) < 60:
            continue

        lead_idx = normalize_to_100(lf.loc[common])
        lag_idx = normalize_to_100(gf.loc[common])
        lead_ret = lead_idx.pct_change().dropna()
        lag_ret = lag_idx.pct_change().dropna()

        corrs = lead_lag_correlation(lead_ret, lag_ret)
        best_lag = max((k for k in corrs if not np.isnan(corrs[k])), key=lambda k: corrs[k])
        _, coint_p, _ = coint(lag_idx.values, lead_idx.values)
        spread = lag_idx - lead_idx
        adf_p = adfuller(spread.values, autolag="AIC")[1]

        rows.append(
            {
                "group": cfg["desc"],
                "n": len(common),
                "corr_lag0": round(corrs[0], 2),
                "corr_lag1": round(corrs[1], 2),
                "best_lag": best_lag,
                "best_corr": round(corrs[best_lag], 2),
                "coint_p": round(coint_p, 3),
                "adf_p": round(adf_p, 3),
                "half_life": round(half_life(spread), 1),
                "spread_now": round(float(spread.iloc[-1]), 1),
            }
        )

    df = pd.DataFrame(rows).sort_values("corr_lag0", ascending=False)
    pd.set_option("display.width", 200)
    print(df.to_string(index=False))
    print("\ncorr_lag0: 같은 날 동행 / corr_lag1: 전일 해외 -> 당일 국내")
    print("coint_p, adf_p < 0.05 이면 스프레드 평균회귀(커플링) 통계적 지지")


if __name__ == "__main__":
    main()
