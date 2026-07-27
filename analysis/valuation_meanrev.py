"""밸류에이션 배수비(국내/해외)가 평균회귀하는지 검증 (일회성 분석).

주가 스프레드는 평균회귀하지 않았다(백테스트 44~48%).
밸류에이션 갭이라면 다를 수 있다: 배수비는 이익 수준으로 정규화돼 있어
주가 인덱스 차이보다 안정적인 균형을 가질 가능성이 있다.

측정
1. 배수비 로그값의 ADF 검정 (정상성 = 평균회귀)
2. 반감기
3. 배수비 Z-Score가 극단일 때 이후 국내-해외 초과수익 (신호 검증)
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.tsa.stattools import adfuller

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from peer_tracker import PEER_GROUPS, fetch_close  # noqa: E402
from valuation_series import group_multiple  # noqa: E402

Z_WINDOW = 60
THRESHOLD = 1.5
HORIZONS = (20, 60)


def half_life(series: pd.Series) -> float:
    lagged = series.shift(1).dropna()
    delta = series.diff().dropna()
    idx = lagged.index.intersection(delta.index)
    fit = sm.OLS(delta.loc[idx], sm.add_constant(lagged.loc[idx])).fit()
    beta = fit.params.iloc[1]
    return float(-np.log(2) / np.log(1 + beta)) if beta < 0 else float("inf")


def main() -> None:
    end = date.today()
    rows = []
    hits = {h: [0, 0] for h in HORIZONS}

    for key, cfg in PEER_GROUPS.items():
        lead = group_multiple(cfg["lead_tickers"], end, "pbr")
        lag = group_multiple(cfg["lag_tickers"], end, "pbr")
        common = lead.index.intersection(lag.index)
        if len(common) < 400:
            continue

        log_ratio = np.log(lag.loc[common] / lead.loc[common])
        adf_p = adfuller(log_ratio.values, autolag="AIC")[1]

        roll = log_ratio.rolling(Z_WINDOW)
        z = ((log_ratio - roll.mean()) / roll.std()).dropna()

        # 국내/해외 상대 주가 성과로 신호를 채점한다.
        kr_px = [s for s in (fetch_close(t, date(2021, 1, 1), end) for t in cfg["lag_tickers"]) if s is not None]
        ov_px = [s for s in (fetch_close(t, date(2021, 1, 1), end) for t in cfg["lead_tickers"]) if s is not None]
        if not kr_px or not ov_px:
            continue
        kr_ret = pd.concat(kr_px, axis=1, sort=True).ffill().pct_change().mean(axis=1)
        ov_ret = pd.concat(ov_px, axis=1, sort=True).ffill().pct_change().mean(axis=1)
        rel = (1 + kr_ret).cumprod() / (1 + ov_ret).cumprod()

        group_hits = {h: [0, 0] for h in HORIZONS}
        for ts, zv in z.items():
            if zv > -THRESHOLD or ts not in rel.index:
                continue  # 국내가 평소보다 크게 할인된 시점만 본다
            pos = rel.index.get_loc(ts)
            for h in HORIZONS:
                if pos + h >= len(rel):
                    continue
                gain = float(rel.iloc[pos + h] / rel.iloc[pos] - 1)
                for bucket in (hits, group_hits):
                    bucket[h][1] += 1
                    if gain > 0:
                        bucket[h][0] += 1

        rows.append(
            {
                "group": cfg["desc"],
                "n": len(common),
                "adf_p": round(adf_p, 3),
                "stationary": adf_p < 0.05,
                "half_life": round(half_life(log_ratio), 1),
                "z_now": round(float(z.iloc[-1]), 2),
                "signals": group_hits[20][1],
                "win20": (
                    round(group_hits[20][0] / group_hits[20][1] * 100, 1)
                    if group_hits[20][1]
                    else None
                ),
            }
        )

    df = pd.DataFrame(rows).sort_values("adf_p")
    pd.set_option("display.width", 240)
    print("PBR 배수비(국내/해외) 평균회귀 검정")
    print(df.to_string(index=False))

    print(f"\n국내 PBR이 평소보다 저평가(Z <= -{THRESHOLD})일 때 이후 국내 상대 성과 우위 비율")
    for h in HORIZONS:
        good, total = hits[h]
        print(f"  {h:>2}거래일: {good}/{total} = {good / total * 100:.1f}%" if total else f"  {h}: 신호 없음")


if __name__ == "__main__":
    main()
