"""후보 티커 검증 (일회성 분석).

candidates.json의 티커가 실제로 존재하는지, 종목명이 의도한 회사인지 확인한다.
추측한 티커를 그대로 대시보드에 넣으면 안 되므로 이 단계를 먼저 통과시킨다.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import yfinance as yf

HERE = Path(__file__).resolve().parent


def probe(ticker: str) -> tuple[bool, str, str]:
    try:
        info = yf.Ticker(ticker).info
        name = info.get("longName") or info.get("shortName")
        cur = info.get("currency") or "?"
        cap = info.get("marketCap")
        if not name:
            return False, "이름 없음", cur
        cap_txt = f"{cap / 1e9:.1f}B {cur}" if cap else "cap 없음"
        return True, name, cap_txt
    except Exception as exc:
        return False, f"오류 {type(exc).__name__}", "?"
    finally:
        time.sleep(0.2)


def main() -> None:
    groups = json.loads((HERE / "candidates.json").read_text(encoding="utf-8"))
    bad = []

    for key, cfg in groups.items():
        print(f"\n[{key}] {cfg['sector']} / {cfg['desc']}")
        for side in ("lead", "lag"):
            for t in cfg[side]:
                ok, name, extra = probe(t)
                mark = "OK " if ok else "XX "
                print(f"  {mark}{side:<4} {t:<14} {name[:44]:<46} {extra}")
                if not ok:
                    bad.append((key, side, t, name))

    print(f"\n실패 티커 {len(bad)}개")
    for key, side, t, why in bad:
        print(f"  {key} {side} {t}: {why}")


if __name__ == "__main__":
    main()
