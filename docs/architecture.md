# Architecture

> **Ce document décrit ce qui existe.**
>
> La version précédente était un document de *conception* — elle promettait GraphQL, des
> WebSockets, une connexion Google OAuth2, du Kubernetes, du rate-limiting Redis et des audit
> trails. **Rien de tout cela n'était dans le code**, mais le document se lisait comme une
> description de l'existant. Une documentation qui invente des fonctionnalités est pire que pas
> de documentation : elle fait perdre des heures à celui qui la croit.
>
> Le projet de conception initial est conservé dans `docs/design-2026-initial.md`.

## Vue d'ensemble

```
  Site Next.js (Vercel)  ─┐
                          ├─► API FastAPI (Render, Docker) ─► PostgreSQL
  App Flutter (Android)  ─┘         │                        └─► Redis (quotas, anti-brute-force)
                                    │
                                    ├─► Mistral OCR      (factures, recettes PDF)
                                    ├─► Anthropic Claude (assistant, extraction)
                                    └─► OpenAI Whisper   (import vidéo hors YouTube)
```

Les trois clients tapent la **même API REST**. Il n'y a **pas** de GraphQL, **pas** de WebSocket,
**pas** de temps réel.

## Authentification

`OAuth2PasswordBearer` + **JWT HS256** (PyJWT). Pas de Google, pas de SSO, pas de cookie : le jeton
voyage dans l'en-tête `Authorization: Bearer`.

- L'algorithme est **épinglé** à la vérification → pas de confusion d'algorithme.
- Chaque jeton porte un claim `tv` (`users.token_version`). `POST /auth/logout` incrémente la
  colonne : **tous** les jetons de l'utilisateur meurent, sur tous ses appareils. Avant, « se
  déconnecter » n'était qu'un `setState(null)` : un refresh token volé restait valable 14 jours.
- **Anti-brute-force** sur `/auth/token` : compteur par compte **et** par IP, backoff exponentiel
  (4 essais libres, puis 30 s → 15 min), dans Redis. Échoue **ouvert** si Redis tombe :
  verrouiller tous les restaurateurs à cause d'un incident de cache serait pire que l'attaque.
- Pas de réinitialisation par email (aucun fournisseur de mail) : un **admin** définit un nouveau
  mot de passe depuis l'écran Administration, ce qui révoque aussi les sessions de l'utilisateur.

## Multi-tenant

Une organisation = un `tenant_id`. **Chaque** lecture et **chaque** écriture le filtre, dans la
couche CRUD. Les identifiants fournis par le client (`product_id` d'une ligne de facture, d'un
ingrédient…) sont **vérifiés** contre le tenant appelant (`app/core/tenancy.py`) : sans ça, on
pouvait référencer le produit d'un autre restaurant et déclencher un recalcul chez lui.

Rôles : `admin`, `manager`, `viewer`. Les écritures exigent `admin` ou `manager`. Il n'y a **pas**
de permissions fines. Les tables `permissions` / `role_permissions` **ont été supprimées** : une
table qui décrit une fonctionnalité qu'on n'a pas finit toujours par être crue.

## Le pipeline qui fait le produit

```
facture (PDF/photo)
   → validation des octets RÉELS (magic bytes, taille, anti-spoofing MIME)
   → OCR (Mistral → Google DocAI ; disjoncteur, réessais, délai d'expiration)
   → lignes persistées
   → rapprochement produit (SKU/nom/alias exacts, puis flou ; < 80 % = « à revoir »)
   → historique de prix + journal d'achats
   → recalcul du coût de TOUTES les recettes qui utilisent ce produit
   → alertes (hausse de prix, marge dégradée)
```

**Il n'y a pas de repli silencieux sur des données d'exemple.** Si l'OCR tombe, la requête échoue
en 502. Le fournisseur « stub » ne peut plus rejoindre la chaîne dès qu'un vrai fournisseur est
configuré : une facture inventée serait prixée, historisée, et propagée dans le coût de toutes les
recettes qui en dépendent.

## Les prix

Un prix entre par **deux** portes, et deux seulement :

- l'**import d'une facture** (OCR → rapprochement produit → historique) ;
- la **saisie manuelle** — `POST /products/{id}/prices`.

La seconde a longtemps manqué, et c'était un trou béant : un chef qui savait parfaitement que le
beurre est à 8,50 €/kg chez Metro n'avait **aucun moyen de le dire**. Toute recette qui l'utilisait
restait non chiffrable jusqu'à ce qu'une facture arrive *et* soit correctement lue. Pour un outil
dont la question entière est « combien me coûte ce plat », c'est une exigence étrange.

Une saisie manuelle enregistre un **prix**, pas un **achat** : rien n'entre dans l'historique
d'achats, parce que rien n'a été acheté. Inventer un achat pour porter un prix corromprait
l'historique même à partir duquel les alertes de prix sont calculées. En revanche, **toutes les
recettes utilisant ce produit sont recalculées immédiatement** : un prix sur lequel personne n'agit
n'est qu'un nombre dans une table.

## Le moteur de coût

`app/services/costing/cost_engine.py` — calcul en `Decimal`, gère les pertes (`loss_pct`), les
rendements (`yield_pct`) et les conversions d'unités. Un prix manquant est **signalé**
(`has_missing_prices`), jamais deviné : un coût sous-estimé en silence, c'est un plat vendu à perte.

`GET /dashboard/loss-making` répond à la seule question pour laquelle cet outil existe : **quels
plats me font perdre de l'argent ?** `margin_estimated` était calculé pour chaque recette depuis la
première version du moteur, et stocké — et **jamais comparé à zéro**. La plateforme savait, et ne le
disait à personne. Ce n'est pas un seuil à régler : un plat dont la portion coûte plus que son prix
de vente perd de l'argent à chaque assiette. Les plats **sans prix de vente** et ceux dont un
ingrédient **n'a pas de prix** sont listés à part : ils ne sont pas « bons », ils sont *inconnus*, et
un plat qu'on ne peut pas évaluer est exactement là où la perte se cache.

Le listing des recettes calcule tous les coûts **en un lot** : 1 requête pour les ingrédients de
toutes les versions, 1 pour le dernier prix de tous les produits, les unités en cache. Avant,
c'était un calcul par recette — **7 500 requêtes SQL pour 500 recettes**.

## Ce qui bloque, et ce qui ne bloque pas

Les appels lents (OCR, Claude, Whisper, stockage objet) tournent **hors de la boucle d'événements**
(`run_in_threadpool`). Dans une coroutine, un appel bloquant de 30 s gèle le **worker entier** :
avec `WEB_CONCURRENCY=2`, un seul import de facture rendait l'API muette **pour tous les clients**.

Le worker Celery existe (`app/tasks.py`) mais **n'est pas utilisé** : les clients appellent le
chemin synchrone. Le code **vérifie qu'un worker répond** avant de lui confier un travail —
`.delay()` réussit même sans worker, et la facture resterait « queued » à vie.

## Quotas et coûts

Chaque route qui facture un tiers (Anthropic, Mistral, OpenAI) ou brûle du CPU a **deux** plafonds
par tenant : un **par minute** (borne la rafale) et un **par jour** (borne la facture). Le second
existe parce que 30 appels IA/minute autorisent quand même **43 200 appels/jour**, soit ~970 $
d'Anthropic pour un seul client en 24 h. Un plafond par minute borne une rafale, pas une dépense.

## Mode hors connexion (mobile uniquement)

Le cache local sert la dernière réponse valide quand le réseau manque — **toujours** avec son âge
affiché. Un coût périmé présenté comme actuel est pire que pas de coût : le chef fixerait un prix
de vente dessus. Une erreur venant du **serveur** (401, 500) n'est pas avalée.

Les **créations** faites hors ligne sont mises en file et rejouées. Seulement les créations : une
création ne peut pas entrer en conflit (le serveur attribue l'id). Mettre en file les modifications
et suppressions obligerait à arbitrer de vrais conflits, et se tromper là-dessus corrompt les coûts
silencieusement.

## Observabilité

- Logs **structurés** JSON (`app/core/logging.py`) avec des événements nommés :
  `ocr.provider.failure`, `login.locked`, `tenancy.cross_tenant_reference`, `quota.unavailable`…
- **Prometheus** sur `/metrics` (protégeable par `METRICS_TOKEN`).
- **Sentry** si `SENTRY_DSN` est défini ; totalement inerte sinon.
- `/live`, `/health`, `/ready` (Postgres, Redis, stockage, OCR). `/ready` ne renvoie **pas**
  l'exception brute : elle contiendrait la chaîne de connexion à la base.

## RGPD

- `GET /rgpd/export` — tout ce que la plateforme détient sur l'organisation, en JSON exploitable
  (art. 15 & 20). Les empreintes de mots de passe en sont **exclues** : elles sont à nous de
  protéger, pas à eux d'emporter.
- `POST /rgpd/delete-organization` — effacement définitif (art. 17). Il faut **retaper le nom exact**
  de l'organisation : c'est la seule chose entre un mauvais clic et toutes les factures, recettes et
  prix jamais enregistrés.
  Six clés étrangères du schéma n'ont **pas** de `ON DELETE` — et c'est voulu : ce sont elles qui
  font que `DELETE /products/{id}` répond 409 au lieu d'arracher un ingrédient d'une recette. Mais
  elles bloquaient aussi la cascade de l'organisation, si bien que l'effacement ne réussissait que
  pour un restaurant **qui n'avait jamais rien fait**. Les lignes bloquantes sont retirées à la
  main, dans l'ordre des dépendances, sans affaiblir aucune des garanties que ces clés protègent.
- `GET /rgpd/audit` — registre : qui a fait quoi, quand (art. 30). Les lignes d'audit d'un
  restaurant effacé partent **avec lui** : ce sont des données personnelles (qui s'est connecté,
  depuis quelle IP). La preuve de l'effacement, elle, est écrite **après**, avec un tenant `NULL` —
  il n'y a plus d'organisation à laquelle l'attacher, et une ligne qui pointait vers elle bloquait
  précisément la suppression qu'elle était censée consigner.
- **Aucun cookie** → **pas de bandeau de consentement** : l'authentification passe par un en-tête.

## Comment on teste

**Tout code qui touche la base est testé contre une vraie base.** Cette règle a coûté trois bugs de
production livrés sous une suite verte — voir [`tests.md`](tests.md), qui raconte lesquels et
pourquoi les mocks ne pouvaient pas les voir.

## Ce qui n'existe pas (et qu'on ne prétend pas avoir)

GraphQL · WebSockets / temps réel · OAuth Google / SSO · Kubernetes · réplicas de lecture ·
permissions fines · **aucun fournisseur d'email** (donc : pas de réinitialisation de mot de passe en
self-service, pas d'alerte par email — un admin remet le mot de passe depuis l'écran Administration)
· notifications push · export PDF ou Excel côté serveur (le CSV est généré dans le navigateur) ·
prévision de coût · gestion de stock et réapprovisionnement (« quoi acheter, et quand ») · mode hors
connexion sur le **web** · édition et suppression depuis le **mobile** · stockage objet configuré en
production (les fichiers de factures ne sont pas conservés).
