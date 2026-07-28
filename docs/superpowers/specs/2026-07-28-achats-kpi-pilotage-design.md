# Pilotage Achats — KPI (morceau C)

**Date :** 2026-07-28
**Statut :** design validé, prêt pour le plan d'implémentation
**Périmètre :** morceau C du pilotage restant (ordre **B → C → A → D** ; B = moteur d'économies, livré #75). Un tableau de bord **Pilotage Achats** tenant-wide, **assemblage des moteurs existants — pas de duplication.**

## Contexte

Le repérage est net : il n'existe **aucune** agrégation tenant-wide « KPI Achats ». Mais tout le calcul existe déjà, par entité (par fournisseur / facture / commande / produit) ou déjà tenant-wide. C est donc un **assembleur**, pas un moteur.

Déjà tenant-wide (réutilisés tels quels) :
- `savings_service._savings_for_order_lines(db, tenant_id)` — économies réalisées (appel sans filtre déjà supporté).
- `quote_matrix.build_for_tenant(db, tenant_id)["potential_savings"]` — économies possibles (ex-ante).
- `purchase_service.price_dashboard(db, tenant_id, limit)` — inflation, hausses/baisses, produits critiques, switch-savings (servi à `/dashboard/price-variations`, écran `/prix`). **Plus gros risque de duplication : on le réutilise, jamais on ne le recalcule.**
- `dashboard_service.top_products(db, tenant_id, ...)` — dépense/top produits.

Par entité (à agréger en bouclant/sommant, sans logique neuve) : montants commandé (`crud_order`), reçu (`reception_service`), facturé (`Invoice`), fournisseurs (`supplier_analytics`).

## Décisions de cadrage (validées)

1. **Pilotage unifié qui réutilise `/prix`.** Un nouvel écran « Pilotage Achats » calcule l'axe **cycle + économies + fournisseurs** ET surface en tête les chiffres clés de `price_dashboard` (inflation, hausse/baisse, produits critiques) — réutilisés, pas recalculés — avec un lien vers `/prix` pour le détail. Une seule porte d'entrée, zéro duplication, répond à toute la Phase 7.
2. **Fenêtre = 12 mois glissants** (cohérent avec `annual_amount` / économies) ; pas de sélecteur de période en v1 (YAGNI).
3. **Assembleur, pas moteur** : cœur pur qui structure/dérive ; enveloppe BDD qui appelle les moteurs existants.

## Section 1 — Architecture backend

Nouveau module `backend/app/services/purchasing/kpi_service.py`, même patron que le reste du domaine.

- **Cœur pur** `assemble(parts: dict) -> dict` : reçoit des données **déjà collectées** et se contente de **structurer + dériver** :
  - écarts : `gap_ordered_received = ordered_total − received_value`, `gap_billed_received = billed_total − received_value` ;
  - classements fournisseurs : top compétitifs (économies réalisées ↓), en retard (`late_count` ↓ / `on_time_rate` ↑), meilleure conformité (`conformity_rate` ↓), sur les lignes fournisseurs fournies ;
  - passe-plat des blocs prix / top-produits / possibles (aucun recalcul).
  Testable sans base.
- **Enveloppe BDD** `purchasing_kpi(db, tenant_id, today) -> dict` : rassemble les `parts` en appelant les moteurs existants, puis délègue à `assemble`.
- **`savings_service.for_tenant(db, tenant_id, today)`** : nouveau one-liner miroir de `for_supplier` (fenêtre 12 mois, `_savings_for_order_lines` sans `supplier_id`, + `SAVINGS_LABELS`).
- **Endpoint** : nouveau routeur `purchasing` (monté à `/purchasing` dans `api.py`) → **`GET /purchasing/kpi`**, read-only (`get_current_tenant_id` + `get_db`, pas de `require_writer`). Un routeur neuf évite le piège d'ordre des routes `/{id}` (incident `/quotes/matrix` en prod).
- **Libellés servis par l'API** : `KPI_LABELS` (+ réutilise `SAVINGS_LABELS`), source unique pour web + mobile.

`parts` (contrat pur, ce que l'enveloppe fournit à `assemble`) :
```python
{
  "savings": {realized, missed, possible, best_choice_rate, compared_lines},  # savings_service.for_tenant
  "possible_open": float,                 # quote_matrix.build_for_tenant()["potential_savings"]
  "ordered_total": float,                 # Σ order.total_amount (non annulées, 12 mois)
  "ordered_by_status": {status: total},   # somme SQL group-by
  "received_value": float,                # valeur acceptée (reception_service, 12 mois)
  "missing_value": float,                 # € commandé non encore livré
  "billed_total": float,                  # Σ invoice.total_amount (12 mois)
  "price": {...},                         # extrait de price_dashboard (surfacé)
  "top_products": [...],                  # dashboard_service.top_products
  "suppliers": [{supplier_id, name, spend, realized, on_time_rate, late_count, conformity_rate}],
}
```

## Section 2 — Catalogue KPI et sources (réutilisation maximale)

| Groupe | KPI | Source réutilisée |
|---|---|---|
| **Économies** | Économisé / Laissé sur la table / Taux de meilleur choix | `savings_service.for_tenant` |
| | Économies possibles (devis ouverts) | `quote_matrix.build_for_tenant()["potential_savings"]` |
| **Cycle (€)** | Commandé | Σ `PurchaseOrder.total_amount` non annulées *(somme SQL)* |
| | Facturé | Σ `Invoice.total_amount` *(somme SQL)* |
| | Reçu (valeur acceptée) + « en attente de livraison » (€) | `reception_service` (source de vérité de l'accepté), borné 12 mois |
| | Écart commandé↔livré, livré↔facturé | **dérivés** dans `assemble` |
| **Prix** *(réutilisé, lien → `/prix`)* | Inflation, produits en hausse/baisse, produits critiques | `purchase_service.price_dashboard()` — surfacé, jamais recalculé |
| | Dépense totale / top produits | `dashboard_service.top_products()` |
| **Fournisseurs** | Plus compétitifs (économies), en retard (ponctualité), conformité | agrégat léger par fournisseur (dépense, retards, conformité, économies) |

**Précision « surfacer le prix »** : `purchasing_kpi` appelle `price_dashboard` et n'en garde qu'un **résumé compact** — `{n_hausse, n_baisse, top_inflation_pct, n_critiques, switch_savings_total}` — pas les listes complètes. Le détail (listes produits, impact recettes) reste sur `/prix`, vers lequel le bloc renvoie. Une seule requête pour l'UI Pilotage, aucune recopie.

**Parti pris de performance** : on réutilise tels quels les moteurs déjà tenant-wide (économies, possibles, prix, top produits) ; les montants commandé/facturé sont des **sommes SQL légères** ; le « reçu » passe par le moteur réception borné aux 12 mois ; les fournisseurs sont un **agrégat ciblé** (dépense/retards/conformité/économies) — **pas** la boucle `supplier_analytics.overview` complète (trop de requêtes par fournisseur). Objectif : un endpoint dashboard qui tient la charge à l'échelle d'un restaurant sans dupliquer de logique.

## Section 3 — L'écran « Pilotage Achats » (web + mobile, parité)

Réutilise les composants dashboard existants — aucune tuile réinventée.

**Web** — nouvelle route `/pilotage`, item de nav « Pilotage » (à côté de `/prix`). Rendu avec `StatCard` (`frontend/src/features/dashboard/stat-card.tsx`) :
- En-tête « Pilotage Achats · 12 mois ».
- **Économies** : 4 tuiles (Économisé, Laissé sur la table, Taux de meilleur choix, Économies possibles).
- **Cycle** : bandeau **Commandé → Reçu → Facturé** + les deux écarts + « en attente de livraison (€) ».
- **Prix (réutilisé)** : bloc compact des chiffres clés de `price_dashboard` + **lien « Voir le détail → /prix »**.
- **Fournisseurs** : listes « plus compétitifs / en retard / conformité » (top-bottom N).
- Service/hook : `purchasing-kpi-service.ts` + `use-purchasing-kpi.ts` ; type `PurchasingKpi`.

**Mobile** — nouveau module **« Pilotage »** (distinct du module no-code « Indicateurs ») dans `home_shell.dart`. **Amélioration ciblée** : sortir `_Stat` / `_MiniStat` / `_SectionCard` (aujourd'hui privés dans `dashboard_screen.dart`) vers un fichier partagé `mobile/lib/features/common/kpi_widgets.dart`, réutilisé par le dashboard ET le nouvel écran Pilotage (pas de duplication). Mêmes groupes que le web. Pas de librairie de graphes (interdites) — barres maison si besoin.

## Section 4 — Tests & validation

- **Pur** `test_kpi_service.py` : `assemble(parts)` dérive les écarts (commandé−reçu, facturé−reçu), structure les 4 groupes, classe top/bottom fournisseurs, tenant vide → zéros/`None` honnêtes, et **ne recalcule pas** prix/économies (passe-plat vérifié).
- **Real Postgres** `test_kpi_real_db.py` : petit scénario tenant (commandes + factures + réception + le scénario d'économies 2 fournisseurs) → `GET /purchasing/kpi` → asserts sur montants commandé/reçu/facturé, économies réalisées, écarts dérivés, et présence des chiffres prix surfacés. Prouve l'assemblage depuis les vrais moteurs.
- **`savings_service`** : ajouter `test` pour `for_tenant` (miroir de `for_supplier`, sans filtre fournisseur) ; `for_supplier` inchangé.
- **Non-régression** : `/prix`, dashboard d'accueil, `savings_service.for_supplier` inchangés ; garde-fou AST `test_model_attribute_contract.py` vert (aucune colonne). Mobile : non-régression du dashboard après extraction des widgets partagés.
- **Web** : `tsc` / lint / build + test de composant. **Mobile** : `flutter analyze` + widget test (l'écran rend les tuiles depuis une réponse simulée).
- **Validation live (RÈGLE ABSOLUE)** : backend E2E prod (réutiliser le scénario d'économies pour realized>0 → vérifier bloc Économies + Cycle + bloc Prix surfacé, puis nettoyer) + émulateur (écran Pilotage rendu, 0 exception logcat). Web : build vert + contrat validé en direct (pas de harnais Playwright dans le repo).

## Réutilisation / hors périmètre

- **Réutilisé, jamais recalculé** : `price_dashboard`, `top_products`, `quote_matrix.build_for_tenant`, `savings_service` (+ nouveau `for_tenant`).
- **Aucune table / migration** : lecture pure (agrégation), rien n'est stocké.
- Hors périmètre : sélecteur de période, export comptable (préparé plus tard), la fiche produit 360° (= morceau A), la vérif stock (= morceau D). Le détail prix reste sur `/prix` (on lie, on n'absorbe pas).

## Contraintes de livraison (rappel)

Branche → CI verte → merge (jamais de push direct sur `main`) ; jamais de mock de la session BDD (real_db pour la BDD) ; routes littérales avant `/{id}` ; RÈGLE ABSOLUE : « terminé » après validation live Android + Web + PostgreSQL réel ; nettoyage des données de test ; ne jamais déclencher de build Codemagic sans accord.
