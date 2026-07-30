"""각 그룹 주도주의 커뮤니티 여론을 주기적으로 훑어 대시보드 JSON을 갱신한다.

    python fomo_watch.py            # 주도주 전체
    python fomo_watch.py --limit 3  # 앞 3종목만 (점검용)

감시 대상은 dashboard_data.json의 bellwether다. 괴리(Z-Score) 탭이 이미 뽑아둔
주도주를 그대로 쓰므로 종목 목록을 따로 관리할 필요가 없고, 티커가 두 탭을 잇는
조인 키가 된다.

종목은 순차로, 소스는 병렬로 돈다. 종목까지 병렬로 돌리면 같은 도메인에 초당 수십
건이 몰려 차단을 부른다.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import fomo_core as core
import fomo_market
import fomo_news
from fomo_indices import INDICES, US_INDEX_LOOKBACK_DAYS, index_levels

ROOT = Path(__file__).parent
DASHBOARD_PATH = ROOT / "frontend" / "public" / "dashboard_data.json"
OUTPUT_PATH = ROOT / "frontend" / "public" / "fomo_data.json"

STOCK_SLEEP_SEC = 2.0   # 종목 사이 간격. 커뮤니티 서버에 대한 예의이자 차단 회피다.
# 회차 단위 이력. 2시간 주기면 하루 12포인트라 3일치다. 짧은 구간의 등락을 본다.
HISTORY_POINTS = 36
# 일별 집계 이력. 하루 평균 한 점으로 줄여 한 달을 본다.
#
# 회차 이력을 그대로 360포인트까지 늘리면 이력만 500KB가 되고, 100px 폭 그래프에
# 360개를 그려도 읽히지 않는다. 하루 평균으로 접으면 30포인트로 같은 기간을 덮는다.
DAILY_POINTS = 30
INTERVAL_HOURS = 2
EVIDENCE_PER_STOCK = 8   # 종목별로 남길 근거 게시글 수
# 지수 카드를 펼치면 근거를 목록으로 펼쳐 보여준다. 화면이 감당하는 만큼 남긴다.
EVIDENCE_PER_INDEX = 24
EVIDENCE_PER_MARKET = 16
# 화제글 피드에 남길 인기글 수. 한 회차에 60건이 들어오므로 전부 담는다.
FEED_LIMIT = 60


def scan_market_wide() -> core.ScanResult | None:
    """검색어 없이 받는 시장 전체 소스(에펨 인기글).

    종목 검색으로는 안 잡히는 글이 여기 있다. `삼전본주 -39% 대인데 엄살인거지?`
    처럼 화제가 된 글은 종목명을 정확히 쓰지 않아도 시장 분위기를 담고 있다.
    """
    sources = [s for s in core.SOURCES if s.market_wide]
    if not sources:
        return None

    results = [
        core._collect_one(s, "", None, core.LOOKBACK_DAYS) for s in sources
    ]
    return core.ScanResult("시장 전체", None, results)


def merge_market_wide(market: dict[str, object], scan: core.ScanResult | None) -> dict[str, object]:
    """인기글 표본을 시장 심리에 더한다.

    개별 종목에는 섞지 않는다. 인기글은 종목을 특정하지 않아서 30종목이 같은 표본을
    공유하게 되고, 지수 별칭으로 걸러봤을 때는 60건 중 2건만 남아 표본이 사라졌다.
    시장 전체 심리는 원래 여러 종목을 합친 값이라 여기 더하는 것이 자연스럽다.
    """
    if scan is None:
        return market

    report = core.analyze(scan)
    stats = report.stats
    if not stats.greed_total and not stats.fear_total:
        return market

    greed = market["greed_total"] + stats.greed_total
    fear = market["fear_total"] + stats.fear_total
    score = core.sentiment_score(greed, fear)

    merged = dict(market)
    merged["greed_total"] = greed
    merged["fear_total"] = fear
    merged["hits"] = greed + fear
    merged["total_posts"] = market["total_posts"] + report.total_posts
    merged["hot_posts"] = market.get("hot_posts", 0) + report.hot_posts
    merged["dropped_posts"] = market.get("dropped_posts", 0) + report.dropped_posts
    merged["score"] = score
    merged["zone"] = core.interpret(score)[0] if score is not None else None
    merged["label"] = core.interpret(score)[1] if score is not None else "표본 부족"

    for side, field_name in (("greed", "greed_counts"), ("fear", "fear_counts")):
        totals = dict(merged["keyword_totals"][side])
        for word, hits in getattr(stats, field_name).items():
            totals[word] = totals.get(word, 0) + hits
        merged["keyword_totals"][side] = dict(sorted(totals.items(), key=lambda kv: -kv[1]))

    # 인기글 근거는 종목 이름이 없다. 어디서 왔는지 알 수 있게 표시를 붙인다.
    extra = [{**item, "stock": "인기글"} for item in report.evidence(EVIDENCE_PER_MARKET)]
    merged["evidence"] = core.interleave_evidence(
        list(market.get("evidence", [])) + extra, EVIDENCE_PER_MARKET
    )
    return merged


def _collect_news(market: dict[str, object]) -> dict[str, object] | None:
    """섹터별 뉴스 논조를 받는다. 통째로 실패해도 회차를 살린다.

    검색어는 섹터 이름을 쓴다(`반도체 주가`). 대표주 이름으로 검색하면 표본이
    3~9건으로 말라 종목 점수와 같은 문제가 재발한다.
    """
    sectors = [s["sector"] for s in market.get("sectors", [])]
    if not sectors:
        return None

    try:
        results = fomo_news.collect(sectors)
    except Exception as exc:                      # noqa: BLE001 - 회차를 잃지 않는다
        print(f"[뉴스] 수집 실패: {type(exc).__name__}: {exc}", file=sys.stderr)
        return None

    payload = fomo_news.payload(results)
    failed = [s["sector"] for s in payload["sectors"] if s["error"]]
    note = f" · 실패 {len(failed)}섹터" if failed else ""
    print(
        f"뉴스 논조 {payload['score']} ({payload['label']}) · "
        f"긍정 {payload['positive_total']} / 부정 {payload['negative_total']} · "
        f"기사 {payload['total']}건{note}"
    )
    return payload


def load_targets() -> list[dict[str, str]]:
    """대시보드 JSON에서 주도주 목록을 뽑는다. 티커 기준으로 중복을 제거한다."""
    if not DASHBOARD_PATH.exists():
        raise FileNotFoundError(
            f"{DASHBOARD_PATH.name}이 없습니다. python peer_tracker.py를 먼저 실행하세요."
        )

    data = json.loads(DASHBOARD_PATH.read_text(encoding="utf-8"))
    # 현재가는 목표 수치 판정에 쓴다. `10만원 가즈아`가 기대인지 조롱인지는
    # 지금 주가를 알아야 갈린다.
    prices: dict[str, float] = {}
    for group in data.get("groups", []):
        for item in group.get("lag_tickers", []) + group.get("lead_tickers", []):
            quote = item.get("quote") or {}
            close = quote.get("close")
            if item.get("ticker") and close:
                prices[item["ticker"]] = float(close)

    targets: dict[str, dict[str, str]] = {}
    for group in data.get("groups", []):
        ticker = group.get("bellwether_ticker")
        name = group.get("bellwether_name")
        if not ticker or not name:
            continue
        # 여러 그룹의 주도주가 같을 수 있다. 먼저 나온 그룹 이름을 대표로 둔다.
        targets.setdefault(
            ticker,
            {
                "key": ticker,
                "name": name,
                "group_desc": group.get("desc", ""),
                "sector": group.get("sector", ""),
                "current": prices.get(ticker),
            },
        )
    return list(targets.values())


def load_previous_history() -> dict[str, list[dict[str, object]]]:
    """이전 실행의 점수 이력. 파일이 없거나 깨졌으면 빈 이력으로 시작한다.

    점검용(--limit)으로 돌 때도 이력은 정식 파일에서 읽는다. 부분 수집 결과가
    이력을 끊어놓으면 추이선이 망가진다.
    """
    if not OUTPUT_PATH.exists():
        return {}
    try:
        data = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return {
        stock["key"]: stock.get("history", [])
        for stock in data.get("stocks", [])
        if stock.get("key")
    }


def load_market_history() -> list[dict[str, object]]:
    """시장 전체 심리 이력. 개별 종목과 따로 보관한다."""
    if not OUTPUT_PATH.exists():
        return []
    try:
        data = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    return data.get("market", {}).get("history", [])


def load_index_history() -> dict[str, list[dict[str, object]]]:
    """지수별 심리 이력."""
    if not OUTPUT_PATH.exists():
        return {}
    try:
        data = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return {
        item["key"]: item.get("history", [])
        for item in data.get("indices", [])
        if item.get("key")
    }


def _load_daily(section: str, key: str | None = None) -> list[dict[str, object]]:
    """이전 실행의 일별 이력. 회차 이력과 따로 보관한다."""
    if not OUTPUT_PATH.exists():
        return []
    try:
        data = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    if key is None:
        return data.get(section, {}).get("daily", [])
    for item in data.get(section, []):
        if item.get("key") == key:
            return item.get("daily", [])
    return []


def roll_daily(
    previous: list[dict[str, object]], stamp: str, score: float | None
) -> list[dict[str, object]]:
    """일별 이력에 오늘 값을 반영한다.

    같은 날 여러 회차가 돌면 평균으로 갱신한다. 마지막 값만 쓰면 그날의 대표값이
    우연히 걸린 한 회차에 좌우된다.
    """
    if score is None:
        return previous[-DAILY_POINTS:]

    day = stamp[:10]
    trail = [dict(p) for p in previous if p.get("date") != day]
    today = next((p for p in previous if p.get("date") == day), None)

    if today:
        count = int(today.get("n", 1)) + 1
        total = float(today["score"]) * int(today.get("n", 1)) + score
        trail.append({"date": day, "score": round(total / count, 1), "n": count})
    else:
        trail.append({"date": day, "score": score, "n": 1})

    trail.sort(key=lambda p: p["date"])
    return trail[-DAILY_POINTS:]


def scan_index(index, stamp: str, history: list, level: float | None = None) -> dict[str, object]:
    """지수 하나를 별칭 묶음으로 스캔한다.

    지수는 게시글이 많고 키워드 표본도 두꺼워 sentiment_score를 바로 쓸 수 있다.
    종목처럼 fomo_score(게시글 수로 나눔)를 쓰면 역시 50에 붙는다.
    """
    # 국내 지수는 종목과 같은 3일, 미국 지수는 언급이 드물어 7일을 본다.
    lookback = index.lookback_days or core.LOOKBACK_DAYS
    report = core.analyze(
        core.scan_aliases(index.label, list(index.aliases), lookback),
        current_level=level,
    )
    stats = report.stats
    score = core.sentiment_score(stats.greed_total, stats.fear_total)
    zone, label = core.interpret(score) if score is not None else (None, "표본 부족")
    trail = list(history)
    if score is not None:
        trail.append({"ts": stamp, "score": score})

    return {
        "key": index.key,
        "label": index.label,
        "market": index.market,
        "aliases": list(index.aliases),
        "current_level": level,
        "lookback_days": lookback,
        "score": score,
        "zone": zone,
        "label_text": label,
        "total_posts": report.total_posts,
        "greed_total": stats.greed_total,
        "fear_total": stats.fear_total,
        "hits": stats.greed_total + stats.fear_total,
        "greed_counts": stats.greed_counts,
        "fear_counts": stats.fear_counts,
        "hot_posts": report.hot_posts,
        "dropped_posts": report.dropped_posts,
        "evidence": report.evidence(EVIDENCE_PER_INDEX),
        "per_source": [
            {
                "key": r.key,
                "count": r.count,
                "error": r.error,
                "unsupported": r.unsupported,
            }
            for r in report.results
        ],
        "history": trail[-HISTORY_POINTS:],
        "daily": roll_daily(_load_daily("indices", index.key), stamp, score),
    }


def scan_target(target: dict[str, str], stamp: str, history: list) -> dict[str, object]:
    """종목 하나를 스캔해 JSON 레코드로 만든다."""
    # 대시보드 티커는 005930.KS 형태다. 네이버 종목토론실은 6자리 코드만 받는다.
    numeric = target["key"].split(".")[0]
    ticker = numeric if numeric.isdigit() and len(numeric) == 6 else None

    report = core.analyze(core.scan(target["name"], ticker), target.get("current"))
    trail = list(history) + [{"ts": stamp, "score": report.score}]

    return {
        "key": target["key"],
        "name": target["name"],
        "ticker": ticker,
        "group_desc": target["group_desc"],
        "sector": target["sector"],
        "current_level": target.get("current"),
        "score": report.score,
        "zone": report.zone,
        "label": report.label,
        "total_posts": report.total_posts,
        "greed_total": report.stats.greed_total,
        "fear_total": report.stats.fear_total,
        "greed_counts": report.stats.greed_counts,
        "fear_counts": report.stats.fear_counts,
        "hot_posts": report.hot_posts,
        "dropped_posts": report.dropped_posts,
        "evidence": report.evidence(EVIDENCE_PER_STOCK),
        "per_source": [
            {
                "key": r.key,
                "count": r.count,
                "error": r.error,
                "unsupported": r.unsupported,
            }
            for r in report.results
        ],
        "history": trail[-HISTORY_POINTS:],
        "daily": roll_daily(
            _load_daily("stocks", target["key"]), stamp, report.score
        ),
    }


def write_output(payload: dict[str, object], path: Path = OUTPUT_PATH) -> None:
    """임시 파일에 쓰고 원자적으로 교체한다.

    프론트가 갱신 중인 JSON을 반쯤 읽는 것을 막는다.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    os.replace(tmp, path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="주도주 커뮤니티 여론 수집")
    parser.add_argument(
        "--limit", type=int, default=None, help="앞 N종목만 스캔 (점검용)"
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="저장 위치 (기본: frontend/public/fomo_data.json)",
    )
    args = parser.parse_args(argv)

    # --limit은 점검용이다. 대시보드가 읽는 파일에 3종목만 남기면 화면이 비어 보이고
    # 지수도 사라진다(--limit에서는 지수를 건너뛰므로). 별도 파일로 뺀다.
    out_path = args.out
    if out_path is None:
        out_path = (
            OUTPUT_PATH.with_name("fomo_data.partial.json")
            if args.limit
            else OUTPUT_PATH
        )

    try:
        targets = load_targets()
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"[실패] {exc}", file=sys.stderr)
        return 1

    if not targets:
        print("[실패] 주도주를 찾지 못했습니다.", file=sys.stderr)
        return 1

    if args.limit:
        targets = targets[: args.limit]

    previous = load_previous_history()
    market_history = load_market_history()
    index_history = load_index_history()
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    stocks: list[dict[str, object]] = []

    # 인기글을 먼저 받는다. 종목 30개를 돈 뒤에는 에펨에 요청이 수백 건 쌓여 429가
    # 온다(실측). 회차 시작 시점은 도메인 카운터가 깨끗하다.
    wide = None if args.limit else scan_market_wide()
    if wide is not None:
        ok = [r for r in wide.results if not r.error]
        failed = [r for r in wide.results if r.error]
        note = f" · 실패: {failed[0].error}" if failed and not ok else ""
        print(f"[인기글] 수집 {sum(r.count for r in ok)}개{note}")

    for index, target in enumerate(targets, start=1):
        if index > 1:
            time.sleep(STOCK_SLEEP_SEC)
        record = scan_target(target, stamp, previous.get(target["key"], []))
        stocks.append(record)
        # 구조상 못 쓰는 소스(unsupported)는 실패로 세지 않는다.
        blocked = sum(
            1 for s in record["per_source"] if s["error"] and not s.get("unsupported")
        )
        note = f" (실패 {blocked})" if blocked else ""
        print(
            f"[{index}/{len(targets)}] {target['name']} "
            f"{record['score']} {record['label']} "
            f"수집 {record['total_posts']}개{note}"
        )

    # 지수는 별칭마다 8소스를 돌아 종목보다 무겁다. 점검용 --limit에서는 건너뛴다.
    indices: list[dict[str, object]] = []
    if not args.limit:
        levels = index_levels()
        for index in INDICES:
            time.sleep(STOCK_SLEEP_SEC)
            record = scan_index(
                index, stamp, index_history.get(index.key, []), levels.get(index.key)
            )
            indices.append(record)
            print(
                f"[지수] {index.label} {record['score']} {record['label_text']} "
                f"수집 {record['total_posts']}개"
            )

    market = core.aggregate(stocks)
    # 인기글은 종목을 특정하지 않으므로 개별 종목이 아니라 시장 심리에만 더한다.
    market = merge_market_wide(market, wide)
    # 화제글 피드. 점수 근거와 달리 키워드가 안 잡힌 글도 담는다. 인기 탭 60건 중
    # 감정 키워드가 붙는 글은 4건뿐인데, 나머지도 분위기는 분명히 담고 있다.
    feed = (
        core.feed_posts([p for r in wide.results for p in r.posts], FEED_LIMIT)
        if wide is not None
        else []
    )
    if market["score"] is not None:
        market_history = market_history + [{"ts": stamp, "score": market["score"]}]
    market["history"] = market_history[-HISTORY_POINTS:]
    market["daily"] = roll_daily(_load_daily("market"), stamp, market["score"])

    # 가격 지표 기반 시장 공포탐욕(CNN 방식). 여론과 나란히 두어 서로 보완한다.
    # 여론은 사람들이 무슨 말을 하는지, 가격 지표는 시장이 실제로 어떤지 말해준다.
    gauge = fomo_market.market_gauge()
    if gauge:
        print(
            f"시장 지표 {gauge['score']} ({gauge['label']}) · "
            + " · ".join(
                f"{c['label']} {c['score']}"
                for c in gauge["components"]
                if c["score"] is not None
            )
        )

    # 섹터별 뉴스 논조. 커뮤니티 여론과 점수를 섞지 않고 나란히 둔다. 성격이 다른
    # 표본이라 합치면 어느 쪽이 움직인 건지 알 수 없어진다.
    news = _collect_news(market)

    write_output(
        {
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "interval_hours": INTERVAL_HOURS,
            "lookback_days": core.LOOKBACK_DAYS,
            "us_index_lookback_days": US_INDEX_LOOKBACK_DAYS,
            "min_sentiment_hits": core.MIN_SENTIMENT_HITS,
            "daily_points": DAILY_POINTS,
            "history_points": HISTORY_POINTS,
            "sources": [{"key": s.key, "label": s.label} for s in core.SOURCES],
            "market": market,
            "market_gauge": gauge,
            "feed": feed,
            "news": news,
            "indices": indices,
            "stocks": stocks,
        },
        out_path,
    )
    print(
        f"\n시장 심리 {market['score']} ({market['label']}) · "
        f"탐욕 {market['greed_total']} / 공포 {market['fear_total']} · "
        f"탐욕우세 {market['greed_leaning']}종목 / 공포우세 {market['fear_leaning']}종목"
    )
    # --out으로 리포 밖 경로를 주면 relative_to가 터진다.
    try:
        shown = out_path.relative_to(ROOT)
    except ValueError:
        shown = out_path
    print(f"저장: {shown} ({len(stocks)}종목)")
    if out_path != OUTPUT_PATH:
        print("  (점검용 출력이라 대시보드 데이터는 건드리지 않았습니다)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
