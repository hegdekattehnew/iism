"""What people said about a listing, and what an operator did about it (Sprint 59, ADR-069).

Fake vacancies are the main trust risk of a jobs marketplace, and until now the only moderation
lever was the owner unpublishing their own listing. A report is the reporter's own words, so the
row goes with their account; the listing it is about is not a foreign key, because a report about
a listing that was later deleted is still a fact about what was reported, and a cascade would
rewrite it. The retention purge clears the ones whose target is gone.
"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from api.core.database import Base, one_of

TARGET_TYPES = ("job", "course")
REPORT_REASONS = (
    "asks_for_money",
    "fake_or_misleading",
    "discriminatory",
    "unsafe_or_illegal",
    "spam_or_duplicate",
    "other",
)
REPORT_STATUSES = ("open", "dismissed", "actioned")
# What is no longer being worked on, and so what retention may delete.
CLOSED = ("dismissed", "actioned")

DETAIL_MAX = 1000


class ListingReport(Base):
    __tablename__ = "listing_reports"
    __table_args__ = (
        CheckConstraint(one_of("target_type", TARGET_TYPES), name="ck_listing_reports_target"),
        CheckConstraint(one_of("reason", REPORT_REASONS), name="ck_listing_reports_reason"),
        CheckConstraint(one_of("status", REPORT_STATUSES), name="ck_listing_reports_status"),
        CheckConstraint(
            f"detail IS NULL OR length(detail) <= {DETAIL_MAX}", name="ck_listing_reports_detail"
        ),
        CheckConstraint(
            "(status = 'open') = (handled_at IS NULL)", name="ck_listing_reports_handled"
        ),
        # Once per person per listing: a second report is the same report, and a brigade of one
        # is not a brigade.
        UniqueConstraint(
            "reporter_id", "target_type", "target_id", name="uq_listing_reports_reporter_target"
        ),
        Index("ix_listing_reports_target", "status", "target_type", "target_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    target_type: Mapped[str] = mapped_column()
    # Not a foreign key; see the module docstring.
    target_id: Mapped[uuid.UUID] = mapped_column()
    # Snapshots, so the queue can say what was reported after the owner renames or deletes it.
    target_slug: Mapped[str] = mapped_column()
    target_title: Mapped[str] = mapped_column()
    # The publishing organisation: named in the queue and the one told of a takedown.
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("tenants.id", ondelete="SET NULL"), default=None
    )
    # CASCADE: the report is the reporter's own words, so erasing the account erases it.
    reporter_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    reason: Mapped[str] = mapped_column()
    detail: Mapped[str | None] = mapped_column(Text, default=None)
    status: Mapped[str] = mapped_column(default="open")
    handled_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    handled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
