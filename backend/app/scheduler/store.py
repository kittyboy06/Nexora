"""Storage and query layer for schedules, run leases, and execution history."""

import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from backend.app.scheduler.database import SchedulerDatabase
from backend.app.scheduler.models import (
    ConcurrencyPolicy,
    MissedRunPolicy,
    RunStatus,
    Schedule,
    ScheduleRun,
    ScheduleStatus,
    TriggerType,
)

logger = logging.getLogger("nexora.scheduler.store")


def _to_iso(dt: Optional[datetime]) -> Optional[str]:
    """Serialize datetime to ISO 8601 UTC string."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat()


def _from_iso(s: Optional[str]) -> Optional[datetime]:
    """Deserialize ISO 8601 string to timezone-aware UTC datetime."""
    if not s:
        return None
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class ScheduleStore:
    """Repository managing Schedule entities and atomic ScheduleRun leases."""

    def __init__(self, database: SchedulerDatabase):
        self.db = database

    # --- Schedule CRUD ---

    def create_schedule(self, schedule: Schedule) -> Schedule:
        """Insert a new schedule into the database."""
        with self.db.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO schedules (
                    id, name, prompt_template, model_profile_id, trigger_type,
                    trigger_expression, timezone, status, missed_run_policy,
                    concurrency_policy, max_instances, retry_grace_seconds,
                    next_run_at, last_run_at, template_hash, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    schedule.id,
                    schedule.name,
                    schedule.prompt_template,
                    schedule.model_profile_id,
                    schedule.trigger_type.value,
                    schedule.trigger_expression,
                    schedule.timezone,
                    schedule.status.value,
                    schedule.missed_run_policy.value,
                    schedule.concurrency_policy.value,
                    schedule.max_instances,
                    schedule.retry_grace_seconds,
                    _to_iso(schedule.next_run_at),
                    _to_iso(schedule.last_run_at),
                    schedule.template_hash,
                    _to_iso(schedule.created_at),
                    _to_iso(schedule.updated_at),
                ),
            )
        return schedule

    def get_schedule(self, schedule_id: str) -> Optional[Schedule]:
        """Retrieve a schedule by its unique ID."""
        with self.db.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM schedules WHERE id = ?", (schedule_id,)
            ).fetchone()
            if not row:
                return None
            return self._row_to_schedule(row)

    def list_schedules(self, status: Optional[ScheduleStatus] = None) -> List[Schedule]:
        """List schedules, optionally filtered by status."""
        query = "SELECT * FROM schedules"
        params = ()
        if status:
            query += " WHERE status = ?"
            params = (status.value,)
        query += " ORDER BY created_at DESC"

        with self.db.get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_schedule(row) for row in rows]

    def update_schedule(self, schedule: Schedule) -> Schedule:
        """Update an existing schedule record."""
        with self.db.get_connection() as conn:
            conn.execute(
                """
                UPDATE schedules SET
                    name = ?,
                    prompt_template = ?,
                    model_profile_id = ?,
                    trigger_type = ?,
                    trigger_expression = ?,
                    timezone = ?,
                    status = ?,
                    missed_run_policy = ?,
                    concurrency_policy = ?,
                    max_instances = ?,
                    retry_grace_seconds = ?,
                    next_run_at = ?,
                    last_run_at = ?,
                    template_hash = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    schedule.name,
                    schedule.prompt_template,
                    schedule.model_profile_id,
                    schedule.trigger_type.value,
                    schedule.trigger_expression,
                    schedule.timezone,
                    schedule.status.value,
                    schedule.missed_run_policy.value,
                    schedule.concurrency_policy.value,
                    schedule.max_instances,
                    schedule.retry_grace_seconds,
                    _to_iso(schedule.next_run_at),
                    _to_iso(schedule.last_run_at),
                    schedule.template_hash,
                    _to_iso(schedule.updated_at),
                    schedule.id,
                ),
            )
        return schedule

    def delete_schedule(self, schedule_id: str) -> bool:
        """Delete a schedule and cascade delete all associated runs."""
        with self.db.get_connection() as conn:
            cursor = conn.execute("DELETE FROM schedules WHERE id = ?", (schedule_id,))
            return cursor.rowcount > 0

    def get_due_schedules(self, now_utc: datetime) -> List[Schedule]:
        """Retrieve all ACTIVE schedules where next_run_at <= now_utc."""
        iso_now = _to_iso(now_utc)
        with self.db.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM schedules
                WHERE status = 'ACTIVE' AND next_run_at IS NOT NULL AND next_run_at <= ?
                ORDER BY next_run_at ASC
                """,
                (iso_now,),
            ).fetchall()
            return [self._row_to_schedule(row) for row in rows]

    # --- Run Lease & Execution History ---

    def acquire_run_lease(
        self,
        schedule_id: str,
        scheduled_for: datetime,
        clock_now: datetime,
        initial_status: RunStatus = RunStatus.DISPATCHED,
    ) -> Optional[ScheduleRun]:
        """
        Attempt to atomically claim a lease for a scheduled occurrence.
        Uses INSERT ... ON CONFLICT(run_key) DO NOTHING to prevent duplicate runs.
        Returns ScheduleRun if lease acquired, None if already claimed.
        """
        iso_scheduled = _to_iso(scheduled_for)
        run_key = f"{schedule_id}:{iso_scheduled}"
        run_id = str(uuid.uuid4())
        iso_now = _to_iso(clock_now)

        with self.db.get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO schedule_runs (
                    run_id, schedule_id, task_id, run_key, status,
                    scheduled_for, dispatched_at, finished_at, error_message
                ) VALUES (?, ?, NULL, ?, ?, ?, ?, NULL, NULL)
                ON CONFLICT(run_key) DO NOTHING
                """,
                (
                    run_id,
                    schedule_id,
                    run_key,
                    initial_status.value,
                    iso_scheduled,
                    iso_now,
                ),
            )
            if cursor.rowcount == 0:
                # Conflict occurred; lease already claimed by another worker or prior tick
                return None

        return ScheduleRun(
            run_id=run_id,
            schedule_id=schedule_id,
            task_id=None,
            run_key=run_key,
            status=initial_status,
            scheduled_for=scheduled_for,
            dispatched_at=clock_now,
            finished_at=None,
            error_message=None,
        )

    def update_run(
        self,
        run_id: str,
        status: RunStatus,
        task_id: Optional[str] = None,
        finished_at: Optional[datetime] = None,
        error_message: Optional[str] = None,
    ) -> Optional[ScheduleRun]:
        """Update an existing schedule run status and task metadata."""
        with self.db.get_connection() as conn:
            conn.execute(
                """
                UPDATE schedule_runs SET
                    status = ?,
                    task_id = COALESCE(?, task_id),
                    finished_at = COALESCE(?, finished_at),
                    error_message = COALESCE(?, error_message)
                WHERE run_id = ?
                """,
                (
                    status.value,
                    task_id,
                    _to_iso(finished_at) if finished_at else None,
                    error_message,
                    run_id,
                ),
            )
        return self.get_run(run_id)

    def get_run(self, run_id: str) -> Optional[ScheduleRun]:
        """Get an individual run by its ID."""
        with self.db.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM schedule_runs WHERE run_id = ?", (run_id,)
            ).fetchone()
            if not row:
                return None
            return self._row_to_run(row)

    def list_runs(
        self,
        schedule_id: Optional[str] = None,
        status: Optional[RunStatus] = None,
        limit: int = 50,
    ) -> List[ScheduleRun]:
        """Query execution history with optional filtering."""
        query = "SELECT * FROM schedule_runs"
        conditions = []
        params = []

        if schedule_id:
            conditions.append("schedule_id = ?")
            params.append(schedule_id)
        if status:
            conditions.append("status = ?")
            params.append(status.value)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY scheduled_for DESC LIMIT ?"
        params.append(limit)

        with self.db.get_connection() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()
            return [self._row_to_run(row) for row in rows]

    def get_in_flight_runs(self) -> List[ScheduleRun]:
        """Retrieve runs currently in DISPATCHED status."""
        with self.db.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM schedule_runs WHERE status = 'DISPATCHED' ORDER BY dispatched_at ASC"
            ).fetchall()
            return [self._row_to_run(row) for row in rows]

    # --- Internal Row Mappers ---

    def _row_to_schedule(self, row) -> Schedule:
        return Schedule(
            id=row["id"],
            name=row["name"],
            prompt_template=row["prompt_template"],
            model_profile_id=row["model_profile_id"],
            trigger_type=TriggerType(row["trigger_type"]),
            trigger_expression=row["trigger_expression"],
            timezone=row["timezone"],
            status=ScheduleStatus(row["status"]),
            missed_run_policy=MissedRunPolicy(row["missed_run_policy"]),
            concurrency_policy=ConcurrencyPolicy(row["concurrency_policy"]),
            max_instances=row["max_instances"],
            retry_grace_seconds=row["retry_grace_seconds"],
            next_run_at=_from_iso(row["next_run_at"]),
            last_run_at=_from_iso(row["last_run_at"]),
            template_hash=row["template_hash"],
            created_at=_from_iso(row["created_at"]),
            updated_at=_from_iso(row["updated_at"]),
        )

    def _row_to_run(self, row) -> ScheduleRun:
        return ScheduleRun(
            run_id=row["run_id"],
            schedule_id=row["schedule_id"],
            task_id=row["task_id"],
            run_key=row["run_key"],
            status=RunStatus(row["status"]),
            scheduled_for=_from_iso(row["scheduled_for"]),
            dispatched_at=_from_iso(row["dispatched_at"]),
            finished_at=_from_iso(row["finished_at"]),
            error_message=row["error_message"],
        )
