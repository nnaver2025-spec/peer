from pathlib import Path


APP = Path(__file__).parents[1] / "frontend" / "src" / "App.jsx"


def test_first_visit_defaults_to_spread():
    """저장된 값이 없는 첫 방문은 스프레드로 연다."""
    source = APP.read_text(encoding="utf-8")

    assert "const DEFAULT_TAB = 'spread'" in source
    assert "return DEFAULT_TAB" in source


def test_tab_ids_stay_stable_when_labels_change():
    """라벨은 한글로 바꿔도 id는 그대로 둔다.

    id는 ?tab= 공유 링크와 localStorage에 저장된 값이다. 여기를 건드리면
    기존 링크가 깨지고 저장된 탭 선택이 기본값으로 떨어진다.
    """
    source = APP.read_text(encoding="utf-8")

    for tab_id, label in (("spread", "갭"), ("fomo", "분위기"), ("backtest", "검증")):
        assert f"{{ id: '{tab_id}', label: '{label}' }}" in source


def test_last_tab_is_restored_from_storage():
    """재방문은 마지막으로 보던 탭을 복원한다."""
    source = APP.read_text(encoding="utf-8")

    assert "localStorage.getItem(TAB_KEY)" in source
    assert "localStorage.setItem(TAB_KEY, tab)" in source


def test_tab_change_syncs_the_url():
    """탭을 옮기면 주소도 따라간다.

    이게 없으면 ?tab=fomo로 한 번 들어온 뒤 다른 탭으로 옮겨도 주소는 그대로라,
    링크를 공유하거나 새로고침할 때 의도와 다른 탭이 열린다.
    """
    source = APP.read_text(encoding="utf-8")

    assert "params.set('tab', tab)" in source


def test_group_hash_only_lives_on_the_spread_tab():
    """상세 해시는 스프레드 전용이다.

    스프레드에서 그룹을 열어 #DEF_Europe가 붙은 채 센티먼트로 옮기면 주소에
    해시가 남아, 그 링크를 공유했을 때 탭과 해시가 어긋난다.
    """
    source = APP.read_text(encoding="utf-8")

    assert "const next = isSpread && selectedKey" in source
