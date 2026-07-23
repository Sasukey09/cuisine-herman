"""Enrichissement d'en-tete propre au DEVIS, par-dessus l'extraction OCR commune.

Le pipeline OCR partage avec les factures (`ocr.service.extract_invoice`) rend
fournisseur / date / numero / total / lignes. Un devis porte en plus une
**validite**, une **remise globale** et des **conditions** — trois choses qui
n'ont pas de sens sur une facture et qui ne justifient donc pas de toucher au
coeur OCR commun.

Tout ici est **pur** (texte -> valeurs) : teste sans BDD ni reseau.
"""
import re
from datetime import date, timedelta
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

# "12/08/2026", "12-08-2026", "12.08.2026"
_DATE = r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})"

# Montant francais : "1 234,56", "12.50", "9,90"
_MONEY = r"(\d[\d  .]*,?\d*)"

_VALID_UNTIL_ABS = re.compile(
    r"(?:valable|validit[ée]|valide)[^\n\d]{0,40}?" + _DATE, re.IGNORECASE
)
_VALID_UNTIL_REL = re.compile(
    r"(?:valable|validit[ée]|valide)[^\n\d]{0,40}?(\d{1,3})\s*jours?", re.IGNORECASE
)
_DISCOUNT = re.compile(
    r"remise[^\n\d%]{0,30}?" + _MONEY + r"\s*(?:€|eur)", re.IGNORECASE
)
_CONDITIONS = re.compile(
    r"(?:conditions?(?:\s+de)?\s+(?:paiement|r[èe]glement|livraison)|modalit[ée]s?"
    r"\s+de\s+(?:paiement|r[èe]glement))\s*[:\-]?\s*(.+)",
    re.IGNORECASE,
)


def _to_float(raw: str) -> Optional[float]:
    """'1 234,56' -> 1234.56. Tolère espaces fines/insécables et point milliers."""
    if not raw:
        return None
    cleaned = raw.replace(" ", "").replace(" ", "")
    # Si une virgule est présente, elle est décimale : le point est un séparateur
    # de milliers ("1.234,56"). Sinon le point est décimal ("12.50").
    if "," in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _to_date(day: str, month: str, year: str) -> Optional[date]:
    try:
        y = int(year)
        if y < 100:  # "26" -> 2026
            y += 2000
        return date(y, int(month), int(day))
    except (TypeError, ValueError):
        return None


def parse_valid_until(text: str, quote_date: Optional[date] = None) -> Optional[date]:
    """Date de fin de validité de l'offre.

    Gère la forme absolue ("valable jusqu'au 31/08/2026") et la forme relative
    ("offre valable 30 jours"), cette dernière calculée depuis ``quote_date``.
    Une offre périmée ne doit pas être comparée comme si elle tenait encore.
    """
    if not text:
        return None
    m = _VALID_UNTIL_ABS.search(text)
    if m:
        return _to_date(m.group(1), m.group(2), m.group(3))
    m = _VALID_UNTIL_REL.search(text)
    if m and quote_date is not None:
        try:
            return quote_date + timedelta(days=int(m.group(1)))
        except (TypeError, ValueError):
            return None
    return None


def parse_discount_total(text: str) -> Optional[float]:
    """Remise globale exprimée en montant ("Remise commerciale : 12,50 €")."""
    if not text:
        return None
    m = _DISCOUNT.search(text)
    return _to_float(m.group(1)) if m else None


def parse_conditions(text: str, max_len: int = 300) -> Optional[str]:
    """Conditions de paiement / règlement / livraison, en une ligne."""
    if not text:
        return None
    m = _CONDITIONS.search(text)
    if not m:
        return None
    value = " ".join(m.group(1).split()).strip(" .;")
    return value[:max_len] or None


def enrich_header(text: str, quote_date: Optional[date] = None) -> dict:
    """Les trois champs propres au devis, depuis le texte OCR brut."""
    return {
        "valid_until": parse_valid_until(text, quote_date),
        "discount_total": parse_discount_total(text),
        "conditions": parse_conditions(text),
    }


# --------------------------------------------------------------------------- #
# Persistance d'un import validé
# --------------------------------------------------------------------------- #
def confirm_import(db: Session, tenant_id: str, payload) -> Dict[str, Any]:
    """Persiste un import de devis validé par l'utilisateur.

    Par ligne : créer un produit (auto-classé + TVA), associer un existant, ou
    ignorer — exactement les mêmes actions que l'import de facture.

    Volontairement **sans** `reprice_line` : un devis est une OFFRE, pas un
    achat. Injecter ses prix dans ``product_prices`` / ``purchase_history``
    calculerait le coût matière des recettes sur des prix jamais payés. On garde
    en revanche le lien catalogue produit↔fournisseur : le devis atteste que ce
    fournisseur référence ce produit (dispo/délai pour le comparateur).

    Vit ici (et non dans l'endpoint) pour être testable contre un vrai Postgres
    et réutilisable (web, mobile, éventuel import asynchrone).
    """
    # Imports locaux : évite un cycle au chargement des modules CRUD.
    from app.core.tenancy import assert_product_in_tenant
    from app.crud import crud_price, crud_product, crud_quote, crud_supplier
    from app.crud import crud_supplier_product
    from app.schemas.schemas import ProductCreate

    supplier_id = payload.supplier_id
    if not supplier_id and payload.supplier:
        sup = crud_supplier.get_or_create_supplier_by_name(db, tenant_id, payload.supplier)
        supplier_id = str(sup.id) if sup is not None else None

    quote = crud_quote.create_imported_quote(db, tenant_id, payload, supplier_id)
    quote_id = str(quote.id)

    units = crud_price.get_units_by_code(db)
    created_products = 0
    associated = 0
    skipped = 0
    persisted = 0

    for l in payload.lines:
        if l.action == "skip":
            skipped += 1
            continue
        unit_id = units.get((l.unit or "").strip().lower()) if l.unit else None
        product_id = None
        if l.action == "associate" and l.product_id:
            assert_product_in_tenant(db, tenant_id, l.product_id)
            product_id = l.product_id
            associated += 1
        elif l.action == "create":
            prod = crud_product.create_product(
                db,
                ProductCreate(
                    name=l.description,
                    base_unit_id=unit_id,
                    category=l.category,
                    vat_rate=l.vat_rate,
                ),
                tenant_id,
            )
            product_id = str(prod.id)
            created_products += 1

        crud_quote.add_import_line(
            db, tenant_id, quote_id, l, unit_id, product_id, supplier_id
        )
        persisted += 1

        if product_id and supplier_id:
            crud_supplier_product.get_or_create_link(db, tenant_id, product_id, supplier_id)

    db.commit()

    return {
        "quote_id": quote_id,
        "reference": quote.reference,
        "lines": persisted,
        "created_products": created_products,
        "associated": associated,
        "skipped": skipped,
    }
