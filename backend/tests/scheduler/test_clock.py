"""Tests for Clock abstraction (SystemClock and SimulatedClock)."""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import pytest

from backend.app.scheduler.clock import SystemClock, SimulatedClock


def test_system_clock_returns_utc():
    clock = SystemClock()
    now = clock.now_utc()
    assert now.tzinfo is not None
    assert now.tzinfo == timezone.utc


def test_simulated_clock_initialization_naive():
    naive_dt = datetime(2026, 11, 7, 10, 0, 0)
    clock = SimulatedClock(naive_dt)
    now = clock.now_utc()
    assert now.tzinfo == timezone.utc
    assert now.year == 2026
    assert now.hour == 10


def test_simulated_clock_initialization_aware():
    eastern = ZoneInfo("America/New_York")
    aware_dt = datetime(2026, 11, 7, 10, 0, 0, tzinfo=eastern)
    clock = SimulatedClock(aware_dt)
    now = clock.now_utc()
    assert now.tzinfo == timezone.utc
    # 10:00 AM EST (UTC-5) is 15:00 UTC
    assert now.hour == 15


def test_simulated_clock_advance():
    start = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    clock = SimulatedClock(start)
    assert clock.now_utc() == start

    # Advance 45 minutes
    new_time = clock.advance(timedelta(minutes=45))
    assert new_time == datetime(2026, 1, 1, 0, 45, 0, tzinfo=timezone.utc)
    assert clock.now_utc() == new_time

    # Advance 10 days
    new_time = clock.advance(timedelta(days=10))
    assert new_time == datetime(2026, 1, 11, 0, 45, 0, tzinfo=timezone.utc)


def test_simulated_clock_leap_year_traversal():
    # 2028 is a leap year
    start = datetime(2028, 2, 28, 12, 0, 0, tzinfo=timezone.utc)
    clock = SimulatedClock(start)

    clock.advance(timedelta(days=1))
    assert clock.now_utc() == datetime(2028, 2, 29, 12, 0, 0, tzinfo=timezone.utc)

    clock.advance(timedelta(days=1))
    assert clock.now_utc() == datetime(2028, 3, 1, 12, 0, 0, tzinfo=timezone.utc)


def test_simulated_clock_set_time():
    clock = SimulatedClock(datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc))
    target = datetime(2027, 6, 15, 8, 30, 0, tzinfo=timezone.utc)

    clock.set_time(target)
    assert clock.now_utc() == target

    # Set naive time converts to UTC
    clock.set_time(datetime(2028, 5, 1, 12, 0, 0))
    assert clock.now_utc() == datetime(2028, 5, 1, 12, 0, 0, tzinfo=timezone.utc)
