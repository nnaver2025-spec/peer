"""국내 티커 종목명 수집 (일회성 유틸).

시트 종목이 470개로 늘어 종목명을 손으로 적으면 오류가 난다.
yfinance 조회명을 그대로 받아 kr_names.json으로 저장하고,
peer_tracker의 KR_NAMES에 이미 있는 한글명은 그대로 유지한다.
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

import yfinance as yf

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from peer_tracker import KR_NAMES  # noqa: E402
from sheet_groups import SHEET_GROUPS  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "kr_names.json"
KR_PATTERN = re.compile(r"^\d{6}\.K[SQ]$")


def main() -> None:
    tickers = []
    for cfg in SHEET_GROUPS.values():
        tickers += cfg["lead"] + cfg["lag"]
    kr = [t for t in dict.fromkeys(tickers) if KR_PATTERN.match(t)]
    print(f"국내 티커 {len(kr)}개 (기존 매핑 {len(KR_NAMES)}개)")

    names = dict(KR_NAMES)
    fetched = 0
    for t in kr:
        if t in names:
            continue
        try:
            info = yf.Ticker(t).info
            name = info.get("longName") or info.get("shortName")
        except Exception:
            name = None
        time.sleep(0.15)
        if name and not name.startswith(t):
            names[t] = name
            fetched += 1
        else:
            print(f"  [warn] {t} 이름 조회 실패")

    OUT.write_text(json.dumps(names, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(f"신규 {fetched}개 수집, 총 {len(names)}개 -> {OUT}")


if __name__ == "__main__":
    main()
