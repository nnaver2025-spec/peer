"""섹터별 뉴스 논조 검증. 네트워크를 타지 않는다."""

from datetime import datetime, timedelta, timezone

import fomo_news as news


def _item(title: str, published: datetime | None = None, source: str = "연합뉴스"):
    positive, negative = news.match_words(title)
    return news.NewsItem(
        title=title,
        url="https://news/1",
        source=source,
        published=published or datetime.now(timezone.utc),
        positive=positive,
        negative=negative,
    )


# --- 역접 처리 -------------------------------------------------------------


def test_concessive_keeps_conclusion_only():
    """`어닝 서프라이즈에도 목표가 하향`은 부정 기사다.

    기사 제목의 결론은 뒤에 온다. 그대로 세면 긍정과 부정이 상쇄된다.
    """
    positive, negative = news.match_words(
        "한화시스템, 2분기 어닝 서프라이즈에도 목표가 하향 이유는?"
    )
    assert positive == []
    assert negative == ["목표가 하향"]


def test_concessive_handles_jiman():
    positive, negative = news.match_words("역대급 실적 냈지만 주가는 또 주춤")
    assert positive == []
    assert negative == ["주춤"]


def test_no_concessive_keeps_whole_title():
    positive, negative = news.match_words("SK하이닉스 역대 최대 실적에 삼전 상승 출발")
    assert positive == ["상승"]
    assert negative == []


def test_nullified_positive_is_dropped():
    """`실적 호재도 소용 없다`는 호재 기사가 아니다."""
    positive, negative = news.match_words("실적 호재도 소용 없다, 반도체주 언제까지")
    assert positive == []


def test_nullified_covers_an_tonghae():
    positive, _ = news.match_words("어닝 서프라이즈도 안 통했다…고평가 시대 끝나나")
    assert positive == []


def test_mixed_title_leans_to_dominant_side():
    """양쪽이 다 있으면 많은 쪽이 방향이다."""
    item = _item("반도체 급락에 日 하락…中 홍콩은 상승")
    assert item.side == "negative"


def test_untagged_item_has_no_side():
    assert _item("삼성전자 신제품 공개 행사 개최").side is None


# --- 집계 -----------------------------------------------------------------


def test_summarize_scores_when_sample_is_thick():
    items = [_item("반도체 급락") for _ in range(6)] + [_item("반도체 상승") for _ in range(4)]
    result = news.summarize("반도체", items)
    assert result.negative_total == 6
    assert result.positive_total == 4
    assert result.score is not None
    assert result.score < 50


def test_summarize_withholds_score_when_thin():
    """표본이 얇으면 점수를 내지 않는다. 커뮤니티 지표와 같은 원칙이다."""
    result = news.summarize("식품", [_item("식품 상승")])
    assert result.score is None
    assert result.label == "표본 부족"


def test_count_skips_nullified_titles():
    """무력화된 호재는 집계에서도 빠진다. 목록과 점수가 어긋나면 안 된다."""
    items = [_item("실적 호재도 소용 없다") for _ in range(10)]
    result = news.summarize("반도체", items)
    assert result.positive_total == 0


# --- payload --------------------------------------------------------------


def test_payload_splits_positive_and_negative():
    items = [_item("조선 수주 호재"), _item("조선 주가 급락"), _item("행사 개최 안내")]
    out = news.payload([news.summarize("조선", items)])
    sector = out["sectors"][0]
    assert len(sector["positive"]) == 1
    assert len(sector["negative"]) == 1
    # 태그 없는 기사는 담지 않는다. 뉴스는 태그율이 높아 그것만으로 충분하다.
    assert sector["total"] == 3


def test_payload_sorts_by_recency():
    now = datetime.now(timezone.utc)
    items = [
        _item("조선 급락 어제", now - timedelta(days=1)),
        _item("조선 급락 방금", now),
    ]
    out = news.payload([news.summarize("조선", items)])
    titles = [i["title"] for i in out["sectors"][0]["negative"]]
    assert titles[0] == "조선 급락 방금"


def test_payload_limits_each_side():
    items = [_item(f"조선 급락 {i}") for i in range(20)]
    out = news.payload([news.summarize("조선", items)])
    assert len(out["sectors"][0]["negative"]) == news.EVIDENCE_PER_SIDE


def test_payload_overall_ignores_failed_sectors():
    """수집이 막힌 섹터는 전체 점수에 넣지 않는다."""
    ok = news.summarize("반도체", [_item("반도체 급락") for _ in range(10)])
    failed = news.summarize("우주", [], error="HTTP 429")
    out = news.payload([ok, failed])
    assert out["negative_total"] == 10
    assert out["score"] is not None
    assert out["sectors"][1]["error"] == "HTTP 429"


def test_payload_withholds_overall_when_thin():
    out = news.payload([news.summarize("식품", [_item("식품 상승")])])
    assert out["score"] is None
    assert out["label"] == "표본 부족"


def test_payload_keeps_lookback_metadata():
    out = news.payload([])
    assert out["lookback_days"] == news.LOOKBACK_DAYS
    assert out["min_hits"] == news.MIN_HITS


# --- 지수 뉴스 논조 --------------------------------------------------------


def test_index_query_uses_jisu_suffix():
    """지수는 `주가`가 아니라 `지수`로 검색한다.

    실측에서 `코스닥 주가`는 태그 49건, `코스닥 지수`는 69건이었다. S&P500은
    44건 -> 100건으로 벌어졌다. `주가`를 붙이면 개별 종목 기사가 섞인다.
    """
    seen = {}

    class FakeResponse:
        status_code = 200
        text = "<rss><channel></channel></rss>"

    class FakeSession:
        def get(self, url, **kwargs):
            seen["url"] = url
            return FakeResponse()

    news.fetch_sector("코스닥", FakeSession(), suffix="지수")
    assert "%EC%A7%80%EC%88%98" in seen["url"]      # '지수'
    assert "when%3A3d" in seen["url"]


def test_index_query_respects_custom_lookback():
    """미국 지수는 7일을 본다. 기본값(3일)을 덮어쓸 수 있어야 한다."""
    seen = {}

    class FakeResponse:
        status_code = 200
        text = "<rss><channel></channel></rss>"

    class FakeSession:
        def get(self, url, **kwargs):
            seen["url"] = url
            return FakeResponse()

    news.fetch_sector("나스닥", FakeSession(), suffix="지수", lookback_days=7)
    assert "when%3A7d" in seen["url"]


def test_tone_payload_shape():
    """지수 카드가 쓰는 요약에는 점수와 양쪽 기사가 들어간다."""
    items = [_item("코스닥 지수 급락"), _item("코스닥 반등 기대감")] * 5
    tone = news.tone_payload(news.summarize("코스닥", items))
    assert tone["score"] is not None
    assert tone["hits"] == tone["positive_total"] + tone["negative_total"]
    assert tone["positive"] and tone["negative"]
    assert tone["error"] is None


def test_tone_payload_passes_error_through():
    tone = news.tone_payload(news.summarize("코스닥", [], error="HTTP 429"))
    assert tone["error"] == "HTTP 429"
    assert tone["score"] is None


# --- 파서 -----------------------------------------------------------------


def test_fetch_drops_stale_articles(monkeypatch):
    """when:3d를 걸어도 오래된 기사가 섞이면 버린다.

    날짜 필터 없이 받으면 기사 나이 중위가 190일, 최대 1686일이었다.
    """
    old = (datetime.now(timezone.utc) - timedelta(days=400)).strftime(
        "%a, %d %b %Y %H:%M:%S %z"
    )
    fresh = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S %z")
    xml = f"""<rss><channel>
      <item><title>반도체 급락</title><link>https://n/1</link>
        <pubDate>{fresh}</pubDate><source>연합뉴스</source></item>
      <item><title>반도체 상승</title><link>https://n/2</link>
        <pubDate>{old}</pubDate><source>한겨레</source></item>
    </channel></rss>"""

    class FakeResponse:
        status_code = 200
        text = xml

    class FakeSession:
        def get(self, *args, **kwargs):
            return FakeResponse()

    items, error = news.fetch_sector("반도체", FakeSession())
    assert error is None
    assert [i.title for i in items] == ["반도체 급락"]
    assert items[0].source == "연합뉴스"


def test_fetch_reports_http_error():
    class FakeResponse:
        status_code = 429
        text = ""

    class FakeSession:
        def get(self, *args, **kwargs):
            return FakeResponse()

    items, error = news.fetch_sector("반도체", FakeSession())
    assert items == []
    assert error == "HTTP 429"


def test_fetch_survives_network_failure():
    class FakeSession:
        def get(self, *args, **kwargs):
            raise TimeoutError("timed out")

    items, error = news.fetch_sector("반도체", FakeSession())
    assert items == []
    assert error == "TimeoutError"


def test_query_includes_recency_filter(monkeypatch):
    """검색어에 when:3d가 빠지면 오래된 기사가 들어온다."""
    seen = {}

    class FakeResponse:
        status_code = 200
        text = "<rss><channel></channel></rss>"

    class FakeSession:
        def get(self, url, **kwargs):
            seen["url"] = url
            return FakeResponse()

    news.fetch_sector("반도체", FakeSession())
    assert "when%3A3d" in seen["url"] or "when:3d" in seen["url"]
