"""Public interface of the skills module.

Other modules import from `api.modules.skills` only. Reaching into `.service` or
`.models` directly is what makes a modular monolith rot into a tangle, and is
what ADR-014's microservices path depends on avoiding.
"""

from api.modules.skills.models import ALIAS_SCRIPTS, SKILL_TYPES, Skill, SkillAlias
from api.modules.skills.routes import router
from api.modules.skills.service import (
    SearchHit,
    count_skills,
    get_skill_by_slug,
    list_skills,
    search_skills,
)

__all__ = [
    "ALIAS_SCRIPTS",
    "SKILL_TYPES",
    "SearchHit",
    "Skill",
    "SkillAlias",
    "count_skills",
    "get_skill_by_slug",
    "list_skills",
    "router",
    "search_skills",
]
