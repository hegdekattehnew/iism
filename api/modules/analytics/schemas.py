"""Analytics payloads. Slugs and counts only — never anything a person typed."""

from pydantic import BaseModel, Field


class CourseOpenedIn(BaseModel):
    course_slug: str = Field(max_length=200)
    # Optional: a course can be opened from a match or from browsing, and the
    # difference is exactly what click-through attribution needs.
    from_job_slug: str | None = Field(None, max_length=200)


class CourseDismissedIn(BaseModel):
    """The negative half of `CourseOpenedIn` (Sprint 33, BL-2.2). Same shape,
    same reason for `from_job_slug`: a dismissal only means something against
    the recommendation it was shown alongside."""

    course_slug: str = Field(max_length=200)
    from_job_slug: str | None = Field(None, max_length=200)
