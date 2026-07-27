"""해외 Lead vs 국내 Lag 밸류에이션 갭 분석 (일회성 분석).

제약: yfinance에서 국내 종목은 trailingPE / priceToBook이 전부 결측이고
분기 EPS도 4개뿐이라 배수 시계열을 만들 수 없다. 따라서 배수는 현재 스냅샷만 쓴다.

측정
1. 그룹별 forwardPE / EV-EBITDA 중위값의 해외-국내 갭 (디스카운트율)
2. 그 디스카운트가 주가 성과 격차와 관계있는지 (그룹 단위 상관)
3. 종목 단위: 밸류 디스카운트가 클수록 이후 수익률이 높았는가
"""

from __future__ import annotations

import sys
import time
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from peer_tracker import KR_NAMES, PEER_GROUPS, fetch_close  # noqa: E402

MULTIPLES = ("forwardPE", "enterpriseToEbitda", "priceToSalesTrailing12Months")


def snapshot(ticker: str) -> dict:
    try:
        info = yf.Ticker(ticker).info
    except Exception:
        return {}
    finally:
        time.sleep(0.2)
    out = {k: info.get(k) for k in MULTIPLES}
    out["marketCap"] = info.get("marketCap")
    out["currency"] = info.get("currency")
    return out


def clean(values: list[float | None]) -> list[float]:
    """음수 배수(적자)와 비정상값은 밸류 비교에서 제외한다."""
    return [v for v in values if v is not None and not np.isnan(v) and 0 < v < 200]


def main() -> None:
    end = date.today()
    start = end - timedelta(days=365)
    rows = []

    for key, cfg in PEER_GROUPS.items():
        snap = {}
        for t in cfg["lead_tickers"] + cfg["lag_tickers"]:
            snap[t] = snapshot(t)

        # 1년 수익률 (같은 통화 내 비교가 아니라 각 종목 수익률이므로 환율 무관)
        def ret_of(tickers):
            vals = []
            for t in tickers:
                s = fetch_close(t, start, end)
                if s is not None and len(s) > 100:
                    vals.append(float(s.iloc[-1] / s.iloc[0] - 1) * 100)
            return float(np.median(vals)) if vals else np.nan

        row = {"group": cfg["desc"], "key": key}
        for m in MULTIPLES:
            lead = clean([snap[t].get(m) for t in cfg["lead_tickers"]])
            lag = clean([snap[t].get(m) for t in cfg["lag_tickers"]])
            lv = float(np.median(lead)) if lead else np.nan
            gv = float(np.median(lag)) if lag else np.nan
            row[f"{m}_lead"] = round(lv, 1) if not np.isnan(lv) else None
            row[f"{m}_lag"] = round(gv, 1) if not np.isnan(gv) else None
            row[f"{m}_disc"] = (
                round((gv / lv - 1) * 100, 1) if not (np.isnan(lv) or np.isnan(gv)) else None
            )

        row["ret_lead"] = round(ret_of(cfg["lead_tickers"]), 1)
        row["ret_lag"] = round(ret_of(cfg["lag_tickers"]), 1)
        row["ret_gap"] = round(row["ret_lag"] - row["ret_lead"], 1)
        rows.append(row)

    df = pd.DataFrame(rows)
    pd.set_option("display.width", 250)

    print("그룹별 밸류에이션 (중위값) 및 1년 성과")
    view = df[
        ["group", "forwardPE_lead", "forwardPE_lag", "forwardPE_disc",
         "enterpriseToEbitda_lead", "enterpriseToEbitda_lag", "enterpriseToEbitda_disc",
         "ret_lead", "ret_lag", "ret_gap"]
    ].rename(
        columns={
            "forwardPE_lead": "fPE해외", "forwardPE_lag": "fPE국내", "forwardPE_disc": "fPE갭%",
            "enterpriseToEbitda_lead": "EV해외", "enterpriseToEbitda_lag": "EV국내",
            "enterpriseToEbitda_disc": "EV갭%",
        }
    )
    print(view.sort_values("fPE갭%").to_string(index=False))

    print("\n디스카운트와 성과 격차의 관계 (그룹 n=%d)" % len(df))
    for m in ("forwardPE", "enterpriseToEbitda", "priceToSalesTrailing12Months"):
        pair = df[[f"{m}_disc", "ret_gap"]].dropna()
        if len(pair) > 4:
            r = pair.corr().iloc[0, 1]
            print(f"  {m:<32} corr(갭, 성과격차) = {r:+.2f}  (n={len(pair)})")


if __name__ == "__main__":
    main()
