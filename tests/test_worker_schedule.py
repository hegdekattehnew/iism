"""What the worker is actually scheduled to do.

**Three production behaviours exist only in this list**, and nothing asserted
it. `drain_notifications` is how every queued message is sent (ADR-006: the
outbox is written in the request and drained here), `send_job_alerts` is how a
vacancy reaches a candidate who never came looking, and `close_expired_jobs` is
what makes a closing date a closing date rather than a decoration -- Sprint 27
was explicit that "a closing date enforced only when somebody loads the page is
not a closing date".

They are registered in `api/worker.py`, the composition root, and **not** in
`api/core/tasks.py`, which registers the heartbeat alone because core must not
import a feature module. That split is correct and it is also a trap: pointing
the Makefile at `api.core.tasks.WorkerSettings` leaves a worker that starts
cleanly, answers the health probe, and silently does none of the three.
`api/worker.py`'s own docstring warned only that the wrong entry point
"restores the duplicate-line behaviour" -- true, and a long way short of what
actually goes wrong.

Nothing here needs a database, a Redis or a container: the schedule is a
property of the module.
"""

import re
from pathlib import Path

import pytest

from api.core.tasks import WorkerSettings as CoreSettings
from api.worker import WorkerSettings

# Every cron the deployment is supposed to run, and why it is not optional.
EXPECTED_CRONS = {
    "cron:publish_heartbeat": "the health probe reads this; the API reports the worker down",
    "cron:drain_notifications": "no queued notification is ever sent",
    "cron:send_job_alerts": "no candidate hears about a vacancy they did not go looking for",
    "cron:close_expired_jobs": "a closing date never closes anything",
    "cron:purge_expired_analytics": "events are kept past their retention period",
}

REPO = Path(__file__).resolve().parent.parent


def _names(settings: type) -> set[str]:
    return {c.name for c in settings.cron_jobs}


class TestTheWorkerSchedule:
    def test_every_expected_cron_is_registered(self) -> None:
        missing = {
            name: why for name, why in EXPECTED_CRONS.items() if name not in _names(WorkerSettings)
        }
        assert not missing, "crons missing from api/worker.py: " + "; ".join(
            f"{n} -- {w}" for n, w in missing.items()
        )

    def test_nothing_unexpected_is_scheduled(self) -> None:
        """A cron added without a line in `EXPECTED_CRONS` fails here.

        Not pedantry: the table is the only written record of what a deployment
        is supposed to be running, and a schedule nobody wrote down is one
        nobody can check a production worker against.
        """
        assert _names(WorkerSettings) == set(EXPECTED_CRONS)

    def test_the_core_settings_are_not_the_entry_point(self) -> None:
        """The probe, stated as an assertion rather than left to a comment.

        `api.core.tasks.WorkerSettings` is deliberately incomplete. If it ever
        gains the feature crons, core is importing feature modules and ADR-014
        has been broken quietly; if the Makefile is ever pointed at it, this
        names exactly what stops running.
        """
        absent = set(EXPECTED_CRONS) - _names(CoreSettings)
        assert absent, "core/tasks.py now registers everything -- has core grown feature imports?"
        assert _names(CoreSettings) < _names(WorkerSettings)

    def test_the_makefile_runs_the_entry_point_that_has_them(self) -> None:
        makefile = (REPO / "Makefile").read_text()
        target = re.search(r"^worker:.*?(?=^\.PHONY|\Z)", makefile, re.S | re.M)
        assert target is not None, "no `worker:` target in the Makefile"
        assert "api.worker.WorkerSettings" in target.group(0)
        assert "api.core.tasks.WorkerSettings" not in target.group(0)

    @pytest.mark.parametrize("name", sorted(EXPECTED_CRONS))
    def test_each_cron_runs_often_enough_to_matter(self, name: str) -> None:
        """A cron with no schedule at all would still be "registered"."""
        job = next(c for c in WorkerSettings.cron_jobs if c.name == name)
        # arq stores each field as a set of matching values, or None for "any".
        schedule = (job.month, job.day, job.weekday, job.hour, job.minute, job.second)
        assert any(v is not None for v in schedule), f"{name} has no schedule"
