"""후보 섹터 구분이 peer 그룹으로 성립하는지 검증 (일회성 분석).

peer 그룹이 유효하려면 두 조건이 필요하다.
1. 그룹 내 응집도: 같은 그룹 종목끼리 서로 상관이 높아야 한다 (안 그러면 묶음이 잘못됨)
2. 해외-국내 커플링: Lead 인덱스와 Lag 인덱스가 동행해야 한다

응집도가 낮으면 섹터 정의가 너무 넓다는 뜻이고,
커플링이 낮으면 그 섹터에서는 해외 선행 논리가 성립하지 않는다는 뜻이다.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from peer_tracker import chain_index, fetch_close  # noqa: E402

HERE = Path(__file__).resolve().parent
START = date(2021, 1, 1)
MIN_DAYS = 300


def mean_pairwise_corr(returns: pd.DataFrame) -> float:
    """그룹 내 종목 쌍 상관의 평균. 응집도 지표."""
    if returns.shape[1] < 2:
        return np.nan
    c = returns.corr()
    vals = c.values[np.triu_indices_from(c.values, k=1)]
    vals = vals[~np.isnan(vals)]
    return float(vals.mean()) if len(vals) else np.nan


def main() -> None:
    groups = json.loads((HERE / "candidates.json").read_text(encoding="utf-8"))
    end = date.today()
    cache: dict[str, pd.Series] = {}
    rows = []

    def get(t: str) -> pd.Series | None:
        if t not in cache:
            s = fetch_close(t, START, end)
            cache[t] = s if s is not None else pd.Series(dtype=float)
        s = cache[t]
        return None if s.empty else s

    for key, cfg in groups.items():
        leads = [s for s in (get(t) for t in cfg["lead"]) if s is not None]
        lags = [s for s in (get(t) for t in cfg["lag"]) if s is not None]
        if len(leads) < 2 or len(lags) < 2:
            print(f"[skip] {key}: 유효 종목 부족 (lead {len(leads)}, lag {len(lags)})")
            continue

        lead_idx, lag_idx = chain_index(leads), chain_index(lags)
        common = lead_idx.index.intersection(lag_idx.index)
        if len(common) < MIN_DAYS:
            print(f"[skip] {key}: 공통 {len(common)}일")
            continue

        lr = lead_idx.loc[common].pct_change()
        gr = lag_idx.loc[common].pct_change()
        same = pd.concat([lr, gr], axis=1).dropna()
        lag1 = pd.concat([lr.shift(1), gr], axis=1).dropna()

        lead_ret = pd.concat(leads, axis=1, sort=True).ffill().pct_change()
        lag_ret = pd.concat(lags, axis=1, sort=True).ffill().pct_change()

        rows.append(
            {
                "key": key,
                "sector": cfg["sector"],
                "desc": cfg["desc"],
                "n": len(common),
                "lead_cohes": round(mean_pairwise_corr(lead_ret), 2),
                "lag_cohes": round(mean_pairwise_corr(lag_ret), 2),
                "corr": round(float(same.iloc[:, 0].corr(same.iloc[:, 1])), 2),
                "corr_lag1": round(float(lag1.iloc[:, 0].corr(lag1.iloc[:, 1])), 2),
            }
        )

    df = pd.DataFrame(rows)
    df["best"] = df[["corr", "corr_lag1"]].max(axis=1)
    df = df.sort_values("best", ascending=False)
    pd.set_option("display.width", 240)

    print("\n섹터 구분 검증 (2021년 이후)")
    print(df[["sector", "desc", "n", "lead_cohes", "lag_cohes", "corr", "corr_lag1"]].to_string(index=False))

    print("\nlead_cohes / lag_cohes: 그룹 내 종목 간 평균 상관 (응집도)")
    print("  0.5 이상이면 잘 묶인 그룹, 0.3 미만이면 섹터 정의가 너무 넓음")
    print("corr / corr_lag1: 해외-국내 동행 / 시차1일 전달")

    print("\n판정")
    for _, r in df.iterrows():
        issues = []
        if r["lag_cohes"] < 0.3:
            issues.append(f"국내 응집도 낮음({r['lag_cohes']})")
        if r["lead_cohes"] < 0.3:
            issues.append(f"해외 응집도 낮음({r['lead_cohes']})")
        if max(r["corr"], r["corr_lag1"]) < 0.15:
            issues.append("커플링 근거 부족")
        verdict = "OK" if not issues else "검토: " + ", ".join(issues)
        print(f"  {r['desc']:<18} {verdict}")


if __name__ == "__main__":
    main()
