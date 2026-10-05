"""Build a marketplace big enough to ask whether matching still works (Sprint 49).

Every number this project has quoted came from a few dozen candidates and about
a hundred and fifty vacancies, and the retrieval stage -- the part that exists
*because* growth does not survive scoring everyone (ADR-007) -- had never run
against a catalogue larger than its own cap. This fills a **separate database**
with a synthetic one, so `make benchmark` can measure it.

**It refuses to run against anything but a database whose name ends in
`_scale`.** The rows are synthetic, but the delete that makes a re-run
idempotent is a delete, and "the wrong `DATABASE_URL`" is how a harness becomes
an incident. `make seed-scale` creates `iism_scale` from a copy of the dev
database (so it carries the real taxonomy and real vacancies) and points this
at it.

**Deterministic.** Ids are derived from an index and every random draw is a hash
of an index, so two runs give identical rows -- a benchmark whose data moves
cannot show whether a change helped. No `random()`, no `gen_random_uuid()`.

**Skewed on purpose.** Real standards are not equally popular: a handful of
generic units are held by most candidates and required by most vacancies. A
uniform draw would hide the very thing retrieval has to survive. `--skew` is the
exponent on a uniform draw (1 = uniform, 3 = a few standards dominate). The
default is steeper than the real corpus will be; the *structure* of the finding
does not depend on it, and the knob is there so that can be checked.

**Noisy on purpose, too.** Evidence source, level floor and experience floor are
drawn at random. The retrieval bound treats those three components as full marks,
so it is exact when they never vary and loosest when they do; a harness where
every candidate is `self_declared` and no vacancy has a level floor would show
perfect recall for a reason that has nothing to do with the bound being good.

What it does not model: geography, languages, or any correlation between a
candidate's evidence and their standards.
"""

import argparse
import asyncio
import sys
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.engine import make_url

from api.core.config import get_settings
from api.core.database import dispose_engine, get_engine, get_sessionmaker

PHONE_PREFIX = "+9170"
SLUG_PREFIX = "scale-job-"
# Programmes the opt-in `--enrolled` seeding creates. A small one beside the large one, so the
# benchmark can time the old per-candidate report on fifty people and extrapolate rather than wait
# an hour for it on ten thousand.
PROGRAMME_SMALL = "SCALE-PROGRAMME-SMALL"
PROGRAMME_LARGE = "SCALE-PROGRAMME"
SMALL_SIZE = 50

# A hash of two strings as a number in [0, 1). Deterministic, and independent of
# plan shape -- `random()` after `setseed()` is not, once a join reorders.
_U = "((('x' || substr(md5({a} || ':' || {b}), 1, 8))::bit(32)::bigint) / 4294967296.0)"


def u(a: str, b: str) -> str:
    return _U.format(a=a, b=b)


def salted(salt: str, index: str) -> str:
    """`u()` of one index under a named salt, so each column draws independently."""
    return u(f"'{salt}' || {index}", "'x'")


def _guard() -> str:
    name = make_url(get_settings().database_url).database or ""
    if not name.endswith("_scale"):
        sys.exit(
            f"Refusing to run: database is {name!r}, and this only runs against one whose name "
            "ends in '_scale'. Use `make seed-scale`, which creates iism_scale."
        )
    return name


@dataclass(frozen=True)
class Extras:
    """Things the retrieval benchmark never needed and the rest of the product does."""

    skill_less: int = 0
    enrolled: int = 0
    applicants: int = 0
    notifications: int = 0


async def _extras(db, go, candidates: int, e: Extras) -> None:  # type: ignore[no-untyped-def]
    """Deterministic like everything here: rows are named by an index, never by `random()`."""
    profile = "md5('scale-profile-' || i)::uuid"
    if e.skill_less:
        # The first N profiles hold no standard at all -- lazily created profiles are common,
        # and they are the rows an embedding sweep cannot embed.
        print(f"  {e.skill_less:,} candidates with no declared standard")
        await go(
            f"DELETE FROM candidate_skills WHERE profile_id IN "
            f"(SELECT {profile} FROM generate_series(1, :n) i)",
            n=e.skill_less,
        )
    if e.enrolled:
        first = e.skill_less + 1
        print(f"  {e.enrolled:,} enrolled in {PROGRAMME_LARGE} ({SMALL_SIZE} in {PROGRAMME_SMALL})")
        await go(
            f"UPDATE candidate_profiles SET enrolled_via_programme = :tag WHERE id IN "
            f"(SELECT {profile} FROM generate_series(CAST(:a AS int), CAST(:b AS int)) i)",
            tag=PROGRAMME_SMALL,
            a=first,
            b=first + SMALL_SIZE - 1,
        )
        await go(
            f"UPDATE candidate_profiles SET enrolled_via_programme = :tag WHERE id IN "
            f"(SELECT {profile} FROM generate_series(CAST(:a AS int), CAST(:b AS int)) i)",
            tag=PROGRAMME_LARGE,
            a=first + SMALL_SIZE,
            b=first + SMALL_SIZE + e.enrolled - 1,
        )
    if e.applicants:
        print(f"  {e.applicants:,} applicants to scale-job-1")
        await go(
            "INSERT INTO applications (id, job_id, profile_id, status, contact_shared_at) "
            f"SELECT md5('scale-app-' || i)::uuid, md5('scale-job-1')::uuid, {profile}, "
            "       'applied', now() FROM generate_series(1, :n) i",
            n=e.applicants,
        )
    if e.notifications:
        print(f"  {e.notifications:,} pending in-app notifications and 200 pending email")
        await go(
            "INSERT INTO notifications (id, recipient_kind, recipient_id, channel, template, "
            "                           payload, locale, status, attempts, created_at) "
            "SELECT md5('scale-note-' || i)::uuid, 'user', "
            "       md5('scale-user-' || (1 + i % :c))::uuid, 'in_app', 'job_alert', "
            '       \'{"scale": true, "vacancy": "x", "organisation": "y", '
            '         "path": "/jobs/x"}\'::jsonb, '
            "       'en', 'pending', 0, now() - ((i % 80) || ' days')::interval "
            "FROM generate_series(1, :n) i",
            n=e.notifications,
            c=candidates,
        )
        await go(
            "INSERT INTO notifications (id, recipient_kind, recipient_id, channel, template, "
            "                           payload, locale, status, attempts, created_at) "
            "SELECT md5('scale-mail-' || i)::uuid, 'user', "
            "       md5('scale-user-' || (1 + i % :c))::uuid, 'email', 'job_alert', "
            '       \'{"scale": true, "vacancy": "x", "organisation": "y", '
            '         "path": "/jobs/x"}\'::jsonb, '
            "       'en', 'pending', 0, now() - (i || ' minutes')::interval "
            "FROM generate_series(1, 200) i",
            c=candidates,
        )


async def _run(
    candidates: int,
    vacancies: int,
    skew: float,
    per_cand: int,
    per_job: int,
    districts: int,
    extras: "Extras",
) -> None:
    name = _guard()
    async with get_sessionmaker()() as db:

        async def go(sql: str, **params: object) -> None:
            await db.execute(text(sql), params)

        print(f"database {name}: clearing earlier synthetic rows")
        # Notifications carry no foreign key, so nothing cascades to them.
        await go("DELETE FROM notifications WHERE payload->>'scale' = 'true'")
        await go(
            "DELETE FROM candidate_skills WHERE profile_id IN "
            "(SELECT p.id FROM candidate_profiles p JOIN users u ON u.id = p.user_id "
            " WHERE u.phone LIKE :pp)",
            pp=PHONE_PREFIX + "%",
        )
        await go(
            "DELETE FROM candidate_profiles WHERE user_id IN "
            "(SELECT id FROM users WHERE phone LIKE :pp)",
            pp=PHONE_PREFIX + "%",
        )
        await go("DELETE FROM users WHERE phone LIKE :pp", pp=PHONE_PREFIX + "%")
        await go(
            "DELETE FROM job_skills WHERE job_id IN (SELECT id FROM jobs WHERE slug LIKE :sp)",
            sp=SLUG_PREFIX + "%",
        )
        await go("DELETE FROM jobs WHERE slug LIKE :sp", sp=SLUG_PREFIX + "%")

        # The vocabulary demand is drawn from: the standards the *real* vacancies
        # already require, in a fixed order. Candidates and synthetic vacancies
        # both pick from it, so a candidate's standards are ones some vacancy asks
        # for, which is what makes retrieval's candidate set large.
        await go("DROP TABLE IF EXISTS scale_hot")
        await go(
            "CREATE TEMP TABLE scale_hot AS "
            "SELECT skill_id, row_number() OVER (ORDER BY skill_id) AS rn "
            "FROM (SELECT DISTINCT skill_id FROM job_skills) q"
        )
        hot = (await db.execute(text("SELECT count(*) FROM scale_hot"))).scalar_one()
        if not hot:
            sys.exit("No vacancy requires a standard in this database; seed it first.")

        def pick(a: str, b: str) -> str:
            # A skewed rank in 1..hot: power(u, skew) crowds draws onto low ranks.
            return f"1 + floor({hot} * power({u(a, b)}, {skew}))::int"

        print(f"generating {candidates:,} candidates ({per_cand} standards each, skew {skew})")
        await go(
            "INSERT INTO users (id, phone, is_active, preferred_locale, is_staff) "
            "SELECT md5('scale-user-' || i)::uuid, :pp || lpad(i::text, 8, '0'), true, 'en', false "
            "FROM generate_series(1, :n) i",
            pp=PHONE_PREFIX,
            n=candidates,
        )
        await go(
            "INSERT INTO candidate_profiles "
            "(id, user_id, years_experience, willing_to_relocate, job_alerts_enabled) "
            "SELECT md5('scale-profile-' || i)::uuid, md5('scale-user-' || i)::uuid, "
            f"       floor({salted('yrs', 'i')} * 16)::int, "
            "       false, true "
            "FROM generate_series(1, :n) i",
            n=candidates,
        )
        await go(
            "INSERT INTO candidate_skills (id, profile_id, skill_id, proficiency, source) "
            "SELECT md5('scale-cs-' || r.i || '-' || r.g)::uuid, "
            "       md5('scale-profile-' || r.i)::uuid, h.skill_id, "
            "       1 + floor(" + u("'prof' || r.i", "r.g::text") + " * 5)::int, "
            "       CASE WHEN " + u("'src' || r.i", "r.g::text") + " < 0.60 THEN 'self_declared' "
            "            WHEN " + u("'src' || r.i", "r.g::text") + " < 0.75 THEN 'inferred' "
            "            WHEN " + u("'src' || r.i", "r.g::text") + " < 0.85 THEN 'assessed' "
            "            ELSE 'certified' END "
            "FROM (SELECT i, g, " + pick("'cs' || i", "g::text") + " AS k "
            "      FROM generate_series(1, :n) i CROSS JOIN generate_series(1, :m) g) r "
            "JOIN scale_hot h ON h.rn = r.k "
            "ON CONFLICT (profile_id, skill_id) DO NOTHING",
            n=candidates,
            m=per_cand,
        )

        print(f"generating {vacancies:,} vacancies ({per_job} standards each)")
        await go("DROP TABLE IF EXISTS scale_emp")
        await go(
            "CREATE TEMP TABLE scale_emp AS SELECT id, row_number() OVER (ORDER BY id) AS rn "
            "FROM tenants WHERE tenant_type = 'employer'"
        )
        employers = (await db.execute(text("SELECT count(*) FROM scale_emp"))).scalar_one()
        if not employers:
            sys.exit("No employer exists in this database; seed it first.")
        await go(
            "INSERT INTO jobs (id, slug, tenant_id, title, employment_type, experience_min_years, "
            "                  nsqf_level_min, status, positions) "
            "SELECT md5('scale-job-' || i)::uuid, :sp || i, "
            f"       (SELECT id FROM scale_emp WHERE rn = 1 + (i % {employers})), "
            "       'Scale Job ' || i, 'full_time', "
            f"       floor({salted('jy', 'i')} * 6)::int, "
            f"       CASE WHEN {salted('jl', 'i')} < 0.25 THEN NULL "
            f"            ELSE 3 + floor({salted('jl2', 'i')} * 4)::int END, "
            "       'published', 1 "
            "FROM generate_series(1, :n) i",
            sp=SLUG_PREFIX,
            n=vacancies,
        )
        await go(
            "INSERT INTO job_skills (id, job_id, skill_id, importance, is_mandatory) "
            "SELECT md5('scale-js-' || r.i || '-' || r.g)::uuid, md5('scale-job-' || r.i)::uuid, "
            "       h.skill_id, 1 + floor(" + u("'imp' || r.i", "r.g::text") + " * 5)::int, "
            "       " + u("'man' || r.i", "r.g::text") + " < 0.5 "
            "FROM (SELECT i, g, " + pick("'js' || i", "g::text") + " AS k "
            "      FROM generate_series(1, :n) i CROSS JOIN generate_series(1, :m) g) r "
            "JOIN scale_hot h ON h.rn = r.k "
            "ON CONFLICT (job_id, skill_id) DO NOTHING",
            n=vacancies,
            m=per_job,
        )
        # Place them. The first `districts` districts by code, each candidate and each
        # vacancy in one by a hash of its own id, so a district's size is not an
        # accident of generation order. Without this the skill-gap view has nothing to
        # group by: the synthetic rows would all be "Unknown".
        if districts:
            await go("DROP TABLE IF EXISTS scale_dist")
            await go(
                "CREATE TEMP TABLE scale_dist AS "
                "SELECT id, state_id, row_number() OVER (ORDER BY district_code) AS rn "
                "FROM districts ORDER BY district_code LIMIT :n",
                n=districts,
            )
            placed = (await db.execute(text("SELECT count(*) FROM scale_dist"))).scalar_one()
            slot = "(('x' || substr(md5({col}::text), 1, 8))::bit(32)::bigint % :k) + 1"
            await go(
                "UPDATE candidate_profiles p SET district_id = d.id, state_id = d.state_id "
                "FROM scale_dist d, users u "
                "WHERE u.id = p.user_id AND u.phone LIKE :pp AND d.rn = " + slot.format(col="p.id"),
                pp=PHONE_PREFIX + "%",
                k=placed,
            )
            await go(
                "UPDATE jobs j SET district_id = d.id, state_id = d.state_id "
                "FROM scale_dist d WHERE j.slug LIKE :sp AND d.rn = " + slot.format(col="j.id"),
                sp=SLUG_PREFIX + "%",
                k=placed,
            )
        # --- opt-in extras (Sprint 50). Off by default, so a plain `make seed-scale` is
        # byte-identical to the dataset Sprint 49's numbers were taken on.
        await _extras(db, go, candidates, extras)
        await db.commit()

    # ANALYZE outside the transaction: the planner's choices are what is being
    # measured, so it must see the real row counts.
    engine = get_engine()
    async with engine.connect() as conn:
        conn = await conn.execution_options(isolation_level="AUTOCOMMIT")
        await conn.execute(text("ANALYZE"))
    async with get_sessionmaker()() as db:
        rows = (
            await db.execute(
                text(
                    "SELECT (SELECT count(*) FROM candidate_profiles), "
                    "(SELECT count(*) FROM candidate_skills), "
                    "(SELECT count(*) FROM jobs WHERE status = 'published'), "
                    "(SELECT count(*) FROM job_skills), "
                    "(SELECT max(c) FROM "
                    "  (SELECT count(*) c FROM candidate_skills GROUP BY skill_id) t)"
                )
            )
        ).one()
    print(
        f"done: {rows[0]:,} profiles, {rows[1]:,} candidate skills, {rows[2]:,} open vacancies, "
        f"{rows[3]:,} job skills; the commonest standard is held by {rows[4]:,} candidates"
    )
    await dispose_engine()


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--candidates", type=int, default=50_000)
    p.add_argument("--vacancies", type=int, default=5_000)
    p.add_argument("--skew", type=float, default=3.0, help="1 = uniform; higher = concentrated")
    p.add_argument("--skills-per-candidate", type=int, default=20)
    p.add_argument("--skills-per-vacancy", type=int, default=5)
    p.add_argument("--districts", type=int, default=25, help="spread rows over this many; 0 = none")
    p.add_argument("--skill-less", type=int, default=0, help="candidates holding no standard")
    p.add_argument("--enrolled", type=int, default=0, help="candidates enrolled in a programme")
    p.add_argument("--applicants", type=int, default=0, help="applications to scale-job-1")
    p.add_argument("--notifications", type=int, default=0, help="pending in-app notifications")
    a = p.parse_args()
    if a.skew < 1.0:
        sys.exit("--skew must be at least 1 (1 is uniform)")
    asyncio.run(
        _run(
            a.candidates,
            a.vacancies,
            a.skew,
            a.skills_per_candidate,
            a.skills_per_vacancy,
            a.districts,
            Extras(a.skill_less, a.enrolled, a.applicants, a.notifications),
        )
    )


if __name__ == "__main__":
    main()
