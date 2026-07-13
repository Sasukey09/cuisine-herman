"""Phase 6 — the assistant knows the restaurant before being asked."""
from app.services.ai import context as ai_context


def _situation(**over):
    base = {"increases": [], "decreases": [], "savings": [], "margin_alerts": []}
    base.update(over)
    return base


# --------------------------------------------------------------------------- #
# The briefing pinned to the system prompt
# --------------------------------------------------------------------------- #
def test_the_briefing_states_the_real_numbers():
    briefing = ai_context.render_briefing(
        _situation(
            increases=[
                {"product_name": "Beurre doux AOP", "change_pct": 18.2,
                 "old_cost": 6.90, "new_cost": 8.51},
            ]
        )
    )
    assert "Beurre doux AOP" in briefing
    assert "+18.2 %" in briefing
    assert "6.90 €" in briefing and "8.51 €" in briefing
    # It must not send the model hunting for data it has already been handed.
    assert "inutile d'appeler un outil" in briefing


def test_the_briefing_demands_a_concrete_action():
    """An analyst that only describes is not worth its tokens."""
    briefing = ai_context.render_briefing(
        _situation(increases=[{"product_name": "Filet de bœuf", "change_pct": 12.4}])
    )
    assert "ACTION CONCRÈTE" in briefing


def test_with_no_data_the_briefing_says_so_instead_of_inventing():
    briefing = ai_context.render_briefing(_situation())
    assert "aucune hausse" in briefing.lower()
    assert "inventer" in briefing  # explicit instruction not to make things up


def test_savings_and_margin_alerts_reach_the_briefing():
    briefing = ai_context.render_briefing(
        _situation(
            savings=[
                {"product_name": "Parmesan AOP", "cheapest_supplier": "Pro à Pro",
                 "cheapest_cost": 21.0, "unit_code": "kg"},
            ],
            margin_alerts=[{"recipe_name": "Risotto aux cèpes", "food_cost_pct": 41.0}],
        )
    )
    assert "Pro à Pro" in briefing
    assert "Risotto aux cèpes" in briefing


# --------------------------------------------------------------------------- #
# Suggestions must come from THIS restaurant's data
# --------------------------------------------------------------------------- #
def test_suggestions_are_built_from_the_tenants_own_data():
    out = ai_context.suggestions(
        _situation(increases=[{"product_name": "Beurre doux AOP", "change_pct": 18.2}])
    )
    assert any("Beurre doux AOP" in s for s in out)


def test_suggestions_fall_back_to_generic_ones_when_there_is_nothing_to_say():
    out = ai_context.suggestions(_situation())
    assert len(out) == 3
    assert all(isinstance(s, str) and s for s in out)


def test_suggestions_stay_short_enough_to_display():
    out = ai_context.suggestions(
        _situation(
            increases=[
                {"product_name": f"Produit {i}", "change_pct": 10 + i} for i in range(6)
            ],
            savings=[{"product_name": "X", "cheapest_supplier": "Y"}],
            margin_alerts=[{"recipe_name": "Z"}],
        )
    )
    assert len(out) <= 4, "the chat shows a handful of chips, not a wall of them"


# --------------------------------------------------------------------------- #
# A briefing that fails must not take the assistant down with it
# --------------------------------------------------------------------------- #
def test_build_situation_never_raises_even_on_a_broken_db():
    class Broken:
        def query(self, *a, **k):
            raise RuntimeError("database on fire")

    situation = ai_context.build_situation(Broken(), "t1")
    assert situation == {"increases": [], "decreases": [], "savings": [], "margin_alerts": []}
