"""Sprint 36, BL-5.1: the embedding text, the worker sweep, and invalidation
on write. `tests/test_matching.py::TestSemanticSimilarity` covers the scoring
term itself; this covers everything that fills the two columns it reads.
"""

import uuid

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.config import PRIVACY_NOTICE_VERSION as CONSENT
from api.modules.identity.models import Tenant, User
from api.modules.marketplace.models import CandidateProfile, Job, JobSkill
from api.modules.matching.tasks import _refresh_jobs, _refresh_profiles
from api.modules.skills import embedding_text_for_skills
from api.modules.skills.content import PerformanceCriterion, PerformanceElement
from api.modules.skills.models import Skill


async def _skill_with_criteria(db: AsyncSession, slug: str, *, criteria: list[str]) -> Skill:
    skill = Skill(slug=slug, name=slug.replace("-", " ").title(), skill_type="technical")
    db.add(skill)
    await db.flush()
    element = PerformanceElement(skill_id=skill.id, ordinal=1, name="Element 1")
    db.add(element)
    await db.flush()
    for i, text in enumerate(criteria):
        db.add(PerformanceCriterion(element_id=element.id, ordinal=i, description=text))
    await db.flush()
    return skill


async def _bare_skill(db: AsyncSession, slug: str, *, description: str | None = None) -> Skill:
    skill = Skill(
        slug=slug,
        name=slug.replace("-", " ").title(),
        skill_type="technical",
        description=description,
    )
    db.add(skill)
    await db.flush()
    return skill


class TestEmbeddingText:
    async def test_joins_performance_criteria_across_skills(self, db: AsyncSession) -> None:
        a = await _skill_with_criteria(db, "wound-care-a", criteria=["Clean the wound site"])
        b = await _skill_with_criteria(db, "wound-care-b", criteria=["Apply a sterile dressing"])
        text = await embedding_text_for_skills(db, [a.id, b.id])
        assert "Clean the wound site" in text
        assert "Apply a sterile dressing" in text

    async def test_falls_back_to_description_with_no_criteria(self, db: AsyncSession) -> None:
        skill = await _bare_skill(
            db, "no-criteria-skill", description="A skill with no recorded criteria"
        )
        text = await embedding_text_for_skills(db, [skill.id])
        assert text == "A skill with no recorded criteria"

    async def test_falls_back_to_name_with_neither(self, db: AsyncSession) -> None:
        skill = await _bare_skill(db, "bare-skill-name")
        text = await embedding_text_for_skills(db, [skill.id])
        assert text == "Bare Skill Name"

    async def test_empty_input_is_empty_text(self, db: AsyncSession) -> None:
        assert await embedding_text_for_skills(db, []) == ""


async def _published_job_with_skill(db: AsyncSession, skill: Skill) -> Job:
    tenant = Tenant(
        name="Embedding Co", slug=f"embedding-co-{uuid.uuid4().hex[:8]}", tenant_type="employer"
    )
    db.add(tenant)
    await db.flush()
    job = Job(
        slug=f"embedding-job-{uuid.uuid4().hex[:8]}",
        tenant_id=tenant.id,
        title="A vacancy",
        status="published",
    )
    db.add(job)
    await db.flush()
    db.add(JobSkill(job_id=job.id, skill_id=skill.id, importance=3, is_mandatory=False))
    await db.commit()
    return job


class TestRefreshJobs:
    async def test_populates_a_null_embedding_with_provenance(self, db: AsyncSession) -> None:
        skill = await _skill_with_criteria(
            db, "job-embed-skill", criteria=["Operate the machine safely"]
        )
        job = await _published_job_with_skill(db, skill)

        processed = await _refresh_jobs(db)
        await db.refresh(job)

        assert processed >= 1
        assert job.embedding is not None
        assert len(job.embedding) == 384
        assert job.embedding_provider == "hashing"
        assert job.embedding_computed_at is not None

    async def test_a_draft_job_is_not_processed(self, db: AsyncSession) -> None:
        skill = await _skill_with_criteria(db, "draft-job-skill", criteria=["Some criterion"])
        job = await _published_job_with_skill(db, skill)
        job.status = "draft"
        await db.commit()

        await _refresh_jobs(db)
        await db.refresh(job)
        assert job.embedding is None

    async def test_an_already_embedded_job_is_left_alone(self, db: AsyncSession) -> None:
        skill = await _skill_with_criteria(db, "already-embedded-skill", criteria=["A criterion"])
        job = await _published_job_with_skill(db, skill)
        await _refresh_jobs(db)
        await db.refresh(job)
        first = job.embedding

        # A second sweep with nothing invalidated must not recompute -- the
        # query only ever selects `embedding IS NULL`.
        processed_again = await _refresh_jobs(db)
        assert processed_again == 0
        await db.refresh(job)
        assert job.embedding == first


class TestRefreshProfiles:
    async def test_populates_a_null_embedding_with_provenance(self, db: AsyncSession) -> None:
        skill = await _skill_with_criteria(
            db, "profile-embed-skill", criteria=["Communicate clearly with patients"]
        )
        user = User(phone=f"+9198{uuid.uuid4().int % 100000000:08d}")
        db.add(user)
        await db.flush()
        profile = CandidateProfile(user_id=user.id)
        db.add(profile)
        await db.flush()
        from api.modules.marketplace.models import CandidateSkill

        db.add(CandidateSkill(profile_id=profile.id, skill_id=skill.id, proficiency=3))
        await db.commit()

        processed = await _refresh_profiles(db)
        await db.refresh(profile)

        assert processed >= 1
        assert profile.embedding is not None
        assert len(profile.embedding) == 384
        assert profile.embedding_model


class TestInvalidationOnWrite:
    async def test_adding_a_skill_invalidates_an_existing_embedding(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        skill = await _skill_with_criteria(db, "invalidate-add-skill", criteria=["A criterion"])
        phone = "9" + uuid.uuid4().int.__str__()[:9]
        code = (await client.post("/auth/otp/request", json={"phone": phone})).json()["debug_code"]
        body = (
            await client.post(
                "/auth/otp/verify",
                json={"phone": phone, "code": code, "consent_version": CONSENT},
            )
        ).json()
        headers = {"authorization": f"Bearer {body['access_token']}"}
        await client.get("/me/profile", headers=headers)  # lazily creates the profile
        me = (await client.get("/auth/me", headers=headers)).json()

        profile = await db.scalar(
            select(CandidateProfile).where(CandidateProfile.user_id == uuid.UUID(me["id"]))
        )
        assert profile is not None
        profile.embedding = [0.1] * 384
        await db.commit()

        await client.post(
            "/me/profile/skills",
            headers=headers,
            json={"skill_slug": skill.slug, "proficiency": 3},
        )
        await db.refresh(profile)
        assert profile.embedding is None

    async def test_removing_a_skill_invalidates_an_existing_embedding(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        skill = await _skill_with_criteria(db, "invalidate-remove-skill", criteria=["A criterion"])
        phone = "9" + uuid.uuid4().int.__str__()[:9]
        code = (await client.post("/auth/otp/request", json={"phone": phone})).json()["debug_code"]
        body = (
            await client.post(
                "/auth/otp/verify",
                json={"phone": phone, "code": code, "consent_version": CONSENT},
            )
        ).json()
        headers = {"authorization": f"Bearer {body['access_token']}"}
        await client.post(
            "/me/profile/skills",
            headers=headers,
            json={"skill_slug": skill.slug, "proficiency": 3},
        )
        me = (await client.get("/auth/me", headers=headers)).json()
        profile = await db.scalar(
            select(CandidateProfile).where(CandidateProfile.user_id == uuid.UUID(me["id"]))
        )
        assert profile is not None
        profile.embedding = [0.1] * 384
        await db.commit()

        await client.delete(f"/me/profile/skills/{skill.slug}", headers=headers)
        await db.refresh(profile)
        assert profile.embedding is None

    async def test_changing_a_jobs_required_skills_invalidates_its_embedding(
        self, db: AsyncSession
    ) -> None:
        from api.modules.marketplace.publishing import _write_skills
        from api.modules.marketplace.schemas import JobSkillIn

        skill = await _skill_with_criteria(db, "invalidate-job-skill", criteria=["A criterion"])
        job = await _published_job_with_skill(db, skill)
        job.embedding = [0.1] * 384
        await db.commit()

        other = await _skill_with_criteria(
            db, "invalidate-job-skill-2", criteria=["Another criterion"]
        )
        await _write_skills(
            db, job, [JobSkillIn(skill_slug=other.slug, importance=3, is_mandatory=False)]
        )
        await db.commit()
        await db.refresh(job)
        assert job.embedding is None
