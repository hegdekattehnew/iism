"""Demo candidates, and the labelled pairs the golden set scores against.

Matching cannot be judged on four declared skills across nine accounts, and it
certainly cannot be tuned that way. These profiles are written to exercise the
cases the scorer is supposed to distinguish:

* someone who holds every mandatory standard for a job and should rank first;
* someone strong on coverage but **missing one mandatory unit**, who must be
  capped rather than ranked above the first;
* someone with the right standards but only self-declared evidence;
* someone in an adjacent occupation, who should place but not lead;
* someone whose only standard belongs to an unrelated occupation, whose
  ranking must therefore *exclude* the healthcare jobs entirely rather than
  place them low.

The expectations in `GOLDEN_PAIRS` are what `scripts/evaluate_matching.py`
measures. They are asserted as *relative* orderings, never as exact scores:
pinning a number would make every future weighting change look like a
regression, which is how a golden set becomes something people delete.
"""

import asyncio
import sys

from sqlalchemy import delete, select

from api.core.database import dispose_engine, get_sessionmaker
from api.modules.identity.models import Tenant, User
from api.modules.marketplace.models import CandidateProfile, CandidateSkill
from api.modules.skills.models import Skill

# phone, name, headline, state, district, years, [(nos_code, proficiency, source)]
CANDIDATES: list[tuple[str, str, str, str, str, int, list[tuple[str, int, str]]]] = [
    (
        "+919000000001",
        "Ward-ready GDA",
        "General Duty Assistant with ward experience",
        "Tamil Nadu",
        "Chennai",
        3,
        [
            ("HSS/N6012", 4, "certified"),  # moving and positioning
            ("HSS/N6002", 4, "assessed"),  # vital parameters
            ("HSS/N9618", 4, "certified"),  # infection control
            ("HSS/N5133", 3, "self_declared"),
            ("THC/N0214", 3, "self_declared"),
        ],
    ),
    (
        # Strong coverage, but missing HSS/N9618, which the GDA job marks
        # mandatory. Must be capped below the candidate above.
        "+919000000002",
        "Almost-ready GDA",
        "Care assistant, no infection-control certificate",
        "Tamil Nadu",
        "Chennai",
        2,
        [
            ("HSS/N6012", 4, "certified"),
            ("HSS/N6002", 4, "assessed"),
            ("HSS/N6006", 4, "certified"),
            ("HSS/N5133", 4, "certified"),
            ("THC/N0214", 3, "certified"),
        ],
    ),
    (
        # Same standards as the first candidate, all self-declared. Should rank
        # below on evidence alone -- that is what the `source` column is for.
        "+919000000003",
        "Self-taught GDA",
        "Family caregiver, no formal assessment",
        "Tamil Nadu",
        "Chennai",
        1,
        [
            ("HSS/N6012", 3, "self_declared"),
            ("HSS/N6002", 3, "self_declared"),
            ("HSS/N9618", 3, "self_declared"),
            ("HSS/N5133", 3, "self_declared"),
            ("THC/N0214", 3, "self_declared"),
        ],
    ),
    (
        "+919000000004",
        "Retail associate",
        "Store assistant, payments and merchandising",
        "Karnataka",
        "Bengaluru",
        2,
        [
            ("RAS/N0115", 4, "certified"),
            ("RAS/N0104", 4, "assessed"),
            ("RAS/N0107", 3, "self_declared"),
            ("THC/N9901", 4, "certified"),
        ],
    ),
    (
        # Nothing in common with any seeded job.
        "+919000000005",
        "Unrelated background",
        "Laboratory chemical handling only",
        "Maharashtra",
        "Pune",
        1,
        [("LFS/N0533", 4, "certified")],
    ),
    # ------------------------------------------------------------------
    # A pool, not a fixture. The five above exist to make the scorer's
    # distinctions testable; these fifteen exist so a ranking has something to
    # rank. Two sectors, and for most vacancies a candidate who is *ready*
    # beside one missing exactly one mandatory standard -- because "who is
    # nearly qualified?" is the first question an employer asks, and a pool
    # with no near-misses cannot answer it.
    # ------------------------------------------------------------------
    (
        "+919000000006",
        "Experienced ward attendant",
        "Ward attendant, four years on general wards",
        "Tamil Nadu",
        "Chennai",
        4,
        [
            ("HSS/N5134", 4, "certified"),
            ("THC/N0214", 4, "certified"),
            ("HSS/N9618", 4, "assessed"),
            ("HYC/N9301", 3, "self_declared"),
        ],
    ),
    (
        # Ward attendant less the infection-control unit the job makes mandatory.
        "+919000000007",
        "Ward attendant, no infection control",
        "Ward support, certificate lapsed",
        "Tamil Nadu",
        "Chennai",
        2,
        [
            ("HSS/N5134", 4, "certified"),
            ("THC/N0214", 4, "certified"),
            ("HYC/N9301", 4, "certified"),
            ("HSS/N9620", 3, "assessed"),
        ],
    ),
    (
        "+919000000008",
        "Critical care attendant",
        "ICU attendant, five years in critical care",
        "Maharashtra",
        "Pune",
        5,
        [
            ("HYC/N3614", 5, "certified"),
            ("HSS/N6002", 4, "assessed"),
            ("HSS/N6012", 4, "certified"),
            ("HSS/N5127", 4, "certified"),
            ("HSS/N9618", 4, "certified"),
        ],
    ),
    (
        # Missing ancillary patient care, which the ICU vacancy makes mandatory.
        "+919000000009",
        "Ward nurse moving to ICU",
        "General ward, CPR certified, no ICU posting yet",
        "Maharashtra",
        "Pune",
        3,
        [
            ("HYC/N3614", 4, "certified"),
            ("HSS/N6002", 4, "certified"),
            ("HSS/N6012", 4, "certified"),
            ("HSS/N9618", 3, "assessed"),
        ],
    ),
    (
        "+919000000010",
        "Home care attendant",
        "Geriatric home care, six years with families",
        "Maharashtra",
        "Pune",
        6,
        [
            ("HSS/N6006", 5, "certified"),
            ("HSS/N6003", 4, "certified"),
            ("HSS/N6012", 4, "assessed"),
            ("HSS/N3016", 4, "certified"),
            ("MEP/N0721", 3, "self_declared"),
        ],
    ),
    (
        "+919000000011",
        "Sterile services technician",
        "CSSD technician, autoclave and biomedical waste",
        "Tamil Nadu",
        "Chennai",
        3,
        [
            ("HSS/N9618", 4, "certified"),
            ("HSS/N5647", 4, "certified"),
            ("HSS/N9620", 4, "certified"),
            ("HYC/N9605", 3, "self_declared"),
        ],
    ),
    (
        "+919000000012",
        "Phlebotomist",
        "Phlebotomy, four years in a diagnostics chain",
        "Telangana",
        "Hyderabad",
        4,
        [
            ("HSS/N0513", 5, "certified"),
            ("HSS/N9618", 4, "certified"),
            ("HSS/N0512", 4, "assessed"),
            ("HYC/N9605", 3, "self_declared"),
            ("LFS/N0533", 3, "self_declared"),
        ],
    ),
    (
        # Draws blood, no infection-control certificate. The single mandatory
        # gap that separates a shortlist from a training recommendation.
        "+919000000013",
        "Trainee phlebotomist",
        "Sample collection, no infection-control certificate",
        "Telangana",
        "Hyderabad",
        1,
        [
            ("HSS/N0513", 3, "assessed"),
            ("HSS/N0512", 3, "self_declared"),
            ("HYC/N9605", 3, "self_declared"),
            ("LFS/N0533", 4, "certified"),
        ],
    ),
    (
        "+919000000014",
        "Laboratory technician",
        "Pathology laboratory, five years of investigations",
        "Telangana",
        "Hyderabad",
        5,
        [
            ("LFS/N0533", 5, "certified"),
            ("LFS/N1306", 5, "certified"),
            ("HSS/N0511", 4, "assessed"),
            ("HSS/N0512", 4, "certified"),
            ("CPC/CAP/N0402", 3, "self_declared"),
        ],
    ),
    (
        "+919000000015",
        "Staff nurse",
        "Staff nurse, seven years across procedure areas",
        "Maharashtra",
        "Pune",
        7,
        [
            ("HSS/N5139", 5, "certified"),
            ("HSS/N5127", 5, "certified"),
            ("HSS/N3015", 4, "assessed"),
            ("HSS/N5508", 4, "certified"),
            ("MEP/N0721", 3, "self_declared"),
        ],
    ),
    (
        "+919000000016",
        "Emergency room assistant",
        "Casualty support, CPR and emergency protocols",
        "Maharashtra",
        "Pune",
        3,
        [
            ("SSD/VSQ/N0104", 4, "certified"),
            ("HYC/N3614", 5, "certified"),
            ("HSS/N3016", 4, "assessed"),
            ("HSS/N5134", 3, "self_declared"),
        ],
    ),
    (
        "+919000000017",
        "Hospital front office",
        "Front office and records at a multispeciality hospital",
        "Maharashtra",
        "Pune",
        2,
        [
            ("THC/N0129", 4, "certified"),
            ("CPC/CAP/N0402", 4, "assessed"),
            ("THC/N9901", 4, "certified"),
            ("ASC/N9839", 3, "self_declared"),
        ],
    ),
    (
        "+919000000018",
        "Store supervisor",
        "Retail supervisor, six years across two formats",
        "Karnataka",
        "Bengaluru",
        6,
        [
            ("RAS/N0101", 5, "certified"),
            ("HYC/N9301", 4, "certified"),
            ("SSC/N9001", 4, "assessed"),
            ("THC/N9901", 4, "certified"),
            ("HYC/N9605", 3, "self_declared"),
            ("RAS/N0107", 3, "self_declared"),
        ],
    ),
    (
        # Missing workplace health and safety, mandatory on the warehouse role.
        "+919000000019",
        "Warehouse hand",
        "Goods receipt and stock replenishment, no safety certificate",
        "Maharashtra",
        "Nagpur",
        2,
        [
            ("RAS/N0101", 4, "certified"),
            ("RAS/N0104", 4, "assessed"),
            ("HYC/N9605", 3, "self_declared"),
        ],
    ),
    (
        "+919000000020",
        "Delivery associate",
        "Last-mile delivery with cash handling",
        "Maharashtra",
        "Nagpur",
        3,
        [
            ("RAS/N0115", 4, "certified"),
            ("SSC/N9001", 4, "certified"),
            ("THC/N9901", 4, "assessed"),
            ("MES/N0104", 4, "certified"),
        ],
    ),
]

# (candidate phone, job slug, expectation)
GOLDEN_PAIRS: list[tuple[str, str, str]] = [
    ("+919000000001", "general-duty-assistant-chennai", "top"),
    ("+919000000002", "general-duty-assistant-chennai", "capped_missing_mandatory"),
    ("+919000000003", "general-duty-assistant-chennai", "below_assessed_peer"),
    ("+919000000004", "cashier-bengaluru", "top"),
    # Holds only a laboratory standard. Genuinely matches the lab technician
    # job -- so the expectation is not "no matches", it is that a job sharing
    # nothing with the profile never appears.
    ("+919000000005", "general-duty-assistant-chennai", "not_ranked"),
]


async def main() -> None:
    created = skills_added = 0
    async with get_sessionmaker()() as db:
        by_code = dict(
            (
                await db.execute(
                    select(Skill.nos_code, Skill.id).where(
                        Skill.source == "nsqf", Skill.nos_code.isnot(None)
                    )
                )
            ).all()  # type: ignore[arg-type]
        )
        if not by_code:
            print("No NSQF skills. Run `make import-nsqf` first.", file=sys.stderr)
            raise SystemExit(1)

        wanted = {c for _, _, _, _, _, _, rows in CANDIDATES for c, _, _ in rows}
        unknown = sorted(wanted - by_code.keys())
        if unknown:
            # A demo candidate silently losing a skill would quietly invalidate
            # the golden set, which is the one thing that must stay trustworthy.
            print(f"Unknown NOS codes: {', '.join(unknown)}", file=sys.stderr)
            raise SystemExit(1)

        for phone, name, headline, state, district, years, rows in CANDIDATES:
            user = await db.scalar(select(User).where(User.phone == phone))
            if user is None:
                user = User(phone=phone, full_name=name)
                db.add(user)
                await db.flush()
                created += 1
                db.add(
                    Tenant(
                        slug=f"personal-{phone[-4:]}",
                        name=name,
                        tenant_type="personal",
                    )
                )
            user.full_name = name

            profile = await db.scalar(
                select(CandidateProfile).where(CandidateProfile.user_id == user.id)
            )
            if profile is None:
                profile = CandidateProfile(user_id=user.id)
                db.add(profile)
            profile.headline = headline
            profile.location_state = state
            profile.location_district = district
            profile.years_experience = years
            await db.flush()

            # Rewritten wholesale: a demo profile is derived from this file, and
            # a leftover skill from an earlier edit would silently change what
            # the golden set measures.
            await db.execute(delete(CandidateSkill).where(CandidateSkill.profile_id == profile.id))
            for code, proficiency, source in rows:
                db.add(
                    CandidateSkill(
                        profile_id=profile.id,
                        skill_id=by_code[code],
                        proficiency=proficiency,
                        source=source,
                    )
                )
                skills_added += 1
            await db.flush()

        await db.commit()

    print(f"candidates created: {created}  skills attached: {skills_added}")
    await dispose_engine()


if __name__ == "__main__":
    asyncio.run(main())
