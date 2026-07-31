"""한국-미국 커플링 그룹의 괴리 수렴(따라잡기) 백테스트.

질문 세 가지에 답한다.
1. 과거에 실제로 커플링이 성립한 그룹이 있었는가 (2020년 이후 상관)
2. 괴리가 벌어진 뒤 국내가 따라잡은 사례가 있었는가
3. 그 결과는 어떻게 됐는가 (회복률, 절반 회복까지 걸린 거래일, 완전 수렴 비율)

괴리는 로그 상대지수로 잰다. rel = log(국내 체인지수) - log(해외 체인지수).
기준일 100 정규화와 달리 시작일을 옮겨도 값이 평행 이동만 하므로,
장기 표본에서 "언제부터 봤느냐"에 따라 괴리 폭이 달라지지 않는다.

결과는 frontend/public/backtest_data.json으로 저장한다.
"""

from __future__ import annotations

import json
import math
import time
from datetime import date, timedelta
from pathlib import Path
from statistics import median

import numpy as np
import pandas as pd

from peer_tracker import (
    COUPLING_START,
    PEER_GROUPS,
    chain_index,
    coupling_stats,
    fetch_batch_closes,
    fetch_close,
    label_of,
)

Z_WINDOW = 60           # 괴리 기준선 윈도우 (거래일). 20일은 잡음이 너무 많다.
THRESHOLD = 1.5         # 에피소드로 인정하는 |Z|
MIN_GAP_PCT = 5.0       # 최소 괴리 폭(%p). 이보다 작으면 되돌림을 재도 의미가 없다.
HORIZONS = (20, 60)     # 결과를 측정하는 거래일
RECOVERY_HALF = 0.5     # "절반 회복" 기준
MIN_DAYS = 250          # 이보다 짧은 표본은 백테스트하지 않는다
CHART_BEFORE = 60       # 에피소드 차트에 보여줄 신호 이전 거래일
COIN_FLIP = 50.0        # 판정 기준선(%). 수렴이 우연보다 나은지 가른다
Z95 = 1.96              # 95% 신뢰구간


def wilson(hits: int, total: int) -> tuple[float, float]:
    """이항비율의 Wilson 95% 신뢰구간(%).

    표본이 40건 안팎이라 정규근사(p ± 1.96·SE)는 구간이 0 밑이나 100 위로 나간다.
    Wilson은 작은 표본에서도 구간이 [0, 100] 안에 머문다.
    """
    if total == 0:
        return (0.0, 100.0)
    p = hits / total
    den = 1 + Z95**2 / total
    center = (p + Z95**2 / (2 * total)) / den
    half = Z95 * math.sqrt(p * (1 - p) / total + Z95**2 / (4 * total**2)) / den
    return (round(max(0.0, center - half) * 100, 1), round(min(1.0, center + half) * 100, 1))


def verdict_of(low: float, high: float) -> str:
    """신뢰구간이 50%와 구분되는지. 걸치면 판정하지 않는다.

    표본 40건에서 나온 43%와 57%는 통계적으로 같은 값이다. 순위를 매기면
    없는 차이를 있는 것처럼 보여주게 되므로, 구간이 기준선을 넘는지만 말한다.
    """
    if low > COIN_FLIP:
        return "converges"      # 확실히 우세
    if high < COIN_FLIP:
        return "diverges"       # 확실히 열세
    return "undecided"          # 표본 부족


def required_sample(rate: float) -> int | None:
    """현재 비율이 참값이라면 50%와 구분하는 데 필요한 표본 수.

    "모른다"로 끝내지 않고 얼마가 더 필요한지 함께 알린다.
    기준선과 차이가 없으면(정확히 50%) 어떤 표본으로도 구분되지 않는다.
    """
    diff = abs(rate / 100 - 0.5)
    if diff < 0.005:
        return None
    return math.ceil(Z95**2 * 0.25 / diff**2)

OUTPUT_PATH = Path(__file__).parent / "frontend" / "public" / "backtest_data.json"


def relative_index(lead: pd.Series, lag: pd.Series) -> pd.Series:
    """두 그룹 체인지수의 로그 비. 양수면 국내가 앞서 있다."""
    common = lead.index.intersection(lag.index)
    return np.log(lag.loc[common]) - np.log(lead.loc[common])


def find_episodes(rel: pd.Series) -> list[dict]:
    """괴리 에피소드와 그 이후 결과.

    d = rel - 기준선(이동평균). d < 0이면 국내가 뒤처진 상태다.
    회복률 = -(rel 변화) / d 로 방향을 흡수한다. 양수면 괴리가 좁혀졌다는 뜻이고
    1.0이면 기준선까지 완전히 돌아온 것이다.

    한 번 잡은 신호는 절반 회복하거나 최장 구간이 지날 때까지 다시 잡지 않는다.
    같은 괴리를 여러 번 세면 표본이 부풀고 성공/실패가 함께 복제된다.
    """
    baseline = rel.rolling(Z_WINDOW).mean()
    sigma = rel.rolling(Z_WINDOW).std()
    z = ((rel - baseline) / sigma).replace([np.inf, -np.inf], np.nan)

    max_h = max(HORIZONS)
    episodes: list[dict] = []
    cooldown_until = -1

    for pos, ts in enumerate(rel.index):
        if pos <= cooldown_until:
            continue
        zv = z.iloc[pos]
        if pd.isna(zv) or abs(zv) < THRESHOLD:
            continue

        gap = float(rel.iloc[pos] - baseline.iloc[pos]) * 100  # %p
        if abs(gap) < MIN_GAP_PCT:
            continue

        # 신호 이후 경로. 표본 끝에 닿으면 결과가 확정되지 않은 진행 중 건이다.
        future = rel.iloc[pos : pos + max_h + 1]
        recovery = -(future - rel.iloc[pos]) / (rel.iloc[pos] - baseline.iloc[pos])

        # 절반 회복 / 완전 수렴까지 걸린 거래일. 도달하지 못하면 None.
        half = next((k for k, r in enumerate(recovery) if r >= RECOVERY_HALF), None)
        full = next((k for k, r in enumerate(recovery) if r >= 1.0), None)

        by_horizon = {}
        for h in HORIZONS:
            if h >= len(future):
                by_horizon[h] = None
                continue
            by_horizon[h] = {
                # 국내 - 해외 초과수익(%p). 방향 없이 실제로 얼마나 움직였는지.
                "excess": round(float(future.iloc[h] - future.iloc[0]) * 100, 2),
                "recovery": round(float(recovery.iloc[h]), 2),
            }

        resolved = len(future) > max_h
        episodes.append(
            {
                "date": ts.date().isoformat(),
                # series 배열 안 위치. 프론트가 날짜를 되짚지 않고 구간을 자를 수 있다.
                "pos": pos,
                "direction": "undershoot" if gap < 0 else "overshoot",
                "gap": round(gap, 2),
                "z": round(float(zv), 2),
                "horizons": by_horizon,
                "days_to_half": half,
                "days_to_full": full,
                "resolved": resolved,
            }
        )

        cooldown_until = pos + (half if half is not None else max_h)

    return episodes


def current_state(rel: pd.Series) -> dict | None:
    """마지막 거래일의 괴리 상태. 에피소드와 같은 기준선/Z를 쓴다.

    과거 사례만 보면 "지금 어디에 있는지"를 알 수 없다. 사례 목록 맨 위에
    현재 위치를 같은 척도로 놓아 바로 비교할 수 있게 한다.

    `active`는 지금이 에피소드 조건(|Z| >= 1.5 그리고 괴리 >= 5%p)을 충족하는지다.
    """
    baseline = rel.rolling(Z_WINDOW).mean()
    sigma = rel.rolling(Z_WINDOW).std()
    if pd.isna(baseline.iloc[-1]) or pd.isna(sigma.iloc[-1]) or sigma.iloc[-1] == 0:
        return None

    gap = float(rel.iloc[-1] - baseline.iloc[-1]) * 100
    z = float((rel.iloc[-1] - baseline.iloc[-1]) / sigma.iloc[-1])
    return {
        "date": rel.index[-1].date().isoformat(),
        "pos": len(rel) - 1,
        "gap": round(gap, 2),
        "z": round(z, 2),
        "direction": "undershoot" if gap < 0 else "overshoot",
        "active": abs(z) >= THRESHOLD and abs(gap) >= MIN_GAP_PCT,
    }


def summarize(episodes: list[dict]) -> dict:
    """확정된 에피소드만 모아 수렴 통계를 낸다."""

    done = [e for e in episodes if e["resolved"]]
    out: dict[str, object] = {"episodes": len(episodes), "resolved": len(done)}

    for h in HORIZONS:
        rows = [e["horizons"][h] for e in done if e["horizons"].get(h)]
        recoveries = [r["recovery"] for r in rows]
        hits = sum(r >= RECOVERY_HALF for r in recoveries)
        low, high = wilson(hits, len(rows))
        rate = round(hits / len(rows) * 100, 1) if rows else None
        out[f"h{h}"] = {
            "count": len(rows),
            # 괴리가 절반 이상 좁혀진 비율. 커플링이 신호로 쓸 만하면 50%를 넘어야 한다.
            "half_rate": rate,
            # 표본이 작으면 비율 하나로는 순위를 만들 수 없다. 구간을 함께 내려보낸다.
            "low": low if rows else None,
            "high": high if rows else None,
            "verdict": verdict_of(low, high) if rows else "undecided",
            "required": required_sample(rate) if rate is not None else None,
            # 방향만이라도 맞은 비율 (조금이라도 좁혀짐)
            "narrow_rate": round(sum(r > 0 for r in recoveries) / len(rows) * 100, 1)
            if rows
            else None,
            "median_recovery": round(median(recoveries), 2) if rows else None,
        }

    halves = [e["days_to_half"] for e in done if e["days_to_half"] is not None]
    max_h = max(HORIZONS)
    # 완전수렴에 '닿은' 것과 그 상태를 '유지한' 것은 다르다.
    # 닿음만 세면 되돌아간 건까지 성공으로 읽힌다(실측 26%p 차이).
    touched = sum(e["days_to_full"] is not None for e in done)
    held = sum(
        1
        for e in done
        if e["horizons"].get(max_h) and e["horizons"][max_h]["recovery"] >= 1.0
    )
    out["full_rate"] = (
        round(touched / len(done) * 100, 1) if done else None
    )
    out["touched_rate"] = round(touched / len(done) * 100, 1) if done else None
    out["held_rate"] = round(held / len(done) * 100, 1) if done else None
    out["touched_ci"] = wilson(touched, len(done)) if done else None
    out["held_ci"] = wilson(held, len(done)) if done else None
    out["median_days_to_half"] = median(halves) if halves else None
    return out


def analyze_group(key: str, cfg: dict, closes: dict[str, pd.Series]) -> dict | None:
    leads = [closes[t] for t in cfg["lead_tickers"] if t in closes]
    lags = [closes[t] for t in cfg["lag_tickers"] if t in closes]
    if not leads or not lags:
        print(f"[{key}] [skip] Lead/Lag 한쪽 데이터 없음")
        return None

    lead_index, lag_index = chain_index(leads), chain_index(lags)
    rel = relative_index(lead_index, lag_index)
    if len(rel) < MIN_DAYS:
        print(f"[{key}] [skip] 표본 {len(rel)}일")
        return None

    # 커플링 상세는 괴리 탭(dashboard_data.json)이 단일 출처다. 여기서는 그룹을
    # 걸러내는 등급만 쓴다. 두 곳에서 같은 값을 내려보내면 실행 시각이 어긋날 때
    # 탭마다 다른 숫자가 표시된다(실측 PCB 0.58 vs 0.59).
    coupling = coupling_stats(lead_index, lag_index)
    tier_only = {"tier": coupling["tier"]} if coupling else None
    episodes = find_episodes(rel)
    summary = summarize(episodes)
    current = current_state(rel)

    tier = coupling["tier"] if coupling else "unknown"
    h60 = summary[f"h{max(HORIZONS)}"]
    print(
        f"[{key}] {cfg['desc']} tier={tier} 에피소드={summary['episodes']}"
        f" 절반회복={h60['half_rate']}% 중위회복={h60['median_recovery']}"
    )

    return {
        "key": key,
        "sector": cfg.get("sector", "기타"),
        "desc": cfg["desc"],
        "lead_labels": [label_of(t) for t in cfg["lead_tickers"] if t in closes],
        "lag_labels": [label_of(t) for t in cfg["lag_tickers"] if t in closes],
        "coupling": tier_only,
        "sample_days": len(rel),
        "sample_from": rel.index[0].date().isoformat(),
        "summary": summary,
        # 표 맨 위에 놓을 '지금' 상태. 과거 사례만 보면 현재 위치를 알 수 없다.
        "current": current,
        "episodes": episodes,
        # 에피소드 차트용 원자료. 프론트가 신호 시점 앞뒤 구간을 잘라 쓴다.
        # 에피소드별로 윈도우를 따로 실으면 구간이 겹쳐 4배 커지므로 그룹당 한 벌만 둔다.
        # 배열 3개를 나란히 두는 형태다. 객체 배열로 만들면 키가 매 포인트마다 반복된다.
        "series": {
            "dates": [ts.date().isoformat() for ts in rel.index],
            "lead": [round(float(v), 2) for v in lead_index.loc[rel.index]],
            "lag": [round(float(v), 2) for v in lag_index.loc[rel.index]],
        },
    }


def overall(groups: list[dict], only_coupled: bool) -> dict:
    """전체(또는 커플링 유효 그룹만) 합산 통계."""
    picked = [
        g
        for g in groups
        if not only_coupled
        or (g["coupling"] and g["coupling"]["tier"] in ("strong", "moderate"))
    ]
    episodes = [e for g in picked for e in g["episodes"]]
    stats = summarize(episodes)
    stats["groups"] = len(picked)
    stats["breakdown"] = breakdown(picked)
    return stats


def _slice(episodes: list[dict], label: str, horizon: int) -> dict:
    """부분집합 하나의 수렴률과 구간. 대비를 보여주기 위한 최소 정보만 담는다."""
    rows = [
        e["horizons"][horizon]
        for e in episodes
        if e["resolved"] and e["horizons"].get(horizon)
    ]
    hits = sum(r["recovery"] >= RECOVERY_HALF for r in rows)
    low, high = wilson(hits, len(rows))
    return {
        "label": label,
        "count": len(rows),
        "rate": round(hits / len(rows) * 100, 1) if rows else None,
        "low": low if rows else None,
        "high": high if rows else None,
    }


def breakdown(groups: list[dict]) -> dict:
    """방향·괴리 크기·커플링 등급으로 갈라 본 수렴률.

    실측에서 세 축 모두 차이가 없었다. 무효 결과지만 "괴리가 크면 더 좁혀진다"
    같은 직관을 데이터로 반박하는 근거라 화면에 그대로 내려보낸다.

    구간 버튼(20일/60일)을 따라가야 하므로 horizon별로 한 벌씩 만든다.
    """
    episodes = [e for g in groups for e in g["episodes"]]
    by_tier = {
        tier: [
            e
            for g in groups
            if g["coupling"] and g["coupling"]["tier"] == tier
            for e in g["episodes"]
        ]
        for tier in ("strong", "moderate")
    }
    return {
        f"h{h}": {
            "direction": [
                _slice([e for e in episodes if e["direction"] == "undershoot"], "국내 뒤처짐", h),
                _slice([e for e in episodes if e["direction"] == "overshoot"], "국내 앞섬", h),
            ],
            "gap": [
                _slice([e for e in episodes if lo <= abs(e["gap"]) < hi], label, h)
                for lo, hi, label in (
                    (5, 8, "5~8%p"),
                    (8, 12, "8~12%p"),
                    (12, 999, "12%p 이상"),
                )
            ],
            "tier": [
                _slice(by_tier["strong"], "커플링 강", h),
                _slice(by_tier["moderate"], "커플링 중", h),
            ],
        }
        for h in HORIZONS
    }


def main() -> None:
    today = date.today()
    end = today + timedelta(days=1)  # yfinance end는 exclusive
    print(f"백테스트 표본: {COUPLING_START} ~ {today} (그룹 {len(PEER_GROUPS)}개)")
    print(f"기준선 {Z_WINDOW}일 · |Z| >= {THRESHOLD} · 최소 괴리 {MIN_GAP_PCT}%p\n")

    universe = sorted(
        {
            t
            for cfg in PEER_GROUPS.values()
            for key in ("lead_tickers", "lag_tickers")
            for t in cfg[key]
        }
    )
    t0 = time.monotonic()
    closes = fetch_batch_closes(universe, COUPLING_START, end)
    for ticker in [t for t in universe if t not in closes]:
        series = fetch_close(ticker, COUPLING_START, end)
        if series is not None:
            closes[ticker] = series
    print(f"수집 완료: {len(closes)}/{len(universe)}개 ({time.monotonic() - t0:.1f}s)\n")

    groups = [
        result
        for key, cfg in PEER_GROUPS.items()
        if (result := analyze_group(key, cfg, closes)) is not None
    ]
    tier_rank = {"strong": 0, "moderate": 1, "weak": 2, "unknown": 3}
    groups.sort(
        key=lambda g: (
            tier_rank[g["coupling"]["tier"] if g["coupling"] else "unknown"],
            -(g["summary"][f"h{max(HORIZONS)}"]["half_rate"] or 0),
        )
    )

    payload = {
        "generated_at": pd.Timestamp.now().isoformat(timespec="seconds"),
        "period": {"start": COUPLING_START.isoformat(), "end": today.isoformat()},
        "z_window": Z_WINDOW,
        "threshold": THRESHOLD,
        "min_gap": MIN_GAP_PCT,
        "horizons": list(HORIZONS),
        "recovery_half": RECOVERY_HALF,
        "chart_before": CHART_BEFORE,
        "overall": overall(groups, only_coupled=False),
        "coupled": overall(groups, only_coupled=True),
        "groups": groups,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    # 다른 산출물과 달리 들여쓰기를 넣지 않는다. 그룹당 6년치 시계열 2개가 들어가
    # indent=2로 쓰면 배열 원소마다 줄바꿈+공백이 붙어 1.7MB가 3.5MB로 커진다.
    OUTPUT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )

    print(f"\n저장: {OUTPUT_PATH}")
    for name, stats in (("전체", payload["overall"]), ("커플링 유효", payload["coupled"])):
        h = stats[f"h{max(HORIZONS)}"]
        print(
            f"{name}: 그룹 {stats['groups']}개 · 확정 {stats['resolved']}건 · "
            f"{max(HORIZONS)}일 절반회복 {h['half_rate']}% "
            f"({h['low']}~{h['high']}%, {h['verdict']}) · "
            f"수렴 닿음 {stats['touched_rate']}% -> 유지 {stats['held_rate']}%"
        )

    # 현재 괴리 상태. 화면 첫 줄에 놓는 값이라 실행 직후 확인할 수 있게 둔다.
    active = [g for g in groups if g["current"] and g["current"]["active"]]
    print(f"현재 괴리 확대 그룹: {len(active)}/{len(groups)}개")
    for g in sorted(active, key=lambda x: x["current"]["gap"])[:5]:
        c = g["current"]
        print(f"  {g['desc']} {c['gap']:+.1f}%p (Z {c['z']:+.2f})")


if __name__ == "__main__":
    main()
