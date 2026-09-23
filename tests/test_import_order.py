"""Every module boots, whichever is imported first.

Several modules import each other, and each cycle is broken by a function-local
import: `matching` <-> `applications` (Sprint 21), `core.authorization` ->
`identity` (Sprint 13), and in Sprint 23 both `skills` and `marketplace` ->
`analytics`, because `analytics` loads its routes, which load
`marketplace.models`, which load `skills`.

The failure is an ImportError at boot, not a wrong answer -- and it depends on
**which module is imported first**. Inside the test process everything is
already in `sys.modules`, so a cycle that would kill a fresh worker passes here
unnoticed. Hence one fresh interpreter per starting point.

CLAUDE.md said a test asserted both orders for `matching` and `applications`
from Sprint 21 onwards. None did until this file.
"""

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

ENTRY_POINTS = [
    "api.modules.alerts",
    "api.modules.analytics",
    "api.modules.applications",
    "api.modules.identity",
    "api.modules.interests",
    "api.modules.marketplace",
    "api.modules.matching",
    "api.modules.notifications",
    "api.modules.operations",
    "api.modules.privacy",
    "api.modules.skills",
    "api.core.authorization",
    "api.main",
    "api.worker",
]


@pytest.mark.parametrize("module", ENTRY_POINTS)
def test_it_imports_first_in_a_fresh_interpreter(module: str) -> None:
    result = subprocess.run(
        [sys.executable, "-c", f"import {module}"],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    assert result.returncode == 0, result.stderr.strip().splitlines()[-1:]
