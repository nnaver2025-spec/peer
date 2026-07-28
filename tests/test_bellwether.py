"""주도주 신호 계산 함수 단위 테스트. 네트워크를 타지 않고 합성 프레임만 쓴다."""

import pandas as pd
import pytest

from peer_tracker import Z_WINDOW, rolling_zscore


def _dates(n):
    return pd.bdate_range("2026-01-01", periods=n)


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
