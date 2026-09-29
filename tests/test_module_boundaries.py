"""No module calls another module's service or route layer (ADR-014).

`CLAUDE.md` said for thirty sprints that modules import one another's public
`__init__` only, "never `.service` or `.models`". An audit on 2026-09-28 found
the `.models` half untrue about sixty times over and enforced nowhere: modules
read each other's ORM tables, schemas and pure constants freely. What *did*
hold, everywhere, is the half that matters for a later split into services --
no module reaches into another's business logic. So that is the rule this
enforces, and `CLAUDE.md` now states the rule the code actually keeps.

Reads the source, like `test_route_delegation.py`: the question is whether the
import is there, which is a property of the module.
"""

import ast
import re
from pathlib import Path

MODULES = Path(__file__).resolve().parent.parent / "api" / "modules"

# `service.py`, `employer_service.py`, `routes.py`, `partner_routes.py`, ...
BUSINESS_LAYER = re.compile(r"(^|_)(service|routes)$")


def _violations(owner: str, source: str) -> list[str]:
    found = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.ImportFrom) or not node.module:
            continue
        parts = node.module.split(".")
        if parts[:2] != ["api", "modules"] or len(parts) < 3 or parts[2] == owner:
            continue
        # Both `from api.modules.x.service import f` and `from api.modules.x import service`.
        if len(parts) > 3:
            targets = [(parts[3], ".".join(parts[:4]))]
        else:
            targets = [(a.name, f"{node.module}.{a.name}") for a in node.names]
        found += [label for name, label in targets if BUSINESS_LAYER.search(name)]
    return found


def test_no_module_imports_another_modules_service_or_routes() -> None:
    files = list(MODULES.rglob("*.py"))
    owners = {f.relative_to(MODULES).parts[0] for f in files}
    # Found what it is checking before asserting anything about it.
    assert len(owners) >= 10, owners

    cross_module = 0
    bad: list[str] = []
    for f in files:
        owner = f.relative_to(MODULES).parts[0]
        source = f.read_text()
        cross_module += source.count("from api.modules.") - source.count(
            f"from api.modules.{owner}"
        )
        bad += [f"{f.relative_to(MODULES)}: {v}" for v in _violations(owner, source)]
    assert cross_module > 20, "found almost no cross-module imports; the walk is wrong"
    assert bad == []


def test_the_detector_recognises_both_import_forms() -> None:
    snippet = (
        "from api.modules.applications.employer_service import set_status\n"
        "from api.modules.matching import service\n"
        "from api.modules.identity.models import User\n"
        "from api.modules.marketplace.partner_routes import router\n"
        "from api.modules.analytics.service import record\n"
    )
    assert _violations("analytics", snippet) == [
        "api.modules.applications.employer_service",
        "api.modules.matching.service",
        "api.modules.marketplace.partner_routes",
    ]
