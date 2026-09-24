"""Route handlers validate and delegate; they do not talk to the database.

The convention has been stated since the first commit (`CLAUDE.md`, and §8.2 of
the product definition). An audit on 2026-09-24 found **17 violations across 107
handlers** -- 84% conformant, which is the number a rule reaches when nothing
checks it.

Most were not sloppiness. `record()` commits, so it has to run *after* the
business commit and outside it, and the handlers that did so were reasoning
correctly about a real constraint. The fix was not to delete that reasoning but
to move it into the service that owns the write, where the ordering is a
property of one function instead of something every handler has to remember.

So this reads the route layer and fails when a handler or a route-module helper
touches the session or the analytics recorder. Both are stand-ins for the same
thing: a decision that outlived the request it was made in.

It reads the source rather than exercising the app. The question is whether the
call is *there*, which is a property of the module -- and a behavioural test
would need one case per handler to ask it.
"""

import ast
from pathlib import Path

import pytest

API = Path(__file__).resolve().parent.parent / "api"

# Anything that reaches the session. `db.refresh` and `db.get` are here for the
# same reason `db.commit` is: they are the service's business, and a handler
# that needs one is a handler that has taken a decision it should have passed on.
SESSION_CALLS = {
    "scalar",
    "scalars",
    "execute",
    "get",
    "add",
    "add_all",
    "commit",
    "flush",
    "delete",
    "refresh",
    "merge",
}

# Measurement. `record()` commits, which is exactly why it must not be here.
RECORDERS = {"record", "record_many", "_record"}

HTTP_VERBS = {"get", "post", "put", "patch", "delete", "head", "options"}


def _route_modules() -> list[Path]:
    return sorted(p for p in API.rglob("*.py") if p.name == "main.py" or "routes" in p.name)


def _offences(path: Path) -> list[tuple[str, list[str]]]:
    """Every function in this module that reaches the session or the recorder."""
    out: list[tuple[str, list[str]]] = []
    for node in ast.walk(ast.parse(path.read_text())):
        if not isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
            continue
        hits: set[str] = set()
        for sub in ast.walk(node):
            if not isinstance(sub, ast.Call):
                continue
            func = sub.func
            if (
                isinstance(func, ast.Attribute)
                and isinstance(func.value, ast.Name)
                and func.value.id == "db"
                and func.attr in SESSION_CALLS
            ):
                hits.add(f"db.{func.attr}()")
            if isinstance(func, ast.Name):
                if func.id in RECORDERS:
                    hits.add(f"{func.id}()")
                elif func.id == "select":
                    hits.add("select()")
        if hits:
            out.append((node.name, sorted(hits)))
    return out


def _handlers(path: Path) -> list[str]:
    names = []
    for node in ast.walk(ast.parse(path.read_text())):
        if not isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
            continue
        if any(
            isinstance(d, ast.Call)
            and isinstance(d.func, ast.Attribute)
            and d.func.attr in HTTP_VERBS
            for d in node.decorator_list
        ):
            names.append(node.name)
    return names


MODULES = _route_modules()
HANDLER_COUNT = sum(len(_handlers(p)) for p in MODULES)


class TestTheRouteLayerDelegates:
    def test_there_are_route_modules_and_handlers_to_check(self) -> None:
        """Anti-vacuity, and it is not theoretical.

        An empty list satisfies every assertion below. If a refactor renames
        `routes.py`, or the decorators stop being `@router.<verb>`, this file
        would go green while checking nothing -- which is how a guard becomes
        decoration. The floors are well under the real numbers (21 modules, 107
        handlers at the time of writing) so ordinary growth never trips them.
        """
        assert len(MODULES) >= 15, [p.name for p in MODULES]
        assert HANDLER_COUNT >= 80, HANDLER_COUNT

    def test_the_detector_can_actually_see_a_violation(self) -> None:
        """The other half of anti-vacuity: prove the matcher matches.

        Without this, a typo in `SESSION_CALLS` or a broken walk would report a
        clean route layer for ever.
        """
        probe = ast.parse(
            "async def handler(db):\n"
            "    row = await db.scalar(select(Thing))\n"
            "    await record(db, 'x')\n"
        )
        hits: set[str] = set()
        for sub in ast.walk(probe):
            if not isinstance(sub, ast.Call):
                continue
            f = sub.func
            if (
                isinstance(f, ast.Attribute)
                and isinstance(f.value, ast.Name)
                and f.value.id == "db"
                and f.attr in SESSION_CALLS
            ):
                hits.add(f"db.{f.attr}()")
            if isinstance(f, ast.Name) and f.id in RECORDERS | {"select"}:
                hits.add(f"{f.id}()")
        assert hits == {"db.scalar()", "record()", "select()"}

    @pytest.mark.parametrize("module", MODULES, ids=lambda p: str(p.name))
    def test_no_handler_reaches_the_session_or_the_recorder(self, module: Path) -> None:
        offences = _offences(module)
        assert not offences, "\n".join(
            f"{module.relative_to(API.parent)}::{name} calls {', '.join(calls)} "
            f"-- move it into the service that owns the write"
            for name, calls in offences
        )
