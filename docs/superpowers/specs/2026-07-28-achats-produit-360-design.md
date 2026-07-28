# Fiche produit 360° (morceau A)

**Date :** 2026-07-28
**Statut :** design validé, prêt pour le plan d'implémentation
**Périmètre :** morceau A du pilotage restant (ordre **B → C → A → D** ; B moteur d'économies #75, C KPI Achats #77 faits). Une **fiche produit 360°** — le miroir produit-centré de la fiche fournisseur — en **assemblage des read models existants, pas de duplication.**

## Contexte

La fiche produit a **déjà 6 onglets** (Infos · Fournisseurs · Prix+historique devis · Factures · Recettes · **Statistiques**) qui montrent déjà prix par fournisseur, historique, factures, recettes. L'onglet **« Statistiques »** calcule ses chiffres **côté client** (approximatifs). Le 360° apporte de la valeur en calculant **côté serveur** les agrégats que l'UI n'a pas : dépense annuelle + mensuelle, inflation sur le produit, économies via la concurrence, offert-vs-payé, top fournisseurs.

Presque tout existe déjà :
- `savings_service._savings_for_order_lines(..., product_id=...)` supporte déjà le filtre produit → **`for_product` = one-liner** (miroir `for_supplier`).
- Read models par produit : `purchase_service.product_suppliers` (moins cher/préféré/prix), `quote_history.product_quote_history` (offres best/latest/avg), `crud_purchase.product_purchases` (ledger d'achat), `crud_product.product_recipes` (recettes utilisant le produit), `supplier_analytics._price_trend` (pur, marche par produit tel quel).
- Pattern à copier : `supplier_analytics.overview` → `GET /suppliers/{id}/overview` + `SupplierScorecard` (web) / `_Scorecard` (mobile).

## Décisions de cadrage (validées)

1. **Remplacer l'onglet « Statistiques »** par un `ProductScorecard` alimenté par `GET /products/{id}/overview` — KPI serveur justes. Pas de nouvel onglet, on upgrade l'existant (la logique de stats client-side est supprimée). Onglet renommé « Vue d'ensemble ».
2. **Produit-centré** : on **abandonne** `conformity_rate`/`on_time_rate`/`score`/`late_count` (vertus *fournisseur*, sans objet pour un produit) ; on **ajoute** `top_suppliers`, `cheapest_supplier`, offert-vs-payé.
3. **Fenêtre = 12 mois glissants** (cohérent avec la fiche fournisseur).
4. **Assembleur, pas moteur** ; aucune table, aucune migration.

## Section 1 — Architecture backend

Nouveau module `backend/app/services/purchasing/product_analytics.py`, calqué sur `supplier_analytics`.

- **Cœur pur** `scorecard(purchases, offers, savings, supplier_rows, recipe_count, today) -> dict` : agrège le ledger (série mensuelle 12 mois, dépense annuelle payée, top fournisseurs par dépense, `price_trend_pct` via `supplier_analytics._price_trend`) et structure les blocs. Testable sans base.
- **Enveloppe BDD** `overview(db, tenant_id, product, today) -> dict` : rassemble en appelant les read models existants, délègue à `scorecard`, ajoute l'en-tête produit (nom, catégorie, unité).
- **`savings_service.for_product(db, tenant_id, product_id, today)`** : one-liner miroir de `for_supplier` (fenêtre 12 mois, `_savings_for_order_lines(..., product_id=...)`, + `SAVINGS_LABELS`).
- **Endpoint** : `GET /products/{id}/overview` (miroir de `/suppliers/{id}/overview` : guard `get_product` → 404 → `product_analytics.overview(db, tenant_id, product, date.today())`), déclaré **avant** `GET /{product_id}` et avec les autres sous-routes `/{id}/…` (convention d'ordre des routes).
- **Libellés servis par l'API** : réutilise `SAVINGS_LABELS` + un `PRODUCT_KPI_LABELS` si besoin.

**Forme de retour de `overview` (produit-centrée, contrat inter-tâches) :**
```python
{
  "product_id": str, "product_name": str, "category": str|None, "unit_code": str|None,
  # dépense (payé, 12 mois)
  "annual_amount": float, "monthly": [{month, amount}],
  "purchase_count": int, "supplier_count": int, "recipe_count": int, "offer_count": int,
  # prix
  "cheapest_supplier": {supplier_id, supplier_name, cost}|None,
  "last_cost": float|None, "avg_cost": float|None, "best_cost": float|None,
  "price_trend_pct": float|None,
  # offres (devis)
  "offers": {best_price, best_supplier_name, latest_price, avg_price, supplier_count}|None,
  # économies (concurrence, ex-post)
  "savings": {realized, missed, possible, best_choice_rate, compared_lines, labels},
  # top fournisseurs par dépense
  "top_suppliers": [{supplier_id, supplier_name, amount, count, is_cheapest}],
}
```

## Section 2 — Catalogue KPI et sources (réutilisation maximale)

| Groupe | KPI | Source réutilisée |
|---|---|---|
| **En-tête** | nom, catégorie, unité de base | `crud_product.get_product_detail` |
| **Dépense** | payé 12 mois, série mensuelle, nb achats, nb fournisseurs distincts | `crud_purchase.product_purchases` (agrégation pure) |
| **Prix** | moins cher (fournisseur + coût), dernier/moyen/meilleur, **inflation produit** (`price_trend_pct` 6m vs 6m) | `purchase_service.product_suppliers` + `supplier_analytics._price_trend` |
| **Offres** | meilleure / dernière / moyenne offre, nb fournisseurs ayant chiffré | `quote_history.product_quote_history` |
| **Économies** | Économisé / Laissé sur la table / Taux de meilleur choix | `savings_service.for_product` (nouveau) |
| **Top fournisseurs** | par dépense (drapeau « moins cher ») | agrégation de `product_purchases` par `supplier_id` + `cheapest_supplier_id` de `product_suppliers` |
| **Recettes** | nb de recettes utilisant le produit | `crud_product.product_recipes` |

**Parti pris** : tout vient des read models existants ; le seul code neuf est l'assembleur `product_analytics`, le one-liner `for_product`, la route, le scorecard UI. Les pièces pures réutilisées (`_price_trend`, `aggregate_supplier_prices`) ne sont pas recopiées. Aucune table, aucune migration.

## Section 3 — L'UI : l'onglet Statistiques devient le scorecard 360° (web + mobile)

**Web** — dans `frontend/src/features/products/product-detail.tsx`, le contenu de l'onglet **Statistiques** (stats client-side) est **remplacé** par `<ProductScorecard productId={…}>`, miroir de `SupplierScorecard`, alimenté par `useProductOverview(id)` → `GET /products/{id}/overview` :
- Tuiles KPI : payé 12 mois · inflation produit (`price_trend_pct`) · économisé (+ taux de meilleur choix).
- Ligne volumes : nb achats · fournisseurs · recettes · offres.
- Barres mensuelles (motif `MonthlyBars` maison réutilisé, pas de librairie de graphes).
- Top fournisseurs (liste liée vers `/fournisseurs/{id}`, drapeau « moins cher ») + bloc offert-vs-payé.
- La logique de stats client-side est **supprimée** (amélioration ciblée). Onglet renommé « Vue d'ensemble ». Cartes annexes enveloppées `SafeBoundary`.
- Câblage : `getProductOverview` + type `ProductOverview` (`frontend/src/services/products-service.ts`, à côté de `SupplierOverview`) ; hook `useProductOverview` (`frontend/src/hooks/use-products.ts`, miroir `useSupplierOverview`).

**Mobile** — dans `mobile/lib/features/products/product_detail_screen.dart`, l'onglet **Stats** (6e) est remplacé par un `_Scorecard` produit (miroir du `_Scorecard` de `supplier_detail_screen.dart`), alimenté par un `productOverviewProvider` (`GET /products/$id/overview`). Mêmes groupes ; réutilise les tuiles/barres du scorecard fournisseur là où c'est trivial.

## Section 4 — Tests & validation

- **Pur** `test_product_analytics.py` : `scorecard` agrège série mensuelle / dépense annuelle / top fournisseurs / `price_trend_pct` ; produit sans historique → zéros honnêtes ; **absence** des champs fournisseur-only (`conformity_rate`/`on_time_rate`/`score`/`late_count`) ; blocs structurés.
- **Real Postgres** `test_product_overview_real_db.py` (miroir `test_supplier_overview_real_db.py`) : produit avec achats de 2 fournisseurs + commande issue d'un devis (économies) + devis (offres) + une recette → `GET /products/{id}/overview` → asserts `annual_amount`, `top_suppliers`, `cheapest_supplier`, `savings.realized`, `offers`, `recipe_count`. + test `savings_service.for_product` (miroir `for_supplier`).
- **Non-régression** : fiche fournisseur `overview`, les 5 autres onglets produit inchangés, `for_supplier`/`for_tenant` inchangés ; AST guard `test_model_attribute_contract.py` vert (aucune colonne).
- **Web** : `tsc` / lint / build + test de composant. **Mobile** : `flutter analyze` + widget test (onglet Vue d'ensemble rendu depuis une réponse simulée).
- **Validation live (RÈGLE ABSOLUE)** : backend E2E prod (créer achats/devis/commande/recette pour un produit → `GET /products/{id}/overview` → vérifier dépense + top fournisseurs + économies + offres + nb recettes → nettoyer) + émulateur (fiche produit → onglet Vue d'ensemble rendu, 0 exception logcat). Web : build vert + contrat validé en direct (pas de harnais Playwright).

## Réutilisation / hors périmètre

- **Réutilisé, jamais recopié** : `product_suppliers`, `product_quote_history`, `product_purchases`, `product_recipes`, `_price_trend`, `aggregate_supplier_prices`, `savings_service` (+ nouveau `for_product`).
- **Aucune table / migration** : lecture pure (agrégation).
- Hors périmètre : la vérif prépa stock (= morceau D) ; les 5 autres onglets produit (déjà là — on ne touche que « Statistiques »). Pas de réception-ligne-par-produit (read model absent, non requis pour le 360°).

## Contraintes de livraison (rappel)

Branche → CI verte → merge (jamais de push direct sur `main`) ; jamais de mock de la session BDD (real_db pour la BDD) ; routes littérales avant `/{id}` ; RÈGLE ABSOLUE : « terminé » après validation live Android + Web + PostgreSQL réel ; nettoyage des données de test ; ne jamais déclencher de build Codemagic sans accord.
