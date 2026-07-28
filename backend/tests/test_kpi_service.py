from app.services.purchasing.kpi_service import assemble, KPI_LABELS


def _parts(**over):
    base = {
        "savings": {"realized": 20.0, "missed": 5.0, "possible": 25.0,
                    "best_choice_rate": 0.8, "compared_lines": 3},
        "possible_open": 40.0,
        "ordered_total": 1000.0, "ordered_by_status": {"received": 600.0, "sent": 400.0},
        "received_value": 700.0, "missing_value": 120.0, "billed_total": 650.0,
        "price": {"n_hausse": 2, "n_baisse": 1, "top_inflation_pct": 12.5,
                  "n_critiques": 4, "switch_savings_total": 33.0},
        "top_products": [{"product_id": "p1", "name": "Beurre", "total_spend": 300.0,
                          "total_qty": 30.0, "line_count": 5}],
        "suppliers": [
            {"supplier_id": "a", "name": "A", "spend": 500.0, "realized": 20.0,
             "on_time_rate": 0.5, "late_count": 3, "conformity_rate": 0.9},
            {"supplier_id": "b", "name": "B", "spend": 300.0, "realized": 0.0,
             "on_time_rate": 1.0, "late_count": 0, "conformity_rate": 1.0},
        ],
    }
    base.update(over)
    return base


def test_cycle_gaps_are_derived():
    k = assemble(_parts())
    c = k["cycle"]
    assert c["ordered_total"] == 1000.0 and c["received_value"] == 700.0 and c["billed_total"] == 650.0
    assert c["gap_ordered_received"] == 300.0   # 1000 - 700 (commandé non encore livré/valorisé)
    assert c["gap_billed_received"] == -50.0    # 650 - 700 (facturé < reçu)
    assert c["missing_value"] == 120.0
    assert c["ordered_by_status"] == {"received": 600.0, "sent": 400.0}


def test_savings_block_gets_labels_and_possible_open():
    k = assemble(_parts())
    assert k["savings"]["realized"] == 20.0
    assert k["savings"]["labels"] == {"realized": "Économisé", "missed": "Laissé sur la table",
                                      "possible": "Économie possible", "best_choice_rate": "Taux de meilleur choix"}
    assert k["possible_open"] == 40.0


def test_price_and_top_products_are_passthrough_not_recomputed():
    parts = _parts()
    k = assemble(parts)
    assert k["price"] == parts["price"]          # aucun recalcul
    assert k["top_products"] == parts["top_products"]


def test_supplier_rankings():
    k = assemble(_parts())
    s = k["suppliers"]
    assert [x["supplier_id"] for x in s["most_competitive"]] == ["a"]   # realized>0, trié desc
    assert [x["supplier_id"] for x in s["most_late"]] == ["a"]          # late_count>0
    assert s["best_conformity"][0]["supplier_id"] == "b"               # conformity 1.0 avant 0.9


def test_empty_tenant_is_honest_zeros():
    k = assemble(_parts(savings={"realized": 0.0, "missed": 0.0, "possible": 0.0,
                                 "best_choice_rate": None, "compared_lines": 0},
                        ordered_total=0.0, received_value=0.0, billed_total=0.0,
                        missing_value=0.0, possible_open=0.0, suppliers=[],
                        ordered_by_status={}, top_products=[]))
    assert k["cycle"]["gap_ordered_received"] == 0.0
    assert k["savings"]["best_choice_rate"] is None
    assert k["suppliers"]["most_competitive"] == []


def test_labels_exposed():
    assert "ordered_total" in KPI_LABELS and "gap_ordered_received" in KPI_LABELS
