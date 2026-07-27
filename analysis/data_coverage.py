"""티커별 실제 데이터 시작일 확인 (일회성 분석).

장기 표본을 어디까지 늘릴 수 있는지, 어느 종목이 표본을 잘라먹는지 본다.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from peer_tracker import KR_NAMES, PEER_GROUPS, fetch_close  # noqa: E402

START = date(2018, 1, 1)


def main() -> None:
    end = date.today()
    for key, cfg in PEER_GROUPS.items():
        print(f"\n[{key}] {cfg['desc']}")
        for side in ("lead_tickers", "lag_tickers"):
            for t in cfg[side]:
                s = fetch_close(t, START, end)
                label = KR_NAMES.get(t, t)
                if s is None:
                    print(f"  {side[:4]:>4} {t:>12} {label:<22} 데이터 없음")
                else:
                    print(
                        f"  {side[:4]:>4} {t:>12} {label:<22} "
                        f"{s.index[0].date()} ~ {s.index[-1].date()}  ({len(s)}일)"
                    )


if __name__ == "__main__":
    main()
