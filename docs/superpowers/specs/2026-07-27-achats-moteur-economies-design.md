# Moteur d'économies (domaine Achats — morceau B)

**Date :** 2026-07-27
**Statut :** design validé, prêt pour le plan d'implémentation
**Périmètre :** premier morceau du « pilotage restant » (Phases 6→8), livré dans l'ordre **B → C → A → D**.

## Contexte

Le domaine Achats sait désormais comparer des offres (comparateur `quote_matrix`),
commander (une commande par fournisseur depuis des lignes de devis retenues),
réceptionner et contrôler les factures. Ce qui manque, c'est de répondre à la
question que le comparateur pose implicitement : **la mise en concurrence a-t-elle
rapporté ?**

En Phase 5, la fiche fournisseur 360° a *délibérément refusé* d'afficher un
« montant économisé » (test `test_no_fabricated_savings_field`), faute d'une
définition honnête. Ce morceau fournit cette définition, une fois, pour tout le
domaine — puis rebranche la fiche fournisseur dessus.

**RÈGLE N°1 respectée :** on ne crée pas un troisième moteur d'« économies » à
côté des deux qui existent. Le comparateur calcule déjà une `potential_savings`
(`quote_matrix.py`) = Σ `(offre la plus chère − offre la moins chère) × qté`,
*avant* commande. Le moteur B mesure le même phénomène *après* commande, avec une
définition qui **se réconcilie exactement** avec celle-là.

## Décision de métrique (validée)

Pour une ligne commandée issue d'une mise en concurrence (≥2 offres réelles sur le
même produit), sur l'ensemble des offres `{choisie} ∪ {concurrentes}` :

| Indicateur | Définition |
|---|---|
| `worst` | `max(offres)` |
| `best` | `min(offres)` |
| **réalisée** | `(worst − chosen) × qty` |
| **manquée** | `(chosen − best) × qty` |
| **possible** | `(worst − best) × qty` |

**Invariant :** `réalisée + manquée = possible` (vérifié par test). Une seule
définition d'économie, ex-ante (comparateur) et ex-post (moteur B), qui boucle et
s'audite.

Baseline retenue = **l'offre la plus chère** (option « vs le plus cher »), parce
qu'elle est déjà la définition maison (`quote_matrix.potential_savings`) et qu'elle
garde une définition unique. Les alternatives (« vs la moyenne », « manquée
seulement ») ont été écartées : la première ne se raccorde pas au « possible » déjà
affiché et peut devenir négative ; la seconde ne fournit pas le « montant
économisé » que réclamait la Phase 5.

## Section 1 — Le cœur pur `savings_service.py`

Nouveau module `backend/app/services/purchasing/savings_service.py`, même patron que
le reste du domaine (cœur pur testable sans base + enveloppes BDD dessous).

**`compute_savings(lines) -> dict`** — pur, aucune base. Chaque ligne d'entrée :

```python
line = {
    "product_id": str,
    "supplier_id": str,
    "qty": float,
    "chosen_unit_price": float,     # ce qu'on a réellement engagé (prix de la ligne de commande)
    "competing_prices": [float],    # offres ÉLIGIBLES des autres fournisseurs, même produit
}
```

Pour chaque ligne, sur `{chosen_unit_price} ∪ competing_prices` :
- `worst = max(...)`, `best = min(...)`
- `realized = (worst − chosen) × qty`
- `missed   = (chosen − best) × qty`
- `possible = (worst − best) × qty`  (≡ realized + missed)
- `is_best_choice = (chosen == best)`

Sortie : le détail par ligne **plus** les totaux
`{realized, missed, possible, best_choice_rate, compared_lines}`, où
`best_choice_rate` = part des lignes comparées où l'on a pris le moins cher
(indicateur de **discipline d'achat**, complémentaire de l'euro).

**Arithmétique en centimes.** Les montants `realized/missed/possible` sont
arrondis à 2 décimales, et `is_best_choice` se juge sur les prix arrondis au
centime (`is_best_choice = chosen ≤ best`, ce qui équivaut à `missed == 0`) —
pour ne pas faire dépendre un « meilleur choix » d'un bruit de virgule flottante.

**Trois règles de rigueur :**
1. **Vraie concurrence obligatoire.** Une ligne sans au moins une offre concurrente
   n'entre pas dans le calcul — ni au numérateur, ni au dénominateur
   (`compared_lines`). Pas de concurrence → aucune économie inventée.
2. **`best`/`worst` ne portent que sur des offres commandables.** Les offres
   périmées ou indisponibles sont exclues **en amont** (dans l'enveloppe BDD, en
   réutilisant exactement les règles d'éligibilité de `quote_matrix` :
   `valid_until` et disponibilité). Le cœur pur reçoit une liste déjà filtrée.
3. **Le mérite de la négociation est compté.** Si `chosen < best` (on a négocié
   sous toutes les offres), alors `missed = 0` et `realized` grossit ; jamais de
   pénalité pour avoir fait mieux que le marché.

## Section 2 — Résolution des offres concurrentes (enveloppe BDD)

Une ligne de commande porte déjà `PurchaseOrderLine.source_quote_line_id` → sa
ligne de devis → son `product_id`. Les concurrents d'une ligne commandée = **les
lignes de devis du même produit, valides à la date de la commande** :

> `quote.date ≤ order.ordered_at` (l'offre existait) **et**
> (`valid_until` nul **ou** `valid_until ≥ order.ordered_at`) (elle était encore
> valable), en excluant les offres périmées / indisponibles.

**Conséquences assumées, conformes à la doctrine « ce qui se déduit ne se stocke pas » :**
- **Rien n'est stocké.** L'économie est *recalculée* depuis les devis (documents
  immuables) et la commande. Aucune colonne `savings` nulle part → aucune migration,
  et l'AST guard `test_model_attribute_contract.py` reste vert sans modification.
- **Chiffre stable et auditable.** Il ne dépend que d'offres qui existaient et
  étaient valides *au moment de commander* ; une offre arrivée après ne réécrit pas
  le passé. Seule dérive possible : supprimer un devis concurrent a posteriori —
  mais supprimer un devis, c'est déjà corriger l'histoire ; on l'accepte.
- **`source_quote_line_id` nullable** ⇒ une commande saisie à la main, sans
  comparatif, **n'a pas d'économie** : elle est absente du calcul, pas comptée
  comme zéro.

## Section 3 — Points de branchement (et ce que B ne fait pas)

**Principe :** B livre le moteur complet, mais **une seule surface** — la fiche
fournisseur. A (produit 360°) et C (KPI) réutiliseront le même cœur sans que B ne
dessine leurs écrans.

**API du moteur** (`savings_service.py`) :
- cœur d'enveloppe scope-agnostique
  `_savings_for_order_lines(db, tenant, *, supplier_id=None, product_id=None, since=None, today)` ;
- fonction publique `for_supplier(...)` **maintenant**. `for_product(...)` et
  `for_tenant(...)` sont des one-liners sur le même cœur, **laissés à A et C**
  (YAGNI : on ne câble pas une surface qui n'existe pas encore).

**Branchement unique — la fiche fournisseur 360° (comble le trou Phase 5) :**
- `supplier_analytics.overview` appelle `savings_service.for_supplier` et **fusionne
  un bloc `savings`** dans la carte déjà renvoyée par `GET /suppliers/{id}/overview`.
  **Aucun nouvel endpoint, aucun nouveau hook.** La fenêtre est **12 mois glissants**
  (`since = today − 365 j`, via le paramètre `since` du cœur), cohérente avec
  `annual_amount` — d'où la tuile « Économisé (12 mois) ».
- **Labels centralisés** `SAVINGS_LABELS` servis par l'API (comme les statuts de
  commande) — « Économisé », « Laissé sur la table », « Économie possible »,
  « Taux de meilleur choix » — pour que web et mobile ne redivergent pas.
- **Web** : `supplier-scorecard.tsx` gagne une tuile « Économisé (12 mois) » + le
  taux de meilleur choix ; `SafeBoundary` isole déjà la carte.
- **Mobile** : même bloc dans `_Scorecard` de `supplier_detail_screen.dart`.
- **Garde-fou inversé** : `test_no_fabricated_savings_field` (qui exigeait
  l'*absence* du champ) est **remplacé** par un test qui exige sa *présence et sa
  justesse*.

**Ce que B ne fait pas :** pas d'écran KPI tenant-wide (→ C), pas de fiche produit
(→ A). Le moteur les sert, il ne les dessine pas.

## Section 4 — Tests & validation

- **Pur** `test_savings_service.py` : l'invariant `réalisée + manquée = possible` ;
  le taux de meilleur choix ; ligne sans concurrent exclue (numérateur et
  dénominateur) ; négocié sous toutes les offres → `manquée = 0` ; offres toutes
  égales → tout à zéro mais `is_best_choice` vrai ; offres périmées/indispo écartées.
- **Real Postgres** `test_savings_real_db.py` : devis multi-fournisseurs (≥2 offres,
  même produit) → commande depuis la ligne la moins chère → bloc `savings` de
  l'overview juste ; commande saisie à la main (`source_quote_line_id` nul) → ne
  contribue rien ; un devis *postérieur* à la commande ne réécrit pas l'économie
  (borne de validité).
- **Mise à jour** de `test_supplier_analytics.py` + `test_supplier_overview_real_db.py`
  (garde-fou inversé).
- **AST guard** `test_model_attribute_contract.py` : vert **sans modification**
  (aucune colonne créée) — preuve que la doctrine tient.
- **Web** : `tsc` / lint / build ; **Playwright live** sur la fiche fournisseur (au
  reset Vercel, empilé avec Phases 4-5 en attente de déploiement).
- **Mobile** : `flutter analyze` + widget test `_Scorecard` + validation
  **émulateur** de la fiche.
- **CI** sur Postgres réel, zéro régression. Nettoyage de tous les jeux de test créés.

## Hors périmètre / à suivre

- `for_product` → **morceau A** (fiche produit 360°).
- `for_tenant` + écran de pilotage → **morceau C** (KPI Achats).
- Déploiement web de B : empilé avec Phases 4 & 5 (mergées, non déployées, Vercel
  rate-limited ~24 h).

## Contraintes de livraison (rappel)

Branche → CI verte → merge (jamais de push direct sur `main`) ; jamais de mock de la
session BDD (tests contre un vrai Postgres) ; ids de révision Alembic ≤ 32 car. (ici
aucune migration) ; RÈGLE ABSOLUE : « terminé » seulement après validation live
Android + Web + Playwright + PostgreSQL réel ; nettoyage des données de test après
validation.
