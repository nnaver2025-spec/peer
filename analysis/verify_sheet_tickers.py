"""시트에서 옮긴 티커 전수 검증 (일회성 분석).

시트의 거래소 표기(TYO:, TPE:, KRX:, NASDAQ:)를 yfinance 접미사로 바꿔 넣었으므로
실제로 가격이 조회되는지 확인해야 한다. 실패 티커는 목록으로 남겨 제거한다.
"""

from __future__ import annotations

import sys
import time
from datetime import date, timedelta
from pathlib import Path

import yfinance as yf

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from sheet_groups import SHEET_GROUPS  # noqa: E402


def main() -> None:
    tickers = []
    for cfg in SHEET_GROUPS.values():
        tickers += cfg["lead"] + cfg["lag"]
    tickers = list(dict.fromkeys(tickers))
    print(f"검증 대상 {len(tickers)}개\n")

    end = date.today()
    start = end - timedelta(days=120)
    ok, bad = [], []

    for t in tickers:
        try:
            df = yf.download(
                t, start=start.isoformat(), end=end.isoformat(),
                progress=False, auto_adjust=True, threads=False,
            )
            rows = 0 if df is None or df.empty else len(df)
        except Exception:
            rows = 0
        time.sleep(0.15)
        (ok if rows >= 40 else bad).append((t, rows))

    print(f"유효 {len(ok)}개 / 무효 {len(bad)}개")
    print("\n무효 티커 (rows < 40)")
    for t, rows in bad:
        where = [k for k, c in SHEET_GROUPS.items() if t in c["lead"] + c["lag"]]
        print(f"  {t:<14} rows={rows:<4} groups={','.join(where)}")


if __name__ == "__main__":
    main()
