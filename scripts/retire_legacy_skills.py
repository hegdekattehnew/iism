"""Retire the 52 hand-curated skills onto the national standards.

Three things, in one script because they are one change and doing them
separately would leave the database briefly inconsistent:

1. **Move candidate skills.** A profile that declared "hand hygiene" should
   declare `HSS/N9618` -- otherwise the person's declared skills stop matching
   anything the moment the marketplace is re-anchored.
2. **Carry the aliases.** The 149 bilingual aliases are the only reason
   `khoon nikalna` resolves, and they attach to curated rows alone. Without
   this, Hindi and transliterated search stop reaching anything real.
3. **Mark the curated rows `legacy`**, which excludes them from search and
   browse. They are *not* deleted: profiles and certificates still reference
   them, and a foreign key is a promise.

Idempotent. Re-running moves nothing that has already moved.
"""

import asyncio
import sys

# Sibling import: `scripts/` is not an installed package, but Python puts a
# script's own directory on sys.path when it is run directly.
from legacy_skill_map import LEGACY_SKILL_MAP
from sqlalchemy import func, select

from api.core.database import dispose_engine, get_sessionmaker
from api.modules.marketplace.models import CandidateCertification, CandidateSkill
from api.modules.skills.models import Skill, SkillAlias


async def main() -> None:
    moved_skills = moved_certs = carried = retired = 0
    problems: list[str] = []

    async with get_sessionmaker()() as db:
        curated = {
            s.slug: s
            for s in (
                await db.scalars(select(Skill).where(Skill.source.in_(("curated", "legacy"))))
            )
        }
        by_nos = dict(
            (
                await db.execute(
                    select(Skill.nos_code, Skill.id).where(
                        Skill.source == "nsqf", Skill.nos_code.isnot(None)
                    )
                )
            ).all()  # type: ignore[arg-type]
        )
        if not by_nos:
            print("No NSQF skills. Run `make import-nsqf` first.", file=sys.stderr)
            raise SystemExit(1)

        # curated skill id -> NSQF skill id
        target: dict[object, object] = {}
        for slug, skill in curated.items():
            code = LEGACY_SKILL_MAP.get(slug)
            if code is None:
                problems.append(f"{slug}: no mapping")
                continue
            nsqf_id = by_nos.get(code)
            if nsqf_id is None:
                problems.append(f"{slug}: mapped to {code}, which the import did not produce")
                continue
            target[skill.id] = nsqf_id

        # --- 1. candidate skills and certificates ------------------------
        for model, counter in ((CandidateSkill, "skills"), (CandidateCertification, "certs")):
            rows = (
                await db.scalars(select(model).where(model.skill_id.in_(list(target.keys()))))
            ).all()
            for row in rows:
                new_id = target[row.skill_id]
                # A candidate may already hold the target standard, either
                # directly or via another curated skill mapping to the same one.
                # Dropping the duplicate is right; two rows would double-count.
                existing = await db.scalar(
                    select(func.count())
                    .select_from(model)
                    .where(
                        model.skill_id == new_id,
                        model.profile_id == row.profile_id,
                    )
                )
                if existing:
                    await db.delete(row)
                else:
                    row.skill_id = new_id  # type: ignore[assignment]
                if counter == "skills":
                    moved_skills += 1
                else:
                    moved_certs += 1
            await db.flush()

        # --- 2. aliases ---------------------------------------------------
        for skill in curated.values():
            nsqf_id = target.get(skill.id)
            if nsqf_id is None:
                continue
            aliases = (
                await db.scalars(select(SkillAlias).where(SkillAlias.skill_id == skill.id))
            ).all()
            for alias in aliases:
                # Several curated skills map to one standard, so the same
                # surface form can arrive twice. The alias table is unique on
                # (skill_id, surface_form).
                clash = await db.scalar(
                    select(func.count())
                    .select_from(SkillAlias)
                    .where(
                        SkillAlias.skill_id == nsqf_id,
                        SkillAlias.surface_form == alias.surface_form,
                    )
                )
                if clash:
                    continue
                db.add(
                    SkillAlias(
                        skill_id=nsqf_id,
                        surface_form=alias.surface_form,
                        script=alias.script,
                    )
                )
                carried += 1
            await db.flush()

        # --- 3. retire ----------------------------------------------------
        for skill in curated.values():
            if skill.id in target and skill.source != "legacy":
                skill.source = "legacy"
                retired += 1

        await db.commit()

    print(
        f"candidate skills moved: {moved_skills}  certificates moved: {moved_certs}  "
        f"aliases carried: {carried}  skills retired: {retired}"
    )
    for p in problems:
        print(f"  [unmapped] {p}", file=sys.stderr)
    if problems:
        print(f"{len(problems)} curated skills could not be retired.", file=sys.stderr)

    await dispose_engine()


if __name__ == "__main__":
    asyncio.run(main())
