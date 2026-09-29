"""A typed, weighted graph over skills (Sprint 36, BL-6.1).

"Most of the long-term value" per the product definition's own framing, and
until now entirely unbuilt (`docs/scope-reconciliation.md` #7). Deliberately
just the foundation: no inference reads this table yet and no career-path
recommendation consumes it (BL-6.2/6.3, held for the next planning cycle) --
a graph with no output is not demoable, and there is no cost to landing only
the model now and deferring the rest.

**A new graph, not a replacement for `concepts.py`'s `SkillConcept`.** A
concept groups rows that mean the *same* thing -- same awarding body, same
normalised name, same level, derived and rebuilt by the importer, never
edited by hand. A `SkillRelation` states a directed relationship between two
*different* skills -- one implies competence toward another, or the two are
merely related -- which equivalence grouping has no way to express and was
never meant to. `skill_concepts` is untouched by this file.
"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.core.database import Base, one_of

# Exactly the two the backlog names. A third type (e.g. "prerequisite_of", for
# BL-6.3's career paths) is additive later -- widening this tuple is a
# hand-written CHECK migration, like every other closed set in this schema,
# not a reason to speculatively add one now with no writer.
SKILL_RELATION_TYPES = ("implies", "related_to")


class SkillRelation(Base):
    """One directed, weighted edge between two skills.

    Directionality matters even for `related_to`: the source's own rows are
    not symmetric length-for-length (a broad "generic" skill relates to many
    specific ones without the reverse being equally informative), and forcing
    symmetry into one row per pair would either double-write every edge or
    silently pick a direction nobody chose. A genuinely symmetric relationship
    is two rows; that is a modelling cost worth paying for the alternative to
    stay honest.
    """

    __tablename__ = "skill_relations"
    __table_args__ = (
        CheckConstraint(
            one_of("relation_type", SKILL_RELATION_TYPES), name="ck_skill_relation_type"
        ),
        CheckConstraint("weight > 0 AND weight <= 1", name="ck_skill_relation_weight"),
        # A skill cannot relate to itself -- that is what `skill_concepts`
        # already expresses, and a self-edge here would just be a different
        # spelling of the same fact.
        CheckConstraint("from_skill_id != to_skill_id", name="ck_skill_relation_not_self"),
        UniqueConstraint(
            "from_skill_id", "to_skill_id", "relation_type", name="uq_skill_relation_edge"
        ),
        Index("ix_skill_relations_from_skill_id", "from_skill_id"),
        Index("ix_skill_relations_to_skill_id", "to_skill_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    from_skill_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("skills.id", ondelete="CASCADE"))
    to_skill_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("skills.id", ondelete="CASCADE"))
    relation_type: Mapped[str] = mapped_column()
    # How strongly `from_skill` bears on `to_skill`. Not yet read by anything
    # -- BL-6.2 is where a weighted graph traversal would consume it -- but a
    # graph with unweighted edges from day one would need a second migration
    # the moment inference actually needs to prefer a strong edge over a weak
    # one, which is exactly the kind of retrofit this table is here to avoid.
    weight: Mapped[float] = mapped_column(default=1.0)
    # Timezone-aware, unlike `tenants.created_at` (a documented, load-bearing
    # gotcha elsewhere in this schema) -- naive vs. aware is what made a
    # rolling-window query on that column refuse outright.
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    from_skill: Mapped["object"] = relationship("Skill", foreign_keys=[from_skill_id])
    to_skill: Mapped["object"] = relationship("Skill", foreign_keys=[to_skill_id])
