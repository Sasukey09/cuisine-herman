"""Moteur de comparaison multi-devis (tableau produit × fournisseur).

Pur : tourne partout. Vérifie surtout les deux garde-fous — on ne compare que ce
qui est comparable, et une offre périmée ne gagne pas."""

from datetime import date

from app.services.quotes.quote_matrix import build_matrix

NAMES = {"A": "Metro", "B": "Transgourmet", "C": "Pomona"}
PRODUITS = {"p1": "Farine T55", "p2": "Huile d'olive"}


def offer(pid, sid, price, **kw):
    base = {
        "product_id": pid,
        "supplier_id": sid,
        "quote_id": f"q-{sid}",
        "quote_reference": f"DEV-{sid}",
        "unit_price": price,
        "qty": 10,
    }
    base.update(kw)
    return base


# --- classement au prix à l'unité de base ---------------------------------
def test_ranks_on_base_unit_not_display_price():
    """Le cœur du comparateur : le sac de 25 kg gagne malgré son prix affiché."""
    res = build_matrix(
        [
            offer("p1", "A", 18.50, pack_size="sac 25kg"),      # 0,74 €/kg
            offer("p1", "B", 4.20, pack_size="plaquette 500g"),  # 8,40 €/kg
        ],
        supplier_names=NAMES,
        product_names=PRODUITS,
    )
    p = res["products"][0]
    assert p["basis"] == "base_unit"
    assert p["best_supplier_id"] == "A"
    by = {o["supplier_id"]: o for o in p["offers"]}
    assert by["A"]["rank"] == "best"
    assert by["B"]["rank"] == "worst"
    # B est ~1035 % plus cher au kilo
    assert by["B"]["delta_pct_vs_best"] > 1000


def test_discount_is_applied_before_ranking():
    res = build_matrix(
        [
            offer("p1", "A", 20.0, pack_size="sac 10kg"),                    # 2,00 €/kg
            offer("p1", "B", 22.0, pack_size="sac 10kg", discount_pct=20),   # 1,76 €/kg
        ],
        supplier_names=NAMES,
    )
    assert res["products"][0]["best_supplier_id"] == "B"


# --- garde-fou 1 : conditionnement illisible ------------------------------
def test_unreadable_packaging_falls_back_and_flags_it():
    res = build_matrix(
        [
            offer("p1", "A", 18.50, pack_size="sac 25kg"),
            offer("p1", "B", 4.20, pack_size="carton"),  # illisible
        ],
        supplier_names=NAMES,
    )
    p = res["products"][0]
    assert p["basis"] == "unit_price"
    assert p["mixed_packaging"] is True, "l'utilisateur doit être averti"
    # Le classement retombe sur le prix affiché : B « gagne », mais c'est signalé.
    assert p["best_supplier_id"] == "B"


# --- garde-fou 2 : offre périmée ------------------------------------------
def test_expired_offer_is_excluded_from_ranking():
    res = build_matrix(
        [
            offer("p1", "A", 1.00, pack_size="sac 1kg", valid_until=date(2026, 1, 1)),
            offer("p1", "B", 2.00, pack_size="sac 1kg", valid_until=date(2026, 12, 31)),
        ],
        supplier_names=NAMES,
        today=date(2026, 7, 23),
    )
    p = res["products"][0]
    by = {o["supplier_id"]: o for o in p["offers"]}
    assert by["A"]["expired"] is True
    assert by["A"]["rank"] is None, "une offre périmée ne peut pas gagner"
    assert p["best_supplier_id"] == "B"


def test_unavailable_offer_is_excluded():
    res = build_matrix(
        [offer("p1", "A", 1.0, pack_size="sac 1kg"), offer("p1", "B", 2.0, pack_size="sac 1kg")],
        catalog={"p1": {"A": {"available": False}}},
        supplier_names=NAMES,
    )
    p = res["products"][0]
    assert p["best_supplier_id"] == "B"
    assert {o["supplier_id"]: o["rank"] for o in p["offers"]}["A"] is None


# --- historique : hausse / baisse -----------------------------------------
def test_compares_best_offer_to_last_paid():
    res = build_matrix(
        [offer("p1", "A", 10.0, pack_size="sac 10kg")],  # 1,00 €/kg
        history={"p1": {"last_paid": 1.25, "avg_paid": 1.30, "best_paid": 0.95}},
        supplier_names=NAMES,
    )
    p = res["products"][0]
    assert p["history"]["last_paid"] == 1.25
    assert p["vs_last_paid_pct"] == -20.0  # baisse de 20 %


# --- synthèse fournisseurs ------------------------------------------------
def test_supplier_totals_fastest_and_savings():
    res = build_matrix(
        [
            offer("p1", "A", 10.0, pack_size="sac 10kg", qty=10),
            offer("p1", "B", 15.0, pack_size="sac 10kg", qty=10),
            offer("p2", "A", 30.0, pack_size="bidon 5L", qty=2),
        ],
        catalog={
            "p1": {"A": {"lead_time_days": 5}, "B": {"lead_time_days": 2}},
            "p2": {"A": {"lead_time_days": 3}},
        },
        supplier_names=NAMES,
    )
    by = {s["supplier_id"]: s for s in res["suppliers"]}
    assert by["A"]["covered"] == 2 and by["B"]["covered"] == 1
    assert by["A"]["best_count"] == 2  # A est le meilleur sur les deux produits
    assert by["A"]["max_lead_time_days"] == 5
    assert res["fastest_supplier_id"] == "B"  # 2 jours
    # Économie possible sur p1 : (1,50 - 1,00) €/kg × 10 = 5,00
    assert res["potential_savings"] == 5.0


def test_single_offer_is_best_without_worst():
    res = build_matrix([offer("p1", "A", 5.0, pack_size="sac 5kg")], supplier_names=NAMES)
    o = res["products"][0]["offers"][0]
    assert o["rank"] == "best"
    assert o["delta_pct_vs_best"] == 0.0
    assert res["potential_savings"] == 0.0


def test_empty_input():
    res = build_matrix([])
    assert res["products"] == []
    assert res["suppliers"] == []
    assert res["cheapest_supplier_id"] is None
    assert res["potential_savings"] == 0.0
