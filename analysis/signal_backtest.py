"""Z-Score 신호가 실제로 수렴했는지 확인 (일회성 분석).

|Z| >= 1.5 시점 이후 N거래일간 스프레드가 0 방향으로 좁혀졌는지 센다.
커플링(평균회귀) 가정이 맞으면 수렴 비율이 50%를 뚜렷하게 넘어야 한다.
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from peer_tracker import (  # noqa: E402
    ALERT_THRESHOLD,
    PEER_GROUPS,
    Z_WINDOW,
    build_group_frame,
    fetch_close,
    normalize_to_100,
)

HORIZONS = (5, 10, 20)


def main() -> None:
    today = date.today()
    start, end = today - timedelta(days=730), today + timedelta(days=1)
    hits = {h: [0, 0] for h in HORIZONS}  # [수렴, 전체]

    for key, cfg in PEER_GROUPS.items():
        leads, lags = [], []
        for bucket, tickers in ((leads, cfg["lead_tickers"]), (lags, cfg["lag_tickers"])):
            for t in tickers:
                s = fetch_close(t, start, end)
                if s is not None:
                    bucket.append(s)
        if not leads or not lags:
            continue

        lf, gf = build_group_frame(leads), build_group_frame(lags)
        common = lf.index.intersection(gf.index)
        if len(common) < 120:
            continue

        spread = normalize_to_100(gf.loc[common]) - normalize_to_100(lf.loc[common])
        roll = spread.rolling(Z_WINDOW)
        z = ((spread - roll.mean()) / roll.std()).dropna()

        for h in HORIZONS:
            for i, (ts, zv) in enumerate(z.items()):
                if abs(zv) < ALERT_THRESHOLD:
                    continue
                pos = spread.index.get_loc(ts)
                if pos + h >= len(spread):
                    continue
                now, later = spread.iloc[pos], spread.iloc[pos + h]
                hits[h][1] += 1
                if abs(later) < abs(now):
                    hits[h][0] += 1

    print(f"2년 구간, |Z| >= {ALERT_THRESHOLD} 신호 이후 스프레드 축소 비율\n")
    for h in HORIZONS:
        good, total = hits[h]
        rate = good / total * 100 if total else 0
        print(f"  {h:>2}거래일 후: {good}/{total} = {rate:.1f}%")


if __name__ == "__main__":
    main()
