# Tester FoodGad

> Ce document existe parce que **trois bugs de production sont passés à travers une suite verte**,
> le même jour, pour la même raison. Ce n'est pas une page de bonnes pratiques : c'est le
> compte-rendu d'une panne, et la règle qui en sort.

## Ce qui s'est passé

`GET /rgpd/export` répondait **500 en production, à chaque appel, depuis le premier jour**.
La suite était verte. 220 tests.

La cause : l'export lisait chaque cellule avec `getattr(row, nom_de_la_colonne_en_base)`. Or dix
de nos tables ont une colonne nommée `metadata` — un nom que SQLAlchemy se réserve — donc mappée
sur l'attribut `meta` :

```python
meta = Column("metadata", JSONB)
```

`getattr(row, "metadata")` ne renvoie donc pas la cellule. Il renvoie **l'objet `MetaData` de
SQLAlchemy** : le schéma entier, des tables qui pointent vers des colonnes qui repointent vers les
tables. FastAPI entrait dedans et n'en sortait plus — `RecursionError`.

Aucun test ne pouvait le voir : **tous mockaient la session**. Un `Mock` ne connaît pas les noms de
colonnes, n'a pas de `MetaData`, et ne fait pas de récursion.

En corrigeant ça, j'ai fait passer les tests contre le vrai Postgres qui tournait déjà dans la CI
sans que personne ne s'en serve. **Deux autres bugs sont tombés dans la même exécution** :

| Bug | Ce que ça cassait |
|---|---|
| `audit_logs.tenant_id` sans `ON DELETE` | Le droit à l'effacement (art. 17) échouait **dès la première connexion** — parce que se connecter écrit une ligne d'audit. |
| 5 autres clés étrangères sans `ON DELETE` (`recipe_ingredients`, `purchases`, `recipe_versions`) | L'effacement échouait pour **tout restaurant possédant une recette**. Il ne fonctionnait que pour un client qui n'avait jamais rien fait. |

Ces clés ne sont pas des oublis : ce sont elles qui font que `DELETE /products/{id}` répond **409**
au lieu d'arracher silencieusement un ingrédient d'une recette. Le bug n'était pas dans le schéma.
Il était dans le fait que **personne n'avait jamais essayé de supprimer une organisation réelle**.

## La règle

> **Tout code qui touche la base est testé contre une vraie base.**

Un `Mock` ne peut pas :

- violer une clé étrangère,
- renvoyer un `Decimal` là où on attendait un `float`,
- distinguer un nom de colonne d'un nom d'attribut Python,
- appliquer une cascade — ni refuser de l'appliquer.

Ce sont exactement les quatre façons dont ce projet s'est cassé.

Les tests mockés restent utiles pour la logique **pure** : le calcul de coût sur des ingrédients
en mémoire, le backoff du limiteur de connexions, le parseur d'unités. Dès qu'une session
SQLAlchemy entre dans la fonction, le mock ment.

## Comment ça marche

`backend/tests/conftest.py` fournit une fixture `db` :

- elle lit `DATABASE_URL` ;
- **si la variable est absente, le test est ignoré** (`skip`), pas en échec — un poste sans
  Postgres reste utilisable ;
- si la base est injoignable, `skip` également, avec la raison.

En CI, `DATABASE_URL` pointe vers un service Postgres, **et les migrations tournent AVANT les
tests**. Cet ordre est le correctif le moins spectaculaire et le plus important de tout l'épisode :
auparavant elles tournaient *après*, donc la base était vide pendant toute la suite.

```python
def test_le_beurre_coute_ce_qu_il_coute(db):
    ...
```

### Les fichiers concernés

| Fichier | Ce qu'il protège |
|---|---|
| `test_rgpd_real_db.py` | Export sérialisable, effacement d'un restaurant **réellement utilisé**, registre d'audit |
| `test_costing_real_db.py` | Le moteur de coût : conversions d'unités, pertes, rendements, prix manquants, isolation |
| `test_loss_making_real_db.py` | Les plats vendus à perte |
| `test_manual_price_real_db.py` | La saisie d'un prix à la main, et le recalcul qui suit |

## Deux pièges, appris à mes dépens

### Semer dans le désordre

Aucune `relationship` n'est déclarée entre nos modèles. SQLAlchemy ignore donc qu'une facture
dépend d'un fournisseur, et l'insère volontiers en premier. **Committez les parents avant les
enfants** — ce n'est pas un bug du code, c'est un piège du test.

### Un test qui ne vérifie que le refus ne prouve rien

`POST /products/{id}/prices` a été livré avec les arguments de `assert_product_in_tenant` inversés.
Le garde-fou refusait **tout le monde**, propriétaire compris : la fonctionnalité ne marchait pour
personne. La CI était verte — parce que **le test inversait les arguments exactement de la même
façon**. Il attendait une exception, il en obtenait une, pour la mauvaise raison. Il était vert *en
accord avec le bug*.

Un garde-fou qui dit non à tout le monde n'est pas un garde-fou, c'est une panne. **Vérifiez
toujours le cas nominal d'abord** : que le propriétaire, lui, passe.

## Le reste de la CI

`.github/workflows/ci.yml` — 4 jobs, tous bloquants :

- **Backend** — Postgres réel, migrations rejouées depuis zéro, la suite complète, **et le
  démarrage avec la commande exacte de production** (gunicorn + `uvicorn_worker`). Cette dernière
  étape existe parce qu'un jour la CI était verte pendant que le conteneur de production était
  incapable de démarrer : `uvicorn ≥ 0.30` avait supprimé `uvicorn.workers.UvicornWorker`, et
  **la CI ne lançait jamais la commande de production**.
- **Web** — lint, types, build.
- **Mobile** — analyze, tests, **APK release**, et une assertion que la permission `INTERNET` est
  dans le manifeste *fusionné* (sans elle, l'app n'a aucun réseau en release, et seulement en
  release).
- **Dépendances** — `pip-audit`, **bloquant** : zéro vulnérabilité connue tolérée.
