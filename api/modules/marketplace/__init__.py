"""Public interface of the marketplace module.

Other modules import from `api.modules.marketplace` only — never from
`.service` or `.models` directly (ADR-014).
"""

from api.modules.marketplace.course_publishing_routes import (
    router as course_publishing_router,
)
from api.modules.marketplace.models import (
    COURSE_LANGUAGES,
    COURSE_MODES,
    EDUCATION_LEVELS,
    EMPLOYMENT_TYPES,
    SKILL_SOURCES,
    STATUSES,
    CandidateProfile,
    CandidateSkill,
    Course,
    CourseSkill,
    Job,
    JobSkill,
)
from api.modules.marketplace.profile_routes import router as profile_router
from api.modules.marketplace.profile_service import (
    add_skill,
    ensure_profile,
    get_or_create_profile,
    remove_skill,
    update_profile,
)
from api.modules.marketplace.publishing_routes import router as publishing_router
from api.modules.marketplace.routes import (
    courses_router,
    jobs_router,
    marketplace_router,
)
from api.modules.marketplace.service import (
    count_courses,
    count_jobs,
    courses_teaching_skill,
    get_course_by_slug,
    get_job_by_slug,
    jobs_requiring_skill,
    list_courses,
    list_jobs,
)

__all__ = [
    "COURSE_LANGUAGES",
    "COURSE_MODES",
    "EDUCATION_LEVELS",
    "EMPLOYMENT_TYPES",
    "SKILL_SOURCES",
    "STATUSES",
    "CandidateProfile",
    "CandidateSkill",
    "Course",
    "CourseSkill",
    "Job",
    "JobSkill",
    "count_courses",
    "count_jobs",
    "courses_router",
    "courses_teaching_skill",
    "get_course_by_slug",
    "get_job_by_slug",
    "jobs_requiring_skill",
    "jobs_router",
    "add_skill",
    "ensure_profile",
    "get_or_create_profile",
    "list_courses",
    "list_jobs",
    "marketplace_router",
    "profile_router",
    "course_publishing_router",
    "publishing_router",
    "remove_skill",
    "update_profile",
]
