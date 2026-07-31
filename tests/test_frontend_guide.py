from pathlib import Path


SRC = Path(__file__).parents[1] / "frontend" / "src"
GUIDE = SRC / "TabGuide.jsx"


def test_guide_exists_for_every_tab():
    """세 탭이 각각 다른 지표를 쓰므로 설명도 탭마다 다르다."""
    source = GUIDE.read_text(encoding="utf-8")

    for tab_id in ("spread", "fomo", "backtest"):
        assert f"{tab_id}:" in source, tab_id


def test_guide_stays_out_of_the_way():
    """평소에는 아이콘만 두고 눌렀을 때만 펼친다.

    화면에 설명을 상시 노출하면 32행을 훑는 밀도를 해친다.
    """
    source = GUIDE.read_text(encoding="utf-8")

    assert "aria-expanded" in source
    assert "fixed" in source


def test_guide_explains_the_terms_a_newcomer_hits_first():
    """Z-Score와 커플링을 모르면 첫 화면에서 아무것도 읽을 수 없다."""
    source = GUIDE.read_text(encoding="utf-8")

    assert "Z-Score" in source
    assert "커플링" in source


def test_header_mounts_the_guide():
    app = (SRC / "App.jsx").read_text(encoding="utf-8")

    assert "TabGuide" in app
