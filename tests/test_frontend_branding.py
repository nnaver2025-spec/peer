from pathlib import Path


ROOT = Path(__file__).parents[1]
NAME = "엇박"


def test_screen_title_and_browser_tab_share_the_name():
    """화면 제목과 브라우저 탭 제목이 어긋나면 즐겨찾기에 옛 이름이 남는다."""
    app = (ROOT / "frontend" / "src" / "App.jsx").read_text(encoding="utf-8")
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")

    assert NAME in app
    assert f"<title>{NAME}" in html
    assert "Peer Spread Tracker" not in app
    assert "Peer Spread Tracker" not in html


def test_header_keeps_the_freshness_signal():
    """이름을 바꿔도 갱신 상태는 남는다. 크론이 멈췄을 때 유일한 신호다."""
    app = (ROOT / "frontend" / "src" / "App.jsx").read_text(encoding="utf-8")

    assert "<Freshness" in app
