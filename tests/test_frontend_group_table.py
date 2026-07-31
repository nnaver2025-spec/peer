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


def test_zscore_cell_is_center_aligned():
    """숫자와 바의 중심이 같은 축에 있어야 한다.

    바는 0을 기준으로 좌우로 뻗는데 숫자만 오른쪽에 붙어 있으면 두 중심이
    어긋나 열 전체가 기울어 보인다.
    """
    source = GROUP_TABLE.read_text(encoding="utf-8")

    assert "flex flex-col items-center" in source
    assert "flex flex-col items-end" not in source


def test_zscore_header_matches_cell_alignment():
    """머리글이 오른쪽에 남으면 셀 가운데 정렬과 어긋난다."""
    source = GROUP_TABLE.read_text(encoding="utf-8")

    assert "{ id: 'zscore', label: 'Z-Score', align: 'center'" in source
    # center를 실제로 클래스로 바꿔주는 분기가 있어야 한다.
    assert "text-center" in source
