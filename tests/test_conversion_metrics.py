"""`scripts/report_conversion_metrics.py`'s own arithmetic (Sprint 38, ADR-047).

The two queries ADR-025 asks for, checked against rows this test controls
rather than the running dev database, so the assertion is about the query
being right rather than about how much real traffic happens to exist.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from api.modules.analytics.models import AnalyticsEvent
from api.modules.identity.models import Tenant, User
from api.modules.interests.models import CourseInterest
from api.modules.marketplace.models import CandidateProfile, Course
from scripts.report_conversion_metrics import click_through, enrolment_conversion


async def _provider(db: AsyncSession) -> Tenant:
    tenant = Tenant(
        slug=f"conversion-metrics-{uuid.uuid4().hex[:8]}",
        name="Metrics Co",
        tenant_type="course_provider",
    )
    db.add(tenant)
    await db.flush()
    return tenant


async def _course(db: AsyncSession, tenant_id: uuid.UUID, slug: str) -> Course:
    course = Course(slug=slug, tenant_id=tenant_id, title=slug, mode="online", status="published")
    db.add(course)
    await db.flush()
    return course


async def _user(db: AsyncSession, phone: str) -> User:
    user = User(phone=phone, full_name="Test Candidate")
    db.add(user)
    await db.flush()
    return user


async def _candidate(db: AsyncSession, phone: str) -> CandidateProfile:
    user = await _user(db, phone)
    profile = CandidateProfile(user_id=user.id)
    db.add(profile)
    await db.flush()
    return profile


async def test_click_through_counts_only_pairs_recommended_and_then_opened(
    db: AsyncSession,
) -> None:
    provider = await _provider(db)
    course_a = await _course(db, provider.id, "metrics-course-a")
    course_b = await _course(db, provider.id, "metrics-course-b")
    user = await _user(db, "+919000099011")
    other_user = await _user(db, "+919000099012")

    db.add_all(
        [
            # Recommended and opened: counts as a click-through.
            AnalyticsEvent(
                name="course_recommended",
                user_id=user.id,
                subject_type="course",
                subject_id=course_a.id,
            ),
            AnalyticsEvent(
                name="course_opened",
                user_id=user.id,
                subject_type="course",
                subject_id=course_a.id,
            ),
            # Recommended, never opened.
            AnalyticsEvent(
                name="course_recommended",
                user_id=user.id,
                subject_type="course",
                subject_id=course_b.id,
            ),
            # Opened by somebody it was never recommended to -- must not count
            # as a click-through for the pair that was recommended.
            AnalyticsEvent(
                name="course_opened",
                user_id=other_user.id,
                subject_type="course",
                subject_id=course_b.id,
            ),
            # Same event name, but `subject_type="job"` -- a pre-migration-0025
            # row that must not be mistaken for a course pair.
            AnalyticsEvent(
                name="course_recommended",
                user_id=user.id,
                subject_type="job",
                subject_id=course_a.id,
            ),
        ]
    )
    await db.commit()

    recommended, opened = await click_through(db)
    assert recommended == 2
    assert opened == 1


async def test_enrolment_conversion_counts_only_enrolled_status(db: AsyncSession) -> None:
    provider = await _provider(db)
    course = await _course(db, provider.id, "metrics-course-c")
    registered = await _candidate(db, "+919000099001")
    contacted = await _candidate(db, "+919000099002")
    enrolled = await _candidate(db, "+919000099003")

    db.add_all(
        [
            CourseInterest(course_id=course.id, profile_id=registered.id, status="registered"),
            CourseInterest(course_id=course.id, profile_id=contacted.id, status="contacted"),
            CourseInterest(course_id=course.id, profile_id=enrolled.id, status="enrolled"),
        ]
    )
    await db.commit()

    total, enrolled_count = await enrolment_conversion(db)
    assert total == 3
    assert enrolled_count == 1
