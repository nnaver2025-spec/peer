"""시트 표 단위 peer 그룹 검증 (일회성 분석).

판정 기준
- lag가 비면 국내 대응이 없어 스프레드 대상이 아니다 (해외 관찰용 표)
- 응집도(그룹 내 평균 쌍상관)가 0.3 미만이면 표 정의가 너무 넓다
- 커플링(동행 또는 시차1일 상관)이 0.15 미만이면 해외 선행 논리가 약하다
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
from sheet_groups import SHEET_GROUPS  # noqa: E402

START = date(2021, 1, 1)
MIN_DAYS = 300
OUT = Path(__file__).resolve().parent / "sheet_validation.json"


def mean_pairwise(returns: pd.DataFrame) -> float:
    if returns.shape[1] < 2:
        return np.nan
    c = returns.corr().values
    v = c[np.triu_indices_from(c, k=1)]
    v = v[~np.isnan(v)]
    return float(v.mean()) if len(v) else np.nan


def main() -> None:
    end = date.today()
    cache: dict[str, pd.Series] = {}

    def get(t: str) -> pd.Series | None:
        if t not in cache:
            s = fetch_close(t, START, end)
            cache[t] = s if s is not None else pd.Series(dtype=float)
        return None if cache[t].empty else cache[t]

    rows, observe_only = [], []

    for key, cfg in SHEET_GROUPS.items():
        if not cfg["lag"]:
            observe_only.append((key, cfg["desc"], len(cfg["lead"])))
            continue

        leads = [s for s in (get(t) for t in cfg["lead"]) if s is not None]
        lags = [s for s in (get(t) for t in cfg["lag"]) if s is not None]
        if len(leads) < 1 or len(lags) < 1:
            print(f"[skip] {key}: 데이터 부족")
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

        rows.append(
            {
                "key": key,
                "sector": cfg["sector"],
                "desc": cfg["desc"],
                "n_lead": len(leads),
                "n_lag": len(lags),
                "days": len(common),
                "lead_cohes": round(mean_pairwise(pd.concat(leads, axis=1, sort=True).ffill().pct_change()), 2),
                "lag_cohes": round(mean_pairwise(pd.concat(lags, axis=1, sort=True).ffill().pct_change()), 2),
                "corr": round(float(same.iloc[:, 0].corr(same.iloc[:, 1])), 2),
                "corr_lag1": round(float(lag1.iloc[:, 0].corr(lag1.iloc[:, 1])), 2),
            }
        )

    df = pd.DataFrame(rows)
    df["best"] = df[["corr", "corr_lag1"]].max(axis=1)
    df = df.sort_values("best", ascending=False)
    pd.set_option("display.width", 260)

    print("\n시트 표 단위 peer 검증 (2021년 이후)")
    print(df.drop(columns="key").to_string(index=False))

    print("\n판정")
    for _, r in df.iterrows():
        issues = []
        if r["lag_cohes"] < 0.3:
            issues.append(f"국내 응집도 {r['lag_cohes']}")
        if r["lead_cohes"] < 0.3:
            issues.append(f"해외 응집도 {r['lead_cohes']}")
        if r["best"] < 0.15:
            issues.append("커플링 부족")
        print(f"  {r['desc']:<22} {'OK' if not issues else '검토: ' + ', '.join(issues)}")

    print(f"\n해외 관찰 전용 (국내 대응 없음) {len(observe_only)}개")
    for key, desc, n in observe_only:
        print(f"  {desc} ({n}종목)")

    OUT.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n저장: {OUT}")


if __name__ == "__main__":
    main()
