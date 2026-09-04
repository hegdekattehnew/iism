"""Public interface of the skills module.

Other modules import from `api.modules.skills` only. Reaching into `.service` or
`.models` directly is what makes a modular monolith rot into a tangle, and is
what ADR-014's microservices path depends on avoiding.
"""

from api.modules.skills.models import ALIAS_SCRIPTS, SKILL_TYPES, Skill, SkillAlias
from api.modules.skills.routes import router
from api.modules.skills.schemas import NsqfLevel, NsqfLevelIn
from api.modules.skills.service import (
    QualificationRef,
    SearchHit,
    count_skills,
    get_skill_by_slug,
    list_skills,
    qualifications_for_skill,
    search_skills,
    skill_facets,
)

__all__ = [
    "ALIAS_SCRIPTS",
    "SKILL_TYPES",
    "NsqfLevel",
    "NsqfLevelIn",
    "QualificationRef",
    "SearchHit",
    "Skill",
    "SkillAlias",
    "count_skills",
    "get_skill_by_slug",
    "list_skills",
    "qualifications_for_skill",
    "router",
    "search_skills",
    "skill_facets",
]
