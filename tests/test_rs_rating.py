"""RS Rating(전체 유니버스 기준 0~100 백분위) 테스트.

IBD 방식과 같은 성격이다. 값의 크기가 아니라 유니버스 안에서의 순위를 본다.
"""

import pandas as pd
import pytest

from peer_tracker import rs_ratings, universe_returns


def _series(values, name):
    idx = pd.date_range("2026-01-02", periods=len(values), freq="D")
    return pd.Series(values, index=idx, name=name)


def test_universe_return_is_period_change_ratio():
    closes = {"A": _series([100.0, 150.0], "A")}
    assert universe_returns(closes) == pytest.approx({"A": 0.5})


def test_universe_return_is_scale_free():
    closes = {
        "CHEAP": _series([10.0, 12.0], "CHEAP"),
        "PRICEY": _series([100000.0, 120000.0], "PRICEY"),
    }
    got = universe_returns(closes)
    assert got["CHEAP"] == pytest.approx(got["PRICEY"])


def test_universe_skips_series_too_short_to_measure():
    closes = {"A": _series([100.0], "A"), "B": _series([100.0, 110.0], "B")}
    assert set(universe_returns(closes)) == {"B"}


def test_universe_skips_zero_base_price():
    closes = {"ZERO": _series([0.0, 10.0], "ZERO")}
    assert universe_returns(closes) == {}


def test_best_performer_scores_100():
    ratings = rs_ratings({"A": 0.5, "B": 0.1, "C": -0.2})
    assert ratings["A"] == 100


def test_worst_performer_scores_1_not_0():
    # 0점은 "측정 불가"와 구분이 안 되므로 최하위도 1점을 준다.
    ratings = rs_ratings({"A": 0.5, "B": 0.1, "C": -0.2})
    assert ratings["C"] == 1


def test_rating_is_monotonic_in_return():
    returns = {"A": -0.3, "B": 0.0, "C": 0.2, "D": 0.9}
    ratings = rs_ratings(returns)
    ordered = sorted(returns, key=lambda t: returns[t])
    scores = [ratings[t] for t in ordered]
    assert scores == sorted(scores)


def test_rating_ignores_magnitude_gaps():
    # 순위만 보므로 격차가 아무리 벌어져도 등급 간격은 같다.
    tight = rs_ratings({"A": 0.10, "B": 0.11, "C": 0.12})
    wide = rs_ratings({"A": 0.1, "B": 5.0, "C": 50.0})
    assert tight == wide


def test_ratings_are_within_1_to_100():
    returns = {f"T{i}": i / 10 for i in range(50)}
    ratings = rs_ratings(returns)
    assert all(1 <= v <= 100 for v in ratings.values())


def test_ties_share_the_same_rating():
    ratings = rs_ratings({"A": 0.2, "B": 0.2, "C": -0.1})
    assert ratings["A"] == ratings["B"]


def test_single_ticker_scores_100():
    assert rs_ratings({"A": 0.3}) == {"A": 100}


def test_empty_returns_empty():
    assert rs_ratings({}) == {}
