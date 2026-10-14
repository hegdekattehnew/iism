"""What an operator decided about an organisation, and when.

**Append-only, and not in `analytics_events`.** That table is purged past a
retention age and `record()` swallows its own failures -- both correct for
measurement and both disqualifying for a record that has to survive and has to
fail loudly. An audit row a retention job silently deletes is not an audit row.

**Revocation is a new row, never a mutation.** "Who un-verified this, when, and
why" is only answerable in a log that keeps both decisions, and mutating would
destroy the grant a candidate may have relied on when they applied. The three
columns on `Tenant` are a projection of the latest decision, denormalised
because `TenantOut` is embedded in every `/jobs` and `/courses` payload and
joining a log per listing is absurd. On revoke those go NULL, so the reason for
a revocation lives **only** here -- which is the argument the paired design is
right rather than redundant.
"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from api.core.database import Base, one_of

# `enrolment_batch_members` points at `candidate_profiles`; SQLAlchemy resolves the ForeignKey
# against the metadata, so the target is imported for the side effect (cross-module keys).
from api.modules.marketplace import models as _marketplace_models  # noqa: F401

# A closed set, like every other one here. `granted` and `revoked` are the only
# two decisions there are: an operator either vouches for an organisation or
# stops vouching for it.
VERIFICATION_DECISIONS = ("granted", "revoked")


class TenantVerificationEvent(Base):
    """One operator decision about one organisation.

    Not a generic `operator_actions` table with `subject_type`/`payload`. That
    is the analytics shape, and half the reason analytics cannot hold this is
    that a JSONB bag is neither CHECK-able nor queryable. The note is a
    first-class column precisely because it is the thing an auditor reads.
    """

    __tablename__ = "tenant_verification_events"
    __table_args__ = (
        CheckConstraint(
            one_of("decision", VERIFICATION_DECISIONS), name="ck_verification_decision"
        ),
        # The same floor the API enforces, at the database. A note is the only
        # evidence a badge carries, and a blank one is a badge with none.
        CheckConstraint("length(btrim(note)) >= 10", name="ck_verification_note_not_blank"),
        Index("ix_tenant_verification_events_tenant_id", "tenant_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    decision: Mapped[str] = mapped_column()
    note: Mapped[str] = mapped_column(Text)
    # SET NULL, not CASCADE: an operator may exercise their own erasure, and the
    # record about the organisation must survive them. The history then reads
    # "a former operator" -- copying the address in to keep the name would
    # recreate the one row in this product that stores somebody else's address.
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EnrolmentBatch(Base):
    """One operator's enrolment of a file of people for an agency programme (Sprint 61, BL-14.10).

    **A record of the act, not of the people.** It holds the programme's free-text tag, the file's
    name, four counts and who attested that the privacy notice was read out to everyone in the
    file, against which notice version. It holds no phone, no name and no row: the people are
    `candidate_profiles` rows that point back here through `enrolment_batch_id`.

    The attestation is the whole reason the row exists. Consent is stamped against each enrolled
    person on the footing of a self sign-up, and nothing else said *who* vouched for it; this does,
    and the person's own export can name the batch. It does not verify the conversation happened.

    `actor_user_id` is SET NULL, like `tenant_verification_events`: an operator may exercise their
    own erasure and the record about the people they enrolled must survive them.
    """

    __tablename__ = "enrolment_batches"
    __table_args__ = (
        CheckConstraint("length(btrim(programme)) >= 2", name="ck_enrolment_programme_not_blank"),
        CheckConstraint(
            "created_count >= 0 AND tagged_count >= 0 AND already_count >= 0 AND error_count >= 0",
            name="ck_enrolment_counts",
        ),
        Index("ix_enrolment_batches_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    programme: Mapped[str] = mapped_column(Text)
    file_name: Mapped[str | None] = mapped_column(Text, default=None)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    attested_notice_version: Mapped[str] = mapped_column(Text)
    attested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_count: Mapped[int] = mapped_column(Integer, default=0)
    tagged_count: Mapped[int] = mapped_column(Integer, default=0)
    already_count: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# How a person came to be in a batch: an account made for them, or one that already existed and
# was tagged (and nothing else about it touched).
ENROLMENT_OUTCOMES = ("created", "tagged")


class EnrolmentBatchMember(Base):
    """Which batch put a person into a programme (Sprint 61, ADR-071).

    **A join table on this side, not a column on `candidate_profiles`.** `marketplace` cannot
    import `operations` (the dependency runs the other way, ADR-014), and a foreign key from a
    profile to a table in a module it may not import is a mapper-configuration failure for every
    script that loads one without the other. This row points *at* the profile instead. One row per
    profile, because a person already in a programme is never enrolled again; erasing the profile
    removes the row with it.
    """

    __tablename__ = "enrolment_batch_members"
    __table_args__ = (
        CheckConstraint(one_of("outcome", ENROLMENT_OUTCOMES), name="ck_enrolment_member_outcome"),
        Index("ix_enrolment_batch_members_batch_id", "batch_id"),
    )

    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("candidate_profiles.id", ondelete="CASCADE"), primary_key=True
    )
    batch_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("enrolment_batches.id", ondelete="CASCADE")
    )
    outcome: Mapped[str] = mapped_column()
