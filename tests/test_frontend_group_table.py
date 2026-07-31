from pathlib import Path


GROUP_TABLE = Path(__file__).parents[1] / "frontend" / "src" / "GroupTable.jsx"


def test_table_shrinks_instead_of_switching_layout():
    """좁아질 때 다른 레이아웃으로 갈아타지 않고 표 자체가 줄어든다."""
    source = GROUP_TABLE.read_text(encoding="utf-8")

    assert 'data-testid="group-table"' in source
    assert 'data-testid="compact-group-list"' not in source


def test_table_has_no_fixed_min_width():
    """900px 최소 폭이 남아 있으면 패널이 열릴 때 오른쪽 열이 잘린다."""
    source = GROUP_TABLE.read_text(encoding="utf-8")

    assert 'min-w-[900px]' not in source


def test_columns_shrink_with_container_width():
    """Z-Score/추이 열과 셀 여백이 컨테이너 폭에 따라 함께 줄어야 한다."""
    source = GROUP_TABLE.read_text(encoding="utf-8")

    assert '@container' in source
    # 좁은 컨테이너에서 줄어드는 폭/여백 지정이 있어야 한다.
    assert '@max-[1000px]:' in source


def test_trend_column_folds_before_right_side_metrics():
    """더 좁아지면 추이를 접어서 커플링/주도주/RS를 남긴다.

    1200px 창에서 패널이 열리면 목록이 598px까지 줄어드는데, 8개 열을 모두
    유지하면 오른쪽이 잘린다. 판단에 덜 쓰이는 추이를 먼저 접는다.
    """
    source = GROUP_TABLE.read_text(encoding="utf-8")

    assert '@max-[700px]:hidden' in source


def test_spread_column_folds_on_very_narrow_lists():
    """900px 창에서 패널이 열리면 목록이 498px까지 줄어든다.

    Spread는 Z-Score와 같은 괴리를 다른 단위로 보여주므로 다음으로 접는다.
    """
    source = GROUP_TABLE.read_text(encoding="utf-8")

    assert '@max-[560px]:hidden' in source


def test_sector_column_folds_last():
    """768px 창에서 패널이 열리면 목록이 368px까지 줄어든다.

    섹터는 왼쪽 사이드바 필터로도 확인되므로 마지막으로 접는다.
    """
    source = GROUP_TABLE.read_text(encoding="utf-8")

    assert '@max-[420px]:hidden' in source
