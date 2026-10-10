"""The field audit, and the two ways it could mislead.

It replaced a grep, and it found two fields the grep had missed. The tests below
pin the properties that made the difference: a field declared on two carriers is
reported for both, and an identifier that nothing resolves is still reported as
unread rather than excused.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _module():
    spec = importlib.util.spec_from_file_location(
        "unread_fields", ROOT / "scripts" / "unread_fields.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MODULE = _module()
RESULT = MODULE.measure()
BY_PAIR = {(row["carrier"], row["field"]): row for row in RESULT["fields"]}


def test_a_field_declared_on_two_carriers_is_reported_for_both() -> None:
    # The first version keyed by field name and silently kept the last carrier,
    # which reported semantic_state as the relation's alone.
    assert ("GovernedClaim", "semantic_state") in BY_PAIR
    assert ("GovernedRelation", "semantic_state") in BY_PAIR


def test_a_field_on_two_carriers_is_counted_once_in_the_summary() -> None:
    assert RESULT["unread"].count("semantic_state") == 1


def test_the_fields_the_product_plainly_uses_are_not_reported_as_unread() -> None:
    # If everything came back unread the audit would be worthless.
    for field in ("canonical_content", "claim_node_id", "relation_type", "severity"):
        assert field not in RESULT["unread"], field
        assert any(
            row["reads"] > 0 for (_, name), row in BY_PAIR.items() if name == field
        ), field


def test_the_known_unread_fields_are_found() -> None:
    # Six, where a grep over the same tree found four. finding_id and relation_id
    # are the two it missed: identifiers nothing resolves.
    assert set(RESULT["unread"]) == {
        "anchor_ambiguous",
        "anchor_normalised",
        "finding_id",
        "proposed_span",
        "relation_id",
        "semantic_state",
    }


def test_a_field_that_is_never_even_set_is_reported_apart() -> None:
    # `Finding.state` carries only its default. That is a stronger statement than
    # "unread", so it must not be folded into the same list.
    assert RESULT["never_written"] == ["state"]
    assert "state" not in RESULT["unread"]


def test_excluding_the_declaration_file_changes_nothing_today() -> None:
    """A tripwire rather than a guard, and worth saying which.

    The audit skips models.py because a declaration is not a use. Mutating that
    exclusion away changes no result, and the reason is measurable: models.py
    contains **no** per-field read of a carrier field at all. The carriers have no
    `from_dict`, and `to_dict` goes through `asdict`, so there is nothing there to
    miscount.

    So the exclusion is inert, and this test says so instead of pretending to
    cover it. It fails the day someone gives a carrier a `from_dict` — which is
    the day the exclusion starts doing work, and the day the next reader needs to
    know it is load-bearing.
    """
    import ast

    tree = ast.parse((MODULE.PRODUCT / MODULE.DECLARED_IN).read_text(encoding="utf-8"))
    names = {field for _, field in MODULE.fields_of(MODULE.CARRIERS)}
    reads = [
        node
        for node in ast.walk(tree)
        if (isinstance(node, ast.Attribute) and node.attr in names)
        or (
            isinstance(node, ast.Subscript)
            and isinstance(node.slice, ast.Constant)
            and node.slice.value in names
        )
    ]
    assert reads == [], (
        "models.py now reads carrier fields, so skipping it is no longer inert: "
        "check that the audit still reports the unread fields correctly"
    )


def test_a_field_name_that_does_not_exist_has_no_uses() -> None:
    assert MODULE.uses("a_field_this_project_does_not_have") == (0, 0)
