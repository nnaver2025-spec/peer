"""국내 시장 공포탐욕 지표 검증. 네트워크를 타지 않는다."""

import pandas as pd
import pytest

import fomo_market as fm


def test_percentile_positions_value_in_history():
    series = pd.Series(range(100))
    assert fm._percentile(series, 50) == pytest.approx(50, abs=1)
    assert fm._percentile(series, 0) == 0.0
    assert fm._percentile(series, 99) == 99.0


def test_percentile_falls_back_when_history_is_short():
    """표본이 적으면 판단하지 않고 중립을 준다."""
    assert fm._percentile(pd.Series([1, 2, 3]), 2) == 50.0


@pytest.mark.parametrize(
    "score,zone",
    [
        (90, "extreme_greed"),
        (75, "extreme_greed"),
        (60, "greed"),
        (50, "neutral"),
        (45, "neutral"),
        (30, "fear"),
        (25, "fear"),
        (10, "extreme_fear"),
    ],
)
def test_zone_boundaries_follow_cnn(score, zone):
    assert fm._interpret(score)[0] == zone


def test_windows_match_cnn_conventions():
    assert fm.MOMENTUM_WINDOW == 125   # CNN Market Momentum과 같은 구간
    assert fm.RANGE_WINDOW == 250      # 52주
    assert fm.RSI_WINDOW == 14


def test_gauge_returns_none_without_data(monkeypatch):
    """지표를 전부 못 받으면 점수를 만들지 않는다."""
    monkeypatch.setattr(fm, "_CACHE_PATH", fm.Path("/tmp/does-not-exist.json"))

    def explode(*args, **kwargs):
        raise RuntimeError("네트워크 없음")

    for name in ("_momentum", "_volatility", "_breadth", "_range_position", "_rsi"):
        monkeypatch.setattr(fm, name, explode)
    assert fm.market_gauge(force=True) is None


def test_gauge_averages_available_components(monkeypatch, tmp_path):
    """지표 하나가 실패해도 나머지 평균으로 계산한다."""
    monkeypatch.setattr(fm, "_CACHE_PATH", tmp_path / "gauge.json")

    def ok(key, score):
        return lambda *a, **k: fm.Component(key, key, score, "detail")

    monkeypatch.setattr(fm, "_momentum", ok("momentum", 20.0))
    monkeypatch.setattr(fm, "_volatility", ok("volatility", 40.0))
    monkeypatch.setattr(fm, "_breadth", ok("breadth", 60.0))
    monkeypatch.setattr(fm, "_range_position", lambda *a, **k: (_ for _ in ()).throw(RuntimeError()))
    monkeypatch.setattr(fm, "_rsi", ok("rsi", 80.0))

    gauge = fm.market_gauge(force=True)
    assert gauge["score"] == 50.0          # (20+40+60+80)/4
    assert len(gauge["components"]) == 4


def test_component_with_none_score_is_excluded_from_average(monkeypatch, tmp_path):
    monkeypatch.setattr(fm, "_CACHE_PATH", tmp_path / "gauge.json")
    monkeypatch.setattr(fm, "_momentum", lambda *a, **k: fm.Component("m", "m", 30.0, ""))
    monkeypatch.setattr(fm, "_volatility", lambda *a, **k: fm.Component("v", "v", None, "조회 실패"))
    for name in ("_breadth", "_range_position", "_rsi"):
        monkeypatch.setattr(fm, name, lambda *a, **k: fm.Component("x", "x", 50.0, ""))

    gauge = fm.market_gauge(force=True)
    # None은 평균에서 빠지지만 목록에는 남아 "조회 실패"를 보여준다.
    assert gauge["score"] == pytest.approx(45.0)
    assert any(c["score"] is None for c in gauge["components"])
