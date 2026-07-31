from pathlib import Path


APP = Path(__file__).parents[1] / "frontend" / "src" / "App.jsx"


def test_header_shows_data_freshness():
    """헤더는 모든 탭에 유효한 정보만 둔다.

    Z 기준과 임계값은 스프레드 전용인데 센티먼트/백테스트에서도 떠 있었다.
    갱신 시각은 세 탭이 같은 크론을 쓰므로 어디서든 유효하다.
    """
    source = APP.read_text(encoding="utf-8")

    assert "import Freshness from './Freshness.jsx'" in source
    assert "<Freshness" in source
    assert "임계 |Z|" not in source.split("<header")[1].split("</header>")[0]


def test_freshness_matches_the_update_cron():
    """경고 기준이 실제 갱신 주기와 어긋나면 신호가 거짓이 된다.

    주기보다 짧게 잡으면 정상 갱신인데도 경고가 뜨고, 길게 잡으면 크론이
    멈춰도 조용하다. 배포 워크플로의 크론과 같은 값을 써야 한다.
    """
    import re

    source = APP.read_text(encoding="utf-8")
    workflow = (
        APP.parents[2] / ".github" / "workflows" / "update-data.yml"
    ).read_text(encoding="utf-8")

    hours = float(re.search(r"intervalHours=\{([\d.]+)\}", source).group(1))
    # '5 */2 * * *' 형태에서 시간 간격을 읽는다.
    cron = re.search(r"cron: '[\d,]+ \*/(\d+)", workflow)
    assert cron, "크론이 시간 간격 형식이 아니다. 값을 직접 맞춰야 한다."

    assert hours == float(cron.group(1)), (
        f"Freshness {hours}시간 vs 크론 {cron.group(1)}시간 주기가 어긋난다"
    )


def test_spread_counts_moved_out_of_the_header():
    """그룹/경고/커플링 유효는 스프레드 전용이라 헤더에서 내린다."""
    source = APP.read_text(encoding="utf-8")
    header = source.split("<header")[1].split("</header>")[0]

    assert "커플링 유효" not in header
    assert 'data-testid="spread-counts"' in source


def test_counts_react_to_the_current_filter():
    """헤더에 있을 때는 필터와 무관한 전체 값만 보여줬다.

    방산만 골라도 '그룹 32'가 그대로라 필터가 걸렸는지 알 수 없었다.
    """
    source = APP.read_text(encoding="utf-8")

    assert "groups.filter((g) => g.alert).length" in source
    assert "groups.filter(isTrusted).length" in source
