"""감시 모드의 이력 집계 검증. 네트워크를 타지 않는다."""

import fomo_watch as watch


def test_first_run_creates_one_daily_point():
    daily = watch.roll_daily([], "2026-07-29 10:00", 41.3)
    assert daily == [{"date": "2026-07-29", "score": 41.3, "n": 1}]


def test_same_day_runs_average_instead_of_overwrite():
    """마지막 값만 쓰면 그날 대표값이 우연히 걸린 한 회차에 좌우된다."""
    daily = watch.roll_daily([], "2026-07-29 10:00", 40.0)
    daily = watch.roll_daily(daily, "2026-07-29 12:00", 50.0)
    assert daily == [{"date": "2026-07-29", "score": 45.0, "n": 2}]
    # 세 번째 회차도 누적 평균으로 들어간다
    daily = watch.roll_daily(daily, "2026-07-29 14:00", 60.0)
    assert daily[0]["score"] == 50.0 and daily[0]["n"] == 3


def test_new_day_appends_point():
    daily = watch.roll_daily([], "2026-07-28 10:00", 30.0)
    daily = watch.roll_daily(daily, "2026-07-29 10:00", 50.0)
    assert [p["date"] for p in daily] == ["2026-07-28", "2026-07-29"]
    assert [p["score"] for p in daily] == [30.0, 50.0]


def test_daily_history_is_capped_at_a_month():
    daily = []
    # 6월 1일부터 7월 10일까지 40일
    for day in range(1, 31):
        daily = watch.roll_daily(daily, f"2026-06-{day:02d} 10:00", float(day))
    for day in range(1, 11):
        daily = watch.roll_daily(daily, f"2026-07-{day:02d} 10:00", float(100 + day))
    assert len(daily) == watch.DAILY_POINTS
    # 오래된 날짜부터 버리고 최신이 남는다
    assert daily[-1]["date"] == "2026-07-10"
    assert daily[0]["date"] == "2026-06-11"


def test_none_score_does_not_create_a_point():
    """표본 부족(S&P500)은 점수가 없다. 빈 점을 만들면 선이 끊긴다."""
    daily = watch.roll_daily([], "2026-07-29 10:00", None)
    assert daily == []
    existing = [{"date": "2026-07-28", "score": 30.0, "n": 1}]
    assert watch.roll_daily(existing, "2026-07-29 10:00", None) == existing


def test_daily_points_cover_a_month():
    assert watch.DAILY_POINTS == 30
    # 회차 이력은 짧게 둔다. 둘을 같은 길이로 두면 JSON이 커진다.
    assert watch.HISTORY_POINTS < watch.DAILY_POINTS * 12
