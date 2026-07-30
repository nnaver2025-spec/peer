"""FOMO 지표 계산과 제목 정규화 검증. 네트워크를 타지 않는다."""

from datetime import date

import pytest
from bs4 import BeautifulSoup

import fomo_core as core
from fomo_indices import INDICES
from fomo_scanner import display_width, pad, render


def test_empty_titles_are_neutral():
    stats = core.count_keywords([])
    assert (stats.greed_total, stats.fear_total) == (0, 0)
    score = core.fomo_score(0, 0, 0)
    assert score == 50.0
    assert core.interpret(score) == ("neutral", "중립")


def test_spec_example_matches_published_score():
    """스펙 출력 예시: 탐욕 23 / 공포 11 / 79개 -> 57.6"""
    assert core.fomo_score(23, 11, 79) == 57.6


def test_shrunk_score_widens_the_useful_range():
    """게시글 분모는 점수를 50에 붙인다. 실측 30종목이 45.1~52.4에 몰렸다."""
    # 같은 데이터로 두 공식을 비교한다(탐욕 6 / 공포 26 / 게시글 130).
    assert core.fomo_score(6, 26, 130) == 42.3
    assert core.shrunk_score(6, 26) < 30      # 공포가 분명히 드러난다


def test_shrunk_score_pulls_thin_samples_toward_neutral():
    """키워드 1개로 0점이나 100점이 찍히면 신호가 아니라 잡음이다."""
    assert core.shrunk_score(0, 0) == 50.0
    thin = core.shrunk_score(1, 0)
    thick = core.shrunk_score(40, 0)
    assert 50 < thin < 60          # 표본 1개는 거의 중립
    assert thick > 85              # 표본 40개는 극단까지 간다


def test_shrunk_score_is_symmetric():
    assert core.shrunk_score(10, 0) + core.shrunk_score(0, 10) == 100.0


def test_shrunk_score_stays_in_range():
    for g, f in [(0, 0), (1, 0), (0, 1), (500, 0), (0, 500), (7, 7)]:
        assert 0.0 <= core.shrunk_score(g, f) <= 100.0


def test_analyze_uses_shrunk_score():
    results = [
        core.SourceResult("a", "A", [core.Post("가즈아 떡상"), core.Post("폭락 손절")]),
    ]
    report = core.analyze(core.ScanResult("삼성전자", "005930", results))
    expected = core.shrunk_score(report.stats.greed_total, report.stats.fear_total)
    assert report.score == expected


def test_score_clamps_at_both_ends():
    # 게시글보다 키워드가 많으면 계산값이 100을 넘는다. 클램프가 잡아야 한다.
    assert core.fomo_score(50, 0, 10) == 100.0
    assert core.fomo_score(0, 50, 10) == 0.0


@pytest.mark.parametrize(
    "score,expected",
    [
        (0, "극단적 공포"),
        (24, "극단적 공포"),
        (25, "공포"),
        (44, "공포"),
        (45, "중립"),
        (54, "중립"),
        (55, "탐욕"),
        (74, "탐욕"),
        (75, "극단적 탐욕"),
        (100, "극단적 탐욕"),
    ],
)
def test_zone_boundaries(score, expected):
    """CNN Fear & Greed와 같은 경계(25/45/55/75).

    원래 스펙은 중립을 41~60으로 뒀는데 폭이 20이나 돼서 실제 공포를 덮었다.
    지수가 18~38인 상황에서 전체 여론만 42.1로 "중립"이 나왔다.
    """
    assert core.interpret(score)[1] == expected


def test_zone_definition_is_shared_with_market_gauge():
    """구간 정의가 두 곳에 있으면 같은 점수가 다른 라벨을 받는다."""
    import fomo_market

    for score in (10, 25, 42.1, 45, 55, 75, 90):
        assert fomo_market._interpret(score) == core.interpret(score)


def test_repeated_keyword_counts_every_occurrence():
    stats = core.count_keywords(["가즈아 가즈아"])
    assert stats.greed_counts["가즈아"] == 2
    assert stats.greed_total == 2


def test_counts_are_sorted_and_drop_zero_hits():
    stats = core.count_keywords(["떡상 떡상 떡상", "가즈아", "손절"])
    assert list(stats.greed_counts) == ["떡상", "가즈아"]
    assert "불장" not in stats.greed_counts
    assert stats.fear_counts == {"손절": 1}


def test_gauge_width_is_fixed_across_scores():
    widths = {len(core.gauge(s)) for s in (0, 33.3, 50, 57.6, 100)}
    assert len(widths) == 1
    assert core.gauge(0).startswith("0●")
    assert core.gauge(100).endswith("●100")


def test_normalize_strips_arca_prefix_and_comment_count():
    assert core.normalize_title("💬 매수 공시) 삼성전자 하닉 [5]") == "매수 공시) 삼성전자 하닉"
    assert core.normalize_title("📰뉴스 삼성전자와 브로드컴") == "삼성전자와 브로드컴"
    assert core.normalize_title("  여러   공백   정리  ") == "여러 공백 정리"


def test_keyword_filter_ignores_spacing():
    assert core.matches_keyword("주성 엔지니어링 살짝 담고", "주성엔지니어링")
    assert not core.matches_keyword("코스닥 900 언제 찍나", "주성엔지니어링")


def test_naver_source_skips_keyword_filter():
    """종목토론실은 종목 전용 게시판이라 제목에 종목명이 없어도 유효하다."""
    naver = next(s for s in core.SOURCES if s.key == "naver")
    assert naver.filter_by_keyword is False
    assert naver.needs_ticker is True
    assert naver.pages == 3


def test_source_set_matches_spec():
    # 스펙의 8개 + 에펨 인기글(검색어를 쓰지 않는 시장 전체 소스)
    assert len(core.SOURCES) == 9
    assert len([s for s in core.SOURCES if not s.market_wide]) == 8
    dc = [s for s in core.SOURCES if s.key.startswith("dc_")]
    assert len(dc) == 4
    # neostock은 일반 갤러리라 mgallery 경로를 쓰면 리다이렉트만 돌아온다.
    neostock = next(s for s in core.SOURCES if s.key == "dc_neostock")
    assert "mgallery" not in neostock.url_template
    assert all("mgallery" in s.url_template for s in dc if s.key != "dc_neostock")
    assert all(s.pages == 2 for s in core.SOURCES if s.key != "naver")


def test_ppomppu_uses_euckr_for_search_keyword():
    ppom = next(s for s in core.SOURCES if s.key == "ppomppu")
    url = core._build_url(ppom, "삼성전자", None, 1)
    assert "%BB%EF%BC%BA%C0%FC%C0%DA" in url
    assert ppom.encoding == "euc-kr"


def test_utf8_sources_encode_keyword_as_utf8():
    arca = next(s for s in core.SOURCES if s.key == "arca")
    url = core._build_url(arca, "삼성전자", None, 2)
    assert "%EC%82%BC%EC%84%B1%EC%A0%84%EC%9E%90" in url
    assert url.endswith("p=2")


def test_transient_status_covers_fmkorea_security_page():
    """에펨은 요청이 몰리면 자체 보안 페이지로 430을 잠깐 준다."""
    assert 430 in core.TRANSIENT_STATUS
    assert 429 in core.TRANSIENT_STATUS
    assert 404 not in core.TRANSIENT_STATUS


def test_circuit_opens_after_consecutive_failures():
    core.reset_circuits()
    assert not core.circuit_open("fmkorea")
    for _ in range(core.CIRCUIT_TRIP_FAILURES):
        core.record_outcome("fmkorea", ok=False)
    assert core.circuit_open("fmkorea")
    core.reset_circuits()


def test_single_success_resets_failure_streak():
    core.reset_circuits()
    core.record_outcome("arca", ok=False)
    core.record_outcome("arca", ok=False)
    core.record_outcome("arca", ok=True)
    core.record_outcome("arca", ok=False)
    assert not core.circuit_open("arca")
    core.reset_circuits()


def test_open_circuit_skips_request(monkeypatch):
    """차단된 소스는 요청 자체를 하지 않는다."""
    core.reset_circuits()
    for _ in range(core.CIRCUIT_TRIP_FAILURES):
        core.record_outcome("fmkorea", ok=False)

    def explode(*args, **kwargs):
        raise AssertionError("차단된 소스에 요청이 나갔다")

    monkeypatch.setattr(core, "fetch_posts", explode)
    source = next(s for s in core.SOURCES if s.key == "fmkorea")
    result = core._collect_one(source, "삼성전자", None, core.LOOKBACK_DAYS)
    assert result.error == "연속 실패로 건너뜀"
    core.reset_circuits()


def test_fmkorea_has_longest_throttle_interval():
    """에펨은 브라우저 쿠키가 관문이다. 간격만 늘려서는 뚫리지 않았다."""
    fmkorea = next(s for s in core.SOURCES if s.key == "fmkorea")
    assert fmkorea.needs_browser_cookies
    # 쿠키를 붙이면 통과하므로 8초까지 벌릴 필요가 없다(실측 0.8초 간격 68회 성공).
    assert core.DOMAIN_MIN_INTERVAL["www.fmkorea.com"] <= 2.0


def test_only_fmkorea_needs_browser_cookies():
    """브라우저 의존은 에펨에만 둔다. 나머지는 requests/cloudscraper로 충분하다."""
    needing = {s.key for s in core.SOURCES if s.needs_browser_cookies}
    assert needing == {"fmkorea", "fmkorea_pop"}
    assert all(s.key.startswith("fmkorea") for s in core.SOURCES if s.needs_browser_cookies)


def test_market_wide_source_is_excluded_from_stock_scan():
    """인기글은 종목을 특정하지 않는다. 종목 점수에 섞으면 30종목이 표본을 공유한다."""
    pop = next(s for s in core.SOURCES if s.key == "fmkorea_pop")
    assert pop.market_wide
    assert pop.filter_by_keyword is False   # 이미 주식 게시판이라 제목 필터가 표본을 없앤다
    assert "{keyword}" not in pop.url_template


def test_browser_session_works_without_cookies(monkeypatch):
    """쿠키를 못 얻어도 세션은 만들어진다. 그 요청이 실패하면 그 소스만 건너뛴다."""
    import fomo_fmkorea

    monkeypatch.setattr(fomo_fmkorea, "get_cookies", lambda ua, force=False: None)
    source = next(s for s in core.SOURCES if s.key == "fmkorea")
    session = core._browser_backed_session(source)
    assert len(session.cookies) == 0


def test_browser_cookies_are_attached(monkeypatch):
    import fomo_fmkorea

    monkeypatch.setattr(
        fomo_fmkorea, "get_cookies", lambda ua, force=False: {"fm5": "abc", "fm6": "def"}
    )
    source = next(s for s in core.SOURCES if s.key == "fmkorea")
    session = core._browser_backed_session(source)
    assert session.cookies.get("fm5", domain=".fmkorea.com") == "abc"


def test_cooldown_prevents_repeated_browser_launches(monkeypatch, tmp_path):
    """IP 차단 중에는 브라우저를 다시 띄우지 않는다.

    차단되면 브라우저로도 5분 넘게 안 풀린다. 종목마다 띄우면 회차만 길어진다.
    """
    import fomo_fmkorea as fm

    monkeypatch.setattr(fm, "_CACHE_PATH", tmp_path / "cookies.json")
    monkeypatch.setattr(fm, "_FAILURE_PATH", tmp_path / "blocked_at")
    calls = []

    def fake_browser(ua):
        calls.append(ua)
        return None      # 차단 상태

    monkeypatch.setattr(fm, "_fetch_with_browser", fake_browser)
    assert fm.get_cookies("UA") is None
    assert fm.get_cookies("UA") is None      # 쿨다운이라 시도하지 않는다
    assert len(calls) == 1


def _record(name, sector, greed, fear, posts=100, greed_counts=None, fear_counts=None):
    return {
        "name": name,
        "sector": sector,
        "greed_total": greed,
        "fear_total": fear,
        "total_posts": posts,
        "greed_counts": greed_counts or {},
        "fear_counts": fear_counts or {},
    }


def test_sentiment_score_needs_minimum_sample():
    """키워드 1개로 100점이 찍히면 신호가 아니라 잡음이다."""
    assert core.sentiment_score(1, 0) is None
    assert core.sentiment_score(0, 1) is None
    assert core.sentiment_score(core.MIN_SENTIMENT_HITS, 0) == 100.0


def test_sentiment_score_uses_keyword_hits_as_denominator():
    # fomo_score는 게시글 수로 나눠 50에 붙는다. 심리 점수는 기울기를 그대로 드러낸다.
    assert core.fomo_score(6, 4, 200) == 50.5
    assert core.sentiment_score(6, 4) == 60.0


def test_aggregate_pools_keywords_before_scoring():
    """종목별 점수를 평균하면 얇은 표본이 두꺼운 표본과 같은 무게를 갖는다."""
    records = [
        _record("A", "반도체", 2, 18),   # 공포 쪽으로 두껍게 기울었다
        _record("B", "반도체", 1, 0),    # 표본 1개
    ]
    market = core.aggregate(records)
    assert market["hits"] == 21
    assert market["score"] == core.sentiment_score(3, 18)
    assert market["score"] < 30  # 두꺼운 쪽이 지표를 끌고 간다


def test_aggregate_reports_breadth():
    records = [
        _record("A", "반도체", 5, 1),
        _record("B", "반도체", 1, 5),
        _record("C", "조선", 3, 3),
    ]
    market = core.aggregate(records)
    assert (market["greed_leaning"], market["fear_leaning"]) == (1, 1)
    assert market["stocks"] == 3


def test_aggregate_merges_keyword_counts_descending():
    records = [
        _record("A", "반도체", 3, 0, greed_counts={"간다": 3}),
        _record("B", "조선", 5, 0, greed_counts={"간다": 2, "떡상": 3}),
    ]
    market = core.aggregate(records)
    assert list(market["keyword_totals"]["greed"].items()) == [("간다", 5), ("떡상", 3)]


def test_aggregate_marks_thin_sectors_without_score():
    records = [
        _record("A", "반도체", 8, 6),
        _record("B", "식품", 1, 1),
    ]
    sectors = {s["sector"]: s for s in core.aggregate(records)["sectors"]}
    assert sectors["반도체"]["score"] is not None
    assert sectors["식품"]["score"] is None
    assert sectors["식품"]["zone"] is None


def test_aggregate_handles_empty_and_missing_sector():
    empty = core.aggregate([])
    assert empty["score"] is None
    assert empty["label"] == "표본 부족"
    assert empty["sectors"] == []

    market = core.aggregate([_record("A", "", 6, 6)])
    assert market["sectors"][0]["sector"] == "기타"


def test_sectors_sorted_coldest_first_with_thin_ones_last():
    records = [
        _record("A", "따뜻", 9, 1),
        _record("B", "차가움", 1, 9),
        _record("C", "중간", 5, 5),
        _record("D", "얇음", 1, 1),
    ]
    names = [s["sector"] for s in core.aggregate(records)["sectors"]]
    assert names == ["차가움", "중간", "따뜻", "얇음"]


def test_indices_cover_four_major_markets():
    keys = {i.key for i in INDICES}
    assert keys == {"kospi", "kosdaq", "sp500", "nasdaq"}
    assert {i.market for i in INDICES} == {"국내", "미국"}


def test_match_keywords_finds_both_sides():
    greed, fear = core.match_keywords("가즈아 떡상 고점 아님")
    assert set(greed) == {"가즈아", "떡상"}
    assert fear == ["고점"]
    assert core.match_keywords("그냥 평범한 제목") == ([], [])


@pytest.mark.parametrize("word", ["간다", "진입", "사도"])
def test_directionless_words_are_not_keywords(word):
    """방향을 담지 않는 말은 세지 않는다.

    실측에서 `간다` 33건 중 "10만원 아래 간다", "코스피 5000 간다"(9000에서 내려온
    조롱)처럼 하락을 뜻하는 사례가 절반이었고, `진입` 19건 중 절반이 "손실 구간
    진입", "조정 국면 진입"이었다. 세 단어가 전체 탐욕의 54%를 차지했다.
    """
    assert word not in core.GREED_KEYWORDS
    assert word not in core.FEAR_KEYWORDS


@pytest.mark.parametrize(
    "title",
    ["코스피 5000 간다", "10만원 아래 간다", "손실 구간 진입", "나스닥 조정 국면 진입"],
)
def test_ambiguous_titles_produce_no_greed(title):
    """조롱이나 악재를 탐욕으로 세면 안 된다."""
    greed, _ = core.match_keywords(title)
    assert greed == []


def test_keyword_sets_mix_slang_and_plain_vocabulary():
    """은어만으로는 표본이 안 채워진다. 실측 760개에서 은어는 0~1회였다."""
    assert "가즈아" in core.GREED_KEYWORDS and "반등" in core.GREED_KEYWORDS
    assert "돔황챠" in core.FEAR_KEYWORDS and "폭락" in core.FEAR_KEYWORDS


@pytest.mark.parametrize("word", ["매수", "바닥", "조정"])
def test_neutral_words_excluded(word):
    """양쪽에 같이 쓰이는 말은 제외한다("바닥 잡았다" vs "바닥이 안 보인다")."""
    assert word not in core.GREED_KEYWORDS
    assert word not in core.FEAR_KEYWORDS


def test_keyword_sets_do_not_overlap():
    assert not set(core.GREED_KEYWORDS) & set(core.FEAR_KEYWORDS)


@pytest.mark.parametrize(
    "title",
    [
        "코스피 상승종목 148개 하락종목 739개",
        "하락종목 739개 상승종목 148개",
    ],
)
def test_market_tally_is_not_sentiment(title):
    """시세 집계는 글쓴이의 심리를 담지 않는다."""
    assert core.is_tally(title)
    assert core.match_keywords(title) == ([], [])
    stats = core.count_keywords([title])
    assert (stats.greed_total, stats.fear_total) == (0, 0)


def test_opinion_with_both_words_still_counts():
    """집계 문장이 아니면 공포는 그대로 센다.

    같은 제목에서 탐욕은 빠진다. 하락을 말하며 쓴 상승 단어는 심리를 담지 않는다.
    """
    title = "급락하면 무조건 다음날 상승"
    assert not core.is_tally(title)
    greed, fear = core.match_keywords(title)
    assert fear == ["급락"]
    assert greed == []


@pytest.mark.parametrize(
    "title",
    [
        "코스피 5천 가즈아 ㅋㅋㅋㅋㅋ",
        "대우건설 풀매수할땐 진짜 인생 바뀌는줄 알았음 ㅋㅋ",
        "오른다고 영차 하고있네 ㅋㅋㅋㅋㅋ",
        "떡상 기원 ^^",
        "이번엔 신고가 가겠지 ㅎㅎ",
    ],
)
def test_sarcastic_greed_is_not_counted(title):
    """탐욕 표현에 웃음이 붙으면 조롱이다.

    `코스피 5천 가즈아 ㅋㅋㅋ`는 6월 고점 9115에서 33% 내려온 상황의 자조다.
    """
    assert core.is_sarcastic(title)
    greed, _ = core.match_keywords(title)
    assert greed == []
    assert core.count_keywords([title]).greed_total == 0


@pytest.mark.parametrize(
    "title,word",
    [("3일만에 반토막 ㅋㅋㅋㅋ", "반토막"), ("실시간 나스닥대폭락ㅋㅋㅋ", "폭락")],
)
def test_sarcasm_does_not_weaken_fear(title, word):
    """공포 표현에 붙는 웃음은 뜻을 강화한다. 빼면 안 된다."""
    _, fear = core.match_keywords(title)
    assert word in fear
    assert core.count_keywords([title]).fear_total >= 1


@pytest.mark.parametrize("title", ["삼전 가즈아", "코스피 반등 시작", "떡상 간다"])
def test_plain_greed_still_counts(title):
    greed, _ = core.match_keywords(title)
    assert greed


@pytest.mark.parametrize(
    "title",
    ["5% 이상 상승했어요 🎉", "10% 이상 하락했어요 🎉", "20% 이상 급등했어요 🎉"],
)
def test_bot_posts_are_excluded(title):
    """네이버 종목토론실 알림봇. 탐욕 139건 중 24건(17%)이 이 형태였다."""
    assert core.is_bot_post(title)
    assert core.match_keywords(title) == ([], [])
    stats = core.count_keywords([title])
    assert (stats.greed_total, stats.fear_total) == (0, 0)


@pytest.mark.parametrize(
    "title",
    [
        "폭락후 소폭반등...",
        "장초 하락때 풀매수했는데 벌었네요",
        "테마개잡주삼성전기도 급등 급락 반복",
        "그러게 반등 줄때 빠지라니까 몇번을 말하는데..",
        "조선업 전반적 상승 때도 하락인겨?",
        "수익보다손실보고 매도후 주식접었는데 존버했으면-50%",
    ],
)
def test_greed_in_down_context_is_dropped(title):
    """하락을 말하며 쓴 탐욕 단어는 탐욕이 아니다."""
    assert not core.greed_is_credible(title)
    greed, _ = core.match_keywords(title)
    assert greed == []


@pytest.mark.parametrize(
    "title",
    ["오늘은 소폭 반등할 줄 알았는데", "다들 한 번에 상한가치기라도 바라신걸까요"],
)
def test_unfulfilled_expectation_is_not_greed(title):
    assert core.is_unfulfilled(title)
    assert core.match_keywords(title)[0] == []


@pytest.mark.parametrize(
    "title",
    [
        "삼성전기오늘 하한가 가즈아 함 조사불자",
        "가짜 상승인거 아시죠?",
        "자사주매입도 호재가 아니야",
        "제발 코스닥 반등",
        "나스닥 또반등주는척보소",
    ],
)
def test_inverted_greed_is_dropped(title):
    """`하한가 가즈아`는 저격이고 `가짜 상승`은 부정이다."""
    assert core.is_inverted(title)
    assert core.match_keywords(title)[0] == []


@pytest.mark.parametrize(
    "title",
    [
        "코스피 4000대 가즈아",
        "상한가 가즈아 200,000원",
        "내일 떡상 하겠는데?",
        "[속보] 코스닥 급등에 매수 사이드카 발동",
        "445주 추매했읍니다",
        "익절 감사",
    ],
)
def test_genuine_greed_survives_all_filters(title):
    """필터를 아무리 걸어도 진짜 탐욕은 남아야 한다."""
    assert core.greed_is_credible(title)
    assert core.match_keywords(title)[0]


@pytest.mark.parametrize(
    "title,word",
    [
        ("폭락후 소폭반등...", "폭락"),
        ("장초 하락때 풀매수했는데", "하락"),
        ("3일만에 반토막", "반토막"),
    ],
)
def test_fear_survives_mixed_context(title, word):
    """하락 문맥 필터는 탐욕에만 적용한다. 공포는 그대로 세야 한다."""
    _, fear = core.match_keywords(title)
    assert word in fear


# 실측 기준. 2026-07-29 코스피 6053, 코스닥 691.
KOSPI_NOW = 6053.0
KOSDAQ_NOW = 691.0


@pytest.mark.parametrize(
    "title",
    [
        "코스피 4000대 가즈아",
        "코스피 4천이 불장전 수치임?",
        "코스피 5000 간다",
        "코스피 5천 가즈아",
    ],
)
def test_target_below_current_is_mockery(title):
    """지수가 6053인데 4000을 외치는 건 조롱이다.

    6월 고점 9115에서 33% 내려온 상황이라 더 내려보내자는 자조로 읽힌다.
    """
    assert core.targets_below_current(title, KOSPI_NOW)
    assert core.match_keywords(title, KOSPI_NOW)[0] == []


@pytest.mark.parametrize("title", ["코스피 7000 가즈아", "코스피 8천 간다", "코스피 6500 돌파"])
def test_target_above_current_is_genuine(title):
    """같은 문장이 목표가 위쪽이면 진짜 기대다."""
    assert not core.targets_below_current(title, KOSPI_NOW)
    if any(k in title for k in core.GREED_KEYWORDS):
        assert core.match_keywords(title, KOSPI_NOW)[0]


def test_same_sentence_flips_with_current_level():
    """단어만으로는 가릴 수 없다. 현재 수준이 판정을 뒤집는다."""
    title = "코스피 4000대 가즈아"
    assert core.match_keywords(title, 6053.0)[0] == []      # 지금은 조롱
    assert core.match_keywords(title, 3000.0)[0] == ["가즈아"]  # 3000이면 기대


def test_kosdaq_target_uses_its_own_scale():
    """코스닥은 691이라 600은 아래, 900은 위다."""
    assert core.targets_below_current("코스닥 600 중초반까지만 가도 풀매수 때릴만함", KOSDAQ_NOW)
    assert not core.targets_below_current("코스닥 900 가즈아", KOSDAQ_NOW)


def test_percentages_and_quantities_are_not_targets():
    """`10%빠진`, `445주`는 목표 수치가 아니다."""
    assert not core.targets_below_current("445주 추매했읍니다", 200000.0)
    assert not core.targets_below_current("나스닥100이 10%빠진 달", 24876.0)
    assert not core.targets_below_current("2주간 풀매수들해라", 6053.0)


def test_number_far_from_current_scale_is_ignored():
    """연도나 종목코드처럼 자릿수가 다른 숫자는 목표가 아니다."""
    assert not core.targets_below_current("2020년부터 존버", 6053.0)


def test_multiple_numbers_take_the_optimistic_reading():
    """과거 경로를 말하는 문장은 하락 목표가 아니다."""
    title = "코스피는 4천에서 건전한상승으로 4개월동안 2000포인트오른거다"
    assert not core.targets_below_current(title, KOSPI_NOW)


def test_greed_without_numbers_is_unaffected():
    """수치가 없으면 이 규칙은 관여하지 않는다."""
    assert core.match_keywords("코스피 반등 시작", KOSPI_NOW)[0] == ["반등"]
    assert core.match_keywords("가즈아", KOSPI_NOW)[0] == ["가즈아"]


def test_missing_current_level_skips_target_check():
    """현재 수준을 모르면 판정하지 않는다. 종목 현재가가 없을 수 있다."""
    assert core.match_keywords("코스피 4000대 가즈아")[0] == ["가즈아"]
    assert not core.targets_below_current("코스피 4000 가즈아", 0)


@pytest.mark.parametrize(
    "text,expected",
    [
        ("2026.07.29 11:08", date(2026, 7, 29)),   # 네이버
        ("2026-07-29 11:05:15", date(2026, 7, 29)),  # 디시 title 속성
        ("2026-07-23T04:24:16.000Z", date(2026, 7, 23)),  # 아카라이브 datetime
        ("10:57", None),   # 에펨: 시각만 있으면 오늘 (아래에서 today로 검증)
        ("", None),
        ("등록일", None),
    ],
)
def test_parse_post_date_formats(text, expected):
    got = core.parse_post_date(text, today=date(2026, 7, 29))
    if text == "10:57":
        assert got == date(2026, 7, 29)
    else:
        assert got == expected


def test_short_date_rolls_back_year_at_boundary():
    """12월 글을 1월에 보면 연도가 하나 밀린다."""
    assert core.parse_post_date("12.28", today=date(2026, 1, 3)) == date(2025, 12, 28)
    assert core.parse_post_date("01.02", today=date(2026, 1, 3)) == date(2026, 1, 2)


def test_lookback_is_three_days():
    assert core.LOOKBACK_DAYS == 3


def test_us_indices_look_back_further_than_domestic():
    """국내 커뮤니티에서 미국 지수 언급은 드물다. 3일로 자르면 표본 부족이었다.

    국내 지수는 표본이 충분해 종목과 같은 기간을 쓴다. 같은 기간이어야 시장 심리와
    나란히 놓고 읽을 수 있다.
    """
    from fomo_indices import US_INDEX_LOOKBACK_DAYS, INDICES

    assert US_INDEX_LOOKBACK_DAYS > core.LOOKBACK_DAYS
    for index in INDICES:
        window = index.lookback_days or core.LOOKBACK_DAYS
        if index.market == "미국":
            assert window == US_INDEX_LOOKBACK_DAYS
        else:
            assert window == core.LOOKBACK_DAYS


def test_fetch_posts_accepts_lookback_override(monkeypatch):
    """지수 스캔이 더 넓은 기간을 넘길 수 있어야 한다."""
    seen = {}

    def fake_fetch(source, keyword, ticker=None, lookback_days=core.LOOKBACK_DAYS):
        seen[source.key] = lookback_days
        return []

    monkeypatch.setattr(core, "fetch_posts", fake_fetch)
    core.reset_circuits()
    core.scan("코스피", ticker=None, lookback_days=7)
    assert set(seen.values()) == {7}


def test_page_limit_allows_going_deeper_than_default():
    """기간을 못 채우면 더 들어갈 여지를 둔다."""
    naver = next(s for s in core.SOURCES if s.key == "naver")
    assert naver.page_limit > naver.pages
    # 디시는 실측에서 검색 결과가 3페이지에서 소진된다.
    dc = next(s for s in core.SOURCES if s.key == "dc_krstock")
    assert dc.page_limit <= 4
    assert all(s.page_limit >= s.pages for s in core.SOURCES)


@pytest.mark.parametrize(
    "title,expect_greed",
    [("신고가 경신", True), ("신고가 경신 실패", False), ("불장 왔다", True), ("불장은 끝났다", False)],
)
def test_negation_only_targets_reversed_phrases(title, expect_greed):
    greed, _ = core.match_keywords(title)
    assert bool(greed) is expect_greed


def test_evidence_skips_posts_without_keywords():
    """수집한 글 대부분은 키워드가 없어 점수에 영향을 주지 않는다."""
    posts = [
        core.Post("아무 키워드 없는 제목", "https://x/1", "arca"),
        core.Post("삼전 가즈아", "https://x/2", "arca"),
    ]
    items = core.evidence_posts(posts)
    assert [i["title"] for i in items] == ["삼전 가즈아"]
    assert items[0]["url"] == "https://x/2"
    assert items[0]["greed"] == ["가즈아"]


def test_evidence_interleaves_both_directions():
    """한쪽으로만 채우면 목록이 실제 분포를 오해하게 만든다."""
    posts = [core.Post(f"가즈아 {i}") for i in range(5)] + [core.Post("손절 하락")]
    items = core.evidence_posts(posts, limit=4)
    assert any(i["fear"] for i in items)
    assert items[0]["greed"] and items[1]["fear"]


def test_evidence_prefers_posts_with_more_keywords():
    posts = [core.Post("간다"), core.Post("가즈아 떡상 풀매수")]
    items = core.evidence_posts(posts, limit=2)
    assert items[0]["title"] == "가즈아 떡상 풀매수"


def test_evidence_respects_limit():
    posts = [core.Post(f"가즈아 {i}") for i in range(30)]
    assert len(core.evidence_posts(posts, limit=6)) == 6


def test_mixed_post_counts_toward_dominant_side():
    """양쪽 키워드가 다 있으면 많은 쪽으로 분류한다."""
    items = core.evidence_posts([core.Post("가즈아 떡상 고점")])
    assert items[0]["greed"] and items[0]["fear"]
    assert len(items[0]["greed"]) > len(items[0]["fear"])


def test_aggregate_merges_evidence_with_stock_name():
    records = [
        {**_record("삼성전자", "반도체", 6, 6),
         "evidence": [{"title": "가즈아", "url": "u1", "source": "arca", "greed": ["가즈아"], "fear": []}]},
        {**_record("SK하이닉스", "반도체", 6, 6),
         "evidence": [{"title": "손절", "url": "u2", "source": "arca", "greed": [], "fear": ["손절"]}]},
    ]
    evidence = core.aggregate(records)["evidence"]
    assert {i["stock"] for i in evidence} == {"삼성전자", "SK하이닉스"}


def test_index_keys_unchanged():
    keys = {i.key for i in INDICES}
    assert keys == {"kospi", "kosdaq", "sp500", "nasdaq"}
    assert {i.market for i in INDICES} == {"국내", "미국"}


def test_every_index_declares_its_own_label_as_alias():
    """별칭 목록에 대표 이름이 빠지면 가장 많이 쓰이는 표기를 놓친다."""
    for index in INDICES:
        assert index.label in index.aliases
        assert len(index.aliases) >= 2


def test_sp500_includes_colloquial_aliases():
    """S&P500만 검색하면 표본의 3분의 2를 놓친다(실측 71개 -> 병합 202개)."""
    sp500 = next(i for i in INDICES if i.key == "sp500")
    assert "에센피" in sp500.aliases
    assert "SPY" in sp500.aliases


def test_scan_aliases_merges_and_dedupes(monkeypatch):
    """같은 글이 두 별칭에 모두 걸리면 한 번만 센다."""
    calls = []

    def fake_scan(keyword, ticker=None, lookback_days=core.LOOKBACK_DAYS, include_market_wide=False):
        calls.append(keyword)
        titles = {
            "S&P500": ["공통 제목", "에센피 전용 아님"],
            "에센피": ["공통 제목", "에센피 글"],
        }[keyword]
        posts = [core.Post(t, f"https://arca.live/{i}", "arca") for i, t in enumerate(titles)]
        return core.ScanResult(keyword, None, [core.SourceResult("arca", "아카", posts)])

    monkeypatch.setattr(core, "scan", fake_scan)
    merged = core.scan_aliases("S&P500", ["S&P500", "에센피"])
    assert calls == ["S&P500", "에센피"]
    assert merged.keyword == "S&P500"
    assert merged.titles == ["공통 제목", "에센피 전용 아님", "에센피 글"]


def test_scan_aliases_keeps_source_ok_if_any_alias_succeeds(monkeypatch):
    def fake_scan(keyword, ticker=None, lookback_days=core.LOOKBACK_DAYS, include_market_wide=False):
        if keyword == "나스닥":
            return core.ScanResult(
                keyword, None, [core.SourceResult("arca", "아카", [core.Post("글")])]
            )
        return core.ScanResult(keyword, None, [core.SourceResult("arca", "아카", error="차단됨")])

    monkeypatch.setattr(core, "scan", fake_scan)
    merged = core.scan_aliases("나스닥", ["나스닥", "QQQ"])
    assert merged.results[0].error is None
    assert merged.ok_count == 1


def test_scan_aliases_reports_error_when_all_aliases_fail(monkeypatch):
    def fake_scan(keyword, ticker=None, lookback_days=core.LOOKBACK_DAYS, include_market_wide=False):
        return core.ScanResult(keyword, None, [core.SourceResult("arca", "아카", error="차단됨")])

    monkeypatch.setattr(core, "scan", fake_scan)
    merged = core.scan_aliases("코스피", ["코스피", "KOSPI"])
    assert merged.results[0].error == "차단됨"
    assert merged.ok_count == 0


def test_scan_result_aggregates_titles_in_source_order():
    results = [
        core.SourceResult("a", "A", [core.Post("가즈아")]),
        core.SourceResult("b", "B", error="차단됨"),
        core.SourceResult("c", "C", [core.Post("손절")]),
    ]
    scan = core.ScanResult("삼성전자", "005930", results)
    assert scan.titles == ["가즈아", "손절"]
    assert scan.ok_count == 2


def test_analyze_survives_partial_failure():
    results = [
        core.SourceResult("a", "A", [core.Post("가즈아 영차"), core.Post("떡상")]),
        core.SourceResult("b", "B", error="차단됨"),
    ]
    report = core.analyze(core.ScanResult("삼성전자", "005930", results))
    assert report.total_posts == 2
    assert report.stats.greed_total == 3
    assert report.score > 50


def test_display_width_counts_hangul_as_two_columns():
    assert display_width("주식") == 4
    assert display_width("ab") == 2
    assert display_width(pad("주식", 10)) == 10


def test_render_shows_both_success_and_failure_rows():
    results = [
        core.SourceResult("a", "네이버 증권 종목토론실", [core.Post("가즈아")]),
        core.SourceResult("b", "에펨코리아 주식·재테크", error="차단됨 (HTTP 430)"),
    ]
    text = render(core.analyze(core.ScanResult("삼성전자", "005930", results)))
    assert "삼성전자 (005930)" in text
    assert "1개" in text
    assert "차단됨 (HTTP 430) (skip)" in text
    assert "FOMO 점수" in text


# ── 반응(조회수/추천수) 기반 가중 ────────────────────────────────────────────

@pytest.mark.parametrize(
    "text,expected",
    [
        ("1,234", 1234),
        ("1.2만", 12000),
        ("12 - 3", 12),      # 뽐뿌 추천-반대 표기
        ("[ 15 ]", 15),      # 네이버·에펨 댓글 수
        ("", None),
        ("-", None),
        (None, None),
    ],
)
def test_parse_count_reads_list_cell_numbers(text, expected):
    assert core.parse_count(text) == expected


def _hot(views=None, votes=None, comments=None, title="글"):
    return core.Post(title, None, "arca", None, views, votes, comments)


def test_post_weight_defaults_to_one_when_metrics_missing():
    """수치를 못 읽은 글은 버리지 않는다. 셀렉터가 깨졌을 때 표본이 통째로 사라진다."""
    assert core.post_weight(_hot(), 100.0, 1.0) == 1


def test_post_weight_boosts_widely_read_posts():
    assert core.post_weight(_hot(views=400), 100.0, None) == core.HOT_WEIGHT


def test_post_weight_boosts_upvoted_posts():
    assert core.post_weight(_hot(views=10, votes=30), 100.0, 1.0) == core.HOT_WEIGHT


def test_post_weight_drops_unread_posts_without_reactions():
    """조회수도 반응도 없는 글은 여론이 아니라 혼잣말이다."""
    assert core.post_weight(_hot(views=10, votes=0, comments=0), 100.0, 1.0) == 0


def test_post_weight_keeps_low_view_post_that_drew_replies():
    assert core.post_weight(_hot(views=10, votes=0, comments=4), 100.0, 1.0) == 1


def test_post_weight_ignores_median_from_thin_sample():
    """중위값이 없으면(표본 부족) 가중도 없다."""
    assert core.post_weight(_hot(views=1), None, None) == 1


def test_weighted_titles_scales_within_each_source():
    """소스를 섞어 기준을 만들면 조회수 높은 사이트 글만 화제글이 된다."""
    quiet = core.SourceResult(
        "dc", "디시", [_hot(views=v, votes=0, comments=0, title=f"조용{v}") for v in (40, 45, 50, 50, 55, 60, 60, 65)]
    )
    loud = core.SourceResult(
        "ppomppu", "뽐뿌", [_hot(views=v, votes=0, comments=1, title=f"시끌{v}") for v in (700, 750, 800, 800, 850, 900, 900, 950)]
    )
    sample = core.weighted_titles([quiet, loud])
    # 뽐뿌 글이 조회수만으로 전부 화제글이 되지 않는다.
    assert sample.hot == 0
    assert sample.dropped == 0
    assert sample.kept == 16


def test_weighted_titles_repeats_hot_post_titles():
    posts = [_hot(views=50, votes=0, comments=1, title=f"조용{i}") for i in range(7)]
    posts.append(_hot(views=600, votes=0, comments=1, title="화제글"))
    sample = core.weighted_titles([core.SourceResult("dc", "디시", posts)])
    assert sample.hot == 1
    assert sample.titles.count("화제글") == core.HOT_WEIGHT
    assert sample.titles.count("조용0") == 1


def test_analyze_weights_greed_from_popular_posts():
    """인기글이 방향을 끌고 간다. 조회수 없는 글이 같은 표를 가지면 왜곡된다."""
    posts = [_hot(views=50, votes=0, comments=1, title=f"손절했다 {i}") for i in range(7)]
    posts.append(_hot(views=900, votes=0, comments=1, title="가즈아 떡상"))
    report = core.analyze(core.ScanResult("삼성전자", None, [core.SourceResult("dc", "디시", posts)]))
    assert report.hot_posts == 1
    assert report.stats.greed_total == 2 * core.HOT_WEIGHT
    assert report.stats.fear_total == 7


def test_evidence_prefers_posts_with_more_reactions():
    posts = [
        _hot(views=30, votes=0, comments=0, title="가즈아 조용한 글"),
        _hot(views=900, votes=40, comments=20, title="가즈아 화제글"),
    ]
    items = core.evidence_posts(posts, limit=2)
    assert items[0]["title"] == "가즈아 화제글"
    assert items[0]["votes"] == 40


def test_prefiltered_popular_source_counts_every_post_as_hot():
    """인기글 목록은 추천 중위가 이미 높아 상대 기준으로는 아무것도 안 잡힌다."""
    posts = [core.Post(f"폭락 {i}", None, "fmkorea_pop", None, None, v, 20)
             for i, v in enumerate((70, 80, 92, 92, 100, 120, 140, 176))]
    sample = core.weighted_titles([core.SourceResult("fmkorea_pop", "에펨 인기글", posts)])
    assert sample.hot == len(posts)
    assert sample.dropped == 0
    assert sample.titles.count("폭락 0") == core.HOT_WEIGHT


def test_naver_parser_reads_counts_when_title_has_reply_marker():
    """제목 셀의 댓글 수(`[ 3 ]`)도 tah 클래스를 써서 위치로 세면 값이 밀린다."""
    html = """
    <table><tbody>
      <tr>
        <td><span class="tah">2026.07.30 15:32</span></td>
        <td class="title"><a href="/item/board_read.naver?code=046970&nid=1" title="고점에 물린 분들에게!">고점에</a></td>
        <td class="p11">돈이다</td>
        <td><span class="tah">36</span></td>
        <td><strong class="tah">2</strong></td>
        <td><strong class="tah">1</strong></td>
      </tr>
      <tr>
        <td><span class="tah">2026.07.30 13:37</span></td>
        <td class="title"><a href="/item/board_read.naver?code=046970&nid=2" title="주식 25년차..">주식</a>
          <span class="tah">[ 3 ]</span></td>
        <td class="p11">워드</td>
        <td><span class="tah">97</span></td>
        <td><strong class="tah">0</strong></td>
        <td><strong class="tah">4</strong></td>
      </tr>
    </tbody></table>
    """
    soup = BeautifulSoup(html, "lxml")
    rows = core._titles_naver(soup, 'td.title a[href*="board_read.naver"]')
    assert [(r.views, r.votes) for r in rows] == [(36, 2), (97, 0)]
    assert rows[1].comments == 3


def test_dcinside_parser_reads_view_and_recommend_cells():
    html = """
    <table><tbody><tr class="ub-content">
      <td class="gall_tit ub-word"><a href="/mgallery/board/view/?id=krstock&no=1">코스피 가즈아</a></td>
      <td class="gall_date" title="2026-07-30 15:26:25">15:26</td>
      <td class="gall_count">10,651</td>
      <td class="gall_recommend">55</td>
    </tr></tbody></table>
    """
    rows = core._titles_dcinside(BeautifulSoup(html, "lxml"), core._DC_SELECTOR)
    assert (rows[0].views, rows[0].votes) == (10651, 55)


def test_arca_parser_reads_view_and_rate_cells():
    html = """
    <div class="list-table">
      <a class="vrow" href="/b/stock/1">
        <span class="vcol col-title">코스피 반등</span>
        <span class="vcol col-time"><time datetime="2026-07-30T06:00:00.000Z">15:00</time></span>
        <span class="vcol col-view">1707</span>
        <span class="vcol col-rate">19</span>
      </a>
    </div>
    """
    rows = core._titles_arca(BeautifulSoup(html, "lxml"), "div.list-table a.vrow")
    assert (rows[0].views, rows[0].votes) == (1707, 19)


def test_ppomppu_parser_reads_view_cell():
    html = """
    <table><tbody><tr class="baseList">
      <td class="baseList-space"><a class="baseList-title" href="view.php?id=stock&no=1"><span>코스피 폭락</span></a>
        <span class="baseList-c">2</span></td>
      <td class="baseList-space"><time class="baseList-time">15:21:09</time></td>
      <td class="baseList-space baseList-rec"></td>
      <td class="baseList-space baseList-views">751</td>
    </tr></tbody></table>
    """
    rows = core._titles_css(BeautifulSoup(html, "lxml"), "a.baseList-title span")
    assert rows[0].views == 751
    assert rows[0].votes is None       # 추천 칸이 비어 있으면 0이 아니라 미지수다
    assert rows[0].comments == 2


def test_fmkorea_search_parser_separates_views_from_votes():
    """조회수와 추천수가 같은 td.m_no를 쓰고 추천에만 m_no_voted가 붙는다."""
    html = """
    <table><tbody><tr>
      <td class="title"><a class="hx" href="/index.php?document_srl=1">코스피 <strong>반등</strong>하냐</a>
        <a class="replyNum" href="#c">3</a></td>
      <td class="time">15:25</td>
      <td class="m_no">120</td>
      <td class="m_no m_no_voted">2</td>
    </tr></tbody></table>
    """
    rows = core._titles_css(BeautifulSoup(html, "lxml"), "td.title a.hx")
    assert (rows[0].views, rows[0].votes, rows[0].comments) == (120, 2, 3)


def test_fmkorea_pop_parser_reads_vote_badge():
    html = """
    <ul><li class="li">
      <a class="pc_voted_count"><span class="label">추천</span><span class="count">48</span></a>
      <h3 class="title"><a href="/index.php?document_srl=1"><span class="ellipsis-target">코스피 떡상</span>
        <span class="comment_count">[15]</span></a></h3>
      <span class="regdate">15:26</span>
    </li></ul>
    """
    rows = core._titles_fmkorea_pop(BeautifulSoup(html, "lxml"), "h3.title a")
    assert rows[0].votes == 48
    assert rows[0].comments == 15
    assert rows[0].views is None
