"""섹터 뉴스가 그 섹터 기사만 담는지 검사한다.

구글 뉴스는 검색어를 한 덩어리로 보고 관련도 순으로 돌려준다. 걸러내지 않으면
`광통신 주가` 27건 중 13건이 무관했고, 바이오 종목인 펩트론과 뉴욕증시 지수
기사까지 광통신 논조에 반영됐다. 점수는 제목 단어를 세어 내므로 무관한 기사가
섞이면 그 섹터 판단이 곧바로 왜곡된다.

네트워크를 타지 않는다. 필터 함수와 검색어 매핑만 본다.
"""

import fomo_news


def test_allowlist_covers_members_and_sector_words():
    """구성 종목명과 섹터 고유어가 모두 통과 대상이어야 한다."""
    allow = fomo_news.sector_allowlist("광통신", ("대한광통신", "RFHIC"))

    assert "대한광통신" in allow
    assert "RFHIC" in allow
    assert "광통신" in allow
    assert "광케이블" in allow


def test_allowlist_has_no_duplicates():
    """종목명이 섹터 고유어와 겹칠 수 있다. 중복은 무의미한 비교를 늘린다."""
    allow = fomo_news.sector_allowlist("반도체", ("반도체", "SK하이닉스"))

    assert len(allow) == len(set(allow))


def test_unknown_sector_falls_back_to_its_own_name():
    """새 섹터가 생겨도 최소한 섹터명으로는 걸러야 한다."""
    allow = fomo_news.sector_allowlist("신규섹터")

    assert allow == ("신규섹터",)


def test_offtopic_titles_are_rejected():
    """실제로 섞여 들어온 제목들. 이 조합이 통과하면 필터가 무력하다."""
    allow = fomo_news.sector_allowlist("광통신", ("대한광통신", "RFHIC", "KMW"))

    offtopic = (
        "펩트론 주가 급반등…장후 NXT서 15만원 돌파하기도, 29일 흐름 '이목'",
        "뉴욕증시 S&P500 '상승'...헬스 섹터 '뛰고' vs 테크 섹터 '뚝'",
        "두산에너빌리티, 주가 급락장에 7만빌리티 다시 붕괴…원전주 동반 약세",
        "램리서치 7.65% 급등…ARM·퀄컴은 하락했다",
    )
    for title in offtopic:
        assert not any(word in title for word in allow), f"걸러지지 않았다: {title}"


def test_ontopic_titles_pass():
    """섹터 기사는 남아야 한다. 너무 좁으면 표본이 사라진다."""
    allow = fomo_news.sector_allowlist("광통신", ("대한광통신",))

    ontopic = (
        "대한광통신 주가, 7월 31일 장중 8,260원 15.36% 상승",
        "中 광통신 이노라이트, 홍콩 증시서 9조 8천억 원 조달",
    )
    for title in ontopic:
        assert any(word in title for word in allow), f"잘못 걸러졌다: {title}"


def test_misleading_sector_names_have_their_own_queries():
    """그룹 이름이 곧 좋은 검색어는 아니다.

    `AI인프라 주가`는 미국 AI 종목만 돌려줘 우리 종목 기사가 49건 중 2건이었다.
    이 섹터의 실제 구성은 변압기·전력기기, EPC 건설, 원전, 신재생이다.
    `IP 주가`는 게임 IP와 International Paper를 끌어왔다.
    """
    assert "AI인프라" in fomo_news.SECTOR_QUERIES
    assert "IP" in fomo_news.SECTOR_QUERIES

    # 대체 검색어에 원래 이름을 그대로 두면 같은 문제가 반복된다.
    for sector, queries in fomo_news.SECTOR_QUERIES.items():
        assert sector not in queries, f"{sector}의 대체 검색어가 원래 이름과 같다"
        assert queries, f"{sector}의 대체 검색어가 비어 있다"


def test_every_dashboard_sector_has_filter_words():
    """화면에 뜨는 섹터에는 모두 걸러낼 어휘가 있어야 한다."""
    import json
    from pathlib import Path

    payload = Path(__file__).parents[1] / "frontend" / "public" / "dashboard_data.json"
    sectors = {g["sector"] for g in json.loads(payload.read_text(encoding="utf-8"))["groups"]}

    missing = [s for s in sectors if s not in fomo_news.SECTOR_WORDS]
    assert not missing, f"섹터 어휘가 없다: {missing}"
