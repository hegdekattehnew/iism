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

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from api.core.database import Base, one_of

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
