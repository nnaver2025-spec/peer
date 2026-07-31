"""배포 설정 회귀 검사.

정적 호스팅에서 하위 경로로 서비스할 때 깨지기 쉬운 지점만 붙잡는다.
"""

from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_vite_base_is_configurable():
    """하위 경로 배포에는 base가 필요하다. 고정값으로 박으면 루트 배포가 깨진다."""
    config = (ROOT / "frontend" / "vite.config.js").read_text(encoding="utf-8")

    assert "process.env.BASE_PATH" in config
    assert "base," in config or "base:" in config


def test_data_is_fetched_through_base_url():
    """절대 경로로 fetch하면 하위 경로 배포에서 404가 된다."""
    src = ROOT / "frontend" / "src"

    for name in ("App.jsx", "FomoTab.jsx", "BacktestTab.jsx"):
        source = (src / name).read_text(encoding="utf-8")
        if "_data.json" not in source:
            continue
        assert "import.meta.env.BASE_URL" in source, f"{name}이 BASE_URL을 쓰지 않는다"
        assert "fetch('/" not in source and 'fetch("/' not in source


def test_payloads_are_tracked_for_pages_deploy():
    """Pages는 커밋된 파일을 배포한다. 데이터가 무시되면 사이트가 빈다."""
    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")

    assert "frontend/public" not in ignore
    assert "*.json" not in ignore.split("\n")


def test_cron_scripts_take_paths_from_env():
    """러너나 다른 계정에서도 돌아야 한다. 홈 경로를 박아두면 그곳에서만 된다."""
    for name in ("update.sh", "fomo_update.sh"):
        source = (ROOT / "scripts" / name).read_text(encoding="utf-8")
        body = "\n".join(
            line for line in source.splitlines() if not line.strip().startswith("#")
        )
        assert "/Users/huisang" not in body, f"{name}에 사용자 경로가 남았다"
        assert "PEER_REPO" in body


def test_update_workflow_survives_partial_collection():
    """여론 수집이 막혀도 나머지 지표는 갱신돼야 한다."""
    wf = (ROOT / ".github" / "workflows" / "update-data.yml").read_text(encoding="utf-8")

    assert "continue-on-error: true" in wf
    # 깨진 JSON을 커밋하면 사이트가 빈 화면이 된다.
    assert "json.loads" in wf
    # 스케줄이 겹칠 때 같은 브랜치에 동시 커밋하면 충돌한다.
    assert "concurrency:" in wf


def test_every_payload_has_an_updater():
    """화면이 읽는 데이터에는 모두 갱신 경로가 있어야 한다.

    검증 탭이 실제로 이 문제를 겪었다. catchup_backtest.py를 돌리는 크론이
    없어서 마지막 수동 실행 시점에 멈춰 있었고, 갭 탭과 날짜가 하루 이상
    어긋났다. 생성 스크립트만 있고 스케줄이 없으면 조용히 낡는다.
    """
    workflow = (ROOT / ".github" / "workflows" / "update-data.yml").read_text(encoding="utf-8")
    launchd = " ".join(
        p.read_text(encoding="utf-8") for p in (ROOT / "scripts").glob("*.sh")
    )

    # payload : 그 값을 만드는 스크립트
    producers = {
        "dashboard_data.json": "peer_tracker.py",
        "fomo_data.json": "fomo_watch.py",
        "backtest_data.json": "catchup_backtest.py",
    }

    for payload, script in producers.items():
        assert (ROOT / "frontend" / "public" / payload).exists(), f"{payload}이 없다"
        assert script in workflow, f"{payload}을 만드는 {script}가 워크플로에 없다"
        assert script in launchd, f"{payload}을 만드는 {script}가 로컬 크론에 없다"
