"""Recurrence engine for cron, fixed interval, and one-shot scheduled execution."""

import calendar
import re
from datetime import datetime, timedelta, timezone
from typing import Optional, Set
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from backend.app.scheduler.models import TriggerType


class RecurrenceEngine:
    """Calculates future recurrence timestamps across timezones and DST shifts."""

    INTERVAL_PATTERN = re.compile(
        r"^(?:every\s+)?(\d+)\s*(s|sec|secs|second|seconds|m|min|mins|minute|minutes|h|hr|hrs|hour|hours|d|day|days)$",
        re.IGNORECASE,
    )

    @classmethod
    def get_zone_info(cls, tz_str: str) -> ZoneInfo:
        """Validate and return ZoneInfo object."""
        try:
            return ZoneInfo(tz_str)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"Invalid timezone '{tz_str}': {exc}") from exc

    @classmethod
    def validate_expression(cls, trigger_type: TriggerType, trigger_expression: str, timezone_str: str = "UTC") -> None:
        """Validate trigger expression and timezone syntax. Raises ValueError on error."""
        cls.get_zone_info(timezone_str)
        expr = trigger_expression.strip()

        if trigger_type == TriggerType.CRON:
            cls._parse_cron_fields(expr)
        elif trigger_type == TriggerType.INTERVAL:
            cls._parse_interval_seconds(expr)
        elif trigger_type == TriggerType.ONE_SHOT:
            cls._parse_one_shot(expr, timezone_str)
        else:
            raise ValueError(f"Unsupported trigger type: {trigger_type}")

    @classmethod
    def calculate_next_run(
        cls,
        trigger_type: TriggerType,
        trigger_expression: str,
        timezone_str: str,
        reference_utc: datetime,
        last_run_at: Optional[datetime] = None,
    ) -> Optional[datetime]:
        """
        Calculate the next execution timestamp in UTC strictly after reference_utc.
        Returns None if no future run is possible (e.g., past one-shot).
        """
        if reference_utc.tzinfo is None:
            reference_utc = reference_utc.replace(tzinfo=timezone.utc)
        else:
            reference_utc = reference_utc.astimezone(timezone.utc)

        if trigger_type == TriggerType.CRON:
            return cls._calculate_next_cron(trigger_expression, timezone_str, reference_utc)
        elif trigger_type == TriggerType.INTERVAL:
            return cls._calculate_next_interval(trigger_expression, reference_utc, last_run_at)
        elif trigger_type == TriggerType.ONE_SHOT:
            return cls._calculate_next_one_shot(trigger_expression, timezone_str, reference_utc)
        else:
            raise ValueError(f"Unsupported trigger type: {trigger_type}")

    # --- Cron Parsing and Evaluation ---

    @classmethod
    def _parse_cron_field(cls, field_str: str, min_val: int, max_val: int) -> Set[int]:
        """Parse a single cron field into an allowed set of integers."""
        field_str = field_str.strip()
        if not field_str:
            raise ValueError("Empty cron field")

        values: Set[int] = set()
        for part in field_str.split(","):
            part = part.strip()
            if not part:
                raise ValueError(f"Invalid empty item in comma-separated field: '{field_str}'")

            if "/" in part:
                subparts = part.split("/")
                if len(subparts) != 2:
                    raise ValueError(f"Invalid step format: '{part}'")
                range_part, step_part = subparts[0].strip(), subparts[1].strip()
                try:
                    step = int(step_part)
                except ValueError:
                    raise ValueError(f"Invalid step value: '{step_part}'")
                if step <= 0:
                    raise ValueError(f"Step must be > 0, got {step}")

                if range_part == "*":
                    start, end = min_val, max_val
                elif "-" in range_part:
                    r_start, r_end = range_part.split("-", 1)
                    start, end = int(r_start.strip()), int(r_end.strip())
                else:
                    start, end = int(range_part), max_val

                if start < min_val or end > max_val or start > end:
                    raise ValueError(f"Range {start}-{end} outside bounds [{min_val}, {max_val}]")
                values.update(range(start, end + 1, step))

            elif "-" in part:
                subparts = part.split("-")
                if len(subparts) != 2:
                    raise ValueError(f"Invalid range format: '{part}'")
                start, end = int(subparts[0].strip()), int(subparts[1].strip())
                if start < min_val or end > max_val or start > end:
                    raise ValueError(f"Range {start}-{end} outside bounds [{min_val}, {max_val}]")
                values.update(range(start, end + 1))

            elif part == "*":
                values.update(range(min_val, max_val + 1))

            else:
                try:
                    val = int(part)
                except ValueError:
                    raise ValueError(f"Invalid integer token: '{part}'")
                if val < min_val or val > max_val:
                    raise ValueError(f"Value {val} outside bounds [{min_val}, {max_val}]")
                values.add(val)

        return values

    @classmethod
    def _parse_cron_fields(cls, expr: str) -> tuple[Set[int], Set[int], Set[int], Set[int], Set[int], bool, bool]:
        """
        Parse 5-field cron expression:
        minute (0-59), hour (0-23), day of month (1-31), month (1-12), day of week (0-7, 0/7=Sun)
        Returns (minutes, hours, doms, months, dows, dom_is_star, dow_is_star)
        """
        fields = expr.split()
        if len(fields) != 5:
            raise ValueError(f"Cron expression must contain exactly 5 fields, got {len(fields)}: '{expr}'")

        min_expr, hour_expr, dom_expr, mon_expr, dow_expr = fields

        minutes = cls._parse_cron_field(min_expr, 0, 59)
        hours = cls._parse_cron_field(hour_expr, 0, 23)
        doms = cls._parse_cron_field(dom_expr, 1, 31)
        months = cls._parse_cron_field(mon_expr, 1, 12)
        dows = cls._parse_cron_field(dow_expr, 0, 7)

        # Standardize dow: 7 is Sunday (0)
        if 7 in dows:
            dows.add(0)

        dom_is_star = (dom_expr.strip() == "*")
        dow_is_star = (dow_expr.strip() == "*")

        return minutes, hours, doms, months, dows, dom_is_star, dow_is_star

    @classmethod
    def _calculate_next_cron(cls, expr: str, tz_str: str, ref_utc: datetime) -> Optional[datetime]:
        """Calculate next cron occurrence strictly after ref_utc."""
        tz = cls.get_zone_info(tz_str)
        minutes, hours, doms, months, dows, dom_is_star, dow_is_star = cls._parse_cron_fields(expr)

        local_ref = ref_utc.astimezone(tz)
        # Advance 1 minute past local_ref to ensure strictly > ref_utc
        candidate = local_ref.replace(second=0, microsecond=0) + timedelta(minutes=1)

        # Scan up to 5 years (approx 1826 days)
        max_year = candidate.year + 5
        curr_year = candidate.year

        sorted_hours = sorted(hours)
        sorted_minutes = sorted(minutes)

        while curr_year <= max_year:
            # Check month
            for month in range(candidate.month if curr_year == candidate.year else 1, 13):
                if month not in months:
                    continue

                days_in_month = calendar.monthrange(curr_year, month)[1]
                start_day = candidate.day if (curr_year == candidate.year and month == candidate.month) else 1

                for day in range(start_day, days_in_month + 1):
                    # Check day of month & day of week
                    # Python weekday: 0=Mon, 1=Tue, ..., 5=Sat, 6=Sun
                    # Cron dow: 0=Sun, 1=Mon, ..., 6=Sat
                    py_dow = calendar.weekday(curr_year, month, day)
                    cron_dow = 0 if py_dow == 6 else (py_dow + 1)

                    if dom_is_star and dow_is_star:
                        day_match = True
                    elif not dom_is_star and not dow_is_star:
                        # POSIX standard: if both are restricted, either matching matches
                        day_match = (day in doms) or (cron_dow in dows)
                    elif not dom_is_star:
                        day_match = (day in doms)
                    else:
                        day_match = (cron_dow in dows)

                    if not day_match:
                        continue

                    # Day matches! Now evaluate hours and minutes
                    is_candidate_day = (curr_year == candidate.year and month == candidate.month and day == candidate.day)
                    start_hour = candidate.hour if is_candidate_day else 0
                    start_min = candidate.minute if is_candidate_day else 0

                    for hour in sorted_hours:
                        if hour < start_hour:
                            continue

                        for minute in sorted_minutes:
                            if hour == start_hour and minute < start_min:
                                continue

                            # Construct timezone-aware local datetime
                            try:
                                cand_dt = datetime(curr_year, month, day, hour, minute, 0, tzinfo=tz)
                            except ValueError:
                                # Non-existent or invalid wall clock time during DST fold/gap
                                continue

                            cand_utc = cand_dt.astimezone(timezone.utc)
                            if cand_utc > ref_utc:
                                return cand_utc

            curr_year += 1

        return None

    # --- Interval Parsing and Evaluation ---

    @classmethod
    def _parse_interval_seconds(cls, expr: str) -> int:
        """Parse interval expression into total seconds."""
        match = cls.INTERVAL_PATTERN.match(expr.strip())
        if not match:
            raise ValueError(f"Invalid interval expression: '{expr}'. Expected format like '30s', '15m', '2h', '1d'")

        value = int(match.group(1))
        unit = match.group(2).lower()

        if value <= 0:
            raise ValueError(f"Interval value must be > 0, got {value}")

        if unit in ("s", "sec", "secs", "second", "seconds"):
            return value
        elif unit in ("m", "min", "mins", "minute", "minutes"):
            return value * 60
        elif unit in ("h", "hr", "hrs", "hour", "hours"):
            return value * 3600
        elif unit in ("d", "day", "days"):
            return value * 86400
        else:
            raise ValueError(f"Unsupported interval unit: '{unit}'")

    @classmethod
    def _calculate_next_interval(
        cls,
        expr: str,
        ref_utc: datetime,
        last_run_at: Optional[datetime] = None,
    ) -> datetime:
        """Calculate next interval execution."""
        seconds = cls._parse_interval_seconds(expr)
        delta = timedelta(seconds=seconds)

        if last_run_at is not None:
            if last_run_at.tzinfo is None:
                last_run_at = last_run_at.replace(tzinfo=timezone.utc)
            else:
                last_run_at = last_run_at.astimezone(timezone.utc)

            candidate = last_run_at + delta
            if candidate > ref_utc:
                return candidate

        return ref_utc + delta

    # --- One-Shot Parsing and Evaluation ---

    @classmethod
    def _parse_one_shot(cls, expr: str, timezone_str: str) -> datetime:
        """Parse ISO 8601 one-shot expression into UTC datetime."""
        try:
            dt = datetime.fromisoformat(expr.strip())
        except ValueError as exc:
            raise ValueError(f"Invalid ISO 8601 timestamp for ONE_SHOT: '{expr}'") from exc

        if dt.tzinfo is None:
            tz = cls.get_zone_info(timezone_str)
            dt = dt.replace(tzinfo=tz)

        return dt.astimezone(timezone.utc)

    @classmethod
    def _calculate_next_one_shot(cls, expr: str, timezone_str: str, ref_utc: datetime) -> Optional[datetime]:
        """Calculate next one-shot execution."""
        target_utc = cls._parse_one_shot(expr, timezone_str)
        if target_utc > ref_utc:
            return target_utc
        return None
