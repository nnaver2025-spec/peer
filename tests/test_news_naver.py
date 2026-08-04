"""네이버 뉴스 API 경로. 네트워크를 타지 않고 가짜 응답으로 확인한다.

스크레이핑은 쓸 수 없다. news.naver.com과 search.naver.com 모두 robots.txt가
`User-agent: * / Disallow: /`로 전면 차단하고 AI 목적 수집을 명시적으로 금지한다.
그래서 공식 검색 API만 쓴다(하루 25,000회 무료).
"""

import os
from datetime import datetime, timezone
from email.utils import format_datetime

import pytest

import fomo_news


def _recent_pubdate() -> str:
    return format_datetime(datetime.now(timezone.utc))



class _Res:
    status_code = 200

    def __init__(self, items):
        self._items = items

    def json(self):
        return {"items": self._items}


class _Session:
    def __init__(self, items):
        self._items = items

    def get(self, *args, **kwargs):
        return _Res(self._items)


@pytest.fixture
def keys(monkeypatch):
    monkeypatch.setenv(fomo_news.NAVER_ID_ENV, "id")
    monkeypatch.setenv(fomo_news.NAVER_SECRET_ENV, "secret")


def test_skipped_without_keys(monkeypatch):
    """키가 없으면 오류가 아니라 비활성이다.

    구글만으로도 지표가 나와야 한다. 여기서 예외를 던지면 키를 넣기 전까지
    뉴스 수집 전체가 멈춘다.
    """
    monkeypatch.delenv(fomo_news.NAVER_ID_ENV, raising=False)
    monkeypatch.delenv(fomo_news.NAVER_SECRET_ENV, raising=False)

    items, error = fomo_news.fetch_naver("광통신 주가")

    assert items == []
    assert error is None


def test_blank_keys_count_as_missing(monkeypatch):
    """CI에서 시크릿이 비어 있으면 빈 문자열이 들어온다."""
    monkeypatch.setenv(fomo_news.NAVER_ID_ENV, "   ")
    monkeypatch.setenv(fomo_news.NAVER_SECRET_ENV, "")

    assert fomo_news.naver_credentials() is None


def test_title_markup_is_stripped(keys):
    """네이버는 검색어에 <b>를 씌우고 엔티티를 그대로 준다.

    태그가 남으면 감정 단어 매칭이 어긋나고 중복 제거도 실패한다.
    """
    session = _Session(
        [
            {
                "title": "대한<b>광통신</b> 주가 &quot;급등&quot;",
                "originallink": "https://www.ggilbo.com/1",
                "link": "https://n.news.naver.com/1",
                "pubDate": _recent_pubdate(),
            }
        ]
    )

    items, error = fomo_news.fetch_naver("광통신 주가", session=session)

    assert error is None
    assert len(items) == 1
    assert "<b>" not in items[0].title
    assert '"급등"' in items[0].title
    # 태그를 지웠으니 감정 단어가 잡혀야 한다.
    assert "급등" in items[0].positive


def test_uses_original_link_not_naver_relay(keys):
    """originallink가 언론사 원문이고 link는 네이버 중계다."""
    session = _Session(
        [
            {
                "title": "광통신 장비 수주",
                "originallink": "https://www.ggilbo.com/1",
                "link": "https://n.news.naver.com/1",
                "pubDate": _recent_pubdate(),
            }
        ]
    )

    items, _ = fomo_news.fetch_naver("광통신 주가", session=session)

    assert items[0].url == "https://www.ggilbo.com/1"
    assert items[0].source == "ggilbo.com"


def test_allowlist_and_cutoff_apply(keys):
    """섹터 필터와 기간 컷이 네이버 쪽에도 걸려야 한다.

    구글은 `when:3d`를 쿼리에 넣지만 네이버 API에는 그 문법이 없다.
    직접 자르지 않으면 2021년 기사가 오늘 논조로 섞인다.
    """
    session = _Session(
        [
            {
                "title": "대한광통신 급등",
                "originallink": "https://a.com/1",
                "link": "https://n.news.naver.com/1",
                "pubDate": _recent_pubdate(),
            },
            {
                "title": "펩트론 주가 급반등",
                "originallink": "https://b.com/2",
                "link": "https://n.news.naver.com/2",
                "pubDate": _recent_pubdate(),
            },
            {
                "title": "대한광통신 옛 기사",
                "originallink": "https://c.com/3",
                "link": "https://n.news.naver.com/3",
                "pubDate": "Mon, 01 Feb 2021 09:00:00 +0900",
            },
        ]
    )
    allow = fomo_news.sector_allowlist("광통신", ("대한광통신",))

    items, _ = fomo_news.fetch_naver("광통신 주가", session=session, allow=allow)

    titles = [i.title for i in items]
    assert titles == ["대한광통신 급등"]


def test_dedupe_key_matches_across_sources():
    """구글은 제목 끝에 ` - 매체명`을 붙이고 네이버는 붙이지 않는다.

    그대로 비교하면 같은 기사가 두 번 세어져 논조가 부풀려진다.
    """
    google = "대한광통신 주가, 급등세... 핵심 사업 살펴보니 - 금강일보"
    naver = "대한광통신 주가, 급등세… 핵심 사업 살펴보니"

    assert fomo_news._dedupe_key(google) == fomo_news._dedupe_key(naver)


def test_dedupe_key_keeps_different_articles_apart():
    """너무 뭉개면 다른 기사가 하나로 합쳐져 표본이 줄어든다."""
    a = fomo_news._dedupe_key("대한광통신 주가 급등 - 금강일보")
    b = fomo_news._dedupe_key("대한광통신 주가 급락 - 금강일보")

    assert a != b
