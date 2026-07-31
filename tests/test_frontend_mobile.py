from pathlib import Path


SRC = Path(__file__).parents[1] / "frontend" / "src"
APP = SRC / "App.jsx"
BACKTEST = SRC / "BacktestTab.jsx"


def test_filters_are_reachable_on_mobile():
    """모바일에서 필터를 여는 경로가 있어야 한다.

    사이드바가 lg:flex로 숨겨져 있어서 390px 화면에서는 보기/섹터 필터
    전부에 도달할 수 없었다. 32개 그룹을 스크롤로만 훑어야 했다.
    """
    source = APP.read_text(encoding="utf-8")

    assert 'data-testid="mobile-filter-toggle"' in source
    assert 'data-testid="mobile-filter-sheet"' in source


def test_backtest_table_can_scroll_sideways():
    """백테스트 표는 모바일에서 407px로 넘쳐 마지막 열이 잘렸다.

    이 탭에는 가로 스크롤 컨테이너가 없어서 중위 회복률이 사라졌다.
    """
    source = BACKTEST.read_text(encoding="utf-8")

    assert "overflow-x-auto" in source


def test_coupling_label_collapses_on_narrow_lists():
    """390px 화면에서 5개 열을 담으려면 커플링 라벨이 자리를 너무 먹는다.

    라벨 텍스트가 77px를 차지해 RS가 밀려났다. 등급 막대만 남기고 이름은
    셀 title로 옮긴다.
    """
    source = (SRC / "GroupTable.jsx").read_text(encoding="utf-8")

    assert '@max-[420px]:hidden' in source
    assert 'coupling.label' in source
