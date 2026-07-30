"""섹터별 뉴스 논조. 구글 뉴스 RSS에서 제목을 받아 긍정/부정으로 나눈다.

커뮤니티 여론과 나란히 두려고 만들었다. 성격이 다른 표본이라 점수를 섞지 않는다.
커뮤니티는 사람들이 무슨 말을 하는지, 뉴스는 매체가 어떻게 쓰는지 말해준다.

**왜 구글 뉴스 RSS인가.** 실측에서 한국어 검색 한 번에 100건까지 돌려주고 언론사도
연합인포맥스, 조선일보, 머니투데이, YTN처럼 실제 매체였다. 네이버 금융 뉴스(200),
한경 RSS(200), 매경 RSS(200)도 열리지만 섹터별 검색이 안 되거나 건수가 적다.
이데일리 RSS는 SSL 오류였다.

**감정 태그가 커뮤니티보다 잘 잡힌다.** 에펨 인기글은 7%인데 뉴스는 41~53%다.
기사 제목은 `SK하이닉스 주가 폭락`처럼 방향을 명시하고 조롱·반어가 거의 없다.

**검색어는 섹터 이름을 쓴다.** 대표주 이름으로 검색하면 표본이 3~9건으로 말라
종목 점수와 같은 문제가 재발한다. 실측 비교(3일 기준):

| 섹터 | 이름 검색 | 대표주 검색 |
|---|---|---|
| 기계 | 56건 | 5건 |
| IP | 50건 | 9건 |
| 식품 | 65건 | 3건 |

**`when:3d`가 없으면 못 쓴다.** 날짜 필터를 빼면 기사 나이 중위가 190일, 최대
1686일이었다. 2021년 기사가 오늘 여론으로 섞인다. 붙이면 중위 1일로 정리된다.
"""

from __future__ import annotations

import re
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote

import cloudscraper
from bs4 import BeautifulSoup

import fomo_core as core

RSS_URL = (
    "https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"
)
LOOKBACK_DAYS = 3
TIMEOUT_SEC = 15
MAX_WORKERS = 4      # 구글은 넉넉하지만 예의를 지킨다
PER_SECTOR_LIMIT = 100
# 화면에 남길 섹터별 기사 수. 긍정/부정 각각 이만큼까지 담는다.
EVIDENCE_PER_SIDE = 10
# 점수를 내려면 이만큼은 태그돼야 한다. 커뮤니티(MIN_SENTIMENT_HITS=10)와 같은 원칙.
MIN_HITS = 8


# 기사 제목에서 실제로 쓰이는 방향 어휘. 787건을 세어 빈도가 확인된 것만 넣었다.
#
# 커뮤니티 사전과 분리한 이유: 기사체와 커뮤니티 말투가 다르다. `가즈아`는 기사에
# 안 나오고 `목표주가 하향`은 커뮤니티에 안 나온다. 한 사전에 섞으면 어느 표본에서
# 온 신호인지 알 수 없다.
POSITIVE_WORDS = (
    "상승", "강세", "급등", "반등", "신고가", "상한가", "호재", "훈풍",
    "호실적", "최대실적", "어닝 서프라이즈", "실적 호조", "목표가 상향",
    "목표주가 상향", "기대감", "순매수", "랠리", "수혜", "흑자",
)
NEGATIVE_WORDS = (
    "하락", "급락", "폭락", "약세", "하한가", "악재", "고점", "부진",
    "하방", "쇼크", "위축", "실망", "주춤", "적자", "한파", "비명",
    "목표가 하향", "목표주가 하향", "어닝쇼크", "실적 부진", "순매도",
    "손실", "우려",
)

# 후보에서 뺀 말들(실측 근거):
#   조정  - `목표가 하향 조정`(부정)과 `밸류에이션 조정`(중립)에 함께 쓰인다
#   돌파  - `15만원 돌파`(긍정)와 `돌파구 못 찾는`(부정)에 함께 쓰인다
#   리스크 - `리스크에도 불구하고 저평가`처럼 역접에 묻힌다
#   회복  - `실적 회복 기대`와 `회복 어려워`에 함께 쓰인다
#   저평가 - 기사에서는 대개 `저평가 매수 기회`(긍정)지만 `저평가 상태일까`처럼
#            의문형이 많아 방향이 흐리다
#   성장  - `성장 기대`와 `성장주 고평가 시대 끝나나`에 함께 쓰인다

# 앞말을 뒤집는 역접. `어닝 서프라이즈에도 목표가 하향`이 실측에서 9건 중 3건이라
# 그대로 세면 긍정과 부정이 동시에 잡혀 서로 상쇄된다. 뒤에 오는 판단이 기사의
# 결론이므로 역접 앞부분을 버린다.
CONCESSIVE = re.compile(r"(?:에도|에 도|지만|however|하고도|고도)\s*")

# 호재를 무력화하는 표현. `실적 호재도 소용 없다`는 역접 어미가 없어 위 규칙으로는
# 안 걸리는데, 긍정어 뒤에 이런 말이 붙으면 기사 논조는 부정이다.
NULLIFIED = re.compile(
    r"(?:소용\s*없|무색|안 통|안통|못 막|무의미|힘 못|힘못|먹히지 않|통하지 않)"
)


@dataclass
class NewsItem:
    title: str
    url: str | None
    source: str          # 언론사
    published: datetime | None
    positive: list[str] = field(default_factory=list)
    negative: list[str] = field(default_factory=list)

    @property
    def side(self) -> str | None:
        if not self.positive and not self.negative:
            return None
        return "positive" if len(self.positive) > len(self.negative) else "negative"


@dataclass
class SectorNews(object):
    sector: str
    total: int
    positive_total: int
    negative_total: int
    score: float | None
    zone: str | None
    label: str
    positive_counts: dict[str, int]
    negative_counts: dict[str, int]
    items: list[NewsItem]
    error: str | None = None


def _session() -> cloudscraper.CloudScraper:
    return cloudscraper.create_scraper()


def effective_half(title: str) -> str:
    """역접 뒤쪽만 남긴다. 기사 제목의 결론은 뒤에 온다."""
    parts = CONCESSIVE.split(title)
    return parts[-1] if len(parts) > 1 else title


def match_words(title: str) -> tuple[list[str], list[str]]:
    """제목에서 긍정/부정 어휘를 찾는다.

    역접이 있으면 뒤쪽만 본다. `어닝 서프라이즈에도 목표가 하향`은 부정 기사다.
    """
    text = effective_half(title)
    positive = [w for w in POSITIVE_WORDS if w in text]
    negative = [w for w in NEGATIVE_WORDS if w in text]
    # `실적 호재도 소용 없다`처럼 호재를 무력화하는 말이 붙으면 긍정이 아니다.
    if positive and NULLIFIED.search(text):
        positive = []
    return positive, negative


def _count(titles: list[str], words: tuple[str, ...]) -> tuple[int, dict[str, int]]:
    """어휘별 출현 횟수. match_words와 같은 규칙을 써야 목록과 점수가 어긋나지 않는다."""
    positive_side = words is POSITIVE_WORDS
    counts: dict[str, int] = {}
    for title in titles:
        text = effective_half(title)
        if positive_side and NULLIFIED.search(text):
            continue
        for word in words:
            hits = text.count(word)
            if hits:
                counts[word] = counts.get(word, 0) + hits
    ordered = dict(sorted(counts.items(), key=lambda kv: -kv[1]))
    return sum(ordered.values()), ordered


def fetch_sector(sector: str, session=None) -> tuple[list[NewsItem], str | None]:
    """섹터 하나의 최근 기사를 받는다. 실패하면 빈 목록과 이유를 돌려준다."""
    own = session or _session()
    query = quote(f"{sector} 주가 when:{LOOKBACK_DAYS}d")
    try:
        res = own.get(
            RSS_URL.format(query=query),
            headers={"User-Agent": core.UA},
            timeout=TIMEOUT_SEC,
        )
        if res.status_code != 200:
            return [], f"HTTP {res.status_code}"
    except Exception as exc:                      # noqa: BLE001 - 네트워크 사정은 다양하다
        return [], type(exc).__name__

    cutoff = datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS + 1)
    items: list[NewsItem] = []
    for node in BeautifulSoup(res.text, "xml").find_all("item")[:PER_SECTOR_LIMIT]:
        title = (node.title.text if node.title else "").strip()
        if not title:
            continue
        published = None
        if node.pubDate:
            try:
                published = parsedate_to_datetime(node.pubDate.text)
            except (TypeError, ValueError):
                published = None
        # when:3d를 이미 걸었지만 응답에 오래된 기사가 섞이는 경우가 있어 한 번 더 본다.
        if published and published < cutoff:
            continue
        source = node.find("source")
        positive, negative = match_words(title)
        items.append(
            NewsItem(
                title=title,
                url=node.link.text if node.link else None,
                source=source.text if source else "",
                published=published,
                positive=positive,
                negative=negative,
            )
        )
    return items, None


def summarize(sector: str, items: list[NewsItem], error: str | None = None) -> SectorNews:
    """섹터 기사 목록을 점수까지 계산한 요약으로 바꾼다."""
    titles = [i.title for i in items]
    pos_total, pos_counts = _count(titles, POSITIVE_WORDS)
    neg_total, neg_counts = _count(titles, NEGATIVE_WORDS)

    hits = pos_total + neg_total
    if hits < MIN_HITS:
        score, zone, label = None, None, "표본 부족"
    else:
        score = core.sentiment_score(pos_total, neg_total)
        zone, label = core.interpret(score) if score is not None else (None, "표본 부족")

    return SectorNews(
        sector=sector,
        total=len(items),
        positive_total=pos_total,
        negative_total=neg_total,
        score=score,
        zone=zone,
        label=label,
        positive_counts=pos_counts,
        negative_counts=neg_counts,
        items=items,
        error=error,
    )


def collect(sectors: list[str]) -> list[SectorNews]:
    """섹터 목록을 병렬로 받는다. 한 섹터가 막혀도 나머지는 진행한다."""

    def one(sector: str) -> SectorNews:
        items, error = fetch_sector(sector)
        return summarize(sector, items, error)

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        return list(pool.map(one, sectors))


def _item_payload(item: NewsItem) -> dict:
    return {
        "title": item.title,
        "url": item.url,
        "source": item.source,
        "published": item.published.isoformat() if item.published else None,
        "positive": item.positive,
        "negative": item.negative,
    }


def payload(results: list[SectorNews]) -> dict:
    """대시보드 JSON에 넣을 형태로 바꾼다.

    기사는 긍정/부정을 따로 담는다. 화면에서 두 열로 나눠 보여주기 때문이다.
    태그가 없는 기사는 담지 않는다. 뉴스는 태그율이 41~53%라 태그된 것만으로도
    충분하고, 방향이 없는 기사까지 담으면 목록이 길어진다(커뮤니티 피드와 다르다).
    """
    sectors = []
    for result in results:
        tagged = [i for i in result.items if i.side]
        positive = [i for i in tagged if i.side == "positive"]
        negative = [i for i in tagged if i.side == "negative"]
        # 최신 기사가 먼저 오게 한다. 뉴스는 반응 수치가 없어 시간이 유일한 순서다.
        for group in (positive, negative):
            group.sort(key=lambda i: i.published or datetime.min.replace(tzinfo=timezone.utc), reverse=True)

        sectors.append(
            {
                "sector": result.sector,
                "total": result.total,
                "hits": result.positive_total + result.negative_total,
                "positive_total": result.positive_total,
                "negative_total": result.negative_total,
                "score": result.score,
                "zone": result.zone,
                "label": result.label,
                "positive_counts": result.positive_counts,
                "negative_counts": result.negative_counts,
                "positive": [_item_payload(i) for i in positive[:EVIDENCE_PER_SIDE]],
                "negative": [_item_payload(i) for i in negative[:EVIDENCE_PER_SIDE]],
                "error": result.error,
            }
        )

    ok = [s for s in sectors if not s["error"]]
    pos = sum(s["positive_total"] for s in ok)
    neg = sum(s["negative_total"] for s in ok)
    overall = core.sentiment_score(pos, neg) if pos + neg >= MIN_HITS else None
    zone, label = core.interpret(overall) if overall is not None else (None, "표본 부족")

    return {
        "lookback_days": LOOKBACK_DAYS,
        "min_hits": MIN_HITS,
        "score": overall,
        "zone": zone,
        "label": label,
        "positive_total": pos,
        "negative_total": neg,
        "total": sum(s["total"] for s in ok),
        "sectors": sectors,
    }
