"""What a National Occupational Standard actually says (ADR-004, ADR-034).

A unit's title is a label — and some of them are literally "OJT", "Project" or
"10.1. Case Studies". The substance is here: ~893,000 rows across four tables.

* **Performance criteria** (349,874) — atomic, assessable "can do X" statements,
  each carrying its own theory / practical / viva / OJT marks, grouped under
  55,747 element headings.
* **Knowledge and understanding** (292,762) — what the candidate must know.
* **Generic skill criteria** (250,281) — the GS1…GSn soft-skill list.

This is the substrate ADR-007 matching, honest gap analysis and ADR-013
embeddings need. "You are missing *this capability*" cannot be said from titles.

**Every table keys on `(parent, ordinal)`, never on the source's own id.**
`pcID` repeats within a unit in 17 of 6,000 standards sampled, `kpID` in 1 and
`skillID` in 2 — a natural key on the source id would fail the import partway
through. The source id is kept alongside, for traceability only.
"""

import uuid

from sqlalchemy import ForeignKey, Index, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.core.database import Base


class PerformanceElement(Base):
    """A named grouping of performance criteria, with the marks for the group."""

    __tablename__ = "skill_performance_elements"
    __table_args__ = (
        UniqueConstraint("skill_id", "ordinal", name="uq_performance_element_ordinal"),
        Index("ix_performance_elements_skill_id", "skill_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    skill_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("skills.id", ondelete="CASCADE"))
    ordinal: Mapped[int] = mapped_column()
    name_en: Mapped[str] = mapped_column(Text)
    name_hi: Mapped[str | None] = mapped_column(Text, default=None)

    theory_marks: Mapped[float | None] = mapped_column(Numeric(8, 2), default=None)
    practical_marks: Mapped[float | None] = mapped_column(Numeric(8, 2), default=None)
    viva_marks: Mapped[float | None] = mapped_column(Numeric(8, 2), default=None)
    ojt_marks: Mapped[float | None] = mapped_column(Numeric(8, 2), default=None)
    total_marks: Mapped[float | None] = mapped_column(Numeric(8, 2), default=None)

    criteria: Mapped[list["PerformanceCriterion"]] = relationship(
        back_populates="element", cascade="all, delete-orphan"
    )


class PerformanceCriterion(Base):
    """One assessable statement. The atomic unit of what a standard requires."""

    __tablename__ = "skill_performance_criteria"
    __table_args__ = (
        UniqueConstraint("element_id", "ordinal", name="uq_performance_criterion_ordinal"),
        Index("ix_performance_criteria_element_id", "element_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    element_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("skill_performance_elements.id", ondelete="CASCADE")
    )
    ordinal: Mapped[int] = mapped_column()
    # The source's own "PC1"/"PC2" label. Not unique within a unit, so it is
    # carried for traceability and is never part of a key.
    pc_ref: Mapped[str | None] = mapped_column(String(32), default=None)
    description_en: Mapped[str] = mapped_column(Text)
    description_hi: Mapped[str | None] = mapped_column(Text, default=None)

    theory_marks: Mapped[float | None] = mapped_column(Numeric(8, 2), default=None)
    practical_marks: Mapped[float | None] = mapped_column(Numeric(8, 2), default=None)
    viva_marks: Mapped[float | None] = mapped_column(Numeric(8, 2), default=None)
    ojt_marks: Mapped[float | None] = mapped_column(Numeric(8, 2), default=None)
    total_marks: Mapped[float | None] = mapped_column(Numeric(8, 2), default=None)

    element: Mapped["PerformanceElement"] = relationship(back_populates="criteria")


class KnowledgeParameter(Base):
    """What the candidate must know, as distinct from what they must do."""

    __tablename__ = "skill_knowledge_params"
    __table_args__ = (
        UniqueConstraint("skill_id", "ordinal", name="uq_knowledge_param_ordinal"),
        Index("ix_knowledge_params_skill_id", "skill_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    skill_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("skills.id", ondelete="CASCADE"))
    ordinal: Mapped[int] = mapped_column()
    kp_ref: Mapped[str | None] = mapped_column(String(32), default=None)
    text_en: Mapped[str] = mapped_column(Text)
    text_hi: Mapped[str | None] = mapped_column(Text, default=None)


class GenericCriterion(Base):
    """The GS1…GSn soft-skill list: writing, reading, teamwork, decision making.

    Heavily repeated across standards — 250,281 rows resolve to 58,998 distinct
    statements — which is why this is the cheapest layer to translate and the
    most valuable to deduplicate.
    """

    __tablename__ = "skill_generic_criteria"
    __table_args__ = (
        UniqueConstraint("skill_id", "ordinal", name="uq_generic_criterion_ordinal"),
        Index("ix_generic_criteria_skill_id", "skill_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    skill_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("skills.id", ondelete="CASCADE"))
    ordinal: Mapped[int] = mapped_column()
    gs_ref: Mapped[str | None] = mapped_column(String(32), default=None)
    text_en: Mapped[str] = mapped_column(Text)
    text_hi: Mapped[str | None] = mapped_column(Text, default=None)
