"""Every `Literal` union on a schema, against the CHECK that backs it.

The convention is that **output schemas stay permissive and input schemas carry
the constraints**, because a constraint on a response model turns one odd row
into a 500 for the whole response. `NsqfLevel` is the case that taught it: the
column was widened to `Numeric(3, 1)` and the schema stayed `int`, and every row
at 4.5 -- 38% of the taxonomy -- 500ed while every test kept passing.

The fifteen unions below sit on output models in apparent breach of that rule.
They are kept, because each names a closed set the database itself enforces, and
a permissive `str` there would give the API no vocabulary at all -- the generated
TypeScript client would type every status as `string`. What makes that safe is
not the CHECK existing; it is the CHECK and the union saying the *same thing*.
Alembic does not diff CHECK bodies, so widening one is invisible to autogenerate
and equally invisible to the schema beside it. That is the drift this file
catches, and it is the reason the exception is admissible at all.

Writing this test is what found the two that were **not** backed:
`candidate_profiles.education_level` and `preferred_employment_type` were typed
as closed unions on a response model with nothing in the database enforcing
either, while every sibling enum on the same table was constrained. That is also
why `EDUCATION_LEVELS` sat exported and read by nothing. Migration `0017` closes
both, so the list below is now the whole set — a union added without a CHECK
fails here.
"""

import re
from typing import Any, Literal, get_args, get_origin

from api.modules.identity import schemas as identity_schemas
from api.modules.identity.models import Membership, Tenant
from api.modules.identity.schemas import MembershipRole, OrgTenantType, TenantType
from api.modules.marketplace import schemas as marketplace_schemas
from api.modules.marketplace.models import (
    CandidateLanguage,
    CandidateProfile,
    CandidateSkill,
    Course,
    Job,
)
from api.modules.marketplace.schemas import (
    CourseLanguage,
    CourseMode,
    EducationLevel,
    EmploymentType,
    Gender,
    LanguageProficiency,
    NoticePeriod,
    SkillSource,
    Status,
)
from api.modules.skills import schemas as skills_schemas
from api.modules.skills.hierarchy import QpSkill
from api.modules.skills.models import Skill, SkillAlias
from api.modules.skills.schemas import AliasScript, QpRequirement, SkillType

# (schema union, model, column). Each column carries a CHECK naming the same set.
BACKED: list[tuple[Any, Any, str]] = [
    (TenantType, Tenant, "tenant_type"),
    (MembershipRole, Membership, "role"),
    (EmploymentType, Job, "employment_type"),
    (Status, Job, "status"),
    (Status, Course, "status"),
    (CourseMode, Course, "mode"),
    (CourseLanguage, Course, "language"),
    (SkillSource, CandidateSkill, "source"),
    (EducationLevel, CandidateProfile, "education_level"),
    (EmploymentType, CandidateProfile, "preferred_employment_type"),
    (Gender, CandidateProfile, "gender"),
    (NoticePeriod, CandidateProfile, "notice_period"),
    (LanguageProficiency, CandidateLanguage, "proficiency"),
    (SkillType, Skill, "skill_type"),
    (AliasScript, SkillAlias, "script"),
]


def _check_values(model: Any, column: str) -> set[str]:
    """The values a column's CHECK admits, read off the table metadata rather
    than re-spelled here — the point is to compare two independent statements
    of the same set, not to compare one to a third copy."""
    for constraint in model.__table__.constraints:
        body = getattr(getattr(constraint, "sqltext", None), "text", "")
        if re.search(rf"\b{re.escape(column)}\s+IN\s*\(", body, re.IGNORECASE):
            return set(re.findall(r"'([^']*)'", body))
    raise AssertionError(f"{model.__tablename__}.{column} has no IN-list CHECK")


class TestEachUnionMatchesItsConstraint:
    def test_every_backed_union_agrees_with_the_database(self) -> None:
        for union, model, column in BACKED:
            assert set(get_args(union)) == _check_values(model, column), (
                f"{model.__tablename__}.{column}"
            )

    def test_the_organisation_union_is_a_strict_subset(self) -> None:
        """`OrgTenantType` deliberately narrows `TenantType`: a personal
        workspace is not an organisation, which is the Sprint 13 hole. It must
        stay a subset of what the column admits, and must stay narrower."""
        assert set(get_args(OrgTenantType)) < _check_values(Tenant, "tenant_type")
        assert "personal" not in get_args(OrgTenantType)

    def test_the_qualification_link_is_covered_too(self) -> None:
        """`QpRequirement` is the one union not on a marketplace or identity
        model. Its CHECK is still hand-written rather than generated from a
        constant, so it is the likeliest of them to drift."""
        assert set(get_args(QpRequirement)) == _check_values(QpSkill, "requirement")

    def test_no_union_is_left_unbacked(self) -> None:
        """Every `Literal` alias exported by a schema module appears in
        `BACKED` above, or is deliberately not a column.

        Without this the list is a snapshot: a thirteenth union added next
        sprint would sit unconstrained and untested, which is exactly the state
        `education_level` was found in.
        """
        declared = {
            alias
            for module in (identity_schemas, marketplace_schemas, skills_schemas)
            for name, alias in vars(module).items()
            if not name.startswith("_") and get_origin(alias) is Literal
        }
        # `OrgTenantType` is a narrowing of a column, not a column of its own;
        # `QpRequirement` is checked by the test above.
        assert declared - {u for u, _, _ in BACKED} == {OrgTenantType, QpRequirement}
