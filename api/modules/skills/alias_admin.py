"""Editing role aliases without an engineer (Sprint 47, BL-12.15, ADR-054).

Role-alias coverage is the product's weakest point -- 43 of 3,417 roles -- and the people
who can improve it are not engineers: somebody who knows what a ward attendant is called in
Kanpur. This is what lets them. It owns the rules and the writes; the operator routes that
reach it live in `operations/` and carry only the permission.

**Three rules sit here, once.**

* *An alias is valid if it passes the same checks `make check-role-aliases` runs.*
  `alias_problems()` is called, not copied: the target must be a current role with
  standards, never a disability-track pack, and the key must not be a role's exact title
  aliased elsewhere. A screen and a script that disagreed about what "wrong" means would be
  two checkers, and the second would drift.
* *The seed never touches an operator's work* (`sync_seed_aliases`). It used to delete the
  whole table on every run.
* *Nothing is deleted by hand.* An operator **retires** an alias; the row stays, owned by
  the operator, so a dict that still names the key cannot bring it back.

The target is stored as the corpus spells it (`AliasTarget.job_role`), not as typed:
search compares `lower(btrim(...))`, so a stray space is harmless, but the screen should
show a reviewer the role's real name.
"""

import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import delete, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from api.modules.skills.hierarchy import RoleAlias, RoleAliasEvent
from api.modules.skills.role_aliases import MIN_ALIAS_PREFIX
from api.modules.skills.service import (
    ROLE_REPRESENTATIVE_ORDER,
    alias_prefix_collisions,
    alias_problems,
)

MIN_KEY_LENGTH = 2
MAX_KEY_LENGTH = 80
MAX_NOTE_LENGTH = 300


@dataclass(frozen=True)
class AliasTarget:
    """The role an alias would resolve to: the pack that stands for it (role search's rule)."""

    job_role: str
    slug: str
    qp_code: str
    nsqf_level: float | None
    standards_count: int
    sector_name: str | None


@dataclass
class AliasCheck:
    """What would happen if this alias were added."""

    surface_form: str
    target: AliasTarget | None
    problems: list[str] = field(default_factory=list)
    """Reasons it must be refused."""
    warnings: list[str] = field(default_factory=list)
    """Ambiguity worth knowing about and never a refusal: role search is a typeahead."""
    existing: str | None = None
    """`active` if the key already has a live alias, `retired` if it had one."""
    conflict: bool = False
    """True when the only problem is that the key is taken: a 409, not a 422."""

    @property
    def ok(self) -> bool:
        return not self.problems


def normalise_key(raw: str) -> str:
    """Lower case, one space between words, nothing at the ends -- what a person types."""
    return " ".join(raw.lower().split())


def _key_problem(key: str) -> str | None:
    if len(key) < MIN_KEY_LENGTH:
        return f"A term needs at least {MIN_KEY_LENGTH} characters."
    if len(key) > MAX_KEY_LENGTH:
        return f"A term is at most {MAX_KEY_LENGTH} characters."
    if any(ch in key for ch in "%_\\") or any(not ch.isprintable() for ch in key):
        return "A term cannot contain %, _, a backslash or control characters."
    return None


async def resolve_target(db: AsyncSession, job_role: str) -> AliasTarget | None:
    """The pack that stands for this role, or `None` if no current qualification with
    standards has that job role. Case and surrounding space do not matter."""
    row = (
        await db.execute(
            text(
                f"""
                SELECT c.job_role, c.slug, c.qp_code, c.nsqf_level, c.standards, sec.name AS sector
                FROM (
                    SELECT qp.job_role, qp.slug, qp.qp_code, qp.nsqf_level, qp.sector_id,
                           lower(btrim(qp.job_role)) AS role_key,
                           (SELECT count(*) FROM qp_skills s WHERE s.qp_id = qp.id) AS standards
                    FROM qualification_packs qp
                    WHERE qp.is_current AND qp.job_role IS NOT NULL
                ) c
                LEFT JOIN sectors sec ON sec.id = c.sector_id
                WHERE c.standards > 0 AND c.role_key = :target
                ORDER BY {ROLE_REPRESENTATIVE_ORDER}
                LIMIT 1
                """
            ),
            {"target": " ".join(job_role.lower().split())},
        )
    ).first()
    if row is None:
        return None
    return AliasTarget(
        job_role=row.job_role.strip(),
        slug=row.slug,
        qp_code=row.qp_code,
        nsqf_level=float(row.nsqf_level) if row.nsqf_level is not None else None,
        standards_count=int(row.standards),
        sector_name=row.sector,
    )


async def _active_aliases(db: AsyncSession) -> dict[str, str]:
    rows = await db.execute(
        select(RoleAlias.surface_form, RoleAlias.job_role).where(RoleAlias.retired_at.is_(None))
    )
    return {row[0]: row[1] for row in rows.all()}


async def check_alias(db: AsyncSession, surface_form: str, job_role: str) -> AliasCheck:
    """What would stop this alias, and what is worth knowing about it. Writes nothing."""
    key = normalise_key(surface_form)
    check = AliasCheck(surface_form=key, target=None)

    if (problem := _key_problem(key)) is not None:
        check.problems.append(problem)
        return check

    check.target = await resolve_target(db, job_role)
    if check.target is None:
        check.problems.append(
            f"No current qualification with standards has the job role {job_role.strip()!r}. "
            "Pick the role from the list."
        )
        return check

    # The Sprint 43 rules, from the one place that holds them.
    report = await alias_problems(db, {key: check.target.job_role})
    if report.disability_track:
        check.problems.append(
            f"{check.target.job_role!r} resolves to a disability-track pack "
            f"({check.target.qp_code}). Point the term at the general role."
        )
    if report.shadowed:
        check.problems.append(
            f"{key!r} is itself a role's exact title. Aliasing it elsewhere would send "
            "somebody who typed that title in full to a different role."
        )

    existing = await db.scalar(select(RoleAlias).where(RoleAlias.surface_form == key))
    if existing is not None:
        check.existing = "retired" if existing.retired_at is not None else "active"
        if existing.retired_at is None:
            check.problems.append(
                f"{key!r} already points at {existing.job_role!r}. Retire it first to change it."
            )
            check.conflict = not (report.disability_track or report.shadowed)

    # Ambiguity, not refusal: another role already claims a prefix of this term.
    active = {k: v.lower().strip() for k, v in (await _active_aliases(db)).items() if k != key}
    collisions = alias_prefix_collisions({**active, key: check.target.job_role.lower().strip()})
    for prefix, targets in collisions.items():
        if key.startswith(prefix) and len(prefix) >= MIN_ALIAS_PREFIX:
            others = [t for t in targets if t != check.target.job_role.lower().strip()]
            if others:
                check.warnings.append(
                    f"Typing {prefix!r} also reaches {', '.join(others)}; the typeahead will "
                    "offer both."
                )
    return check


def _refusal(check: AliasCheck) -> HTTPException:
    return HTTPException(
        status.HTTP_409_CONFLICT if check.conflict else status.HTTP_422_UNPROCESSABLE_ENTITY,
        " ".join(check.problems),
    )


def _clean_note(note: str | None) -> str | None:
    cleaned = (note or "").strip()
    return cleaned[:MAX_NOTE_LENGTH] or None


async def add_alias(
    db: AsyncSession,
    *,
    surface_form: str,
    job_role: str,
    note: str | None,
    actor_user_id: uuid.UUID,
) -> RoleAlias:
    """Add an alias, or revive a retired one, after the same checks `check_alias` reports.

    Revival keeps the row (and so the key's history) and hands it to the operator: a row
    the seed once owned is theirs the moment they decide about it.
    """
    check = await check_alias(db, surface_form, job_role)
    if not check.ok or check.target is None:
        raise _refusal(check)
    target = check.target.job_role

    revived = await db.scalar(
        select(RoleAlias)
        .where(RoleAlias.surface_form == check.surface_form)
        .with_for_update(of=RoleAlias)
        .execution_options(populate_existing=True)
    )
    try:
        async with db.begin_nested():
            if revived is not None:
                if revived.retired_at is None:
                    # Added by somebody else between the check and here.
                    raise HTTPException(
                        status.HTTP_409_CONFLICT, f"{check.surface_form!r} already has an alias."
                    )
                revived.job_role = target
                revived.retired_at = None
                revived.source = "operator"
                alias = revived
            else:
                alias = RoleAlias(
                    surface_form=check.surface_form, job_role=target, source="operator"
                )
                db.add(alias)
            await db.flush()
    except IntegrityError:
        # Two operators adding the same key at once: the constraint decides (ADR-052).
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"{check.surface_form!r} already has an alias."
        ) from None

    db.add(
        RoleAliasEvent(
            action="added",
            surface_form=check.surface_form,
            job_role=target,
            note=_clean_note(note),
            actor_user_id=actor_user_id,
        )
    )
    await db.commit()
    await db.refresh(alias)
    return alias


async def retire_alias(
    db: AsyncSession, alias_id: uuid.UUID, *, note: str | None, actor_user_id: uuid.UUID
) -> RoleAlias:
    """Withdraw an alias. The row stays, owned by the operator, so the seed cannot revive it."""
    # `FOR UPDATE`: two operators retiring one alias must not both write an event.
    alias = await db.scalar(
        select(RoleAlias)
        .where(RoleAlias.id == alias_id)
        .with_for_update(of=RoleAlias)
        .execution_options(populate_existing=True)
    )
    if alias is None or alias.retired_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Alias not found")
    alias.retired_at = datetime.now(UTC)
    alias.source = "operator"
    db.add(
        RoleAliasEvent(
            action="retired",
            surface_form=alias.surface_form,
            job_role=alias.job_role,
            note=_clean_note(note),
            actor_user_id=actor_user_id,
        )
    )
    await db.commit()
    await db.refresh(alias)
    return alias


def _like_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


async def list_aliases(
    db: AsyncSession, *, query: str | None = None, limit: int = 100
) -> tuple[list[RoleAlias], int]:
    """Live aliases, alphabetical, optionally filtered by the term or its target; and the
    total live count, so a screen can say "showing 100 of 114"."""
    live = RoleAlias.retired_at.is_(None)
    statement = select(RoleAlias).where(live)
    if query and query.strip():
        pattern = f"%{_like_escape(query.strip().lower())}%"
        statement = statement.where(
            RoleAlias.surface_form.like(pattern, escape="\\")
            | RoleAlias.job_role.ilike(pattern, escape="\\")
        )
    rows = await db.scalars(statement.order_by(RoleAlias.surface_form).limit(limit))
    total = await db.scalar(select(text("count(*)")).select_from(RoleAlias).where(live))
    return list(rows.all()), int(total or 0)


async def recent_events(db: AsyncSession, *, limit: int = 30) -> list[RoleAliasEvent]:
    rows = await db.scalars(
        select(RoleAliasEvent).order_by(RoleAliasEvent.created_at.desc()).limit(limit)
    )
    return list(rows.all())


@dataclass(frozen=True)
class SeedSync:
    added: int
    updated: int
    removed: int
    left_alone: int
    """Rows an operator owns, which the seed did not touch."""


async def sync_seed_aliases(db: AsyncSession, aliases: Mapping[str, str]) -> SeedSync:
    """Project `ROLE_ALIASES` into the table without touching an operator's work.

    Inserts what is missing, updates a `seed` row whose target changed, and removes a
    `seed` row the dict no longer names. A row with `source='operator'` -- including a
    retired one -- is left exactly as it is, whatever the dict says. This replaces the
    old "delete everything and rewrite it", which is what made the table impossible for
    anybody but an engineer to edit.
    """
    existing = {row.surface_form: row for row in (await db.scalars(select(RoleAlias))).all()}
    added = updated = removed = 0
    for key, role in aliases.items():
        row = existing.get(key)
        if row is None:
            db.add(RoleAlias(surface_form=key, job_role=role, source="seed"))
            added += 1
        elif row.source == "seed" and row.job_role != role:
            row.job_role = role
            updated += 1
    for key, row in existing.items():
        if row.source == "seed" and key not in aliases:
            await db.execute(delete(RoleAlias).where(RoleAlias.id == row.id))
            removed += 1
    await db.commit()
    return SeedSync(
        added=added,
        updated=updated,
        removed=removed,
        left_alone=sum(1 for r in existing.values() if r.source == "operator"),
    )
