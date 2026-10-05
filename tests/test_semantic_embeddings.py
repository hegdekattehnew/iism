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


class _OtherModel:
    """A stand-in for the real provider: same 384 dimensions, a different model."""

    name = "sentence_transformer"
    model = "a-different-model"

    def embed(self, text: str) -> list[float]:
        return [0.5] * 384


class TestAProviderSwitchRefreshesOldVectors:
    """Both sweeps selected only `embedding IS NULL`, so switching from the
    placeholder to the real model left every old vector in place, and a query
    vector from one model was then compared against stored vectors from
    another."""

    async def test_a_job_embedded_by_another_model_is_recomputed(
        self, db: AsyncSession, monkeypatch
    ) -> None:  # type: ignore[no-untyped-def]
        skill = await _skill_with_criteria(db, "switch-job-skill", criteria=["Stack the shelves"])
        job = await _published_job_with_skill(db, skill)
        await _refresh_jobs(db)
        await db.refresh(job)
        assert job.embedding_model != _OtherModel.model

        monkeypatch.setattr("api.adapters.embeddings.get_embedding_provider", lambda: _OtherModel())
        processed = await _refresh_jobs(db)
        await db.refresh(job)

        assert processed >= 1
        assert job.embedding_model == _OtherModel.model
        assert job.embedding_provider == "sentence_transformer"

    async def test_a_second_sweep_with_the_same_model_leaves_it_alone(
        self, db: AsyncSession, monkeypatch
    ) -> None:  # type: ignore[no-untyped-def]
        skill = await _skill_with_criteria(db, "switch-stable-skill", criteria=["Label the stock"])
        job = await _published_job_with_skill(db, skill)
        monkeypatch.setattr("api.adapters.embeddings.get_embedding_provider", lambda: _OtherModel())
        await _refresh_jobs(db)
        await db.refresh(job)

        assert await _refresh_jobs(db) == 0

    async def test_a_profile_embedded_by_another_model_is_recomputed(
        self, db: AsyncSession, monkeypatch
    ) -> None:  # type: ignore[no-untyped-def]
        from api.modules.marketplace.models import CandidateSkill

        skill = await _skill_with_criteria(db, "switch-profile-skill", criteria=["Greet people"])
        user = User(phone=f"+9197{uuid.uuid4().int % 100000000:08d}")
        db.add(user)
        await db.flush()
        profile = CandidateProfile(user_id=user.id)
        db.add(profile)
        await db.flush()
        db.add(CandidateSkill(profile_id=profile.id, skill_id=skill.id, proficiency=3))
        await db.commit()
        await _refresh_profiles(db)
        await db.refresh(profile)
        assert profile.embedding_model != _OtherModel.model

        monkeypatch.setattr("api.adapters.embeddings.get_embedding_provider", lambda: _OtherModel())
        await _refresh_profiles(db)
        await db.refresh(profile)
        assert profile.embedding_model == _OtherModel.model


class TestTheRoleSweep:
    async def test_it_embeds_nothing_under_the_placeholder_provider(self, db: AsyncSession) -> None:
        """`search_roles` never reads a role vector under hashing, so the sweep
        was embedding about 4,400 packs for nothing."""
        from api.modules.skills.hierarchy import QualificationPack
        from api.modules.skills.tasks import _refresh_packs

        # A pack that is current and unembedded: without the early return it
        # would be picked up. An empty table would make this pass for nothing.
        pack = QualificationPack(
            qp_code=f"TST/Q{uuid.uuid4().int % 100000:05d}",
            version="1.0",
            name="Cashier",
            job_role="Cashier",
            slug=f"cashier-{uuid.uuid4().hex[:8]}",
            is_current=True,
        )
        db.add(pack)
        await db.commit()

        assert await _refresh_packs(db) == 0
        await db.refresh(pack)
        assert pack.embedding is None

    async def test_it_embeds_stale_packs_once_a_real_provider_is_active(
        self, db: AsyncSession, monkeypatch
    ) -> None:  # type: ignore[no-untyped-def]
        from api.modules.skills.hierarchy import QualificationPack
        from api.modules.skills.tasks import _refresh_packs

        pack = QualificationPack(
            qp_code=f"TST/Q{uuid.uuid4().int % 100000:05d}",
            version="1.0",
            name="Warehouse Assistant",
            job_role="Warehouse Assistant",
            slug=f"warehouse-assistant-{uuid.uuid4().hex[:8]}",
            is_current=True,
        )
        db.add(pack)
        await db.commit()

        monkeypatch.setattr("api.adapters.embeddings.get_embedding_provider", lambda: _OtherModel())
        assert await _refresh_packs(db) >= 1
        await db.refresh(pack)
        assert pack.embedding_model == _OtherModel.model


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


class TestASweepCannotStallBehindWhatItCannotEmbed:
    """Sprint 50. A profile with no declared standard has no text, stays `embedding IS NULL`,
    and was picked again first on every tick: `LIMIT` with no `ORDER BY` returned the same
    rows. A hundred of them -- profiles are created lazily, so that is ordinary -- and nothing
    behind them was ever embedded."""

    async def test_profiles_behind_unembeddable_ones_are_still_embedded(
        self, db: AsyncSession, monkeypatch
    ) -> None:  # type: ignore[no-untyped-def]
        from api.modules.marketplace.models import CandidateSkill
        from api.modules.matching import tasks

        monkeypatch.setattr(tasks, "BATCH_SIZE", 5)
        skill = await _skill_with_criteria(db, "stall-profile-skill", criteria=["Greet people"])

        async def profile(n: int, with_skill: bool) -> CandidateProfile:
            user = User(phone=f"+9196{n:08d}")
            db.add(user)
            await db.flush()
            # Fixed ids, so the tie-break among never-looked-at rows is not luck: the one that
            # can be embedded sorts *last*, and the sweep has to get to it on the second tick.
            p = CandidateProfile(user_id=user.id, id=uuid.UUID(int=n + 1))
            db.add(p)
            await db.flush()
            if with_skill:
                db.add(CandidateSkill(profile_id=p.id, skill_id=skill.id, proficiency=3))
            return p

        # Created first, so heap order puts them ahead of the one that can be embedded.
        for n in range(7):
            await profile(n, with_skill=False)
        skilled = await profile(99, with_skill=True)
        await db.commit()

        await _refresh_profiles(db)
        await _refresh_profiles(db)
        await db.refresh(skilled)

        assert skilled.embedding is not None, "the sweep never got past the unembeddable rows"

    async def test_the_row_looked_at_longest_ago_goes_first(
        self, db: AsyncSession, monkeypatch
    ) -> None:  # type: ignore[no-untyped-def]
        """Rows already stamped recently queue behind one stamped long ago -- which is what a
        profile that has just been given its first skill looks like."""
        from datetime import UTC, datetime, timedelta

        from api.modules.marketplace.models import CandidateSkill
        from api.modules.matching import tasks

        monkeypatch.setattr(tasks, "BATCH_SIZE", 5)
        skill = await _skill_with_criteria(db, "order-profile-skill", criteria=["Greet people"])
        recent = datetime.now(UTC) - timedelta(hours=1)
        long_ago = datetime.now(UTC) - timedelta(days=30)
        for n in range(7):
            user = User(phone=f"+9194{n:08d}")
            db.add(user)
            await db.flush()
            db.add(CandidateProfile(user_id=user.id, embedding_computed_at=recent))
        user = User(phone="+919400009999")
        db.add(user)
        await db.flush()
        skilled = CandidateProfile(user_id=user.id, embedding_computed_at=long_ago)
        db.add(skilled)
        await db.flush()
        db.add(CandidateSkill(profile_id=skilled.id, skill_id=skill.id, proficiency=3))
        await db.commit()

        await _refresh_profiles(db)
        await db.refresh(skilled)

        assert skilled.embedding is not None, "a row looked at long ago did not go first"

    async def test_an_unembeddable_row_is_looked_at_and_goes_to_the_back(
        self, db: AsyncSession
    ) -> None:
        user = User(phone=f"+9195{uuid.uuid4().int % 100000000:08d}")
        db.add(user)
        await db.flush()
        empty = CandidateProfile(user_id=user.id)
        db.add(empty)
        await db.commit()
        assert empty.embedding_computed_at is None

        await _refresh_profiles(db)
        await db.refresh(empty)

        assert empty.embedding is None
        assert empty.embedding_computed_at is not None

    async def test_jobs_behind_unembeddable_ones_are_still_embedded(
        self, db: AsyncSession, monkeypatch
    ) -> None:  # type: ignore[no-untyped-def]
        from api.modules.matching import tasks

        monkeypatch.setattr(tasks, "BATCH_SIZE", 5)
        tenant = Tenant(slug="stall-job-employer", name="Stall Co", tenant_type="employer")
        db.add(tenant)
        await db.flush()
        for n in range(7):  # published, with no standard at all
            db.add(
                Job(slug=f"stall-empty-{n}", tenant_id=tenant.id, title="Empty", status="published")
            )
        await db.flush()
        skill = await _skill_with_criteria(db, "stall-job-skill", criteria=["Stack shelves"])
        skilled = await _published_job_with_skill(db, skill)

        await _refresh_jobs(db)
        await _refresh_jobs(db)
        await db.refresh(skilled)

        assert skilled.embedding is not None, "the sweep never got past the unembeddable rows"
