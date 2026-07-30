"""주식 커뮤니티 게시글 제목으로 종목별 공포탐욕(FOMO) 지표를 계산한다.

8개 게시판에서 제목만 모아 탐욕/공포 키워드 출현 빈도로 0~100 점수를 낸다.
50이 중립이고, 탐욕 키워드가 많을수록 100에 가까워진다.

사이트 구조를 아는 파일은 여기 하나뿐이다. 셀렉터가 깨지면 SOURCES만 고치면 된다.
수집은 소스 단위 병렬이고, 한 소스 안의 페이지는 같은 도메인을 연속으로 두드리지
않도록 순차로 돈다.
"""

from __future__ import annotations

import json
import re
import threading
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from itertools import zip_longest
from pathlib import Path
from urllib.parse import quote, urljoin, urlsplit

import cloudscraper
import requests
from bs4 import BeautifulSoup

# 게시판 목록은 데스크톱 크롬으로 들어온 사람만 온전히 받는다.
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)
BASE_HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8",
}

PAGE_SLEEP_SEC = 0.3     # 같은 도메인 연속 호출 간격
REQUEST_TIMEOUT = 15     # 페이지 요청 타임아웃
MAX_WORKERS = 8          # 소스 수와 같게 둔다
RETRY_SLEEP_SEC = 1.5    # 일시 차단 재시도 간 대기
MAX_RETRIES = 2          # 첫 시도 외 추가 시도 횟수

# 수집 기간. 페이지 수만 정하면 소스마다 시간 폭이 제멋대로다. 실측에서 디시는
# 2페이지가 반나절인데 아카라이브는 2페이지가 6년치였고(2020년 글 포함), S&P500
# 표본의 64%가 아카라이브였다. 6년 전 여론이 지금 지표에 같은 무게로 들어가면
# 지표가 아니다. 날짜로 잘라 소스 간 시간 축을 맞춘다.
LOOKBACK_DAYS = 3

# 서버가 잠깐 밀어내는 응답들. 에펨은 요청이 몰리면 자체 보안 페이지로 430을 준다.
TRANSIENT_STATUS = frozenset({429, 430, 503})

# 도메인별 최소 요청 간격(초). 감시 모드는 종목 수십 개를 연달아 돌기 때문에
# 한 종목 안에서 예의를 지켜도 도메인 누적 요청이 임계를 넘는다. 실제로 30종목을
# 돌렸을 때 에펨이 26종목에서 430을 돌려줬다. 프로세스 전체에 걸쳐 간격을 지킨다.
DOMAIN_MIN_INTERVAL = {
    # 에펨은 브라우저 쿠키를 붙이면 통과한다. 실측에서 0.8초 간격 68회 연속 성공.
    # 쿠키 없이 두드릴 때는 8초를 줘도 막혔으니, 간격보다 쿠키가 관문이었다.
    "www.fmkorea.com": 1.0,
    "www.ppomppu.co.kr": 1.0,
    "gall.dcinside.com": 0.5,
    "arca.live": 0.5,
}
DEFAULT_MIN_INTERVAL = 0.0

# 한 소스가 이만큼 연달아 실패하면 남은 종목에서는 요청하지 않는다. 차단된 사이트를
# 계속 두드리면 차단이 길어지고, 스캔 시간만 늘어난다.
CIRCUIT_TRIP_FAILURES = 3

# 집계 심리를 신뢰하는 최소 키워드 표본. 키워드 1~2개로 0점이나 100점이 찍히는 것은
# 신호가 아니라 잡음이다. 이 값을 못 넘기면 점수 대신 "표본 부족"으로 표시한다.
MIN_SENTIMENT_HITS = 10

# 반응(조회수/추천수/댓글)으로 게시글 무게를 조절한다. 아무도 안 읽은 글과 수백 명이
# 추천한 글을 같게 세면 여론이 아니라 글쓴 사람 수를 재는 것이 된다.
#
# 절대 임계값은 못 쓴다. 같은 3일치 코스피 표본에서 조회수 중위가 디시 미국주식 46,
# 아카라이브 121, 에펨 204, 뽐뿌 792였다. 스케일이 20배 차이 나서 하나로 자르면
# 한 사이트만 남는다. 그래서 소스별 중위값 대비 배수로 판단한다.
#
# 추천수는 필터로 쓸 수 없다. 디시는 86%가 추천 0이고 뽐뿌·에펨 인기글은 추천 칸이
# 아예 다른 스케일이다. 추천은 무게를 더하는 쪽으로만 쓴다.
HOT_VIEW_RATIO = 3.0     # 소스 중위 조회수의 이 배수를 넘으면 화제글
HOT_VOTE_RATIO = 3.0     # 추천도 같은 기준. 최소 3표는 넘어야 한다
HOT_VOTE_FLOOR = 3
HOT_WEIGHT = 3           # 화제글을 몇 배로 세는지
DEAD_VIEW_RATIO = 0.4    # 중위의 이 비율 미만이고 반응이 전혀 없으면 제외
SCALE_MIN_SAMPLE = 8     # 중위값을 신뢰할 최소 표본

_throttle_lock = threading.Lock()
_last_request_at: dict[str, float] = {}

_circuit_lock = threading.Lock()
_consecutive_failures: dict[str, int] = {}


def circuit_open(source_key: str) -> bool:
    """차단으로 판단해 요청을 멈춘 상태인지."""
    with _circuit_lock:
        return _consecutive_failures.get(source_key, 0) >= CIRCUIT_TRIP_FAILURES


def record_outcome(source_key: str, ok: bool) -> None:
    """연속 실패를 센다. 한 번이라도 성공하면 초기화한다."""
    with _circuit_lock:
        if ok:
            _consecutive_failures[source_key] = 0
        else:
            _consecutive_failures[source_key] = _consecutive_failures.get(source_key, 0) + 1


def reset_circuits() -> None:
    """회차 경계에서 상태를 비운다."""
    with _circuit_lock:
        _consecutive_failures.clear()


def _throttle(url: str) -> None:
    """같은 도메인에 대한 연속 요청 사이에 최소 간격을 강제한다.

    소스를 병렬로 돌기 때문에 대기 계산과 기록을 한 락 안에서 처리한다. 락을 쥔 채
    자는 건 의도한 동작이다. 같은 도메인을 노리는 다른 스레드도 함께 밀려야 간격이
    지켜진다.
    """
    host = urlsplit(url).hostname or ""
    interval = DOMAIN_MIN_INTERVAL.get(host, DEFAULT_MIN_INTERVAL)
    if not interval:
        return

    with _throttle_lock:
        wait = interval - (time.monotonic() - _last_request_at.get(host, 0.0))
        if wait > 0:
            time.sleep(wait)
        _last_request_at[host] = time.monotonic()

# 키워드는 그 말 자체로 방향이 정해지는 것만 쓴다.
#
# `간다`, `진입`, `사도`는 처음 사전에 있었지만 빼냈다. 방향을 담고 있지 않아서다.
# 실제 수집 데이터에서 `간다` 33건 중 "10만원 아래 간다", "50간다", "코스피 5000
# 간다"(9000에서 내려온 조롱)처럼 하락을 뜻하는 사례가 절반이었고, `진입` 19건 중
# 절반은 "손실 구간 진입", "조정 국면 진입"이었다. 두 방향에 같은 빈도로 쓰이는 말은
# 세어도 신호가 아니라 잡음만 늘린다. 세 키워드가 전체 탐욕의 54%를 차지했으니
# 지표를 왜곡하는 규모도 작지 않았다.
# 은어만으로는 표본이 안 채워진다. 실제 760개 제목을 세어보니 `가즈아`/`떡상` 같은
# 커뮤니티 은어는 0~1회인데 `반등`(15) `상승`(14) `폭락`(13) `급락`(8)처럼 평범한
# 시장 어휘가 훨씬 많이 쓰였다. 그래서 은어와 일반 어휘를 함께 담는다.
#
# `매수`, `바닥`, `조정`은 후보에서 뺐다. "매수 진입 시작"과 "매수 못하겠다",
# "바닥 잡았다"와 "바닥이 안 보인다"처럼 양쪽에 같이 쓰여 방향을 담지 못한다.
GREED_KEYWORDS = (
    # 커뮤니티 은어
    "가즈아", "영차", "풀매수", "떡상", "추매", "불장", "간닷",
    "존버", "물타기", "탑승", "우상향",
    # 방향이 분명한 일반 어휘
    "급등", "반등", "상승", "신고가", "상한가", "익절", "호재",
)
FEAR_KEYWORDS = (
    # 커뮤니티 은어
    "설거지", "돔황챠", "손절", "구조대", "물렸", "나락",
    "곡소리", "반토막", "떡락",
    # 방향이 분명한 일반 어휘
    "고점", "끝났다", "망했다", "하락", "패닉", "청산",
    "폭락", "급락", "약세", "붕괴", "악재", "하한가",
)

# 방향이 분명한 키워드만 남겼어도 부분 문자열 매칭의 한계는 남는다.
# `신고가 경신 실패`처럼 뒤에 붙는 말이 뜻을 뒤집는 경우만 걸러낸다.
NEGATED_PATTERNS = (
    re.compile(r"신고가\s*(?:경신\s*)?(?:실패|못)"),
    re.compile(r"우상향\s*(?:은\s*)?(?:끝|깨졌|무너)"),
    re.compile(r"불장\s*(?:은\s*)?(?:끝|아님|없)"),
)

# 시세 집계를 그대로 옮긴 제목은 여론이 아니다. "상승종목 148개 하락종목 739개"는
# 양쪽 키워드를 다 갖지만 글쓴이의 심리를 담고 있지 않다. 숫자와 함께 두 방향이
# 나란히 나오는 형태만 제외한다.
TALLY_PATTERN = re.compile(
    r"(?:상승|오름)종목\s*\d+.*?(?:하락|내림)종목\s*\d+"
    r"|(?:하락|내림)종목\s*\d+.*?(?:상승|오름)종목\s*\d+"
)


def is_tally(title: str) -> bool:
    """시세 집계 문장인지. 여론 판정에서 제외한다."""
    return bool(TALLY_PATTERN.search(title))


# 자조 표시. 탐욕 표현에 웃음이 붙으면 대개 조롱이다.
# `코스피 5천 가즈아 ㅋㅋㅋㅋㅋ`는 6월 고점 9115에서 33% 내려온 상황의 자조이고,
# `급등장엔 역시 급락이지ㅋㅋ`, `오른다고 영차 하고있네 ㅋㅋㅋ`도 같은 결이다.
# 반대로 공포 표현에 붙는 웃음은 뜻을 뒤집지 않고 오히려 강화한다
# (`3일만에 반토막 ㅋㅋㅋ`, `실시간 나스닥대폭락ㅋㅋㅋ`). 그래서 탐욕에만 적용한다.
SARCASM_PATTERN = re.compile(r"[ㅋㅎ]{2,}|[ㅠㅜ]{2,}|\^\^|하고\s?있네")


def is_sarcastic(title: str) -> bool:
    """탐욕 표현이 조롱으로 쓰였는지."""
    return bool(SARCASM_PATTERN.search(title))


# 사람이 쓴 글이 아닌 자동 알림. 네이버 종목토론실에 봇이 등락률을 찍는데, 탐욕으로
# 분류된 139건 중 24건(17%)이 `5% 이상 상승했어요 🎉` 같은 같은 문장이었다.
# 시세를 옮긴 것이라 여론이 아니고, 한 종목에 여러 번 찍혀 표본을 왜곡한다.
BOT_PATTERNS = (
    re.compile(r"\d+%\s*이상\s*(?:상승|하락|급등|급락)했어요"),
    re.compile(r"^(?:상승|하락)\s*\d+(?:\.\d+)?%$"),
)


def is_bot_post(title: str) -> bool:
    """자동 알림 글인지. 여론 판정에서 제외한다."""
    return any(p.search(title) for p in BOT_PATTERNS)


# 하락을 말하면서 탐욕 단어를 함께 쓰는 문장. `폭락후 소폭반등`, `장초 하락때
# 풀매수했는데`, `급등 급락 반복`처럼 두 방향이 섞이면 어느 쪽이 글쓴이의 심리인지
# 규칙으로 가릴 수 없다. 억지로 한쪽에 넣기보다 판정을 포기하는 편이 정확하다.
_DOWN_CONTEXT = re.compile(
    r"빠지|빠질|하락|폭락|급락|떨어|반토막|손실|나락|물렸|망했|약세|음봉|저점|털렸"
)


def is_mixed_context(title: str) -> bool:
    """탐욕 단어와 하락 문맥이 함께 있는지."""
    return bool(_DOWN_CONTEXT.search(title))


# 기대가 어긋났음을 말하는 어미. `반등할 줄 알았는데`, `상한가 바라신걸까요`처럼
# 탐욕 단어가 들어가도 실제 심리는 실망이다.
_UNFULFILLED = re.compile(r"줄\s*알았|바라신|바랬|기대했는데|하겠지|겠지만|안\s*주")


def is_unfulfilled(title: str) -> bool:
    """탐욕 표현이 어긋난 기대를 말하는지."""
    return bool(_UNFULFILLED.search(title))


# 탐욕 단어를 부정하거나 반대로 쓰는 형태.
# `하한가 가즈아`는 남의 종목을 저격하는 말이고, `가짜 상승`, `호재가 아니야`는
# 부정, `제발 코스닥 반등`은 이미 빠진 뒤의 간청이다.
_INVERTED = re.compile(
    r"하한가\s*(?:가즈아|가자)"
    r"|가짜\s*(?:상승|반등)"
    r"|(?:호재|상승|반등|불장)(?:가|이|은|도)?\s*아(?:니|님)"
    r"|제발"
    r"|척\s*(?:보소|하네|하지)"
)


def is_inverted(title: str) -> bool:
    """탐욕 단어를 부정하거나 반대 뜻으로 쓰는지."""
    return bool(_INVERTED.search(title))


# 제목에 나오는 목표 수치. `코스피 4000`, `4천`, `10만원`, `200,000원`을 잡는다.
_TARGET_NUMBER = re.compile(
    r"(\d[\d,]*(?:\.\d+)?)\s*(만원|천원|만|천|포인트|p|원)?", re.IGNORECASE
)
# 비율이나 수량은 목표 수치가 아니다. `10%빠진`, `445주`, `2주간`은 걸러낸다.
_NOT_A_TARGET = re.compile(r"\d[\d,.]*\s*(?:%|퍼|프로|주|일|개월|년|월|시|분|배)")


def _parse_target(text: str, unit: str | None) -> float | None:
    """제목 속 수치를 실제 값으로. `4천`->4000, `10만원`->100000."""
    try:
        value = float(text.replace(",", ""))
    except ValueError:
        return None
    if unit in ("만원", "만"):
        value *= 10000
    elif unit in ("천원", "천"):
        value *= 1000
    return value


# 목표가 현재보다 이만큼 낮으면 상승 기대가 아니다. 5%는 표현의 헐렁함을 감안한 여유다.
DOWNSIDE_TARGET_RATIO = 0.95

# 지나온 경로를 말하는 어미. `4천에서 2000포인트 오른거다`는 과거 서술이라 목표가
# 아니다. 이걸 구분하지 않으면 상승 서술이 하락 목표로 뒤집힌다.
_PAST_PATH = re.compile(r"오른거|올랐|상승했|올라왔|에서\s*\d|지나|왔다|찍었|기록")


def targets_below_current(title: str, current: float) -> bool:
    """제목의 목표 수치가 현재 수준보다 낮은지.

    `코스피 4000대 가즈아`는 지수가 6053일 때 33% 아래로 내려보내자는 조롱이다.
    같은 문장이 코스피 3000 시절에는 진짜 기대였을 테니, 단어만으로는 가릴 수 없고
    현재 수준과 비교해야 한다.

    제목에 유효한 수치가 여럿이면 하나라도 현재보다 높으면 상승 기대로 본다
    (`4천에서 2000포인트 오른거다`처럼 과거 경로를 말하는 경우).
    """
    if not current or current <= 0:
        return False

    # 과거 경로 서술은 목표 수치가 아니다.
    if _PAST_PATH.search(title):
        return False

    found = False
    for match in _TARGET_NUMBER.finditer(title):
        raw, unit = match.group(1), match.group(2)
        # 비율/수량 표현은 건너뛴다.
        tail = title[match.start() : match.end() + 3]
        if _NOT_A_TARGET.match(tail.strip()):
            continue
        value = _parse_target(raw, unit)
        if value is None:
            continue
        # 현재 수준과 자릿수가 너무 다르면 다른 뜻의 숫자다(연도, 종목코드 등).
        if not (current * 0.1 <= value <= current * 10):
            continue
        found = True
        if value >= current * DOWNSIDE_TARGET_RATIO:
            return False   # 하나라도 현재 이상이면 하락 목표가 아니다
    return found


def greed_is_credible(title: str, current_level: float | None = None) -> bool:
    """제목의 탐욕 단어를 믿을 수 있는지.

    같은 단어라도 문맥이 뒤집으면 탐욕이 아니다. 세 가지를 본다.
    - 자조: `코스피 5천 가즈아 ㅋㅋㅋ`
    - 하락 문맥: `폭락후 소폭반등`, `장초 하락때 풀매수했는데`
    - 어긋난 기대: `오늘은 소폭 반등할 줄 알았는데`
    - 부정과 역설: `하한가 가즈아`, `가짜 상승`, `호재가 아니야`, `제발 코스닥 반등`

    `current_level`을 주면 목표 수치까지 본다. `코스피 4000대 가즈아`는 지수가
    6053일 때 조롱이지만 3000일 때는 진짜 기대다. 숫자를 현재 수준과 비교해야
    가릴 수 있다.

    공포에는 적용하지 않는다. 공포 표현은 이런 문맥에서 뜻이 그대로거나 강해진다.
    """
    if (
        is_sarcastic(title)
        or is_mixed_context(title)
        or is_unfulfilled(title)
        or is_inverted(title)
    ):
        return False
    if current_level and targets_below_current(title, current_level):
        return False
    return True


def _strip_negated(title: str) -> str:
    """반대 뜻으로 쓰인 구간을 지운 제목. 키워드 카운트 전에 적용한다."""
    if is_tally(title):
        return ""
    for pattern in NEGATED_PATTERNS:
        title = pattern.sub(" ", title)
    return title

# (하한, 한글 라벨, JSON용 구간 키). 위에서부터 처음 맞는 구간을 쓴다.
#
# CNN Fear & Greed와 같은 경계를 쓴다(25/45/55/75). 원래 스펙은 중립을 41~60으로
# 뒀는데 그 폭이 20이나 돼서 실제 공포를 중립으로 덮었다. 지수가 18~38이고 섹터
# 13개 중 10개가 45 미만인 상황에서 전체 여론만 42.1로 "중립"이 나왔다.
# 같은 화면에 시장 지표(CNN 경계)가 나란히 있으니 자를 하나로 맞춰야 비교가 된다.
ZONES = (
    (75, "극단적 탐욕", "extreme_greed"),
    (55, "탐욕", "greed"),
    (45, "중립", "neutral"),
    (25, "공포", "fear"),
    (0, "극단적 공포", "extreme_fear"),
)

_CACHE_DIR = Path(__file__).parent / ".cache"
_LISTING_PATH = _CACHE_DIR / "krx_listing.json"
_LISTING_TTL_SEC = 24 * 60 * 60


def _load_listing() -> dict[str, str]:
    """KRX 상장 종목명 -> 6자리 코드 매핑. 24시간 캐시.

    크론이 주기적으로 도는 스크립트라 매번 2800행을 내려받지 않게 캐시한다.
    FinanceDataReader가 없거나 조회가 실패하면 빈 매핑을 돌려주고, 호출한 쪽에서
    네이버 소스만 건너뛴다.
    """
    if _LISTING_PATH.exists():
        age = time.time() - _LISTING_PATH.stat().st_mtime
        if age < _LISTING_TTL_SEC:
            try:
                return json.loads(_LISTING_PATH.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass  # 캐시가 깨졌으면 새로 받는다

    try:
        import FinanceDataReader as fdr

        listing = fdr.StockListing("KRX")
        mapping = {
            str(name): str(code).zfill(6)
            for name, code in zip(listing["Name"], listing["Code"])
            if name and code
        }
    except Exception:
        return {}

    try:
        _CACHE_DIR.mkdir(exist_ok=True)
        _LISTING_PATH.write_text(
            json.dumps(mapping, ensure_ascii=False), encoding="utf-8"
        )
    except OSError:
        pass  # 캐시 쓰기 실패는 치명적이지 않다
    return mapping


def resolve_ticker(name: str) -> str | None:
    """한글 종목명을 네이버 증권용 6자리 코드로 바꾼다. 없으면 None.

    정확 일치 다음 공백 제거 일치까지만 본다. 부분 일치로 추측하면 엉뚱한 종목의
    토론실을 긁게 되고, 그건 수집 실패보다 나쁘다.
    """
    listing = _load_listing()
    if not listing:
        return None

    if name in listing:
        return listing[name]

    squashed = name.replace(" ", "")
    for candidate, code in listing.items():
        if candidate.replace(" ", "") == squashed:
            return code
    return None


@dataclass
class KeywordStats:
    greed_total: int = 0
    fear_total: int = 0
    greed_counts: dict[str, int] = field(default_factory=dict)
    fear_counts: dict[str, int] = field(default_factory=dict)


def _count(titles: list[str], keywords: tuple[str, ...]) -> tuple[int, dict[str, int]]:
    counts: dict[str, int] = {}
    cleaned = [_strip_negated(t) for t in titles]
    for keyword in keywords:
        hits = sum(title.count(keyword) for title in cleaned)
        if hits:
            counts[keyword] = hits
    ordered = dict(sorted(counts.items(), key=lambda kv: -kv[1]))
    return sum(ordered.values()), ordered


def count_keywords(titles: list[str], current_level: float | None = None) -> KeywordStats:
    """제목 목록에서 탐욕/공포 키워드 출현 횟수를 센다.

    한 제목에 같은 키워드가 두 번 나오면 2회로 센다. 반복 자체가 강도를 담고 있다.
    """
    # match_keywords와 같은 규칙을 써야 근거 목록과 점수가 어긋나지 않는다.
    usable = [t for t in titles if not is_bot_post(t)]
    # 탐욕은 문맥이 뒤집지 않은 제목에서만 센다. 공포는 그대로 센다.
    greed_total, greed_counts = _count(
        [t for t in usable if greed_is_credible(t, current_level)], GREED_KEYWORDS
    )
    fear_total, fear_counts = _count(usable, FEAR_KEYWORDS)
    return KeywordStats(greed_total, fear_total, greed_counts, fear_counts)


def match_keywords(
    title: str, current_level: float | None = None
) -> tuple[list[str], list[str]]:
    """제목에 등장한 탐욕/공포 키워드를 각각 돌려준다."""
    if is_bot_post(title):
        return [], []
    cleaned = _strip_negated(title)
    greed = [k for k in GREED_KEYWORDS if k in cleaned]
    fear = [k for k in FEAR_KEYWORDS if k in cleaned]
    # 문맥이 뒤집은 탐욕 단어는 버린다. 공포 키워드가 같이 있으면 그쪽이 진심이다.
    if greed and not greed_is_credible(title, current_level):
        greed = []
    return greed, fear


def evidence_posts(
    posts: list[Post], limit: int = 12, current_level: float | None = None
) -> list[dict]:
    """점수를 만든 게시글만 골라낸다.

    지표가 "탐욕 우세"라고만 말하면 근거를 확인할 길이 없다. 키워드가 실제로 잡힌
    글을 링크와 함께 남겨 원글로 갈 수 있게 한다. 수집한 글 대부분은 키워드가 없어
    점수에 영향을 주지 않으므로 전부 저장할 이유도 없다.

    한쪽으로 치우친 목록은 오해를 부르므로 탐욕/공포를 번갈아 담는다.

    반응이 많은 글을 먼저 담는다. 점수가 화제글에 무게를 더 주니 근거도 같은 순서로
    보여야 화면과 계산이 어긋나지 않는다.
    """
    greed_side: list[dict] = []
    fear_side: list[dict] = []

    for post in posts:
        greed, fear = match_keywords(post.title, current_level)
        if not greed and not fear:
            continue
        item = {
            "title": post.title,
            "url": post.url,
            "source": post.source,
            "greed": greed,
            "fear": fear,
            "views": post.views,
            "votes": post.votes,
            "comments": post.comments,
        }
        # 양쪽 키워드가 다 있으면 많은 쪽으로 분류한다.
        (greed_side if len(greed) >= len(fear) else fear_side).append(item)

    # 많이 읽히고 추천받은 글이 여론을 대표한다. 반응이 같으면 키워드가 여러 개
    # 잡힌 글이 방향을 더 분명히 말한다.
    for side in (greed_side, fear_side):
        side.sort(key=lambda i: (-_reaction_rank(i), -(len(i["greed"]) + len(i["fear"]))))

    out: list[dict] = []
    for a, b in zip_longest(greed_side, fear_side):
        for item in (a, b):
            if item is not None and len(out) < limit:
                out.append(item)
        if len(out) >= limit:
            break
    return out


def _reaction_rank(item: dict) -> int:
    """근거 정렬용 반응 점수.

    조회수 스케일이 소스마다 20배 차이 나서 그대로 더하면 뽐뿌 글만 앞에 온다.
    추천과 댓글은 사람이 직접 남긴 반응이라 조회수보다 무겁게 본다.
    """
    votes = item.get("votes") or 0
    comments = item.get("comments") or 0
    views = item.get("views") or 0
    return votes * 20 + comments * 10 + min(views, 2000) // 100


def fomo_score(greed: int, fear: int, total_posts: int) -> float:
    """0~100 여론 점수. 기준 50에서 키워드 편차만큼 움직인다.

    분모가 전체 게시글 수라 제목 200개에서 키워드가 5~10개만 잡히면 점수가 50에
    붙는다. 실측에서 30종목이 45.1~52.4(표준편차 1.65)에 몰려 라벨이 전부 "중립"
    이었다. 다섯 구간 중 한 칸만 쓰는 셈이다.

    지금은 `shrunk_score`를 쓴다. 이 함수는 원래 스펙의 수식을 기록으로 남긴다.
    """
    score = 50 + ((greed - fear) / max(total_posts, 1)) * 50
    return round(max(0.0, min(100.0, score)), 1)


# 축소 추정 강도. 키워드 표본이 이 값과 같을 때 편차를 절반만 반영한다.
# 크게 하면 보수적으로 50에 붙고, 작게 하면 민감해진다. 12에서 30종목 표준편차가
# 1.65에서 10.87로 살아나 다섯 구간이 실제로 쓰였다.
SHRINK_K = 12


def shrunk_score(greed: int, fear: int) -> float:
    """표본 크기를 반영한 0~100 여론 점수.

    방향은 키워드 비율로 잡고(`(탐욕-공포)/(탐욕+공포)`), 표본이 적을수록 중립인
    50 쪽으로 당긴다. 키워드 1개로 0점이나 100점이 찍히는 것을 수식 자체가 막는다.

    `sentiment_score`는 표본이 얇으면 None을 돌려주는데, 그러면 종목 표에 빈칸이
    생긴다(30종목 중 3개). 축소 추정은 같은 문제를 값으로 해결해 빈칸을 없앤다.
    """
    hits = greed + fear
    if hits == 0:
        return 50.0
    tone = (greed - fear) / hits          # -1 ~ +1
    confidence = hits / (hits + SHRINK_K)  # 0 ~ 1
    return round(max(0.0, min(100.0, 50 + tone * 50 * confidence)), 1)


def interpret(score: float) -> tuple[str, str]:
    """점수를 (구간 키, 한글 라벨)로 바꾼다."""
    for lower, label, key in ZONES:
        if score >= lower:
            return key, label
    return "extreme_fear", "극단적 공포"


GAUGE_WIDTH = 41  # 0~100을 41칸에 대응. 점수와 무관하게 폭이 고정된다.


def gauge(score: float) -> str:
    """CLI용 눈금 막대. 20 단위 눈금 위에 현재 위치를 표시한다."""
    span = GAUGE_WIDTH - 1
    cells = ["─"] * GAUGE_WIDTH
    for tick in (20, 40, 60, 80):
        cells[round(tick / 100 * span)] = "┼"
    cells[round(score / 100 * span)] = "●"
    return f"0{''.join(cells)}100"


_WS = re.compile(r"\s+")
# 아카라이브 말머리(이모지 + 선택적 분류어)와 목록 끝 댓글 수를 떼어낸다.
_ARCA_PREFIX = re.compile(r"^[\U0001F300-\U0001FAFF\u2600-\u27BF\uFE0F]+\s*(?:뉴스|공지|정보|질문)?\s*")
_COMMENT_SUFFIX = re.compile(r"\s*\[\d+\]\s*$")


def normalize_title(raw: str) -> str:
    """말머리 이모지와 댓글 수를 떼고 공백을 정리한다."""
    text = unicodedata.normalize("NFC", raw)
    text = _ARCA_PREFIX.sub("", text)
    text = _COMMENT_SUFFIX.sub("", text)
    return _WS.sub(" ", text).strip()


def matches_keyword(title: str, keyword: str) -> bool:
    """제목에 검색어가 있는지 본다. 띄어쓰기 차이는 무시한다.

    뽐뿌는 제목 전용 검색 파라미터가 없어 본문까지 걸린다. 종목명이 본문에만 있는
    글까지 여론으로 세면 지표가 흐려지므로 제목 기준으로 한 번 더 거른다.
    """
    return keyword.replace(" ", "") in title.replace(" ", "")


@dataclass(frozen=True)
class Source:
    key: str
    label: str
    url_template: str      # {keyword}, {ticker}, {page} 를 채운다
    pages: int
    kind: str              # 파서 선택용: naver | dcinside | arca | css
    selector: str = ""
    encoding: str | None = None          # None이면 응답 헤더를 믿는다
    use_cloudscraper: bool = True
    needs_ticker: bool = False
    keyword_charset: str = "utf-8"       # 검색어 URL 인코딩 문자셋
    referer: str = ""
    filter_by_keyword: bool = True
    max_pages: int = 0                   # 0이면 pages와 같다
    needs_browser_cookies: bool = False  # 브라우저로 받은 쿠키가 필요한지
    # 검색어를 URL에 넣지 않는 소스(인기글 목록). 지수처럼 시장 전체를 보는
    # 대상에만 쓰고 개별 종목에는 붙이지 않는다.
    market_wide: bool = False
    # 목록 자체가 추천순으로 걸러진 소스. 여기에 다시 상대 기준을 적용하면 안 된다.
    # 인기글 목록은 추천 중위가 92라 그 3배(276)를 넘는 글이 없어 전부 보통 글로
    # 판정됐다. 이미 커뮤니티가 골라준 목록이므로 전부 화제글로 본다.
    prefiltered_popular: bool = False

    @property
    def page_limit(self) -> int:
        """기간을 채우기 위해 더 들어갈 수 있는 최대 페이지."""
        return self.max_pages or self.pages


_DC_SELECTOR = 'td.gall_tit.ub-word a[href*="no="]'


def _dc_source(key: str, label: str, gallery: str, minor: bool) -> Source:
    """디시 갤러리 소스. 마이너 갤러리와 일반 갤러리는 경로가 다르다.

    경로를 틀리면 디시는 목록 대신 location.replace 스크립트만 돌려주므로
    갤러리별 타입을 여기서 고정한다.
    """
    base = "mgallery/board" if minor else "board"
    return Source(
        key=key,
        label=label,
        url_template=(
            f"https://gall.dcinside.com/{base}/lists/?id={gallery}"
            "&s_type=search_subject&s_keyword={keyword}&page={page}"
        ),
        pages=2,
        # 실측: 검색 결과가 3페이지에서 소진된다(4페이지째는 3행). 더 들어갈 여지가 없다.
        max_pages=4,
        kind="dcinside",
        selector=_DC_SELECTOR,
        referer=f"https://gall.dcinside.com/{base}/lists/?id={gallery}",
    )


SOURCES: tuple[Source, ...] = (
    Source(
        key="naver",
        label="네이버 증권 종목토론실",
        url_template=(
            "https://finance.naver.com/item/board.naver?code={ticker}&page={page}"
        ),
        pages=3,
        # 활발한 종목은 30페이지도 오늘 하루치다. 3일을 채우려면 깊게 들어가야 한다.
        max_pages=12,
        kind="naver",
        selector='td.title a[href*="board_read.naver"]',
        use_cloudscraper=False,
        needs_ticker=True,
        referer="https://finance.naver.com/",
        # 종목 전용 게시판이라 제목에 종목명이 없어도 그 종목 여론이다.
        filter_by_keyword=False,
    ),
    _dc_source("dc_krstock", "디시 한국 주식 갤러리", "krstock", minor=True),
    _dc_source("dc_stockus", "디시 미국 주식 갤러리", "stockus", minor=True),
    _dc_source("dc_neostock", "디시 주식 갤러리", "neostock", minor=False),
    _dc_source("dc_jusik", "디시 실전주식투자 갤러리", "jusik", minor=True),
    Source(
        key="arca",
        label="아카라이브 주식 채널",
        url_template="https://arca.live/b/stock?target=title&keyword={keyword}&p={page}",
        pages=2,
        # 페이지당 5일 남짓이라 2페이지면 3일 기간을 넉넉히 덮는다.
        max_pages=3,
        kind="arca",
        selector="div.list-table a.vrow",
        referer="https://arca.live/b/stock",
    ),
    Source(
        key="fmkorea",
        label="에펨코리아 주식·재테크",
        url_template=(
            "https://www.fmkorea.com/search.php?mid=stock&search_target=title"
            "&search_keyword={keyword}&page={page}"
        ),
        pages=2,
        max_pages=5,
        kind="css",
        selector="td.title a.hx",
        referer="https://www.fmkorea.com/stock",
        # 에펨은 wasm 서명을 요구해 cloudscraper로는 뚫리지 않는다. 브라우저로 한 번
        # 받아둔 쿠키를 붙여야 200이 온다.
        needs_browser_cookies=True,
        use_cloudscraper=False,
    ),
    Source(
        key="ppomppu",
        label="뽐뿌 증권포럼",
        url_template=(
            "https://www.ppomppu.co.kr/zboard/zboard.php?id=stock&page={page}"
            "&divpage=1&search_type=sub_memo&keyword={keyword}"
        ),
        pages=2,
        max_pages=4,
        kind="css",
        selector="a.baseList-title span",
        encoding="euc-kr",
        keyword_charset="euc-kr",
        referer="https://www.ppomppu.co.kr/zboard/zboard.php?id=stock",
    ),
    Source(
        key="fmkorea_pop",
        label="에펨코리아 주식 인기글",
        # 인기 탭은 검색이 아니라 추천순 정렬 목록이다. 검색어를 URL에 넣지 않고
        # 목록을 받은 뒤 제목으로 걸러낸다. 종목명을 직접 쓰지 않아도 화제가 된 글이
        # 여론을 담고 있어(`삼전본주 -39% 대인데 엄살인거지?`) 검색으로 안 잡히던
        # 표본을 보탠다.
        url_template=(
            "https://www.fmkorea.com/index.php?mid=stock"
            "&sort_index=pop&order_type=desc&page={page}"
        ),
        pages=2,
        max_pages=3,
        kind="fmkorea_pop",
        selector="h3.title a",
        referer="https://www.fmkorea.com/stock",
        needs_browser_cookies=True,
        use_cloudscraper=False,
        market_wide=True,
        # 인기 탭은 이미 주식 게시판이라 제목에 종목명이 없어도 주식 여론이다.
        # 지수 별칭으로 걸러보니 60건 중 2건만 남아 표본이 사라졌다.
        filter_by_keyword=False,
        prefiltered_popular=True,
    ),
)


# 게시판마다 목록에 찍는 날짜 형식이 다르다. 시각만 있으면(에펨 `10:57`) 오늘 글이고,
# 연도가 없으면(디시 `07.29`) 올해 글이다.
_ABS_DATE = re.compile(r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})")
_SHORT_DATE = re.compile(r"^(\d{1,2})[.\-/](\d{1,2})\.?$")
_TIME_ONLY = re.compile(r"^\d{1,2}:\d{2}$")
_CLOCK = re.compile(r"^\d{1,2}:\d{2}:\d{2}$")   # 뽐뿌는 초까지 찍는다
# 뽐뿌 지난 글은 `26.07.27`처럼 두 자리 연도를 쓴다.
_YY_DATE = re.compile(r"^(\d{2})[.\-/](\d{1,2})[.\-/](\d{1,2})\.?$")


def parse_post_date(text: str, today: date | None = None) -> date | None:
    """목록 셀의 날짜 문자열을 date로. 해석할 수 없으면 None."""
    if not text:
        return None
    today = today or date.today()
    text = text.strip()

    if _TIME_ONLY.match(text) or _CLOCK.match(text):
        return today

    m = _ABS_DATE.search(text)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None

    m = _YY_DATE.match(text)
    if m:
        try:
            return date(2000 + int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None

    m = _SHORT_DATE.match(text)
    if m:
        try:
            parsed = date(today.year, int(m.group(1)), int(m.group(2)))
        except ValueError:
            return None
        # 12월 글을 1월에 보면 연도가 하나 밀린다.
        return parsed.replace(year=today.year - 1) if parsed > today else parsed
    return None


@dataclass(frozen=True)
class RawRow:
    """목록 한 행에서 읽어낸 값. 링크는 상대경로라 호출한 쪽에서 절대화한다.

    날짜와 반응 수치는 읽지 못하면 None이다. 0과 구분해야 한다. 뽐뿌 추천 칸처럼
    실제로 비어 있는 경우(추천 0)와 셀렉터가 깨져 못 읽은 경우를 같게 취급하면
    참여도 필터가 표본을 통째로 날린다.
    """

    title: str
    href: str | None = None
    posted: date | None = None
    views: int | None = None
    votes: int | None = None
    comments: int | None = None


# 목록 셀의 숫자는 형식이 제멋대로다. 뽐뿌는 `12 - 3`(추천-반대), 디시는 `1.2만`,
# 에펨 인기글 댓글은 `[15]`로 찍는다. 앞쪽 정수만 읽고 만 단위는 풀어준다.
_COUNT_NUM = re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*(만|천)?")


def parse_count(text: str | None) -> int | None:
    """목록 셀의 반응 수치를 정수로. 숫자가 없으면 None."""
    if text is None:
        return None
    match = _COUNT_NUM.search(text)
    if match is None:
        return None
    try:
        value = float(match.group(1).replace(",", ""))
    except ValueError:
        return None
    unit = match.group(2)
    if unit == "만":
        value *= 10_000
    elif unit == "천":
        value *= 1_000
    return int(value)


def _cell_count(node, selector: str) -> int | None:
    """행 안에서 셀렉터로 찾은 첫 셀의 숫자. 셀이 없으면 None."""
    if node is None:
        return None
    cell = node.select_one(selector)
    if cell is None:
        return None
    return parse_count(cell.get_text(" ", strip=True))


def _titles_naver(soup: BeautifulSoup, selector: str) -> list[RawRow]:
    """종목토론실은 목록에서 제목이 잘린다. title 속성에 전체 제목이 있다.

    조회/공감/비공감은 클래스 없는 마지막 세 td에 순서로 들어 있다. 제목 셀 안의
    댓글 수(`[ 3 ]`)도 같은 tah 클래스를 쓰므로 tah 노드를 세면 한 칸씩 밀린다.
    td 위치로 읽는다.
    """
    out = []
    for anchor in soup.select(selector):
        row = anchor.find_parent("tr")
        stamp = row.select_one("td.tah") if row else None
        views = votes = comments = None
        if row is not None:
            cells = row.select("td")
            # [날짜, 제목, 작성자, 조회, 공감, 비공감] 6칸 구조다.
            if len(cells) >= 6:
                views = parse_count(cells[-3].get_text(" ", strip=True))
                votes = parse_count(cells[-2].get_text(" ", strip=True))
            # 댓글 수는 제목 셀 안에 `[ 3 ]`으로 붙는다.
            reply = anchor.find_parent("td")
            if reply is not None:
                marker = reply.select_one("span.tah, strong.tah")
                if marker is not None:
                    comments = parse_count(marker.get_text(" ", strip=True))
        out.append(
            RawRow(
                title=anchor.get("title") or anchor.get_text(" ", strip=True),
                href=anchor.get("href"),
                posted=parse_post_date(stamp.get_text(strip=True) if stamp else ""),
                views=views,
                votes=votes,
                comments=comments,
            )
        )
    return out


def _titles_dcinside(soup: BeautifulSoup, selector: str) -> list[RawRow]:
    out = []
    for a in soup.select(selector):
        row = a.find_parent("tr")
        cell = row.select_one("td.gall_date") if row else None
        # 오늘 글은 본문에 시각만 찍히고 전체 날짜는 title 속성에 있다.
        raw = (cell.get("title") or cell.get_text(strip=True)) if cell else ""
        out.append(
            RawRow(
                title=a.get_text(" ", strip=True),
                href=a.get("href"),
                posted=parse_post_date(raw),
                views=_cell_count(row, "td.gall_count"),
                votes=_cell_count(row, "td.gall_recommend"),
                comments=_cell_count(a.find_parent("td"), "a.reply_numbox, span.reply_num"),
            )
        )
    return out


def _titles_arca(soup: BeautifulSoup, selector: str) -> list[RawRow]:
    """공지는 목록 상단에 고정돼 검색 결과와 무관하다. 클래스로 걸러낸다."""
    out = []
    for row in soup.select(selector):
        if "notice" in (row.get("class") or []):
            continue
        cell = row.select_one("span.vcol.col-title")
        if cell is None:
            continue
        stamp = row.select_one("span.vcol.col-time time")
        raw = (stamp.get("datetime") or stamp.get_text(strip=True)) if stamp else ""
        out.append(
            RawRow(
                title=cell.get_text(" ", strip=True),
                href=row.get("href"),
                posted=parse_post_date(raw),
                views=_cell_count(row, "span.vcol.col-view"),
                votes=_cell_count(row, "span.vcol.col-rate"),
                comments=_cell_count(cell, "span.comment-count"),
            )
        )
    return out


def _titles_css(soup: BeautifulSoup, selector: str) -> list[RawRow]:
    """에펨은 검색어가 <strong>으로 감싸져 있어 구분자 없이 붙여 읽는다.

    뽐뿌는 셀렉터가 <span>을 가리키므로 링크는 부모 <a>에서 찾는다.
    """
    out = []
    for node in soup.select(selector):
        anchor = node if node.name == "a" else node.find_parent("a")
        row = node.find_parent("tr")
        stamp = None
        if row is not None:
            # 에펨은 td.time에 찍는다. 뽐뿌는 날짜 셀에 전용 클래스가 없고
            # 오늘 글은 시각(11:20:53), 지난 글은 날짜(26.07.27)가 들어간다.
            stamp = row.select_one("td.time") or row.select_one("td.list-regi")
            if stamp is None:
                for cell in row.select("td"):
                    text = cell.get_text(strip=True)
                    if _TIME_ONLY.match(text) or _CLOCK.match(text) or _SHORT_DATE.match(text):
                        stamp = cell
                        break
        # 에펨 검색 목록은 조회/추천 모두 td.m_no인데 추천 쪽에만 m_no_voted가 붙는다.
        views = _cell_count(row, "td.baseList-views") if row is not None else None
        votes = _cell_count(row, "td.baseList-rec") if row is not None else None
        if row is not None and views is None:
            plain = [c for c in row.select("td.m_no") if "m_no_voted" not in (c.get("class") or [])]
            views = parse_count(plain[0].get_text(" ", strip=True)) if plain else None
            votes = _cell_count(row, "td.m_no.m_no_voted")
        out.append(
            RawRow(
                title=node.get_text("", strip=True),
                href=anchor.get("href") if anchor else None,
                posted=parse_post_date(stamp.get_text(strip=True) if stamp else ""),
                views=views,
                votes=votes,
                comments=_cell_count(row, "a.replyNum, span.baseList-c"),
            )
        )
    return out


# 인기글 목록의 시각 표기. `19:07`(오늘) 또는 `07.28`(지난 글)이 li 안에 섞여 있다.
_POP_TIME = re.compile(r"\b(\d{1,2}:\d{2}|\d{2}\.\d{2})\b")


def _titles_fmkorea_pop(soup: BeautifulSoup, selector: str) -> list[RawRow]:
    """에펨 인기 탭. 검색 목록과 마크업이 달라 별도 파서가 필요하다.

    제목은 `h3.title a`이고 날짜 셀에 전용 클래스가 없어 li 텍스트에서 시각 패턴을
    찾는다. 제목 끝의 댓글 수(`[31]`)는 normalize_title이 떼어낸다.

    추천 수는 썸네일 위 배지(`a.pc_voted_count span.count`)에 있고 조회수는 없다.
    """
    out = []
    for anchor in soup.select(selector):
        row = anchor.find_parent("li") or anchor.find_parent("tr")
        stamp = ""
        if row is not None:
            match = _POP_TIME.search(row.get_text(" ", strip=True))
            if match:
                stamp = match.group(1)
        out.append(
            RawRow(
                title=anchor.get_text(" ", strip=True),
                href=anchor.get("href"),
                posted=parse_post_date(stamp),
                votes=_cell_count(row, "a.pc_voted_count span.count"),
                comments=_cell_count(anchor, "span.comment_count"),
            )
        )
    return out


_PARSERS = {
    "naver": _titles_naver,
    "dcinside": _titles_dcinside,
    "arca": _titles_arca,
    "css": _titles_css,
    "fmkorea_pop": _titles_fmkorea_pop,
}


def _new_session(source: Source):
    """소스마다 새 세션을 만든다.

    cloudscraper 세션은 스레드 안전을 보장하지 않는다. 소스를 병렬로 도는 구조라
    세션을 공유하면 쿠키와 챌린지 상태가 섞인다.
    """
    if source.needs_browser_cookies:
        return _browser_backed_session(source)
    if not source.use_cloudscraper:
        return requests.Session()
    return cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "darwin", "mobile": False}
    )


def _browser_backed_session(source: Source, force_refresh: bool = False):
    """브라우저로 받아둔 쿠키를 붙인 세션.

    쿠키를 못 얻으면 쿠키 없는 세션을 돌려준다. 그러면 첫 요청이 430으로 실패하고
    평소처럼 그 소스만 건너뛴다.
    """
    import fomo_fmkorea

    session = requests.Session()
    cookies = fomo_fmkorea.get_cookies(UA, force=force_refresh)
    if cookies:
        for name, value in cookies.items():
            session.cookies.set(name, value, domain=".fmkorea.com")
    return session


def _build_url(source: Source, keyword: str, ticker: str | None, page: int) -> str:
    return source.url_template.format(
        keyword=quote(keyword.encode(source.keyword_charset)),
        ticker=ticker or "",
        page=page,
    )


def _get_with_retry(session, url: str, headers: dict[str, str]):
    """일시 차단(429/430/503)만 재시도한다.

    404나 500은 다시 물어도 같은 답이 온다. 반면 에펨은 요청이 몰리면 보안 페이지로
    430을 잠깐 주고 곧 풀어주므로, 이 경우만 짧게 기다렸다 다시 시도한다.
    """
    last: requests.Response | None = None
    for attempt in range(MAX_RETRIES + 1):
        if attempt:
            time.sleep(RETRY_SLEEP_SEC * attempt)
        _throttle(url)
        last = session.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        if last.status_code not in TRANSIENT_STATUS:
            break
    assert last is not None
    last.raise_for_status()
    return last


def fetch_posts(
    source: Source,
    keyword: str,
    ticker: str | None = None,
    lookback_days: int = LOOKBACK_DAYS,
) -> list[Post]:
    """한 소스에서 최근 게시글을 모은다.

    기본 페이지를 먼저 훑고, 아직 기간 안에 머물러 있으면 최대 페이지까지 더 들어간다.
    한 페이지가 전부 기간 밖이면 그 뒤는 더 오래된 글뿐이라 멈춘다(목록은 최신순).
    """
    session = _new_session(source)
    headers = dict(BASE_HEADERS)
    if source.referer:
        headers["Referer"] = source.referer

    parser = _PARSERS[source.kind]
    cutoff = date.today() - timedelta(days=lookback_days - 1)
    seen: set[str] = set()
    posts: list[Post] = []
    refreshed = False   # 브라우저 쿠키 재발급은 소스당 한 번만

    for page in range(1, source.page_limit + 1):
        if page > 1:
            time.sleep(PAGE_SLEEP_SEC)

        url = _build_url(source, keyword, ticker, page)
        try:
            response = _get_with_retry(session, url, headers)
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            # 브라우저 쿠키가 만료되면 다시 430이 온다. 한 번만 새로 받아 재시도한다.
            if source.needs_browser_cookies and status in TRANSIENT_STATUS and not refreshed:
                import fomo_fmkorea

                fomo_fmkorea.invalidate()
                session = _browser_backed_session(source, force_refresh=True)
                refreshed = True
                response = _get_with_retry(session, url, headers)
            else:
                raise
        if source.encoding:
            response.encoding = source.encoding

        # 마이너/일반 갤러리 경로가 틀리면 디시는 목록 대신 리다이렉트 스크립트를 준다.
        if source.kind == "dcinside" and "location.replace" in response.text[:400]:
            raise RuntimeError("갤러리 경로 불일치")

        soup = BeautifulSoup(response.text, "lxml")
        rows = parser(soup, source.selector)
        if not rows:
            break  # 검색 결과 소진

        fresh_on_page = 0
        for row in rows:
            # 날짜를 못 읽은 글은 버리지 않는다. 파서가 깨졌을 때 표본이 통째로
            # 사라지는 편이 오래된 글 몇 개보다 위험하다.
            if row.posted is not None and row.posted < cutoff:
                continue
            fresh_on_page += 1

            title = normalize_title(row.title)
            if not title or title in seen:
                continue
            if source.filter_by_keyword and not matches_keyword(title, keyword):
                continue
            seen.add(title)
            # 링크는 전부 상대경로다. 뽐뿌는 경로조차 없는 형태(view.php?...)라
            # 목록 페이지 URL을 기준으로 합쳐야 정상 주소가 된다.
            posts.append(
                Post(
                    title=title,
                    url=urljoin(response.url, row.href) if row.href else None,
                    source=source.key,
                    posted_on=row.posted,
                    views=row.views,
                    votes=row.votes,
                    comments=row.comments,
                )
            )

        # 이 페이지가 전부 기간 밖이면 뒤 페이지는 더 오래됐다. 기본 페이지는 채운다.
        if fresh_on_page == 0 and page >= source.pages:
            break

    return posts


@dataclass(frozen=True)
class Post:
    """수집한 게시글 하나. 점수 계산에는 제목만 쓰고, 링크는 원글 확인용이다."""

    title: str
    url: str | None = None
    source: str = ""
    posted_on: date | None = None
    # 목록에서 읽은 반응 수치. 읽지 못했으면 None이다(0과 구분한다).
    views: int | None = None
    votes: int | None = None
    comments: int | None = None


def titles_of(posts: list[Post]) -> list[str]:
    return [p.title for p in posts]


def _median(values: list[int]) -> float | None:
    if len(values) < SCALE_MIN_SAMPLE:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[mid])
    return (ordered[mid - 1] + ordered[mid]) / 2


def _source_scale(posts: list[Post]) -> tuple[float | None, float | None]:
    """소스 안의 조회수/추천수 중위값. 표본이 얇으면 None(가중 없음)."""
    return (
        _median([p.views for p in posts if p.views is not None]),
        _median([p.votes for p in posts if p.votes is not None]),
    )


def post_weight(post: Post, view_median: float | None, vote_median: float | None) -> int:
    """게시글 하나의 무게. 0이면 표본에서 뺀다.

    반응을 읽지 못한 글(수치가 전부 None)은 기본 무게 1을 준다. 셀렉터가 깨졌을 때
    표본이 통째로 사라지는 것을 막는다. 날짜 처리와 같은 원칙이다.
    """
    if post.views is None and post.votes is None and post.comments is None:
        return 1

    reacted = bool(post.votes) or bool(post.comments)
    if (
        not reacted
        and view_median is not None
        and post.views is not None
        and post.views < view_median * DEAD_VIEW_RATIO
    ):
        return 0

    hot_views = (
        view_median is not None
        and post.views is not None
        and post.views >= view_median * HOT_VIEW_RATIO
    )
    hot_votes = (
        vote_median is not None
        and post.votes is not None
        and post.votes >= max(vote_median * HOT_VOTE_RATIO, HOT_VOTE_FLOOR)
    )
    return HOT_WEIGHT if hot_views or hot_votes else 1


@dataclass
class WeightedSample:
    """반응 가중을 적용한 제목 표본."""

    titles: list[str] = field(default_factory=list)   # 화제글은 여러 번 들어간다
    kept: int = 0
    dropped: int = 0
    hot: int = 0


def weighted_titles(results: list[SourceResult]) -> WeightedSample:
    """소스별로 반응 중위값을 재서 제목 표본을 만든다.

    중위값은 소스 안에서만 낸다. 소스를 섞어 하나의 기준을 만들면 조회수가 원래
    높은 사이트의 글이 전부 화제글이 되고, 낮은 사이트는 전부 잘려나간다.
    """
    prefiltered = {s.key for s in SOURCES if s.prefiltered_popular}
    sample = WeightedSample()
    for result in results:
        if not result.posts:
            continue
        # 추천순으로 이미 걸러진 목록은 전부 화제글이다. 상대 기준을 다시 적용하면
        # 중위값이 높아서 아무것도 화제글로 잡히지 않는다.
        if result.key in prefiltered:
            sample.kept += len(result.posts)
            sample.hot += len(result.posts)
            for post in result.posts:
                sample.titles.extend([post.title] * HOT_WEIGHT)
            continue
        view_median, vote_median = _source_scale(result.posts)
        for post in result.posts:
            weight = post_weight(post, view_median, vote_median)
            if weight == 0:
                sample.dropped += 1
                continue
            sample.kept += 1
            if weight > 1:
                sample.hot += 1
            sample.titles.extend([post.title] * weight)
    return sample


@dataclass
class SourceResult:
    key: str
    label: str
    posts: list[Post] = field(default_factory=list)
    error: str | None = None

    @property
    def count(self) -> int:
        return len(self.posts)

    @property
    def titles(self) -> list[str]:
        return titles_of(self.posts)


def _describe_error(exc: Exception) -> str:
    """실패 사유를 사람이 읽을 짧은 한국어로 바꾼다."""
    if isinstance(exc, requests.HTTPError):
        status = exc.response.status_code if exc.response is not None else None
        if status in (403, 429, 430, 503):
            return f"차단됨 (HTTP {status})"
        return f"HTTP {status}" if status else "HTTP 오류"
    if isinstance(exc, requests.Timeout):
        return "응답 없음 (타임아웃)"
    if isinstance(exc, requests.ConnectionError):
        return "연결 실패"
    message = str(exc).strip()
    return message[:40] if message else type(exc).__name__


def _collect_one(
    source: Source, keyword: str, ticker: str | None, lookback_days: int
) -> SourceResult:
    if source.needs_ticker and not ticker:
        return SourceResult(source.key, source.label, error="티커 변환 실패")
    if circuit_open(source.key):
        return SourceResult(source.key, source.label, error="연속 실패로 건너뜀")
    try:
        posts = fetch_posts(source, keyword, ticker, lookback_days)
    except Exception as exc:  # 한 사이트가 죽어도 나머지는 계속 간다
        record_outcome(source.key, ok=False)
        return SourceResult(source.key, source.label, error=_describe_error(exc))
    record_outcome(source.key, ok=True)
    return SourceResult(source.key, source.label, posts)


@dataclass
class ScanResult:
    keyword: str
    ticker: str | None
    results: list[SourceResult]

    @property
    def posts(self) -> list[Post]:
        return [p for r in self.results for p in r.posts]

    @property
    def titles(self) -> list[str]:
        return titles_of(self.posts)

    @property
    def ok_count(self) -> int:
        return sum(1 for r in self.results if r.error is None)


def scan(
    keyword: str,
    ticker: str | None = None,
    lookback_days: int = LOOKBACK_DAYS,
    include_market_wide: bool = False,
) -> ScanResult:
    """소스를 병렬로 훑는다. 실패한 소스는 결과에 사유만 담고 넘어간다.

    `include_market_wide`는 검색어를 URL에 넣지 않는 소스(인기글)를 포함할지다.
    종목 스캔에서는 끄고, 지수처럼 시장 전체를 보는 대상에서만 켠다. 인기글은
    종목을 특정하지 않으므로 개별 종목 점수에 섞으면 30종목이 같은 표본을 공유한다.
    """
    if ticker is None:
        ticker = resolve_ticker(keyword)

    sources = [
        s for s in SOURCES if include_market_wide or not s.market_wide
    ]
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = [
            pool.submit(_collect_one, s, keyword, ticker, lookback_days) for s in sources
        ]
        # SOURCES 순서를 유지한다. 완료 순으로 받으면 출력이 실행마다 달라진다.
        results = [f.result() for f in futures]

    return ScanResult(keyword, ticker, results)


def scan_aliases(
    label: str,
    aliases: list[str],
    lookback_days: int = LOOKBACK_DAYS,
    include_market_wide: bool = False,
) -> ScanResult:
    """같은 대상을 여러 이름으로 검색해 하나로 합친다.

    지수는 부르는 말이 갈린다. S&P500은 `에센피`, `SPY`로도 불리고 어느 하나만
    검색하면 표본의 대부분을 놓친다. 별칭별 결과를 소스 단위로 합치고, 제목이
    겹치면 한 번만 센다(같은 글이 두 별칭에 모두 걸릴 수 있다).
    """
    merged: dict[str, SourceResult] = {
        s.key: SourceResult(s.key, s.label) for s in SOURCES
    }
    seen: dict[str, set[str]] = {s.key: set() for s in SOURCES}
    errors: dict[str, list[str]] = {s.key: [] for s in SOURCES}

    for position, alias in enumerate(aliases):
        # 인기글은 검색어와 무관한 같은 목록이다. 별칭마다 받으면 같은 글을 여러 번
        # 요청하게 되니 첫 별칭에서만 포함한다(중복 제목은 어차피 걸러진다).
        results = scan(
            alias,
            lookback_days=lookback_days,
            include_market_wide=include_market_wide and position == 0,
        ).results
        for result in results:
            if result.key not in merged:
                merged[result.key] = SourceResult(result.key, result.label)
                seen[result.key] = set()
                errors[result.key] = []
            if result.error:
                errors[result.key].append(result.error)
                continue
            target = merged[result.key]
            for post in result.posts:
                if post.title in seen[result.key]:
                    continue
                seen[result.key].add(post.title)
                target.posts.append(post)

    # 별칭 하나라도 성공했으면 그 소스는 성공이다. 전부 실패했을 때만 사유를 남긴다.
    for key, result in merged.items():
        if not result.posts and errors[key]:
            result.error = errors[key][0]

    # 한 번도 응답을 받지 못한 소스는 결과에서 뺀다. 빈 성공으로 남기면 "수집 0개"로
    # 보이지만 실제로는 시도조차 안 된 상태다.
    attempted = [r for r in merged.values() if r.posts or r.error]
    return ScanResult(label, None, attempted)


@dataclass
class FomoReport:
    keyword: str
    ticker: str | None
    score: float
    zone: str
    label: str
    stats: KeywordStats
    results: list[SourceResult]
    current_level: float | None = None
    # 반응 가중 적용 결과. 표본이 얼마나 걸러졌는지 화면에서 보여주기 위해 남긴다.
    kept_posts: int = 0
    dropped_posts: int = 0
    hot_posts: int = 0

    @property
    def total_posts(self) -> int:
        return sum(r.count for r in self.results)

    @property
    def posts(self) -> list[Post]:
        return [p for r in self.results for p in r.posts]

    def evidence(self, limit: int = 12) -> list[dict]:
        return evidence_posts(self.posts, limit, self.current_level)


def analyze(scan_result: ScanResult, current_level: float | None = None) -> FomoReport:
    """수집 결과를 점수까지 계산한 리포트로 바꾼다.

    `current_level`(현재 지수나 주가)을 주면 목표 수치를 현재와 비교해 조롱을 가려낸다.
    """
    # 제목을 그대로 세지 않고 반응으로 무게를 준다. 조회수도 없는 글이 화제글과 같은
    # 한 표를 갖는 구조에서는 여론이 아니라 글쓴 사람 수를 재게 된다.
    sample = weighted_titles(scan_result.results)
    stats = count_keywords(sample.titles, current_level)
    # 게시글 수로 나누면 점수가 50에 붙어 구간이 죽는다. 표본 크기를 반영한
    # 축소 추정을 쓴다.
    score = shrunk_score(stats.greed_total, stats.fear_total)
    zone, label = interpret(score)
    return FomoReport(
        keyword=scan_result.keyword,
        ticker=scan_result.ticker,
        score=score,
        zone=zone,
        label=label,
        stats=stats,
        results=scan_result.results,
        current_level=current_level,
        kept_posts=sample.kept,
        dropped_posts=sample.dropped,
        hot_posts=sample.hot,
    )


def sentiment_score(greed: int, fear: int) -> float | None:
    """키워드 표본만으로 계산하는 심리 점수. 표본이 얇으면 None.

    fomo_score()는 전체 게시글 수로 나눈다. 제목 100개에서 키워드가 3개만 잡히는 게
    보통이라 점수가 50에 붙고, 종목 30개를 늘어놓으면 전부 중립으로 보인다.
    여기서는 탐욕/공포 키워드 합만 분모로 써서 기울기를 그대로 드러낸다.
    대신 표본이 얇을 때 극단값이 나오므로 개별 종목이 아니라 집계에만 쓴다.
    """
    hits = greed + fear
    if hits < MIN_SENTIMENT_HITS:
        return None
    return round(50 + (greed - fear) / hits * 50, 1)


def aggregate(records: list[dict]) -> dict:
    """종목 레코드를 시장 전체 / 섹터별 심리로 묶는다.

    종목별 점수를 평균하면 얇은 표본과 두꺼운 표본이 같은 무게를 갖는다. 키워드를
    먼저 합친 뒤 한 번에 계산해야 실제로 많이 언급된 쪽이 지표를 끌고 간다.
    """
    greed = sum(r["greed_total"] for r in records)
    fear = sum(r["fear_total"] for r in records)
    posts = sum(r["total_posts"] for r in records)
    hot = sum(r.get("hot_posts", 0) for r in records)
    dropped = sum(r.get("dropped_posts", 0) for r in records)

    keyword_totals: dict[str, dict[str, int]] = {"greed": {}, "fear": {}}
    for record in records:
        for side, field_name in (("greed", "greed_counts"), ("fear", "fear_counts")):
            for word, hits in record.get(field_name, {}).items():
                keyword_totals[side][word] = keyword_totals[side].get(word, 0) + hits
    for side, counts in keyword_totals.items():
        keyword_totals[side] = dict(sorted(counts.items(), key=lambda kv: -kv[1]))

    # 폭(breadth): 몇 종목이 탐욕 쪽으로 기울었는지. 점수 하나로는 "한 종목이 끌고 가는
    # 쏠림"과 "전반적인 온기"를 구분할 수 없다.
    greed_leaning = sum(1 for r in records if r["greed_total"] > r["fear_total"])
    fear_leaning = sum(1 for r in records if r["greed_total"] < r["fear_total"])

    sectors = []
    by_sector: dict[str, list[dict]] = {}
    for record in records:
        by_sector.setdefault(record.get("sector") or "기타", []).append(record)
    for name, group in by_sector.items():
        g = sum(r["greed_total"] for r in group)
        f = sum(r["fear_total"] for r in group)
        score = sentiment_score(g, f)
        sectors.append(
            {
                "sector": name,
                "stocks": len(group),
                "greed_total": g,
                "fear_total": f,
                "hits": g + f,
                "score": score,
                "zone": interpret(score)[0] if score is not None else None,
            }
        )

    # 공포가 심한 쪽부터 늘어놓는다. 이름 순으로 두면 어디가 차가운지 훑을 수 없다.
    # 표본이 얇아 점수가 없는 섹터는 뒤로 밀고 이름 순으로 정리한다.
    sectors.sort(
        key=lambda s: (s["score"] is None, s["score"] if s["score"] is not None else 0, s["sector"])
    )

    score = sentiment_score(greed, fear)
    return {
        "score": score,
        "zone": interpret(score)[0] if score is not None else None,
        "label": interpret(score)[1] if score is not None else "표본 부족",
        "greed_total": greed,
        "fear_total": fear,
        "hits": greed + fear,
        "total_posts": posts,
        "hot_posts": hot,
        "dropped_posts": dropped,
        "stocks": len(records),
        "greed_leaning": greed_leaning,
        "fear_leaning": fear_leaning,
        "keyword_totals": keyword_totals,
        "sectors": sectors,
        # 종목별로 저장된 근거를 모아 시장 전체 대표 사례를 만든다. 키워드가 많이
        # 잡힌 글부터 담아 "왜 이 점수인지"를 바로 확인하게 한다.
        "evidence": _merge_evidence(records),
    }


def _merge_evidence(records: list[dict], limit: int = 16) -> list[dict]:
    """종목별 근거 게시글을 합친다. 종목 이름을 붙여 어디서 온 글인지 알린다."""
    pool: list[dict] = []
    for record in records:
        for item in record.get("evidence", []):
            pool.append({**item, "stock": record.get("name", "")})

    return interleave_evidence(pool, limit)


def interleave_evidence(pool: list[dict], limit: int = 16) -> list[dict]:
    """근거 목록을 탐욕/공포 번갈아 배치한다. 반응이 많은 글을 먼저 담는다."""
    greed_side = [i for i in pool if len(i.get("greed", [])) >= len(i.get("fear", []))]
    fear_side = [i for i in pool if len(i.get("greed", [])) < len(i.get("fear", []))]
    for side in (greed_side, fear_side):
        side.sort(
            key=lambda i: (-_reaction_rank(i), -(len(i.get("greed", [])) + len(i.get("fear", []))))
        )

    out: list[dict] = []
    for a, b in zip_longest(greed_side, fear_side):
        for item in (a, b):
            if item is not None and len(out) < limit:
                out.append(item)
        if len(out) >= limit:
            break
    return out
