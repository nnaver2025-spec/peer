"""밸류에이션 지표 가용성 조사 (일회성 분석).

PER/PBR 시계열을 만들 수 있는지 확인한다. yfinance에서 얻을 수 있는 것은
- info: 현재 시점 스냅샷 (forwardPE 등). 국내는 trailingPE/priceToBook이 자주 None
- quarterly_income_stmt / quarterly_balance_sheet: 분기 EPS, 자본 (시계열 가능하나 짧음)

분기 재무 + 일별 종가를 결합하면 trailing PER/PBR 시계열을 직접 만들 수 있다.
그 전에 종목별로 분기 수가 몇 개인지, 결측이 얼마인지 센다.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd
import yfinance as yf

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from peer_tracker import KR_NAMES, PEER_GROUPS  # noqa: E402


def probe(ticker: str) -> dict:
    tk = yf.Ticker(ticker)
    out = {"ticker": ticker, "label": KR_NAMES.get(ticker, ticker)}
    try:
        info = tk.info
        out["fwd_pe"] = info.get("forwardPE")
        out["trail_pe"] = info.get("trailingPE")
        out["pbr"] = info.get("priceToBook")
        out["ev_ebitda"] = info.get("enterpriseToEbitda")
    except Exception:
        pass

    try:
        q = tk.quarterly_income_stmt
        eps_rows = [r for r in q.index if "Diluted EPS" in str(r)]
        if eps_rows:
            eps = q.loc[eps_rows[0]].dropna()
            out["eps_q"] = len(eps)
            out["eps_oldest"] = str(min(eps.index).date()) if len(eps) else None
    except Exception:
        out["eps_q"] = 0

    try:
        bs = tk.quarterly_balance_sheet
        eq_rows = [r for r in bs.index if "Stockholders Equity" in str(r)]
        if eq_rows:
            eq = bs.loc[eq_rows[0]].dropna()
            out["eq_q"] = len(eq)
    except Exception:
        out["eq_q"] = 0

    time.sleep(0.2)
    return out


def main() -> None:
    tickers = []
    for cfg in PEER_GROUPS.values():
        tickers += cfg["lead_tickers"] + cfg["lag_tickers"]

    rows = [probe(t) for t in dict.fromkeys(tickers)]
    df = pd.DataFrame(rows)
    df["kr"] = df["ticker"].str.contains(r"\.K[SQ]$", regex=True)
    pd.set_option("display.width", 220)
    print(df.to_string(index=False))

    print("\n지표별 결측 종목 수 (전체 %d개)" % len(df))
    for col in ["fwd_pe", "trail_pe", "pbr", "ev_ebitda"]:
        kr_na = df[df.kr][col].isna().sum()
        ov_na = df[~df.kr][col].isna().sum()
        print(f"  {col:<12} 국내 결측 {kr_na}/{df.kr.sum()}  해외 결측 {ov_na}/{(~df.kr).sum()}")

    print("\n분기 EPS 개수 분포")
    print(df.groupby("kr")["eps_q"].describe()[["count", "min", "50%", "max"]].to_string())


if __name__ == "__main__":
    main()
