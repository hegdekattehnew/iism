"""Analytics payloads. Slugs and counts only — never anything a person typed."""

from pydantic import BaseModel, Field


class CourseOpenedIn(BaseModel):
    course_slug: str = Field(max_length=200)
    # Optional: a course can be opened from a match or from browsing, and the
    # difference is exactly what click-through attribution needs.
    from_job_slug: str | None = Field(None, max_length=200)
