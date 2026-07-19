import pytest

from app.services.customization.formula_eval import (
    evaluate,
    validate,
    collect_names,
    FormulaError,
)

CTX = {
    "cost_per_portion": 2.5,
    "food_cost_pct": 25.0,
    "selling_price": 10.0,
    "yield_qty": 4.0,
    "computed_cost_total": 10.0,
    "missing": None,
}
ALLOWED = list(CTX.keys())


# --- correctness ---------------------------------------------------------- #
def test_basic_arithmetic():
    assert evaluate("cost_per_portion * 3", CTX) == 7.5
    assert evaluate("(selling_price - cost_per_portion) / selling_price * 100", CTX) == 75.0


def test_functions():
    assert evaluate("round(cost_per_portion * 3, 1)", CTX) == 7.5
    assert evaluate("max(food_cost_pct, 30)", CTX) == 30
    assert evaluate("min(food_cost_pct, 30)", CTX) == 25.0
    assert evaluate("abs(cost_per_portion - selling_price)", CTX) == 7.5


def test_ternary_and_compare():
    assert evaluate("1 if food_cost_pct > 30 else 0", CTX) == 0
    assert evaluate("food_cost_pct <= 25", CTX) is True


def test_none_propagates():
    assert evaluate("missing * 2", CTX) is None
    assert evaluate("missing + cost_per_portion", CTX) is None


def test_division_by_zero_returns_none():
    assert evaluate("cost_per_portion / 0", CTX) is None


# --- security ------------------------------------------------------------- #
@pytest.mark.parametrize(
    "expr",
    [
        "__import__('os').system('echo hi')",
        "os.system('x')",
        "(1).__class__",
        "cost_per_portion.__class__",
        "open('x')",
        "exec('x')",
        "[i for i in range(10)]",
        "lambda: 1",
        "{'a': 1}",
        "cost_per_portion['a']",
        "'string'",
        "unknown_var + 1",
    ],
)
def test_rejected_expressions(expr):
    # either validation flags it, or evaluation refuses it
    ok, _ = validate(expr, ALLOWED)
    assert ok is False
    with pytest.raises(FormulaError):
        evaluate(expr, CTX)


def test_validate_accepts_good_formula():
    ok, err = validate("round(cost_per_portion * 3, 2)", ALLOWED)
    assert ok is True and err is None


def test_validate_rejects_unknown_function():
    ok, err = validate("pow(cost_per_portion, 2)", ALLOWED)
    assert ok is False
    assert "min, max, round, abs" in err


def test_pow_exponent_capped():
    with pytest.raises(FormulaError):
        evaluate("cost_per_portion ** 50", CTX)
    assert evaluate("cost_per_portion ** 2", CTX) == 6.25


def test_collect_names_excludes_functions():
    assert collect_names("round(cost_per_portion * markup, 2)") == ["cost_per_portion", "markup"]


# --- I4: DoS guards -------------------------------------------------------- #
def test_nested_exponentiation_is_refused_before_it_explodes():
    # Every per-node exponent is 8 (passes the _MAX_POW check), but the value
    # grows as 2^(8^n). The bit-length guard must refuse it, fast, not OOM.
    payload = "((((((2**8)**8)**8)**8)**8)**8)**8"
    with pytest.raises(FormulaError):
        evaluate(payload, {})


def test_small_powers_still_work():
    assert evaluate("2 ** 8", {}) == 256
    assert evaluate("cost_per_portion ** 2", CTX) == 6.25


def test_overlong_formula_is_rejected():
    long_formula = "1+" * 400 + "1"   # > 500 chars
    with pytest.raises(FormulaError):
        evaluate(long_formula, {})
    ok, err = validate(long_formula, [])
    assert ok is False


def test_deeply_nested_formula_is_rejected():
    # Nested unary minus creates real AST depth (parentheses alone do not).
    deep = "-" * 60 + "1"   # ------...1  -> 60 nested UnaryOp, depth > _MAX_DEPTH
    with pytest.raises(FormulaError):
        evaluate(deep, {})


def test_too_many_nodes_is_rejected():
    wide = "+".join(["1"] * 300)   # > _MAX_NODES nodes
    with pytest.raises(FormulaError):
        evaluate(wide, {})


def test_a_null_byte_in_the_source_is_a_clean_formula_error():
    # ast.parse raises ValueError (not SyntaxError) on an embedded NUL byte; it
    # must surface as a FormulaError, not an uncaught 500.
    with pytest.raises(FormulaError):
        evaluate("1\x00+1", CTX)


def test_a_recursionerror_during_parse_becomes_a_formula_error(monkeypatch):
    import app.services.customization.formula_eval as fe

    def boom(*_a, **_k):
        raise RecursionError("maximum recursion depth exceeded")

    monkeypatch.setattr(fe.ast, "parse", boom)
    with pytest.raises(FormulaError):
        evaluate("1 + 1", CTX)
