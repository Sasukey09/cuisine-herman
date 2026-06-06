from datetime import datetime

from app.services.dashboard.dashboard_service import select_low_margin


def row(vid, food_cost, when, name="R"):
    return {
        "recipe_version_id": vid,
        "recipe_id": "r-" + vid,
        "recipe_name": name,
        "food_cost_pct": food_cost,
        "cost_per_portion": 1.0,
        "computed_at": when,
    }


def test_keeps_latest_snapshot_per_version():
    rows = [
        row("v1", 20.0, datetime(2026, 1, 1)),  # old
        row("v1", 40.0, datetime(2026, 2, 1)),  # newer -> wins
    ]
    alerts = select_low_margin(rows, max_food_cost_pct=35.0)
    assert len(alerts) == 1
    assert alerts[0]["food_cost_pct"] == 40.0


def test_threshold_and_sorting():
    rows = [
        row("v1", 40.0, datetime(2026, 2, 1)),
        row("v2", 30.0, datetime(2026, 2, 1)),  # below threshold -> excluded
        row("v3", 50.0, datetime(2026, 2, 1)),
    ]
    alerts = select_low_margin(rows, max_food_cost_pct=35.0)
    assert [a["recipe_version_id"] for a in alerts] == ["v3", "v1"]  # sorted desc


def test_none_food_cost_ignored():
    rows = [row("v1", None, datetime(2026, 2, 1))]
    assert select_low_margin(rows, 35.0) == []
