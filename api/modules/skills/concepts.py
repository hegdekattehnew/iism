"""One concept, many rows saying the same thing (ADR-004).

The national corpus states the same unit many times: 4,838 skill rows share a
name with another row, and `Employability Skills` alone is 67 rows across four
awarding bodies and eight levels. Each is a real, separately-coded standard, so
none can be deleted -- but if a candidate declares one row and a job requires
another, they do not match, and no amount of scoring repairs that. They are
different primary keys.

A concept is the grouping that lets both sides mean the same thing.

**The rule is derived, never authored:** same awarding body + same normalised
name + same NSQF level. Against the real corpus that yields 18,958 concepts from
21,303 rows, collapsing 2,345.

Three limits, each because merging further would assert something untrue:

* **Level is part of the key.** 576 duplicate groups span levels, and a level-4
  unit is not a level-6 unit of the same name -- they are different attainments.
* **Awarding body is part of the key.** 174 groups cross bodies, and one body's
  certification is not interchangeable with another's.
* **Nothing merges on description or similarity.** That would be a judgement,
  and this table is meant to be reproducible from the source.

Every skill belongs to a concept, including the ones with no duplicates at all.
A concept of one costs a row and saves every consumer from having two paths.
"""

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Index, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from api.core.database import Base


class SkillConcept(Base):
    """A group of skill rows that mean the same thing.

    Rebuilt by the importer on every run, like `Skill.qp_count`. It is derived
    data: nothing here should ever be edited by hand, because the next import
    would overwrite it.
    """

    __tablename__ = "skill_concepts"
    __table_args__ = (
        UniqueConstraint(
            "awarding_body_id",
            "normalised_name",
            "nsqf_level",
            name="uq_skill_concept_identity",
        ),
        Index("ix_skill_concepts_body", "awarding_body_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(280), unique=True, index=True)

    # Lower-cased, whitespace-collapsed. The grouping key, kept so the rule is
    # visible in the data rather than only in the importer.
    normalised_name: Mapped[str] = mapped_column(Text)
    name_en: Mapped[str] = mapped_column(Text)
    name_hi: Mapped[str | None] = mapped_column(Text, default=None)

    awarding_body_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("awarding_bodies.id", ondelete="CASCADE"), default=None
    )
    nsqf_level: Mapped[float | None] = mapped_column(Numeric(3, 1), default=None)

    # The member an employer is most likely to mean: the row required by the
    # most current qualifications. Ties break on nos_code so a rebuild is stable.
    canonical_skill_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("skills.id", ondelete="SET NULL"), default=None
    )
    member_count: Mapped[int] = mapped_column(default=1, server_default="1")

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    # No ORM relationship to Skill in either direction. A string-based
    # relationship only resolves if both modules are imported, which silently
    # breaks any script that loads one of them -- and every query here joins
    # explicitly regardless.
