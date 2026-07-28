"""주도주 신호 계산 함수 단위 테스트. 네트워크를 타지 않고 합성 프레임만 쓴다."""

import pandas as pd
import pytest

from peer_tracker import (
    Z_WINDOW,
    relative_strength,
    rolling_zscore,
    select_bellwether,
    select_top_pick,
)


def _dates(n):
    return pd.bdate_range("2026-01-01", periods=n)


def _frame(last_prices, base=100.0):
    """기준일 base에서 출발해 마지막 날 last_prices가 되는 3행 프레임."""
    return pd.DataFrame(
        {t: [base, base, p] for t, p in last_prices.items()}, index=_dates(3)
    )


def test_rolling_zscore_drops_warmup_rows():
    n = Z_WINDOW + 5
    series = pd.Series(range(n), index=_dates(n), dtype=float)
    z = rolling_zscore(series)
    assert len(z) == n - Z_WINDOW + 1
    assert z.notna().all()


def test_rolling_zscore_last_value_matches_manual_calc():
    n = Z_WINDOW + 3
    series = pd.Series([100.0] * (n - 1) + [130.0], index=_dates(n))
    window = series.tail(Z_WINDOW)
    expected = (series.iloc[-1] - window.mean()) / window.std()
    assert rolling_zscore(series).iloc[-1] == pytest.approx(expected)


def test_rolling_zscore_returns_empty_when_flat():
    n = Z_WINDOW + 3
    series = pd.Series([50.0] * n, index=_dates(n))
    assert rolling_zscore(series).empty


def test_rs_is_normalized_level_at_last_date():
    rs = relative_strength(_frame({"A": 120.0, "B": 90.0}))
    assert rs["A"] == pytest.approx(120.0)
    assert rs["B"] == pytest.approx(90.0)


def test_rs_is_scale_free_across_price_levels():
    # 절대 주가가 달라도 상승률이 같으면 RS가 같아야 한다.
    frame = pd.DataFrame(
        {"A": [10.0, 10.0, 12.0], "B": [500.0, 500.0, 600.0]}, index=_dates(3)
    )
    rs = relative_strength(frame)
    assert rs["A"] == pytest.approx(120.0)
    assert rs["B"] == pytest.approx(120.0)


def test_bellwether_is_highest_rs_regardless_of_cap():
    # A가 RS 1등이고 시총은 최하위여도 Bellwether는 A다.
    assert select_bellwether(_frame({"A": 140.0, "B": 120.0, "C": 100.0})) == "A"


def test_bellwether_tie_breaks_on_column_order():
    assert select_bellwether(_frame({"A": 110.0, "B": 110.0})) == "A"


def test_bellwether_single_ticker_group():
    assert select_bellwether(_frame({"A": 111.0})) == "A"


def test_bellwether_empty_frame_returns_none():
    assert select_bellwether(pd.DataFrame()) is None


def test_top_pick_is_largest_market_cap():
    assert select_top_pick({"A": 1e11, "B": 9e12, "C": 5e12}) == "B"


def test_top_pick_ignores_missing_caps():
    assert select_top_pick({"A": None, "B": 5e12, "C": None}) == "B"


def test_top_pick_returns_none_when_all_caps_missing():
    assert select_top_pick({"A": None, "B": None}) is None


def test_bellwether_and_top_pick_are_selected_independently():
    # RS 1등(A)과 시총 1등(B)이 갈리는 경우 서로 영향을 주지 않는다.
    frame = _frame({"A": 140.0, "B": 120.0, "C": 100.0})
    caps = {"A": 1e11, "B": 9e12, "C": 5e12}
    assert select_bellwether(frame) == "A"
    assert select_top_pick(caps) == "B"


def test_bellwether_and_top_pick_can_be_the_same_ticker():
    assert select_bellwether(_frame({"A": 140.0, "B": 100.0})) == "A"
    assert select_top_pick({"A": 9e12, "B": 1e11}) == "A"
