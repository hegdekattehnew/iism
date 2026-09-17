"""One table for every translation, and one way to read it (ADR-041).

Translatable text used to be a column pair per field -- `title` beside
`title_hi` -- which reached 18 pairs across 12 tables and made a third language
a schema migration. The base column now holds the text in the row's own
language, `source_locale` says which language that is, and everything else
lives here.

**This module is generic on purpose.** It names entities by string, not by
foreign key: a translation table cannot hold an FK to twelve different parents,
and `core` must not import a feature module (ADR-014). The cost is that a
deleted row's translations are not removed by the database -- `delete_for()`
is what the owning module calls instead.
"""

import uuid
from collections.abc import Iterable, Sequence
from datetime import datetime
from typing import TYPE_CHECKING, Protocol

from fastapi import Depends, Query, Request
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Index,
    Text,
    UniqueConstraint,
    func,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from api.core.database import Base, one_of
from api.core.security import get_optional_user

if TYPE_CHECKING:  # pragma: no cover - typing only
    from api.modules.identity.models import User

# What can be translated. Closed, like every other set in this project: an open
# string column becomes four spellings of "qualification_pack" within a month.
ENTITY_TYPES = (
    "skill",
    "skill_concept",
    "job",
    "course",
    "awarding_body",
    "sector",
    "sub_sector",
    "occupation",
    "qualification_pack",
    "model_curriculum",
    "performance_element",
    "performance_criterion",
    "knowledge_parameter",
    "generic_criterion",
)

# The translatable fields, after the rename: `title` -> `title` and so on.
FIELDS = ("name", "title", "description", "text", "job_role")

# Where the text came from. A machine translation and a reviewed one are not
# the same claim, and a product that cannot tell them apart cannot later decide
# to show only one.
SOURCES = ("human", "machine", "imported")

# The default when nothing else is known -- the corpus is published in English.
DEFAULT_LOCALE = "en"


class ContentTranslation(Base):
    """One field, in one language, for one row.

    **`locale` deliberately carries no CHECK.** Every other closed set in this
    project has one; constraining this one would put "add a language" back into
    a migration, which is the whole thing ADR-041 removes.
    """

    __tablename__ = "content_translations"
    __table_args__ = (
        UniqueConstraint(
            "entity_type", "entity_id", "field", "locale", name="uq_content_translation"
        ),
        CheckConstraint(one_of("entity_type", ENTITY_TYPES), name="ck_content_translation_entity"),
        CheckConstraint(one_of("field", FIELDS), name="ck_content_translation_field"),
        CheckConstraint(one_of("source", SOURCES), name="ck_content_translation_source"),
        # The shape every read uses: give me this locale for these rows.
        Index("ix_content_translations_lookup", "entity_type", "locale", "entity_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    entity_type: Mapped[str]
    entity_id: Mapped[uuid.UUID]
    field: Mapped[str]
    locale: Mapped[str]
    text: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(default="human")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


async def translations_for(
    db: AsyncSession,
    entity_type: str,
    entity_ids: Sequence[uuid.UUID],
    locale: str,
) -> dict[tuple[uuid.UUID, str], str]:
    """Every translation these rows have in this locale, in one query.

    Keyed by `(entity_id, field)`. **Batched deliberately**: a per-row lookup
    would put back the N+1 that Sprint 20 took out of the employer overview,
    and a listing page asks for fifty rows at a time.
    """
    if not entity_ids or locale == DEFAULT_LOCALE:
        # The default locale is never *stored* as a translation: it is either
        # the row's own source text or it is a fallback, and both are already
        # in the base column.
        return {}
    rows = (
        await db.execute(
            select(
                ContentTranslation.entity_id,
                ContentTranslation.field,
                ContentTranslation.text,
            ).where(
                ContentTranslation.entity_type == entity_type,
                ContentTranslation.locale == locale,
                ContentTranslation.entity_id.in_(entity_ids),
            )
        )
    ).all()
    return {(entity_id, field): text for entity_id, field, text in rows}


def resolve(
    translations: dict[tuple[uuid.UUID, str], str],
    entity_id: uuid.UUID,
    field: str,
    source_text: str | None,
) -> str | None:
    """Requested language, else the row's own text.

    The caller holds the fallback chain in one place rather than at every
    render site -- which is what the 37 `isHi && x.name_hi ? … : x.name`
    ternaries were, one chain spelled out 37 times.
    """
    return translations.get((entity_id, field)) or source_text


async def upsert(
    db: AsyncSession,
    entity_type: str,
    entity_id: uuid.UUID,
    field: str,
    locale: str,
    text: str,
    *,
    source: str = "human",
) -> None:
    """Write one translation, replacing any it already had."""
    existing = await db.scalar(
        select(ContentTranslation).where(
            ContentTranslation.entity_type == entity_type,
            ContentTranslation.entity_id == entity_id,
            ContentTranslation.field == field,
            ContentTranslation.locale == locale,
        )
    )
    if existing is not None:
        existing.text = text
        existing.source = source
        return
    db.add(
        ContentTranslation(
            entity_type=entity_type,
            entity_id=entity_id,
            field=field,
            locale=locale,
            text=text,
            source=source,
        )
    )


async def delete_for(db: AsyncSession, entity_type: str, entity_ids: Iterable[uuid.UUID]) -> None:
    """Remove translations for rows that are going.

    There is no foreign key to cascade from -- see this module's docstring --
    so the owning module calls this when it deletes. An orphaned translation is
    invisible rather than harmful, which is exactly why it would accumulate.
    """
    ids = list(entity_ids)
    if not ids:
        return
    from sqlalchemy import delete as sql_delete

    await db.execute(
        sql_delete(ContentTranslation).where(
            ContentTranslation.entity_type == entity_type,
            ContentTranslation.entity_id.in_(ids),
        )
    )


def negotiate(header: str | None, override: str | None, preferred: str | None) -> str:
    """Which language to answer in.

    Order: an explicit `?locale=`, then `Accept-Language`, then the account's
    `preferred_locale`, then the default.

    **The header beats the stored preference, and that ordering is deliberate.**
    The web client sends the locale of the page the person is actually reading
    -- the one they chose with the switcher -- while `users.preferred_locale`
    defaults to `"en"` for every account and no surface writes it yet. Ranking
    it first meant a default silently overrode a real choice: every signed-in
    reader got English on `/hi`, which is precisely what the first test of this
    endpoint caught. When a real preference control exists, it can move ahead
    of the header, because then it will mean something.

    Parsing is deliberately shallow -- the first tag, region stripped. Quality
    values are a negotiation this product does not need: it has a handful of
    locales, not a content-negotiated API.
    """
    if override:
        return override.strip().lower().split("-")[0]
    if header:
        first = header.split(",")[0].strip().lower()
        if first and first != "*":
            return first.split(";")[0].split("-")[0]
    if preferred:
        return preferred.strip().lower().split("-")[0]
    return DEFAULT_LOCALE


class HasId(Protocol):
    """Anything with a primary key -- which is every row this resolves for."""

    id: uuid.UUID


async def overrides_for(
    db: AsyncSession,
    entity_type: str,
    rows: Sequence[HasId],
    fields: Sequence[str],
    locale: str,
) -> dict[uuid.UUID, dict[str, str]]:
    """Per-row field overrides for a page of rows, in one query.

    Returned as plain dictionaries rather than applied to the rows themselves.
    **Never mutate the loaded row**: several read endpoints call `record()`,
    which commits, so a translated title assigned to an ORM instance would be
    written back to the database as though someone had edited the listing.
    """
    ids = [row.id for row in rows]
    translations = await translations_for(db, entity_type, ids, locale)
    if not translations:
        return {}
    out: dict[uuid.UUID, dict[str, str]] = {}
    for row in rows:
        row_id = row.id
        found = {
            field: translations[(row_id, field)]
            for field in fields
            if (row_id, field) in translations
        }
        if found:
            out[row_id] = found
    return out


async def request_locale(
    request: Request,
    locale: str | None = Query(None, description="Override the negotiated language"),
    user: "User | None" = Depends(get_optional_user),
) -> str:
    """The language this response should be in (ADR-041).

    A dependency rather than a parameter on forty handlers, for the reason
    `require()` absorbed its second question in Sprint 15: a thing every
    handler must remember is one that eventually is not there.
    """
    return negotiate(
        request.headers.get("accept-language"),
        locale,
        user.preferred_locale if user is not None else None,
    )
