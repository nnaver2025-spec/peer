"""2020년 이후 장기 표본으로 그룹별 커플링 강도 측정 (일회성 분석).

티커 상장 시점이 달라 교집합만 쓰면 표본이 짧아진다(GEV 2024-03 등).
여기서는 체인 방식 인덱스를 쓴다: 각 시점에 존재하는 종목의 정규화 평균을 쓰고,
구성 종목이 바뀌는 날에는 직전 레벨을 이어붙여 인덱스 점프를 제거한다.

출력: 그룹별 동행 상관, 시차 1일 전달 상관, 연도별 상관 안정성.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from peer_tracker import PEER_GROUPS, fetch_close  # noqa: E402

START = date(2020, 1, 1)
MIN_DAYS = 250


def chain_index(closes: list[pd.Series]) -> pd.Series:
    """구성 종목 변화를 이어붙인 그룹 인덱스. 시작 100."""
    frame = pd.concat(closes, axis=1, sort=True).ffill()
    frame = frame.loc[frame.notna().any(axis=1)]

    # 각 종목의 일간 수익률 -> 그 날 데이터가 있는 종목만 평균 -> 누적
    rets = frame.pct_change()
    avail = frame.notna() & frame.shift(1).notna()
    daily = rets.where(avail).mean(axis=1, skipna=True).fillna(0.0)
    return 100 * (1 + daily).cumprod()


def yearly_corr(lead_ret: pd.Series, lag_ret: pd.Series) -> dict[int, float]:
    out = {}
    pair = pd.concat([lead_ret.rename("l"), lag_ret.rename("g")], axis=1).dropna()
    for year, chunk in pair.groupby(pair.index.year):
        out[int(year)] = round(float(chunk["l"].corr(chunk["g"])), 2) if len(chunk) > 30 else np.nan
    return out


def main() -> None:
    end = date.today()
    rows, detail = [], {}

    for key, cfg in PEER_GROUPS.items():
        leads, lags = [], []
        for bucket, tickers in ((leads, cfg["lead_tickers"]), (lags, cfg["lag_tickers"])):
            for t in tickers:
                s = fetch_close(t, START, end)
                if s is not None:
                    bucket.append(s)
        if not leads or not lags:
            continue

        lead_idx = chain_index(leads)
        lag_idx = chain_index(lags)
        common = lead_idx.index.intersection(lag_idx.index)
        if len(common) < MIN_DAYS:
            print(f"[skip] {key}: 공통 {len(common)}일")
            continue

        lead_ret = lead_idx.loc[common].pct_change().dropna()
        lag_ret = lag_idx.loc[common].pct_change().dropna()
        pair = pd.concat([lead_ret.rename("l"), lag_ret.rename("g")], axis=1).dropna()
        same = float(pair["l"].corr(pair["g"]))
        shifted = pd.concat([lead_ret.shift(1).rename("l"), lag_ret.rename("g")], axis=1).dropna()
        lag1 = float(shifted["l"].corr(shifted["g"]))

        by_year = yearly_corr(lead_ret, lag_ret)
        vals = [v for v in by_year.values() if not np.isnan(v)]

        rows.append(
            {
                "group": cfg["desc"],
                "key": key,
                "n": len(common),
                "from": str(common[0].date()),
                "corr": round(same, 2),
                "corr_lag1": round(lag1, 2),
                "yr_min": round(min(vals), 2),
                "yr_max": round(max(vals), 2),
                "yr_std": round(float(np.std(vals)), 2),
            }
        )
        detail[key] = by_year

    df = pd.DataFrame(rows).sort_values("corr", ascending=False)
    pd.set_option("display.width", 220)
    print(df.to_string(index=False))
    print("\n연도별 동행 상관")
    order = dict(zip(df["key"], df["corr"]))
    for key in sorted(detail, key=lambda k: -order[k]):
        print(f"  {key:<18} {json.dumps(detail[key])}")


if __name__ == "__main__":
    main()
