"""Self-running tests for markup engine — matches test_route.py style, no pytest.

Covers the task's required 3 scenarios (global / category override / product
override) plus pricing math, min_margin floor, and rounding modes.

Run: python test_markup_engine.py
"""

import sys
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from modules.markup.engine import apply_markup, resolve_rule


def rule(scope, markup_pct, *, priority=0, min_margin=None, rounding="none"):
    return SimpleNamespace(
        id=uuid4(),
        scope=scope,
        markup_pct=markup_pct,
        priority=priority,
        min_margin=min_margin,
        rounding=rounding,
    )


# -------- rule resolution --------

def test_global_only():
    r = resolve_rule([rule("all", 50)], "PC61", "T-Shirts")
    assert r is not None and r.scope == "all", r


def test_category_override_beats_global():
    rules = [rule("all", 50, priority=100), rule("category:T-Shirts", 30)]
    r = resolve_rule(rules, "PC61", "T-Shirts")
    assert r.scope == "category:T-Shirts", r.scope


def test_product_override_beats_category():
    rules = [
        rule("all", 50, priority=100),
        rule("category:T-Shirts", 30, priority=50),
        rule("product:PC61", 20),
    ]
    r = resolve_rule(rules, "PC61", "T-Shirts")
    assert r.scope == "product:PC61", r.scope


def test_priority_within_same_tier():
    rules = [rule("all", 20, priority=1), rule("all", 99, priority=10)]
    r = resolve_rule(rules, "PC61", "T-Shirts")
    assert r.markup_pct == 99, r.markup_pct


def test_category_rule_does_not_match_different_category():
    rules = [rule("category:Hats", 40), rule("all", 10)]
    r = resolve_rule(rules, "PC61", "T-Shirts")
    assert r.scope == "all", r.scope


def test_product_with_no_category_falls_back_to_global():
    rules = [rule("category:T-Shirts", 40), rule("all", 10)]
    r = resolve_rule(rules, "PC61", None)
    assert r.scope == "all", r.scope


def test_no_rules_returns_none():
    assert resolve_rule([], "PC61", "T-Shirts") is None


def test_no_matching_rule_returns_none():
    r = resolve_rule([rule("product:OTHER", 50)], "PC61", "T-Shirts")
    assert r is None


# -------- pricing math --------

def test_apply_markup_basic_percentage():
    # 3.99 * 1.50 = 5.985 → 5.99
    assert apply_markup(Decimal("3.99"), rule("all", 50)) == Decimal("5.99")


def test_apply_markup_min_margin_floor():
    # Small markup (10%) < min_margin (50%) → min_margin wins
    r = rule("all", 10, min_margin=50)
    assert apply_markup(Decimal("3.99"), r) == Decimal("5.99")


def test_apply_markup_min_margin_not_triggered():
    # Big markup (80%) > min_margin (10%) → keep markup
    r = rule("all", 80, min_margin=10)
    # 3.99 * 1.80 = 7.182 → 7.18
    assert apply_markup(Decimal("3.99"), r) == Decimal("7.18")


def test_apply_markup_nearest_99_rounding():
    # 3.99 * 1.50 = 5.985 → floor(5) + 0.99 = 5.99
    r = rule("all", 50, rounding="nearest_99")
    assert apply_markup(Decimal("3.99"), r) == Decimal("5.99")


def test_apply_markup_nearest_dollar_rounds_down():
    # 3.99 * 1.33 = 5.3067 → round() = 5
    r = rule("all", 33, rounding="nearest_dollar")
    assert apply_markup(Decimal("3.99"), r) == Decimal("5.00")


def test_none_rule_returns_quantized_base():
    assert apply_markup(Decimal("3.99"), None) == Decimal("3.99")


def test_none_base_price_returns_none():
    assert apply_markup(None, rule("all", 50)) is None


TESTS = [
    test_global_only,
    test_category_override_beats_global,
    test_product_override_beats_category,
    test_priority_within_same_tier,
    test_category_rule_does_not_match_different_category,
    test_product_with_no_category_falls_back_to_global,
    test_no_rules_returns_none,
    test_no_matching_rule_returns_none,
    test_apply_markup_basic_percentage,
    test_apply_markup_min_margin_floor,
    test_apply_markup_min_margin_not_triggered,
    test_apply_markup_nearest_99_rounding,
    test_apply_markup_nearest_dollar_rounds_down,
    test_none_rule_returns_quantized_base,
    test_none_base_price_returns_none,
]


if __name__ == "__main__":
    failed = 0
    for t in TESTS:
        try:
            t()
            print(f"ok   {t.__name__}")
        except Exception as exc:
            failed += 1
            print(f"FAIL {t.__name__}: {exc!r}")
    print(f"\n{len(TESTS) - failed}/{len(TESTS)} passed")
    sys.exit(1 if failed else 0)
