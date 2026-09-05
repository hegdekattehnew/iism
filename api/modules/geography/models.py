"""Indian administrative geography, as the NSQF master data defines it.

Its own module rather than part of `skills` because it is not a taxonomy
concept: jobs, candidate profiles and preferred locations all reference it, and
none of them are skills.

Two things the source dictates:

* **The `district` collection carries no state reference at all.** A district is
  tied to a state only by the array embedded in the state document, so that
  array is the authority for the hierarchy and the standalone collection
  contributes sub-districts only.
* **The policy flags live only on the embedded copy.** Aspirational, border,
  tribal, LWE and north-east are precisely the axes government skilling schemes
  target, so they are worth carrying even though nothing consumes them yet.
"""

import uuid

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.core.database import Base


class State(Base):
    """36 states and union territories. All active in the source."""

    __tablename__ = "states"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    state_code: Mapped[int] = mapped_column(unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    slug: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    # NCVET's own identifier for the state, which differs from stateCode.
    ncvet_code: Mapped[str | None] = mapped_column(String(32), default=None)
    status: Mapped[str | None] = mapped_column(String(32), default=None)

    districts: Mapped[list["District"]] = relationship(
        back_populates="state", cascade="all, delete-orphan"
    )


class District(Base):
    """767 districts. Eight carry no name in the source and are kept anyway --
    the code is still a valid reference, and dropping them would silently break
    any row pointing at one."""

    __tablename__ = "districts"
    __table_args__ = (Index("ix_districts_state_id", "state_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    district_code: Mapped[int] = mapped_column(unique=True, index=True)
    state_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("states.id", ondelete="CASCADE"))
    name: Mapped[str | None] = mapped_column(String(160), default=None)
    slug: Mapped[str | None] = mapped_column(String(200), unique=True, index=True, default=None)
    short_name: Mapped[str | None] = mapped_column(String(64), default=None)

    # Scheme-targeting attributes, carried verbatim from the source.
    is_aspirational: Mapped[bool] = mapped_column(default=False, server_default="false")
    is_border: Mapped[bool] = mapped_column(default=False, server_default="false")
    is_tribal: Mapped[bool] = mapped_column(default=False, server_default="false")
    is_lwe: Mapped[bool] = mapped_column(default=False, server_default="false")
    is_north_east: Mapped[bool] = mapped_column(default=False, server_default="false")
    is_rural_or_municipal: Mapped[bool] = mapped_column(default=False, server_default="false")

    state: Mapped["State"] = relationship(back_populates="districts")
    sub_districts: Mapped[list["SubDistrict"]] = relationship(
        back_populates="district", cascade="all, delete-orphan"
    )


class SubDistrict(Base):
    """7,138 sub-districts (tehsils / mandals / blocks).

    `code` is nullable and not unique: a handful of source rows carry a name
    with no code, and codes are not guaranteed distinct across districts.
    """

    __tablename__ = "sub_districts"
    __table_args__ = (
        UniqueConstraint("district_id", "name", name="uq_sub_district_name"),
        Index("ix_sub_districts_district_id", "district_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    district_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("districts.id", ondelete="CASCADE"))
    code: Mapped[int | None] = mapped_column(default=None, index=True)
    name: Mapped[str] = mapped_column(String(160))

    district: Mapped["District"] = relationship(back_populates="sub_districts")
