from types import SimpleNamespace

from app.services.ai import tools as ai_tools


def test_tool_schemas_are_well_formed():
    schemas = ai_tools.tool_schemas()
    assert len(schemas) == 10
    names = {s["name"] for s in schemas}
    assert names == {
        "list_recipes",
        "get_recipe_details",
        "search_products",
        "get_price_history",
        "get_margin_alerts",
        "get_price_increase_alerts",
        "find_cheaper_alternatives",
        "create_recipe_draft",
        "create_product",
        "link_recipe_products",
    }
    for s in schemas:
        assert s["name"] and s["description"]
        assert s["input_schema"]["type"] == "object"


def test_execute_unknown_tool_returns_error():
    res = ai_tools.execute_tool(db=None, tenant_id="t1", name="nope", tool_input={})
    assert res == {"error": "unknown_tool", "tool": "nope"}


def test_execute_tool_catches_executor_failure():
    # db=None makes the real executor raise; the dispatcher must catch and report
    res = ai_tools.execute_tool(
        db=None, tenant_id="t1", name="search_products", tool_input={"query": "x"}
    )
    assert res["error"] == "tool_execution_failed"
    assert res["tool"] == "search_products"
    assert "detail" in res


def test_create_recipe_draft_validates_name():
    res = ai_tools.execute_tool(
        db=None, tenant_id="t1", name="create_recipe_draft",
        tool_input={"name": "", "ingredients": [{"name": "fraise", "qty": 1, "unit": "kg"}]},
    )
    assert res == {"error": "missing_name"}


def test_create_recipe_draft_requires_ingredients():
    res = ai_tools.execute_tool(
        db=None, tenant_id="t1", name="create_recipe_draft",
        tool_input={"name": "Gâteau", "ingredients": []},
    )
    assert res == {"error": "no_ingredients"}


def test_create_product_validates_name():
    res = ai_tools.execute_tool(
        db=None, tenant_id="t1", name="create_product", tool_input={"name": "  "}
    )
    assert res == {"error": "missing_name"}


def test_price_per_base_normalises_by_unit_ratio():
    # 5 / kg with ratio 1 -> 5 ; 0.5 priced in grams (ratio 0.001) -> 500 per base
    ratios = {1: 1.0, 2: 0.001}
    assert ai_tools._price_per_base(SimpleNamespace(price=5.0, unit_id=1), ratios) == 5.0
    assert ai_tools._price_per_base(SimpleNamespace(price=0.5, unit_id=2), ratios) == 500.0
    assert ai_tools._price_per_base(None, ratios) is None
