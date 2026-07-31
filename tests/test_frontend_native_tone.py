"""네이티브 톤을 기본으로 확정한 뒤의 회귀 검사.

스킨 비교 실험은 끝났다. 확정된 규칙이 조용히 되돌아가지 않도록 붙잡는다.
"""

import re
from pathlib import Path


ROOT = Path(__file__).parents[1]
SRC = ROOT / "frontend" / "src"


def test_skin_experiment_is_gone():
    """스킨 전환 장치가 남아 있으면 화면이 두 갈래로 갈린다."""
    css = (SRC / "index.css").read_text(encoding="utf-8")
    app = (SRC / "App.jsx").read_text(encoding="utf-8")
    theme = (SRC / "theme.js").read_text(encoding="utf-8")

    assert "data-skin" not in css
    assert "SkinPicker" not in app
    assert "useSkin" not in theme


def test_legacy_skin_choice_is_cleared():
    """실험 중 저장된 값이 남으면 다음 방문에서 원인 모를 차이가 생긴다."""
    theme = (SRC / "theme.js").read_text(encoding="utf-8")
    app = (SRC / "App.jsx").read_text(encoding="utf-8")

    assert "peer:skin" in theme
    assert "clearLegacySkin" in app


def test_light_background_stays_white():
    """배경 흰색은 확정된 요구사항이다. 첫 페인트 색도 함께 맞아야 한다."""
    css = (SRC / "index.css").read_text(encoding="utf-8")
    theme = (SRC / "theme.js").read_text(encoding="utf-8")
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")

    light = re.search(r":root\[data-theme='light'\]\s*\{([^}]*)\}", css).group(1)
    assert re.search(r"--color-canvas:\s*#ffffff", light)
    assert "light: '#ffffff'" in theme
    assert "'#ffffff'" in html


def test_native_tone_rules_are_present():
    """native.html에서 남기기로 한 것들. 하나라도 빠지면 톤이 달라진다."""
    css = (SRC / "index.css").read_text(encoding="utf-8")

    # 시스템 타이포 스케일(Title2 17)과 조용한 머리글 라벨
    assert "font-size: 17px" in css
    assert re.search(r"thead th \{[^}]*font-size: 11px", css, re.S)

    # 스크롤되는 표 위에 떠 있는 유리 한 겹
    assert "backdrop-filter" in css


def test_row_separator_is_hairline():
    """1px은 이 밀도에서 격자처럼 두껍게 읽힌다. 0.5px로 둔다."""
    table = (SRC / "GroupTable.jsx").read_text(encoding="utf-8")

    assert "border-b-[0.5px]" in table


def test_glass_is_only_on_header():
    """유리는 크롬 한 곳에만. 본문에 걸리면 숫자가 흐려진다."""
    css = (SRC / "index.css").read_text(encoding="utf-8")

    # backdrop-filter를 선언한 블록의 선택자를 모은다(해제용 none은 제외).
    owners = []
    for selector, body in re.findall(r"([^{}]+)\{([^}]*)\}", css):
        if "backdrop-filter" not in body:
            continue
        if re.search(r"backdrop-filter:\s*none", body):
            continue
        owners.append(selector.strip().splitlines()[-1].strip())

    assert owners, "유리가 아예 없다"
    for owner in owners:
        assert "header" in owner, f"헤더 밖에 유리가 걸렸다: {owner}"


def test_meaning_colors_survive():
    """톤을 바꿔도 판단에 쓰이는 색은 남아야 한다."""
    css = (SRC / "index.css").read_text(encoding="utf-8")

    for token in ("--color-warn", "--color-accent", "--color-good", "--color-up", "--color-down"):
        assert token in css, f"{token}이 사라졌다"

    # 라이트에서 오버슈팅과 언더슈팅이 같은 색이면 구분이 죽는다.
    light = re.search(r":root\[data-theme='light'\]\s*\{([^}]*)\}", css).group(1)
    warn = re.search(r"--color-warn:\s*([^;]+);", light).group(1).strip()
    accent = re.search(r"--color-accent:\s*([^;]+);", light).group(1).strip()
    assert warn != accent


def _hue_spread(hex_color):
    h = hex_color.lstrip("#")
    parts = [int(h[i : i + 2], 16) for i in (0, 2, 4)]
    return max(parts) - min(parts)


def test_selection_background_stays_neutral():
    """선택 배경에 색조가 남으면 그 위의 의미 색이 배경에 묻힌다.

    언더슈팅 숫자가 파란색인데 배경도 파랗던 것이 실제 문제였다.
    밝기로만 선택을 알리고 색조는 빼둔다.
    """
    css = (SRC / "index.css").read_text(encoding="utf-8")

    values = re.findall(r"--color-accent-soft:\s*(#[0-9a-fA-F]{6})", css)
    assert len(values) == 2, f"다크/라이트 두 벌이어야 한다: {values}"
    for v in values:
        assert _hue_spread(v) <= 10, f"선택 배경 {v}에 색조가 너무 남았다 (편차 {_hue_spread(v)})"


def test_selection_does_not_flood_row():
    """선택 행을 강조색으로 가득 채우면 셀마다 실린 신호가 전부 지워진다."""
    css = (SRC / "index.css").read_text(encoding="utf-8")

    flooded = re.search(
        r"tr\[aria-selected='true'\]\s*\{[^}]*background:\s*var\(--color-accent\)", css
    )
    assert not flooded, "선택 행을 진한 강조색으로 채우고 있다"
