"""PER / PBR 시계열을 직접 만들어 해외-국내 밸류에이션 커플링 측정 (일회성 분석).

yfinance의 info는 스냅샷 하나뿐이고 국내는 trailingPE/priceToBook이 결측이다.
대신 재무제표 항목명은 국내외 동일하므로 직접 계산한다.

  PER(t) = 주가(t) / TTM EPS(발표일 기준으로 계단식 적용)
  PBR(t) = 주가(t) / BPS(발표일 기준)

분기 5개 + 연간 4~5년을 합쳐 EPS/BPS 시계열을 만들고, 각 관측일 이후 구간에
forward-fill 한다(발표 시점 이전 값을 쓰지 않도록 lookahead를 차단).

측정: 그룹별 PER 로그 변화율의 해외-국내 상관, PER 갭의 평균회귀 여부.
"""

from __future__ import annotations

import sys
import time
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from peer_tracker import PEER_GROUPS, fetch_close  # noqa: E402

START = date(2021, 1, 1)
REPORT_DELAY = pd.Timedelta(days=45)   # 결산일 -> 공시까지의 지연 가정


def fundamental_series(ticker: str) -> tuple[pd.Series, pd.Series] | None:
    """(EPS TTM, BPS) 시계열. 결산일에 REPORT_DELAY를 더해 공시 시점으로 옮긴다."""
    tk = yf.Ticker(ticker)
    try:
        qi, ai = tk.quarterly_income_stmt, tk.income_stmt
        qb, ab = tk.quarterly_balance_sheet, tk.balance_sheet
    except Exception:
        return None
    finally:
        time.sleep(0.2)

    def row(frames: list[pd.DataFrame], name: str) -> pd.Series:
        parts = []
        for f in frames:
            if f is not None and not f.empty and name in f.index:
                s = f.loc[name].dropna()
                s.index = pd.to_datetime(s.index)
                parts.append(s)
        if not parts:
            return pd.Series(dtype=float)
        merged = pd.concat(parts)
        return merged[~merged.index.duplicated(keep="first")].sort_index()

    ni_q = row([qi], "Net Income")
    ni_a = row([ai], "Net Income")
    equity = row([qb, ab], "Stockholders Equity")
    shares = row([qi, ai], "Diluted Average Shares")
    if equity.empty or shares.empty or (ni_q.empty and ni_a.empty):
        return None

    # TTM 순이익: 분기가 4개 이상이면 4분기 합, 아니면 연간값 사용
    if len(ni_q) >= 4:
        ttm = ni_q.rolling(4).sum().dropna()
        ttm = pd.concat([ni_a[ni_a.index < ttm.index.min()], ttm]).sort_index()
    else:
        ttm = ni_a

    shares_ff = shares.reindex(ttm.index.union(equity.index)).ffill().bfill()
    eps = (ttm / shares_ff.reindex(ttm.index)).dropna()
    bps = (equity / shares_ff.reindex(equity.index)).dropna()

    eps.index = eps.index + REPORT_DELAY
    bps.index = bps.index + REPORT_DELAY
    return eps, bps


def multiple_series(ticker: str, end: date) -> pd.DataFrame | None:
    """일별 PER / PBR. EPS가 음수인 구간은 PER을 결측 처리한다."""
    px = fetch_close(ticker, START, end)
    fund = fundamental_series(ticker)
    if px is None or fund is None:
        return None
    eps, bps = fund

    eps_d = eps.reindex(px.index.union(eps.index)).ffill().reindex(px.index)
    bps_d = bps.reindex(px.index.union(bps.index)).ffill().reindex(px.index)

    per = (px / eps_d).where(eps_d > 0)
    pbr = (px / bps_d).where(bps_d > 0)
    df = pd.DataFrame({"per": per, "pbr": pbr}).dropna(how="all")
    # 극단값 제거: 배수 500 초과는 실질적으로 의미 없다
    return df.mask(df > 500)


def group_multiple(tickers: list[str], end: date, col: str) -> pd.Series:
    """그룹 배수 = 종목별 배수의 일별 중위값."""
    series = []
    for t in tickers:
        df = multiple_series(t, end)
        if df is not None and df[col].notna().sum() > 100:
            series.append(df[col].rename(t))
    if not series:
        return pd.Series(dtype=float)
    return pd.concat(series, axis=1, sort=True).median(axis=1, skipna=True).dropna()


def main() -> None:
    end = date.today()
    rows = []

    for key, cfg in PEER_GROUPS.items():
        for col in ("per", "pbr"):
            lead = group_multiple(cfg["lead_tickers"], end, col)
            lag = group_multiple(cfg["lag_tickers"], end, col)
            common = lead.index.intersection(lag.index)
            if len(common) < 250:
                continue

            l, g = lead.loc[common], lag.loc[common]
            # 배수 변화율(로그차분) 상관: 레벨 상관은 추세 때문에 과대평가된다
            dl = np.log(l).diff()
            dg = np.log(g).diff()
            same = pd.concat([dl, dg], axis=1).dropna()
            lag1 = pd.concat([dl.shift(1), dg], axis=1).dropna()

            ratio = g / l           # 국내 배수 / 해외 배수
            rows.append(
                {
                    "group": cfg["desc"],
                    "metric": col.upper(),
                    "n": len(common),
                    "d_corr": round(float(same.iloc[:, 0].corr(same.iloc[:, 1])), 2),
                    "d_corr_lag1": round(float(lag1.iloc[:, 0].corr(lag1.iloc[:, 1])), 2),
                    "lead_now": round(float(l.iloc[-1]), 1),
                    "lag_now": round(float(g.iloc[-1]), 1),
                    "ratio_now": round(float(ratio.iloc[-1]), 2),
                    "ratio_med": round(float(ratio.median()), 2),
                    "ratio_z": round(
                        float((ratio.iloc[-1] - ratio.mean()) / ratio.std()), 2
                    ),
                }
            )

    df = pd.DataFrame(rows)
    pd.set_option("display.width", 250)
    for metric in ("PER", "PBR"):
        sub = df[df.metric == metric].sort_values("d_corr", ascending=False)
        if sub.empty:
            continue
        print(f"\n===== {metric} 커플링 (배수 변화율 상관)")
        print(sub.drop(columns="metric").to_string(index=False))

    print("\nd_corr: 같은 날 배수 변화 동행 / d_corr_lag1: 전일 해외 -> 당일 국내")
    print("ratio_now: 현재 국내/해외 배수비 (1 미만이면 국내 할인)")
    print("ratio_z: 배수비의 과거 평균 대비 Z-Score (음수면 평소보다 더 할인)")


if __name__ == "__main__":
    main()
