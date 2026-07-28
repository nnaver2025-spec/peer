"""종목별 표시용 시세(종가/전일대비/구간수익률) 테스트."""

import pandas as pd
import pytest

from peer_tracker import ticker_quote


def _series(values):
    idx = pd.date_range("2026-01-02", periods=len(values), freq="D")
    return pd.Series(values, index=idx)


def test_quote_reports_last_close_and_date():
    got = ticker_quote(_series([100.0, 110.0, 121.0]))
    assert got["close"] == 121.0
    assert got["date"] == "2026-01-04"


def test_daily_change_is_percent_vs_previous_close():
    got = ticker_quote(_series([100.0, 110.0]))
    assert got["change"] == pytest.approx(10.0)


def test_daily_change_can_be_negative():
    got = ticker_quote(_series([100.0, 90.0]))
    assert got["change"] == pytest.approx(-10.0)


def test_period_return_uses_window_start():
    # 구간 첫 값 대비 마지막 값. RS와 같은 기준이다.
    got = ticker_quote(_series([100.0, 150.0, 200.0]))
    assert got["period"] == pytest.approx(100.0)


def test_single_point_has_no_daily_change():
    got = ticker_quote(_series([100.0]))
    assert got["close"] == 100.0
    assert got["change"] is None


def test_empty_series_returns_none():
    assert ticker_quote(_series([])) is None


def test_zero_previous_close_leaves_change_none():
    got = ticker_quote(_series([0.0, 50.0]))
    assert got["change"] is None


def test_values_are_rounded_for_json():
    got = ticker_quote(_series([100.0, 133.333333]))
    assert got["close"] == 133.33
    assert got["change"] == 33.33
