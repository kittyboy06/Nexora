"""Tests for RecurrenceEngine (cron, fixed interval, one-shot, timezones, and DST)."""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import pytest

from backend.app.scheduler.models import TriggerType
from backend.app.scheduler.recurrence import RecurrenceEngine


def test_timezone_validation():
    # Valid timezones
    assert RecurrenceEngine.get_zone_info("UTC") is not None
    assert RecurrenceEngine.get_zone_info("America/New_York") is not None
    assert RecurrenceEngine.get_zone_info("Asia/Tokyo") is not None

    # Invalid timezone
    with pytest.raises(ValueError, match="Invalid timezone"):
        RecurrenceEngine.get_zone_info("NonExistent/Zone_123")


def test_expression_validation():
    # Valid cron expressions
    RecurrenceEngine.validate_expression(TriggerType.CRON, "* * * * *")
    RecurrenceEngine.validate_expression(TriggerType.CRON, "*/15 9-17 * * 1-5")
    RecurrenceEngine.validate_expression(TriggerType.CRON, "0 0 1,15 * *")

    # Invalid cron expressions
    with pytest.raises(ValueError, match="Cron expression must contain exactly 5 fields"):
        RecurrenceEngine.validate_expression(TriggerType.CRON, "* * * *")

    with pytest.raises(ValueError, match="outside bounds"):
        RecurrenceEngine.validate_expression(TriggerType.CRON, "65 * * * *")

    with pytest.raises(ValueError, match="Step must be > 0"):
        RecurrenceEngine.validate_expression(TriggerType.CRON, "*/0 * * * *")

    # Valid intervals
    RecurrenceEngine.validate_expression(TriggerType.INTERVAL, "30s")
    RecurrenceEngine.validate_expression(TriggerType.INTERVAL, "15m")
    RecurrenceEngine.validate_expression(TriggerType.INTERVAL, "2h")
    RecurrenceEngine.validate_expression(TriggerType.INTERVAL, "1d")
    RecurrenceEngine.validate_expression(TriggerType.INTERVAL, "every 10 minutes")

    # Invalid intervals
    with pytest.raises(ValueError, match="Invalid interval expression"):
        RecurrenceEngine.validate_expression(TriggerType.INTERVAL, "abc")

    with pytest.raises(ValueError, match="Interval value must be > 0"):
        RecurrenceEngine.validate_expression(TriggerType.INTERVAL, "0s")

    # Valid one-shot
    RecurrenceEngine.validate_expression(TriggerType.ONE_SHOT, "2026-12-31T23:59:59Z")
    RecurrenceEngine.validate_expression(TriggerType.ONE_SHOT, "2026-12-31T18:59:59-05:00")

    # Invalid one-shot
    with pytest.raises(ValueError, match="Invalid ISO 8601"):
        RecurrenceEngine.validate_expression(TriggerType.ONE_SHOT, "tomorrow at 5pm")


def test_cron_every_minute():
    ref = datetime(2026, 6, 1, 10, 15, 23, tzinfo=timezone.utc)
    next_run = RecurrenceEngine.calculate_next_run(
        TriggerType.CRON, "* * * * *", "UTC", ref
    )
    assert next_run == datetime(2026, 6, 1, 10, 16, 0, tzinfo=timezone.utc)


def test_cron_daily_at_fixed_hour():
    # Before 09:00
    ref1 = datetime(2026, 6, 1, 8, 30, 0, tzinfo=timezone.utc)
    next1 = RecurrenceEngine.calculate_next_run(
        TriggerType.CRON, "0 9 * * *", "UTC", ref1
    )
    assert next1 == datetime(2026, 6, 1, 9, 0, 0, tzinfo=timezone.utc)

    # At or after 09:00
    ref2 = datetime(2026, 6, 1, 9, 0, 0, tzinfo=timezone.utc)
    next2 = RecurrenceEngine.calculate_next_run(
        TriggerType.CRON, "0 9 * * *", "UTC", ref2
    )
    assert next2 == datetime(2026, 6, 2, 9, 0, 0, tzinfo=timezone.utc)


def test_cron_weekdays():
    # Friday 2026-06-05 at 10:00 UTC
    # 0 9 * * 1-5 should skip Saturday (6) and Sunday (7) and run Monday 2026-06-08 at 09:00
    ref = datetime(2026, 6, 5, 10, 0, 0, tzinfo=timezone.utc)
    next_run = RecurrenceEngine.calculate_next_run(
        TriggerType.CRON, "0 9 * * 1-5", "UTC", ref
    )
    assert next_run == datetime(2026, 6, 8, 9, 0, 0, tzinfo=timezone.utc)


def test_cron_leap_day():
    # 2028 is a leap year; 2026 is not
    ref = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    next_run = RecurrenceEngine.calculate_next_run(
        TriggerType.CRON, "0 12 29 2 *", "UTC", ref
    )
    assert next_run == datetime(2028, 2, 29, 12, 0, 0, tzinfo=timezone.utc)


def test_cron_dst_wall_clock_preservation():
    """
    In America/New_York:
    Standard Time (EST) is UTC-5 (e.g. January).
    Daylight Saving Time (EDT) is UTC-4 (e.g. July).
    A schedule for 09:00 AM local time should evaluate to:
    - 14:00 UTC during EST
    - 13:00 UTC during EDT
    """
    tz_ny = "America/New_York"

    # Winter (EST): 2026-01-15 08:00 EST (13:00 UTC)
    ref_winter = datetime(2026, 1, 15, 13, 0, 0, tzinfo=timezone.utc)
    next_winter = RecurrenceEngine.calculate_next_run(
        TriggerType.CRON, "0 9 * * *", tz_ny, ref_winter
    )
    # 09:00 EST is 14:00 UTC
    assert next_winter == datetime(2026, 1, 15, 14, 0, 0, tzinfo=timezone.utc)
    # Check local time is indeed 09:00
    assert next_winter.astimezone(ZoneInfo(tz_ny)).hour == 9

    # Summer (EDT): 2026-07-15 08:00 EDT (12:00 UTC)
    ref_summer = datetime(2026, 7, 15, 12, 0, 0, tzinfo=timezone.utc)
    next_summer = RecurrenceEngine.calculate_next_run(
        TriggerType.CRON, "0 9 * * *", tz_ny, ref_summer
    )
    # 09:00 EDT is 13:00 UTC
    assert next_summer == datetime(2026, 7, 15, 13, 0, 0, tzinfo=timezone.utc)
    # Check local time is indeed 09:00
    assert next_summer.astimezone(ZoneInfo(tz_ny)).hour == 9


def test_interval_recurrence():
    ref = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)

    # 30 seconds
    next30s = RecurrenceEngine.calculate_next_run(
        TriggerType.INTERVAL, "30s", "UTC", ref
    )
    assert next30s == datetime(2026, 6, 1, 12, 0, 30, tzinfo=timezone.utc)

    # 15 minutes
    next15m = RecurrenceEngine.calculate_next_run(
        TriggerType.INTERVAL, "every 15m", "UTC", ref
    )
    assert next15m == datetime(2026, 6, 1, 12, 15, 0, tzinfo=timezone.utc)

    # 2 hours with last_run_at
    last_run = datetime(2026, 6, 1, 11, 0, 0, tzinfo=timezone.utc)
    # last_run + 2h = 13:00 > ref (12:00) -> returns 13:00
    next2h = RecurrenceEngine.calculate_next_run(
        TriggerType.INTERVAL, "2h", "UTC", ref, last_run_at=last_run
    )
    assert next2h == datetime(2026, 6, 1, 13, 0, 0, tzinfo=timezone.utc)


def test_one_shot_recurrence():
    ref = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)

    # Future one-shot
    future_str = "2026-06-01T15:30:00Z"
    next_future = RecurrenceEngine.calculate_next_run(
        TriggerType.ONE_SHOT, future_str, "UTC", ref
    )
    assert next_future == datetime(2026, 6, 1, 15, 30, 0, tzinfo=timezone.utc)

    # Past one-shot returns None
    past_str = "2026-05-31T10:00:00Z"
    next_past = RecurrenceEngine.calculate_next_run(
        TriggerType.ONE_SHOT, past_str, "UTC", ref
    )
    assert next_past is None
