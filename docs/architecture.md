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
de permissions fines (les tables `permissions` / `role_permissions` existent mais ne sont jamais
lues).

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

## Le moteur de coût

`app/services/costing/cost_engine.py` — calcul en `Decimal`, gère les pertes (`loss_pct`), les
rendements (`yield_pct`) et les conversions d'unités. Un prix manquant est **signalé**
(`has_missing_prices`), jamais deviné : un coût sous-estimé en silence, c'est un plat vendu à perte.

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
- `GET /rgpd/audit` — registre : qui a fait quoi, quand (art. 30).
- **Aucun cookie** → **pas de bandeau de consentement** : l'authentification passe par un en-tête.

## Ce qui n'existe pas (et qu'on ne prétend pas avoir)

GraphQL · WebSockets / temps réel · OAuth Google / SSO · Kubernetes · réplicas de lecture ·
permissions fines · notifications push · mode hors connexion sur le **web** · édition et
suppression depuis le **mobile** · réinitialisation de mot de passe par email · stockage objet
configuré en production (les fichiers de factures ne sont pas conservés).
