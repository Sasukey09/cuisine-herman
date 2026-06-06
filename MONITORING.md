# Monitoring & Observabilité

Observabilité complète du backend FastAPI : métriques Prometheus, dashboards
Grafana, health checks et alerting.

## Sommaire
- [Vue d'ensemble](#vue-densemble)
- [Installation](#installation)
- [Configuration](#configuration)
- [Endpoints](#endpoints)
- [Métriques exposées](#métriques-exposées)
- [Dashboards Grafana](#dashboards-grafana)
- [Alerting](#alerting)

## Vue d'ensemble

```
FastAPI (/metrics) ──scrape──▶ Prometheus ──datasource──▶ Grafana
        │
        ├─ middleware HTTP      → request_count / request_duration / request_errors
        ├─ orchestrateur OCR    → ocr_* (requests/success/failure/fallback/timeout/circuit/duration)
        ├─ pipeline factures    → invoices_/invoice_lines_/products_/price_changes_*
        └─ /health /live /ready → dependency_up{dependency}
```

Le client Prometheus est **optionnel** : sans `prometheus_client`, les métriques
deviennent des no-ops et `/metrics` renvoie un message neutre (l'app ne casse pas).

## Installation

Tout est inclus dans `docker-compose.yml` :

```bash
cp .env.example .env
docker compose up -d
```

Services exposés :

| Service     | URL                          | Notes                          |
|-------------|------------------------------|--------------------------------|
| Backend     | http://localhost:8000        | `/metrics`, `/health`, `/ready`|
| Prometheus  | http://localhost:9090        | scrape `backend:8000/metrics`  |
| Alertmanager| http://localhost:9093        | routage des alertes            |
| Grafana     | http://localhost:3001        | login `admin` / `admin`        |

Grafana provisionne automatiquement le datasource Prometheus et le dashboard
« Cuisine Herman — Observabilité » (dossier *Cuisine Herman*).

> Le paquet `prometheus-client` est dans `backend/requirements.txt`. En local
> sans Docker : `pip install -r requirements.txt`.

## Configuration

Variables d'environnement (cf. `.env.example`) :

| Variable                     | Défaut  | Rôle                                    |
|------------------------------|---------|-----------------------------------------|
| `LOG_LEVEL`                  | `INFO`  | Niveau des logs structurés JSON         |
| `GRAFANA_USER` / `_PASSWORD` | `admin` | Identifiants Grafana                    |

Scrape : `monitoring/prometheus/prometheus.yml` (intervalle 15s).
Règles d'alerte : `monitoring/prometheus/alerts.yml`.

> **Multi-workers** : avec gunicorn/uvicorn multi-process, activez le mode
> multiprocess de `prometheus_client` (`PROMETHEUS_MULTIPROC_DIR`) sinon chaque
> worker expose ses propres compteurs. En mono-process (défaut) rien à faire.

## Endpoints

| Endpoint   | Usage                                                        | Code |
|------------|--------------------------------------------------------------|------|
| `/metrics` | Exposition Prometheus                                        | 200  |
| `/live`    | Liveness (process up, aucune dépendance)                     | 200  |
| `/health`  | Check léger (load balancer)                                  | 200  |
| `/ready`   | Readiness : PostgreSQL, Redis, S3/MinIO, OCR                 | 200 / 503 |

`/ready` renvoie **503** si une dépendance *critique* (PostgreSQL, Redis) est
DOWN. S3 et OCR sont non-critiques (dégradation) — réponse JSON détaillée :

```json
{
  "status": "ready",
  "checks": {
    "postgres": { "status": "up" },
    "redis":    { "status": "up" },
    "s3":       { "status": "up" },
    "ocr":      { "status": "up", "detail": { "configured": ["mistral"] } }
  }
}
```

## Métriques exposées

> Les compteurs portent le suffixe `_total` (convention Prometheus).

### OCR
- `ocr_requests_total{provider}` — tentatives
- `ocr_success_total{provider}` / `ocr_failure_total{provider}`
- `ocr_fallback_total{provider}` — bascule vers le provider suivant
- `ocr_timeout_total{provider}` — timeouts
- `ocr_circuit_open_total{provider}` — ouvertures de circuit
- `ocr_processing_duration_seconds{provider}` — histogramme de durée

### Métier restauration
- `invoices_processed_total`
- `invoice_lines_processed_total`
- `products_matched_total`
- `products_manual_review_total`
- `recipes_recalculated_total`
- `price_changes_detected_total`

### API (par endpoint)
- `request_count_total{method,endpoint,status}`
- `request_duration_seconds{method,endpoint}` — histogramme
- `request_errors_total{method,endpoint}` — 5xx

### Santé
- `dependency_up{dependency}` — 1 = up, 0 = down (mis à jour par `/ready`)

## Dashboards Grafana

Dashboard unique avec 5 sections (`monitoring/grafana/dashboards/cuisine-herman.json`) :

- **OCR** : débit par provider, succès/échecs, durée p95, fallback/timeout/circuit
- **Factures** : factures traitées, lignes/s, changements de prix
- **Produits** : auto-match vs revue manuelle, taux d'auto-match
- **Recettes** : recalculs/s, état des dépendances
- **API** : débit par endpoint, taux d'erreur 5xx, latence p95

Pour le modifier : éditez dans Grafana puis exportez le JSON (Share → Export)
vers `monitoring/grafana/dashboards/`.

## Alerting

Règles dans `monitoring/prometheus/alerts.yml` (visibles sur
http://localhost:9090/alerts) :

| Alerte               | Condition                                   | Sévérité  |
|----------------------|---------------------------------------------|-----------|
| `HighApiErrorRate`   | > 5% de 5xx sur 5m                          | warning   |
| `ApiLatencyP95High`  | latence p95 > 2s sur 10m                    | warning   |
| `OcrFailuresHigh`    | > 30% d'échecs OCR sur 10m                  | warning   |
| `OcrCircuitOpen`     | circuit OCR ouvert                          | critical  |
| `DependencyDown`     | `dependency_up == 0` depuis 2m              | critical  |

**Alertmanager** est inclus (http://localhost:9093) et reçoit les alertes de
Prometheus. Sa configuration est dans `monitoring/alertmanager/alertmanager.yml` :
- route par défaut + route dédiée `severity="critical"` (répétition 1h)
- règle d'inhibition (un critical masque le warning de même `alertname`)
- récepteurs Slack / email / PagerDuty **prêts à décommenter** (placeholders).

Les seuils se règlent dans `alerts.yml`, le routage/notifications dans
`alertmanager.yml`. Après modification : `docker compose restart prometheus alertmanager`.
