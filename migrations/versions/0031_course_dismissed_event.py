"""A "not interested" signal on course recommendations

Revision ID: 0031
Revises: 0030
Create Date: 2026-09-25

Sprint 33, BL-2.2. `docs/scope-reconciliation.md` #3: the product definition
promises analytics on every recommendation "served, clicked and dismissed";
`course_opened` measures served and clicked, and there has never been a
dismissed. Precision@5 (ADR-025) has had a positive signal only -- "five shown,
one opened" and "five shown, one opened, four explicitly rejected" were the
same rows, indistinguishable.

**The analytics CHECK is rewritten by hand**, as in 0020/0024/0027: Alembic
does not diff CHECK bodies, and `record()` swallows its own failures, so a
name added to `EVENT_NAMES` alone would produce events that silently never
appear -- the exact failure mode `tests/test_enumerations.py` exists to catch
statically instead.

The names are frozen here rather than imported from the model, for the same
reason 0024 gives: a migration describes one moment, and importing the live
tuple would make this revision produce a wider constraint the day a later
sprint adds a name.
"""

from collections.abc import Sequence

from alembic import op

from api.core.database import one_of

revision: str = "0031"
down_revision: str | None = "0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_BEFORE = (
    "matches_viewed",
    "match_opened",
    "gap_viewed",
    "course_recommended",
    "course_opened",
    "employer_overview_viewed",
    "employer_shortlist_viewed",
    "application_submitted",
    "application_withdrawn",
    "application_status_changed",
    "job_saved",
    "role_suggested",
    "skills_bulk_added",
    "course_interest_registered",
    "course_interest_withdrawn",
    "course_interest_status_changed",
    "member_invited",
    "member_invitation_accepted",
    "member_removed",
    "member_role_changed",
    "job_closed",
    "job_reopened",
    "job_alerts_sent",
)
_ADDED = ("course_dismissed",)


def upgrade() -> None:
    op.drop_constraint("ck_analytics_event_name", "analytics_events", type_="check")
    op.create_check_constraint(
        "ck_analytics_event_name", "analytics_events", one_of("name", _BEFORE + _ADDED)
    )


def downgrade() -> None:
    # A row carrying the name the narrower constraint forbids would block it.
    op.execute("DELETE FROM analytics_events WHERE name = 'course_dismissed'")
    op.drop_constraint("ck_analytics_event_name", "analytics_events", type_="check")
    op.create_check_constraint(
        "ck_analytics_event_name", "analytics_events", one_of("name", _BEFORE)
    )
