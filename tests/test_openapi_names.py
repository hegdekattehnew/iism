"""Two response models with one class name are two renamed schemas, and a client breaks.

Sprint 98 gave a batch's organisation the class name `OrgRefOut`, which delivery (Sprint 97) already
used for a different shape. FastAPI does not fail: it renames **both** to a path-qualified name
(`api__modules__delivery__schemas__OrgRefOut`), so the generated TypeScript lost `OrgRefOut` and the
Delivery screen stopped compiling, and `tsc` was the only thing that said so. A schema name that
contains `__` is that rename; a class name is unique across the API's models or this fails first.
"""

from api.main import app


def test_no_schema_was_renamed_to_avoid_a_clash() -> None:
    schemas = app.openapi()["components"]["schemas"]
    assert len(schemas) > 100, "it found the schemas it checks (an empty walk would pass)"
    renamed = sorted(name for name in schemas if "__" in name)
    assert renamed == [], (
        "Two models share a class name, so FastAPI renamed them. Give one a distinct name: "
        f"{renamed}"
    )
