"""Détection du fournisseur sur un document (facture OU devis).

Le parseur ne cherchait que l'étiquette « Fournisseur : », qu'aucun document
réel n'écrit — le nom du fournisseur est l'EN-TÊTE de la page. Ces tests
couvrent la lecture d'en-tête et, surtout, ce qu'elle doit REFUSER : mieux vaut
un champ vide qu'un mauvais fournisseur pré-rempli, qui serait validé sans être
relu.

Pur : tourne partout. Le pipeline OCR étant partagé, ceci vaut pour les deux
modules."""

import pytest

from app.services.ocr.service import guess_supplier


# --- étiquette explicite : priorité absolue -------------------------------
def test_explicit_label_wins():
    text = "FACTURE N° 42\nFournisseur : Metro Cash & Carry\nTotal 90,00 €"
    assert guess_supplier(text) == "Metro Cash & Carry"


def test_explicit_label_variants():
    for label in ("Fournisseur", "Supplier", "Vendeur", "Émetteur"):
        assert guess_supplier(f"{label}: Pomona TerreAzur\nautre") == "Pomona TerreAzur"


def test_explicit_label_beats_letterhead():
    text = "GRANDE SURFACE SA\nFacture\nFournisseur : Le Vrai Fournisseur"
    assert guess_supplier(text) == "Le Vrai Fournisseur"


# --- en-tête de document (le cas réel) ------------------------------------
def test_letterhead_all_caps():
    """Le cas constaté en production : le nom est la 1re ligne du devis."""
    text = (
        "TRANSGOURMET FRANCE\n"
        "12 rue des Halles - 75001 Paris\n"
        "DEVIS N° DV-2026-0457\n"
        "Date : 22/07/2026\n"
    )
    assert guess_supplier(text) == "TRANSGOURMET FRANCE"


def test_letterhead_with_legal_form_beats_a_plain_line():
    text = "Bienvenue\nDistribution Alimentaire SARL\nFACTURE N° 7\n"
    assert guess_supplier(text) == "Distribution Alimentaire SARL"


def test_letterhead_skips_markdown_markers():
    # Mistral rend souvent du markdown.
    text = "# **METRO CASH & CARRY**\n\n| Designation | Qte |\nFACTURE\n"
    assert guess_supplier(text) == "METRO CASH & CARRY"


def test_earliest_wins_on_equal_score():
    text = "PRIMEURS DU MARCHE\nGROSSISTE DU SUD\nFACTURE\n"
    assert guess_supplier(text) == "PRIMEURS DU MARCHE"


# --- ce que la détection doit REFUSER -------------------------------------
@pytest.mark.parametrize(
    "line",
    [
        "FACTURE",
        "DEVIS N° DV-2026-0457",
        "Bon de commande 12",
        "Invoice #998",
    ],
)
def test_document_type_is_never_a_supplier(line):
    assert guess_supplier(f"{line}\n") is None


@pytest.mark.parametrize(
    "line",
    [
        "12 rue des Halles",
        "75001 Paris",
        "Tel : 01 23 45 67 89",
        "contact@fournisseur.fr",
        "www.fournisseur.fr",
        "SIRET 123 456 789 00012",
        "TVA intracommunautaire FR12345678901",
        "IBAN FR76 3000 4000 0100 0000 0000 123",
        "Date : 22/07/2026",
        "1 234,56",
    ],
)
def test_contact_and_identifier_lines_are_refused(line):
    assert guess_supplier(f"{line}\n") is None


def test_returns_none_rather_than_a_doubtful_line():
    # Un document sans en-tête exploitable : champ vide, pas une invention.
    text = "FACTURE\n12 rue des Halles\n75001 Paris\nTotal TTC 90,00 €\n"
    assert guess_supplier(text) is None


def test_empty_or_blank_text():
    assert guess_supplier("") is None
    assert guess_supplier("   \n\n  ") is None


def test_very_long_line_is_not_a_company_name():
    assert guess_supplier("x" * 120 + "\n") is None


# --- non-régression : le document de test complet -------------------------
def test_full_quote_document():
    text = (
        "TRANSGOURMET FRANCE\n"
        "12 rue des Halles - 75001 Paris\n"
        "DEVIS N° DV-2026-0457\n"
        "Date : 22/07/2026\n"
        "Offre valable jusqu'au 30/09/2026\n"
        "Designation Qte Unite PU HT Total\n"
        "Farine de ble T55 sac 25kg 10 sac 18,50 185,00\n"
        "Conditions de paiement : virement a 30 jours fin de mois\n"
    )
    assert guess_supplier(text) == "TRANSGOURMET FRANCE"


def test_full_invoice_document():
    text = (
        "METRO CASH & CARRY\n"
        "FACTURE N° FA-2026-0912\n"
        "Date : 22/07/2026\n"
        "Farine de ble T55 sac 25kg 4 sac 18,90 75,60\n"
    )
    assert guess_supplier(text) == "METRO CASH & CARRY"


# --- garde-fou : ne pas détecter le tenant comme son propre fournisseur ----
def test_own_company_in_letterhead_is_ignored():
    """Certains documents portent le DESTINATAIRE en tête. Détecter le
    restaurant comme son propre fournisseur créerait un fournisseur fantôme."""
    text = "CUISINE HERMAN\nFACTURE\nMETRO CASH & CARRY\n"
    assert guess_supplier(text, exclude="Cuisine Herman") == "METRO CASH & CARRY"


def test_own_company_matching_is_tolerant_to_case_and_punctuation():
    text = "Cuisine  Herman S.A.R.L.\nGROSSISTE DU SUD\n"
    assert guess_supplier(text, exclude="cuisine herman sarl") == "GROSSISTE DU SUD"


def test_explicit_label_naming_the_tenant_is_ignored():
    text = "Fournisseur : Cuisine Herman\nPOMONA TERREAZUR\n"
    assert guess_supplier(text, exclude="Cuisine Herman") == "POMONA TERREAZUR"


def test_exclude_none_keeps_previous_behaviour():
    text = "CUISINE HERMAN\nFACTURE\n"
    assert guess_supplier(text) == "CUISINE HERMAN"
