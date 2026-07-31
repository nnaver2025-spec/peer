from pathlib import Path


SRC = Path(__file__).parents[1] / "frontend" / "src"
COUPLING = SRC / "coupling.js"


def test_tier_label_does_not_read_as_progress():
    """'커플링 중'의 '중'이 등급이 아니라 '~하는 중'으로 읽혔다.

    열 제목이 이미 커플링이므로 셀에서는 등급만 밝힌다.
    """
    labels = [
        line.split("'")[1]
        for line in COUPLING.read_text(encoding="utf-8").splitlines()
        if line.strip().startswith("label:")
    ]

    assert labels, "라벨을 찾지 못했다"
    for label in labels:
        assert not label.startswith("커플링"), label


def test_tier_labels_are_unambiguous():
    """등급끼리 한눈에 서열이 읽혀야 한다."""
    source = COUPLING.read_text(encoding="utf-8")

    assert "'강함'" in source
    assert "'보통'" in source
    assert "'약함'" in source


def test_tier_keeps_a_rank_for_sorting_and_gauge():
    """라벨을 바꿔도 등급 서열과 게이지는 유지된다."""
    source = COUPLING.read_text(encoding="utf-8")

    assert "rank" in source
