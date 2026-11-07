"""Clock abstraction for deterministic, timezone-aware time management."""

from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone


class Clock(ABC):
    """Abstract clock interface providing current UTC time."""

    @abstractmethod
    def now_utc(self) -> datetime:
        """Return the current time as a timezone-aware UTC datetime."""
        pass


class SystemClock(Clock):
    """System wall clock returning true real-world UTC time."""

    def now_utc(self) -> datetime:
        return datetime.now(timezone.utc)


class SimulatedClock(Clock):
    """Simulated time traveler clock for deterministic unit and integration testing."""

    def __init__(self, initial_time: datetime):
        if initial_time.tzinfo is None:
            self._current_time: datetime = initial_time.replace(tzinfo=timezone.utc)
        else:
            self._current_time = initial_time.astimezone(timezone.utc)

    def now_utc(self) -> datetime:
        return self._current_time

    def advance(self, delta: timedelta) -> datetime:
        """Advance simulated time by the given timedelta."""
        self._current_time += delta
        return self._current_time

    def set_time(self, new_time: datetime) -> datetime:
        """Explicitly set simulated time to a new datetime."""
        if new_time.tzinfo is None:
            self._current_time = new_time.replace(tzinfo=timezone.utc)
        else:
            self._current_time = new_time.astimezone(timezone.utc)
        return self._current_time
