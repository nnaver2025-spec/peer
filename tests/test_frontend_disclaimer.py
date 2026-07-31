from pathlib import Path


SRC = Path(__file__).parents[1] / "frontend" / "src"


def test_disclaimer_component_exists():
    """면책 문구는 한 곳에서 관리한다. 탭마다 적으면 문구가 갈린다."""
    assert (SRC / "Disclaimer.jsx").exists()


def test_every_tab_shows_the_disclaimer():
    """어느 탭으로 들어와도 보여야 한다. 링크는 탭 단위로 공유된다."""
    for name in ("App.jsx", "FomoTab.jsx", "BacktestTab.jsx"):
        source = (SRC / name).read_text(encoding="utf-8")
        assert "Disclaimer" in source, name


def test_disclaimer_states_it_is_not_investment_advice():
    """투자 권유가 아니라는 점과 책임 소재를 밝힌다."""
    source = (SRC / "Disclaimer.jsx").read_text(encoding="utf-8")

    assert "투자 권유가 아닙니다" in source
    assert "책임" in source
