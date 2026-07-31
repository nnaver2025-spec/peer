"""괴리 수렴 백테스트 로직 단위 테스트. 합성 시계열만 쓰고 네트워크를 타지 않는다."""

import numpy as np
import pandas as pd

from catchup_backtest import (
    HORIZONS,
    MIN_GAP_PCT,
    Z_WINDOW,
    current_state,
    find_episodes,
    relative_index,
    required_sample,
    summarize,
    verdict_of,
    wilson,
)

MAX_H = max(HORIZONS)


def _dates(n):
    return pd.bdate_range("2020-01-01", periods=n)


def _rel(values):
    return pd.Series(values, index=_dates(len(values)), dtype=float)


def test_relative_index_is_zero_when_groups_move_together():
    idx = _dates(5)
    lead = pd.Series([100, 110, 121, 133.1, 146.41], index=idx)
    rel = relative_index(lead, lead * 2)  # 레벨만 다르고 수익률이 같은 경우
    assert np.allclose(rel.diff().dropna(), 0)


def test_quiet_series_has_no_episodes():
    """작은 잡음만 있으면 Z가 튀어도 괴리 폭 조건에서 걸러진다."""
    noise = np.tile([0.001, -0.001], (Z_WINDOW + MAX_H + 10) // 2)
    assert find_episodes(_rel(noise)) == []


def test_undershoot_that_recovers_is_counted_as_catch_up():
    """국내가 10%p 뒤처진 뒤 기준선으로 복귀하면 회복률 1.0으로 잡힌다."""
    flat = [0.0] * (Z_WINDOW + 10)
    drop = [-0.10] * 5                       # 국내가 10%p 뒤처진 구간
    back = [0.0] * (MAX_H + 5)               # 이후 원위치
    episodes = find_episodes(_rel(flat + drop + back))

    assert episodes, "괴리 에피소드가 하나는 잡혀야 한다"
    first = episodes[0]
    assert first["direction"] == "undershoot"
    assert first["gap"] <= -MIN_GAP_PCT
    assert first["horizons"][MAX_H]["recovery"] >= 1.0
    assert first["days_to_half"] is not None
    assert first["resolved"] is True


def test_widening_gap_records_negative_recovery():
    """괴리가 더 벌어지면 회복률이 음수로 남아야 한다 (실패 사례)."""
    flat = [0.0] * (Z_WINDOW + 10)
    widening = list(np.linspace(-0.10, -0.30, MAX_H + 10))
    episodes = find_episodes(_rel(flat + widening))

    assert episodes
    assert episodes[0]["horizons"][MAX_H]["recovery"] < 0
    assert episodes[0]["days_to_full"] is None


def test_unresolved_episode_is_excluded_from_summary():
    """표본 끝에 걸린 진행 중 건은 성공률 계산에서 빠진다."""
    flat = [0.0] * (Z_WINDOW + 10)
    tail = [-0.10] * 5                       # 결과를 볼 구간이 없다
    episodes = find_episodes(_rel(flat + tail))
    stats = summarize(episodes)

    assert stats["episodes"] >= 1
    assert stats["resolved"] == 0
    assert stats[f"h{MAX_H}"]["half_rate"] is None


def test_pos_points_at_the_signal_date():
    """차트가 pos로 구간을 자르므로, pos가 가리키는 날짜가 date와 같아야 한다."""
    flat = [0.0] * (Z_WINDOW + 10)
    drop = [-0.10] * 5
    back = [0.0] * (MAX_H + 5)
    rel = _rel(flat + drop + back)
    episodes = find_episodes(rel)

    assert episodes
    for e in episodes:
        assert rel.index[e["pos"]].date().isoformat() == e["date"]


def test_wilson_interval_stays_inside_zero_to_hundred():
    """작은 표본에서도 구간이 [0, 100]을 벗어나지 않아야 한다."""
    for hits, total in ((0, 5), (5, 5), (1, 3), (28, 49)):
        low, high = wilson(hits, total)
        assert 0.0 <= low <= high <= 100.0


def test_wilson_interval_narrows_as_sample_grows():
    """같은 비율이면 표본이 클수록 구간이 좁아야 한다."""
    small = wilson(20, 40)
    large = wilson(500, 1000)
    assert (large[1] - large[0]) < (small[1] - small[0])


def test_empty_sample_gives_widest_interval():
    assert wilson(0, 0) == (0.0, 100.0)


def test_verdict_requires_interval_to_clear_the_coin_flip():
    """50%를 걸치는 구간은 판정하지 않는다. 표본 40건의 57%가 여기 해당한다."""
    assert verdict_of(*wilson(28, 49)) == "undecided"     # 57.1%, n=49
    assert verdict_of(*wilson(513, 1183)) == "diverges"   # 43.4%, n=1183
    assert verdict_of(60.0, 70.0) == "converges"
    assert verdict_of(30.0, 40.0) == "diverges"


def test_required_sample_grows_as_rate_approaches_the_coin_flip():
    """50%에 가까울수록 판정에 더 많은 표본이 필요하다."""
    assert required_sample(30.0) < required_sample(45.0)
    # 정확히 기준선이면 어떤 표본으로도 구분되지 않는다
    assert required_sample(50.0) is None


def test_summary_separates_touching_convergence_from_holding_it():
    """수렴에 닿았다가 되돌아간 건은 '유지'로 세지 않는다."""
    flat = [0.0] * (Z_WINDOW + 10)
    drop = [-0.10] * 5
    # 기준선까지 되돌아온 뒤(닿음) 다시 크게 벌어진다(유지 실패)
    back = [0.0] * 10 + list(np.linspace(0.0, -0.25, MAX_H))
    stats = summarize(find_episodes(_rel(flat + drop + back)))

    assert stats["touched_rate"] == 100.0
    assert stats["held_rate"] == 0.0


def test_current_state_reports_the_last_trading_day():
    """현재 괴리는 마지막 거래일을 가리키고, pos로 차트를 그릴 수 있어야 한다."""
    rel = _rel([0.0] * (Z_WINDOW + 10) + [-0.10] * 3)
    state = current_state(rel)

    assert state["date"] == rel.index[-1].date().isoformat()
    assert state["pos"] == len(rel) - 1
    assert state["direction"] == "undershoot"
    assert state["gap"] < 0


def test_current_state_flags_active_only_past_both_thresholds():
    """Z와 괴리 폭을 모두 넘겨야 '괴리 확대'로 본다."""
    quiet = _rel([0.0] * (Z_WINDOW + 5) + [0.001])
    assert current_state(quiet)["active"] is False

    wide = _rel([0.0] * (Z_WINDOW + 10) + [-0.10] * 3)
    assert wide is not None
    assert current_state(wide)["active"] is True


def test_current_state_needs_a_full_baseline_window():
    """기준선을 못 만들 만큼 짧으면 None을 준다(화면에서 현재 행을 뺀다)."""
    assert current_state(_rel([0.0] * (Z_WINDOW - 5))) is None
