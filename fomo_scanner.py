"""종목 하나의 커뮤니티 여론을 훑어 FOMO 지표를 콘솔에 출력한다.

    python fomo_scanner.py 삼성전자
    python fomo_scanner.py 한화에어로스페이스

한 사이트가 막혀도 나머지로 계산을 진행한다. 전부 실패하면 종료 코드 1로 끝나므로
크론에서 실패를 감지할 수 있다.
"""

from __future__ import annotations

import sys
import unicodedata

import fomo_core as core
from fomo_indices import INDICES, index_levels

RULE_WIDTH = 43
LABEL_WIDTH = 32        # 소스 이름 열의 표시 폭. 가장 긴 이름보다 넉넉히 둔다.
TOP_KEYWORDS = 6        # 키워드 분석에 나열할 상위 개수
GAUGE_INDENT = 2
EVIDENCE_LINES = 8      # 근거로 보여줄 게시글 수


def display_width(text: str) -> int:
    """터미널 표시 폭. 한글과 이모지는 두 칸을 차지한다.

    len()으로 패딩하면 한글이 섞인 열이 어긋난다.
    """
    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in text)


def pad(text: str, width: int) -> str:
    return text + " " * max(0, width - display_width(text))


def format_counts(counts: dict[str, int]) -> str:
    items = list(counts.items())[:TOP_KEYWORDS]
    return " ".join(f"{word}({n})" for word, n in items) if items else "없음"


def render(report: core.FomoReport, index=None) -> str:
    lines: list[str] = []
    rule = "═" * RULE_WIDTH
    title = report.keyword
    if report.ticker:
        title = f"{title} ({report.ticker})"

    lines.append(rule)
    lines.append(f"통합 공포탐욕(FOMO) 지표 — {title}")
    lines.append(rule)
    if index is not None:
        lines.append(f"검색어: {' / '.join(index.aliases)}")
    lines.append("")
    lines.append("[수집 결과]")

    for result in report.results:
        if result.error:
            lines.append(f"  ⚠️ {pad(result.label, LABEL_WIDTH)}{result.error} (skip)")
        else:
            lines.append(f"  ✅ {pad(result.label, LABEL_WIDTH)}{result.count}개")

    lines.append("  " + "─" * 35)
    lines.append(f"  총 수집: {report.total_posts}개 게시글")
    lines.append("")

    stats = report.stats
    lines.append("[키워드 분석]")
    lines.append(f"  😈 탐욕 키워드: {stats.greed_total}회")
    lines.append(f"     - {format_counts(stats.greed_counts)}")
    lines.append(f"  👻 공포 키워드: {stats.fear_total}회")
    lines.append(f"     - {format_counts(stats.fear_counts)}")
    lines.append("")

    lines.append("[최종 지표]")
    lines.append(f"  FOMO 점수: {report.score} / 100 ({report.label})")
    bar = core.gauge(report.score)
    lines.append(" " * GAUGE_INDENT + bar)
    # 눈금 양끝(0, 100) 아래에 방향 라벨을 붙인다.
    tail = display_width(bar) - display_width("공포") - display_width("탐욕")
    lines.append(" " * GAUGE_INDENT + "공포" + " " * max(1, tail) + "탐욕")

    # 게시글 수로 나눈 점수는 대개 50에 붙는다. 키워드 표본만으로 계산한 심리를
    # 함께 보여줘야 실제로 어느 쪽으로 기울었는지 읽힌다.
    sentiment = core.sentiment_score(stats.greed_total, stats.fear_total)
    lines.append("")
    if sentiment is None:
        lines.append(
            f"  키워드 심리: 표본 부족 ({stats.greed_total + stats.fear_total}"
            f"/{core.MIN_SENTIMENT_HITS}회)"
        )
    else:
        lines.append(
            f"  키워드 심리: {sentiment} / 100 ({core.interpret(sentiment)[1]})"
            f"  ← 키워드 {stats.greed_total + stats.fear_total}회 기준"
        )

    # 점수만 보여주면 근거를 확인할 길이 없다. 키워드가 실제로 잡힌 글을 링크와 함께 남긴다.
    evidence = report.evidence(EVIDENCE_LINES)
    if evidence:
        lines.append("")
        lines.append("[점수를 만든 글]")
        for item in evidence:
            mark = "😈" if len(item["greed"]) >= len(item["fear"]) else "👻"
            words = ",".join(item["greed"] + item["fear"])
            lines.append(f"  {mark} {item['title'][:52]}  [{words}]")
            if item["url"]:
                lines.append(f"     {item['url']}")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    if len(argv) < 2 or not argv[1].strip():
        print("사용법: python fomo_scanner.py <종목명>", file=sys.stderr)
        print("  예) python fomo_scanner.py 삼성전자", file=sys.stderr)
        names = " / ".join(i.label for i in INDICES)
        print(f"  지수) {names}", file=sys.stderr)
        return 2

    keyword = argv[1].strip()

    # 지수는 부르는 말이 갈려서 별칭을 묶어 검색한다. S&P500만 검색하면 `에센피`,
    # `SPY`로 오가는 글을 모두 놓친다.
    index = next(
        (i for i in INDICES if keyword in (i.label, *i.aliases, i.key)), None
    )
    if index is not None:
        # 현재 지수를 알아야 `코스피 4천 가즈아`가 기대인지 조롱인지 갈린다.
        level = index_levels().get(index.key)
        report = core.analyze(
            core.scan_aliases(index.label, list(index.aliases)), current_level=level
        )
    else:
        report = core.analyze(core.scan(keyword))

    if all(r.error for r in report.results):
        print(f"[실패] {keyword} — 모든 사이트 수집 실패", file=sys.stderr)
        for result in report.results:
            print(f"  - {result.label}: {result.error}", file=sys.stderr)
        return 1

    print(render(report, index=index))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
