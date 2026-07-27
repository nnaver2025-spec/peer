"""메모리 그룹 개별 종목 커플링 (일회성 분석).

"마이크론 보고 삼전/하이닉스 산다"는 주장을 종목 쌍 단위로 확인한다.
MU 전일 수익률 -> 국내 당일 수익률 회귀로 전달 계수(beta)와 설명력(R^2)을 본다.
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import statsmodels.api as sm

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from peer_tracker import fetch_close  # noqa: E402

TICKERS = ["MU", "WDC", "000660.KS", "005930.KS"]


def main() -> None:
    today = date.today()
    start, end = today - timedelta(days=365), today + timedelta(days=1)
    closes = {t: fetch_close(t, start, end) for t in TICKERS}
    frame = pd.concat([s for s in closes.values() if s is not None], axis=1, sort=True).ffill().dropna()
    ret = frame.pct_change().dropna()

    print(f"기간 {ret.index[0].date()} ~ {ret.index[-1].date()}, {len(ret)} 거래일\n")

    print("일간 수익률 상관 (동일 날짜)")
    print(ret.corr().round(2).to_string(), "\n")

    print("전일 미국 -> 당일 국내 전달 회귀")
    for kr in ["000660.KS", "005930.KS"]:
        for us in ["MU", "WDC"]:
            x = ret[us].shift(1)
            pair = pd.concat([x.rename("x"), ret[kr].rename("y")], axis=1).dropna()
            fit = sm.OLS(pair["y"], sm.add_constant(pair["x"])).fit()
            beta, r2, p = fit.params.iloc[1], fit.rsquared, fit.pvalues.iloc[1]
            print(f"  {us}(t-1) -> {kr}(t): beta={beta:5.2f}  R2={r2:5.3f}  p={p:6.4f}")

    print("\n누적 수익률 (1년)")
    total = (frame.iloc[-1] / frame.iloc[0] - 1) * 100
    for t, v in total.items():
        print(f"  {t:>10}: {v:+7.1f}%")


if __name__ == "__main__":
    main()
