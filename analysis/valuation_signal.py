"""밸류 디스카운트가 성과를 설명하는지 종목 단위 검증 (일회성 분석).

그룹 n=11은 표본이 너무 작아 상관이 불안정하다. 여기서는 50개 종목 전체를 쓴다.

가설: 같은 섹터 내에서 forwardPE가 낮은(저평가) 종목이 이후 수익률이 높았는가?
배수는 현재 스냅샷뿐이므로 인과 방향을 확정할 수 없다는 한계를 명시한다.
실제로는 "주가가 오른 종목이 배수도 높다"는 역방향 효과가 섞인다.
"""

from __future__ import annotations

import sys
import time
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from peer_tracker import KR_NAMES, PEER_GROUPS, fetch_close  # noqa: E402


def main() -> None:
    end = date.today()
    rows = []

    for key, cfg in PEER_GROUPS.items():
        for side in ("lead_tickers", "lag_tickers"):
            for t in cfg[side]:
                try:
                    info = yf.Ticker(t).info
                except Exception:
                    continue
                time.sleep(0.2)
                fpe = info.get("forwardPE")
                ev = info.get("enterpriseToEbitda")
                if fpe is None or not (0 < fpe < 200):
                    continue

                s = fetch_close(t, end - timedelta(days=400), end)
                if s is None or len(s) < 200:
                    continue
                r12 = float(s.iloc[-1] / s.iloc[0] - 1) * 100
                r3 = float(s.iloc[-1] / s.iloc[-63] - 1) * 100

                rows.append(
                    {
                        "ticker": t,
                        "label": KR_NAMES.get(t, t),
                        "group": cfg["desc"],
                        "kr": bool(pd.Series([t]).str.contains(r"\.K[SQ]$").iloc[0]),
                        "fpe": fpe,
                        "ev": ev if ev and 0 < ev < 300 else np.nan,
                        "ret12m": r12,
                        "ret3m": r3,
                    }
                )

    df = pd.DataFrame(rows)
    pd.set_option("display.width", 220)

    print(f"종목 {len(df)}개 (국내 {df.kr.sum()}, 해외 {(~df.kr).sum()})\n")

    print("forwardPE 중위값")
    print(f"  국내 {df[df.kr].fpe.median():.1f}   해외 {df[~df.kr].fpe.median():.1f}")
    u = stats.mannwhitneyu(df[df.kr].fpe, df[~df.kr].fpe, alternative="less")
    print(f"  국내 < 해외 검정 (Mann-Whitney) p = {u.pvalue:.4f}\n")

    print("밸류에이션과 수익률 (Spearman 순위상관)")
    for label, sub in (("전체", df), ("국내", df[df.kr]), ("해외", df[~df.kr])):
        for hor in ("ret3m", "ret12m"):
            pair = sub[["fpe", hor]].dropna()
            rho, p = stats.spearmanr(pair["fpe"], pair[hor])
            print(f"  {label:<4} fPE vs {hor:<7} rho={rho:+.2f} p={p:.3f} n={len(pair)}")

    print("\n섹터 내 상대 밸류 (그룹 중위값 대비 할인율) vs 수익률")
    df["rel_fpe"] = df.groupby("group")["fpe"].transform(lambda s: s / s.median() - 1)
    for hor in ("ret3m", "ret12m"):
        pair = df[["rel_fpe", hor]].dropna()
        rho, p = stats.spearmanr(pair["rel_fpe"], pair[hor])
        print(f"  상대fPE vs {hor:<7} rho={rho:+.2f} p={p:.3f} n={len(pair)}")


if __name__ == "__main__":
    main()
