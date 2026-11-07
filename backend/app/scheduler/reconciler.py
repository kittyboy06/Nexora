"""Startup reconciliation for recovering crashed runs and handling downtime catchup."""

import logging
from typing import Dict

from backend.app.scheduler.clock import Clock
from backend.app.scheduler.dispatcher import TaskDispatcher
from backend.app.scheduler.models import (
    MissedRunPolicy,
    RunStatus,
    ScheduleStatus,
    TriggerType,
)
from backend.app.scheduler.recurrence import RecurrenceEngine
from backend.app.scheduler.store import ScheduleStore

logger = logging.getLogger("nexora.scheduler.reconciler")


class StartupReconciler:
    """Reconciles scheduler state upon application startup after downtime or crash."""

    def __init__(self, store: ScheduleStore, dispatcher: TaskDispatcher, clock: Clock):
        self.store = store
        self.dispatcher = dispatcher
        self.clock = clock

    async def reconcile_startup(self) -> Dict[str, int]:
        """
        Execute startup reconciliation:
        1. Recover orphaned in-flight runs to INTERRUPTED.
        2. Evaluate overdue schedules according to MissedRunPolicy.
        """
        now = self.clock.now_utc()
        stats = {
            "interrupted_runs_recovered": 0,
            "catchup_runs_dispatched": 0,
            "missed_runs_skipped": 0,
        }

        # 1. Recover orphaned DISPATCHED runs
        in_flight_runs = self.store.get_in_flight_runs()
        for run in in_flight_runs:
            logger.warning(
                "Marking orphaned in-flight run %s (schedule %s) as INTERRUPTED.",
                run.run_id,
                run.schedule_id,
            )
            self.store.update_run(
                run_id=run.run_id,
                status=RunStatus.INTERRUPTED,
                finished_at=now,
                error_message="Server restarted while execution was in flight. Run was interrupted.",
            )
            stats["interrupted_runs_recovered"] += 1

        # 2. Reconcile overdue active schedules
        due_schedules = self.store.get_due_schedules(now)
        for schedule in due_schedules:
            if schedule.status != ScheduleStatus.ACTIVE or not schedule.next_run_at:
                continue

            scheduled_for = schedule.next_run_at

            if schedule.missed_run_policy == MissedRunPolicy.RUN_ONCE_CATCHUP:
                logger.info(
                    "Executing catchup run for schedule '%s' per RUN_ONCE_CATCHUP policy.",
                    schedule.name,
                )
                await self.dispatcher.dispatch_due_schedule(schedule, scheduled_for)
                stats["catchup_runs_dispatched"] += 1

            elif schedule.missed_run_policy == MissedRunPolicy.SKIP_NOTIFY:
                logger.info(
                    "Skipping missed run for schedule '%s' per SKIP_NOTIFY policy.",
                    schedule.name,
                )
                run = self.store.acquire_run_lease(
                    schedule_id=schedule.id,
                    scheduled_for=scheduled_for,
                    clock_now=now,
                    initial_status=RunStatus.SKIPPED,
                )
                if run:
                    self.store.update_run(
                        run_id=run.run_id,
                        status=RunStatus.SKIPPED,
                        finished_at=now,
                        error_message="Missed run during downtime skipped per safety policy.",
                    )

                # Advance next_run_at to future recurrence strictly after now
                schedule.last_run_at = scheduled_for
                schedule.updated_at = now
                if schedule.trigger_type == TriggerType.ONE_SHOT:
                    schedule.status = ScheduleStatus.COMPLETED
                    schedule.next_run_at = None
                else:
                    schedule.next_run_at = RecurrenceEngine.calculate_next_run(
                        trigger_type=schedule.trigger_type,
                        trigger_expression=schedule.trigger_expression,
                        timezone_str=schedule.timezone,
                        reference_utc=now,
                        last_run_at=scheduled_for,
                    )
                self.store.update_schedule(schedule)
                stats["missed_runs_skipped"] += 1

        logger.info("Startup reconciliation complete: %s", stats)
        return stats
