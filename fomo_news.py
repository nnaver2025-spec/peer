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

import html as html_lib
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote

from bs4 import BeautifulSoup
import requests

import fomo_core as core

RSS_URL = (
    "https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"
)
# 네이버 뉴스 검색 API. 스크레이핑은 robots.txt가 전면 금지(`Disallow: /`)하므로
# 공식 API만 쓴다. 하루 25,000회 무료이고 우리 사용량은 하루 300회 남짓이다.
NAVER_URL = "https://openapi.naver.com/v1/search/news.json"
NAVER_ID_ENV = "NAVER_CLIENT_ID"
NAVER_SECRET_ENV = "NAVER_CLIENT_SECRET"
# 한 검색어당 받을 건수. API 최댓값은 100이다.
NAVER_DISPLAY = 100
LOOKBACK_DAYS = 3
TIMEOUT_SEC = 15
MAX_WORKERS = 4      # 구글은 넉넉하지만 예의를 지킨다
# 연결 실패는 재시도한다. 회차 끝(요청 700건 뒤)에 섹터 뉴스 14개가 전부
# ConnectionError로 죽는 일이 4회차 연속 있었다. 같은 코드가 단독 실행에서는
# 매번 성공했으니 소스 문제가 아니라 그 시점의 연결 상태였다. 지수 뉴스는 회차
# 시작 무렵에 받아 늘 성공했다는 점도 같은 방향을 가리킨다.
RETRY_COUNT = 2
RETRY_SLEEP_SEC = 1.5
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
    provider: str = "google"


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


def _session() -> requests.Session:
    """구글 뉴스 RSS는 표준 requests로 200이 온다.

    cloudscraper를 쓰지 않는다. 그쪽은 내부에서 임시 파일과 JS 인터프리터를 찾는데,
    launchd 환경에서 TMPDIR과 PATH가 달라 세션 생성 자체가 OSError로 죽었다.
    크론 회차에서 뉴스가 통째로 빠지는 원인이었다. 우회가 필요 없는 소스에
    무거운 도구를 쓸 이유도 없다.
    """
    return requests.Session()


def effective_half(title: str) -> str:
    """역접 뒤쪽만 남긴다. 기사 제목의 결론은 뒤에 온다."""
    parts = CONCESSIVE.split(title)
    return parts[-1] if len(parts) > 1 else title


def naver_credentials() -> tuple[str, str] | None:
    """네이버 API 키. 없으면 None이고 호출한 쪽이 그 소스를 건너뛴다.

    키가 없어도 구글만으로 지표가 나와야 한다. 키를 넣는 순간 표본이 늘어나는
    구조로 두어, 발급 전후에 코드를 고칠 일이 없게 한다.
    """
    cid = os.environ.get(NAVER_ID_ENV, "").strip()
    secret = os.environ.get(NAVER_SECRET_ENV, "").strip()
    return (cid, secret) if cid and secret else None


def _clean_naver_title(raw: str) -> str:
    """네이버는 검색어에 <b> 태그를 씌우고 HTML 엔티티를 그대로 준다.

    태그가 남으면 감정 단어 매칭이 어긋나고(`<b>급등</b>`) 제목 기준 중복
    제거도 실패한다.
    """
    return html_lib.unescape(re.sub(r"<[^>]+>", "", raw)).strip()


def fetch_naver(
    query: str,
    session=None,
    lookback_days: int | None = None,
    allow: tuple[str, ...] = (),
) -> tuple[list[NewsItem], str | None]:
    """네이버 뉴스 검색 API로 최근 기사를 받는다.

    구글 RSS와 같은 `NewsItem`을 돌려주므로 호출한 쪽에서 두 소스를 그냥 합칠 수
    있다. 키가 없으면 빈 목록과 None을 준다(오류가 아니라 비활성이다).

    `when:3d` 같은 기간 문법이 없어서 `sort=date`로 최신순을 받은 뒤 직접 자른다.
    """
    creds = naver_credentials()
    if creds is None:
        return [], None

    cid, secret = creds
    days = lookback_days or LOOKBACK_DAYS
    own = session or _session()
    res = None
    last_error = None
    for attempt in range(RETRY_COUNT + 1):
        try:
            res = own.get(
                NAVER_URL,
                params={"query": query, "display": NAVER_DISPLAY, "sort": "date"},
                headers={
                    "X-Naver-Client-Id": cid,
                    "X-Naver-Client-Secret": secret,
                    "User-Agent": core.UA,
                },
                timeout=TIMEOUT_SEC,
            )
            if res.status_code == 200:
                break
            last_error = f"HTTP {res.status_code}"
            res = None
        except Exception as exc:                  # noqa: BLE001 - 네트워크 사정은 다양하다
            last_error = type(exc).__name__
            res = None
        if attempt < RETRY_COUNT:
            time.sleep(RETRY_SLEEP_SEC * (attempt + 1))

    if res is None:
        return [], last_error or "실패"

    try:
        rows = res.json().get("items", [])
    except ValueError:
        return [], "JSON 아님"

    cutoff = datetime.now(timezone.utc) - timedelta(days=days + 1)
    items: list[NewsItem] = []
    for row in rows:
        title = _clean_naver_title(row.get("title", ""))
        if not title:
            continue
        if allow and not any(word in title for word in allow):
            continue
        published = None
        if row.get("pubDate"):
            try:
                published = parsedate_to_datetime(row["pubDate"])
            except (TypeError, ValueError):
                published = None
        if published and published < cutoff:
            continue
        positive, negative = match_words(title)
        items.append(
            NewsItem(
                title=title,
                # originallink는 언론사 원문이고 link는 네이버 중계다. 원문을 쓴다.
                url=row.get("originallink") or row.get("link"),
                source=_source_of(row.get("originallink") or ""),
                published=published,
                positive=positive,
                negative=negative,
                provider="naver",
            )
        )
    return items, None


def _source_of(url: str) -> str:
    """언론사 표기. 네이버 API는 매체명을 주지 않아 도메인으로 대신한다."""
    m = re.match(r"https?://(?:www\.)?([^/]+)", url)
    return m.group(1) if m else ""


def _dedupe_key(title: str) -> str:
    """두 소스가 같은 기사를 조금씩 다르게 준다.

    구글 RSS는 제목 끝에 ` - 매체명`을 붙이고 네이버는 붙이지 않는다. 공백과
    따옴표, 줄임표 표기도 갈린다(`급등세...`와 `급등세…`). 그대로 비교하면 같은
    기사가 두 번 세어져 논조가 부풀려진다.
    """
    core_title = re.split(r"\s+-\s+[^-]+$", title)[0]
    # 문장부호를 전부 지워 표기 차이를 흡수한다. 남는 건 글자와 숫자다.
    return re.sub(r"[^0-9A-Za-z가-힣]+", "", core_title)


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


def fetch_sector(
    sector: str,
    session=None,
    suffix: str = "주가",
    lookback_days: int | None = None,
    allow: tuple[str, ...] = (),
) -> tuple[list[NewsItem], str | None]:
    """검색어 하나의 최근 기사를 받는다. 실패하면 빈 목록과 이유를 돌려준다.

    `suffix`로 검색어 꼬리를 바꾼다. 섹터는 `반도체 주가`가 맞지만 지수는
    `코스닥 지수`가 훨씬 낫다(실측: 코스닥 태그 49 -> 69, S&P500 24 -> 63).
    `주가`를 붙이면 개별 종목 기사가 섞이고 S&P500은 44건까지 줄었다.

    `allow`가 있으면 제목에 그 단어가 있는 기사만 남긴다. 구글 뉴스는 검색어를
    한 덩어리로 보고 관련도 순으로 돌려주므로, 걸러내지 않으면 섹터와 무관한
    기사가 섞인다(실측: `광통신 주가` 27건 중 13건이 무관, 바이오 종목인
    펩트론과 뉴욕증시 지수 기사까지 들어왔다).
    """
    days = lookback_days or LOOKBACK_DAYS
    query = quote(f"{sector} {suffix} when:{days}d")
    res = None
    last_error = None
    for attempt in range(RETRY_COUNT + 1):
        try:
            # 세션 생성도 실패할 수 있다. cloudscraper는 내부적으로 임시 파일과
            # JS 인터프리터를 찾는데, launchd 환경에서는 TMPDIR과 PATH가 달라
            # OSError가 났다. try 안에 두어 이 회차만 건너뛰게 한다.
            own = session or _session()
            res = own.get(
                RSS_URL.format(query=query),
                headers={"User-Agent": core.UA},
                timeout=TIMEOUT_SEC,
            )
            if res.status_code == 200:
                break
            last_error = f"HTTP {res.status_code}"
            res = None
        except Exception as exc:                  # noqa: BLE001 - 네트워크 사정은 다양하다
            last_error = type(exc).__name__
            res = None
        if attempt < RETRY_COUNT:
            time.sleep(RETRY_SLEEP_SEC * (attempt + 1))

    if res is None:
        return [], last_error or "실패"

    cutoff = datetime.now(timezone.utc) - timedelta(days=days + 1)
    items: list[NewsItem] = []
    for node in BeautifulSoup(res.text, "xml").find_all("item")[:PER_SECTOR_LIMIT]:
        title = (node.title.text if node.title else "").strip()
        if not title:
            continue
        # 섹터 어휘에 걸리지 않는 기사는 버린다. 점수는 제목 단어를 세어 내므로
        # 무관한 기사가 섞이면 그 섹터 논조가 곧바로 왜곡된다.
        if allow and not any(word in title for word in allow):
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


# 검색어를 섹터 실체에 맞게 바꾼다.
#
# 그룹 이름이 곧 좋은 검색어는 아니다. `AI인프라 주가`는 미국 AI 종목 기사만
# 돌려줬는데(49건 중 우리 종목 관련 2건), 이 섹터의 실제 구성은 변압기·전력기기,
# EPC 건설, 원전, 신재생이다. 검색어를 국내 테마어로 바꿔 표본을 되찾는다.
SECTOR_QUERIES: dict[str, tuple[str, ...]] = {
    "AI인프라": ("전력기기", "원전", "건설사", "신재생에너지"),
    # `IP 주가`는 게임 IP와 International Paper까지 끌어온다. 이 섹터의 구성은
    # 하이브·에스엠·JYP 같은 엔터와 콘텐츠 제작사다.
    "IP": ("엔터주", "K팝", "콘텐츠주"),
}


# 섹터를 가리키는 고유 어휘. 종목명만으로는 부족한 경우를 메운다.
#
# 구글 뉴스가 `광통신 주가`를 한 덩어리로 보고 관련도 순으로 돌려주기 때문에
# 걸러내지 않으면 섹터와 무관한 기사가 그 섹터 논조에 그대로 반영된다.
# 종목명(구성 종목)과 아래 어휘 중 하나라도 제목에 있어야 통과시킨다.
SECTOR_WORDS: dict[str, tuple[str, ...]] = {
    "반도체": ("반도체", "메모리", "DRAM", "D램", "낸드", "NAND", "HBM", "파운드리", "웨이퍼"),
    "AI인프라": ("전력", "변압기", "송전", "원전", "데이터센터", "전선", "케이블", "발전"),
    "광통신": ("광통신", "광케이블", "트랜시버", "네트워크 장비", "통신장비", "광모듈"),
    "조선": ("조선", "선박", "수주", "해운", "LNG선", "컨테이너선", "엔진"),
    "방산": ("방산", "무기", "미사일", "전투기", "장갑차", "군수", "국방"),
    "로봇": ("로봇", "협동로봇", "자동화", "감속기", "액추에이터"),
    "우주": ("우주", "위성", "발사체", "로켓", "항공우주"),
    "화학": ("화학", "배터리", "이차전지", "2차전지", "양극재", "음극재", "정유", "석유"),
    "화장품": ("화장품", "뷰티", "ODM", "스킨", "코스메틱"),
    "식품": ("식품", "라면", "제과", "음료", "건강기능식품"),
    "IP": ("엔터", "아이돌", "콘텐츠", "드라마", "웹툰", "공연", "음반"),
    "기계": ("건설기계", "굴착기", "농기계", "공작기계", "기계"),
    "증권": ("증권", "은행", "금융지주", "보험", "카드"),
    "지주": ("지주", "홀딩스", "그룹"),
}


def sector_allowlist(sector: str, members: tuple[str, ...] = ()) -> tuple[str, ...]:
    """그 섹터 기사로 인정할 어휘. 구성 종목명 + 섹터 고유어."""
    return tuple(dict.fromkeys((*members, *SECTOR_WORDS.get(sector, (sector,)))))


def collect(
    sectors: list[str],
    members: dict[str, tuple[str, ...]] | None = None,
) -> list[SectorNews]:
    """섹터 목록을 병렬로 받는다. 한 섹터가 막혀도 나머지는 진행한다.

    `members`로 섹터별 구성 종목명을 넘기면 그 이름이 제목에 있는 기사도
    통과시킨다. 종목 기사가 섹터 논조의 실제 근거이므로 함께 남긴다.
    """
    names = members or {}

    def one(sector: str) -> SectorNews:
        allow = sector_allowlist(sector, names.get(sector, ()))
        queries = SECTOR_QUERIES.get(sector, (sector,))
        merged: list[NewsItem] = []
        seen: set[str] = set()
        error = None
        for query in queries:
            # 구글 RSS와 네이버 API를 함께 받는다. 네이버 키가 없으면 그 소스만
            # 조용히 비고 구글 결과로 지표가 나온다.
            for items, err in (
                fetch_sector(query, allow=allow),
                fetch_naver(f"{query} 주가", allow=allow),
            ):
                error = error or err
                for item in items:
                    # 검색어가 여럿이고 소스도 둘이라 같은 기사가 겹친다.
                    key = _dedupe_key(item.title)
                    if key in seen:
                        continue
                    seen.add(key)
                    merged.append(item)
        # 하나라도 받았으면 성공으로 본다. 일부 검색어만 막히는 경우가 있다.
        return summarize(sector, merged, None if merged else error)

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        return list(pool.map(one, sectors))


def index_tone(label: str, lookback_days: int) -> SectorNews:
    """지수 하나의 뉴스 논조. 커뮤니티 표본이 얇은 지수를 보완한다.

    커뮤니티에서 지수를 지수로 이야기하는 양이 지수마다 크게 다르다. 코스닥은
    3일치 히트가 11회로 하한(20)에 못 미쳤고, 페이지·기간·별칭을 다 늘려봐도
    15회가 한계였다. 미태그 제목 697건을 읽어보니 `나스닥 선물 현황`,
    `코스피 예상 ㅋㅋㅋ`처럼 감정 판정이 불가능한 글이 대부분이었다.

    뉴스는 같은 지수에서 태그가 훨씬 많이 잡힌다(실측 `지수` 검색 기준).

    | 지수 | 커뮤니티 히트 | 뉴스 히트 |
    |---|---|---|
    | 코스피 | 68 | 73 |
    | 코스닥 | 11 | 58 |
    | S&P500 | 4 | 28 |
    | 나스닥 | 63 | 55 |
    """
    items, error = fetch_sector(label, suffix="지수", lookback_days=lookback_days)
    return summarize(label, items, error)


def collect_indices(specs: list[tuple[str, int]]) -> dict[str, SectorNews]:
    """지수별 뉴스 논조를 병렬로 받는다. specs는 (라벨, 기간) 목록이다."""

    def one(spec: tuple[str, int]) -> tuple[str, SectorNews]:
        label, days = spec
        return label, index_tone(label, days)

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        return dict(pool.map(one, specs))


def tone_payload(result: SectorNews) -> dict:
    """지수 카드에 넣을 뉴스 논조 요약."""
    tagged = [i for i in result.items if i.side]
    positive = [i for i in tagged if i.side == "positive"]
    negative = [i for i in tagged if i.side == "negative"]
    for group in (positive, negative):
        group.sort(
            key=lambda i: i.published or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
    return {
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


def _item_payload(item: NewsItem) -> dict:
    return {
        "title": item.title,
        "url": item.url,
        "source": item.source,
        "provider": item.provider,
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
