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


def test_tier_still_drives_the_color():
    """등급은 색으로만 남는다. 길이와 숫자가 실제 강도를 말한다."""
    source = COUPLING.read_text(encoding="utf-8")

    assert "bar:" in source
    assert "chip:" in source


def test_table_shows_the_actual_strength_not_just_the_tier():
    """등급만 보여주면 실제 차이가 왜곡된다.

    강함 최하(통신 기자재 0.31)와 보통 최상(반도체 IP/디자인 0.29)의 차이는
    0.02인데 3칸 대 2칸으로 갈렸다. 반대로 PCB/기판 0.59와 통신 기자재 0.31은
    두 배 차이인데 같은 3칸이었다. 강함 내부 폭 0.28이 등급 경계보다 크다.
    """
    source = (SRC / "GroupTable.jsx").read_text(encoding="utf-8")

    assert "corrPercent" in source
    assert "TIER_STEPS" not in source


def test_strength_number_is_visible_next_to_the_gauge():
    """막대 길이만으로는 값을 비교하기 어렵다. Z-Score 열과 같은 문법을 쓴다."""
    source = (SRC / "GroupTable.jsx").read_text(encoding="utf-8")

    assert "strength" in source
