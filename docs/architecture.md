Architecture détaillée — Plateforme SaaS de gestion de restauration

Résumé exécutif

Conception d'une plateforme SaaS multi-tenant, hautement disponible et extensible pour la gestion complète des achats, factures, recettes, fiches techniques et analyses IA. L'architecture suit DDD, Clean Architecture et Event-Driven Architecture : services métier découplés, API HTTP exposée par un Backend FastAPI, traitements asynchrones via Celery, stockage PostgreSQL, cache Redis, files d'attente Celery, stockage objets compatible S3, et frontends Next.js (web) et Flutter (mobile). Sécurité, observabilité, CI/CD et scalabilité cloud-ready sont intégrés dès la conception.

Contraintes technologiques imposées
- Backend : Python + FastAPI
- DB : PostgreSQL
- Cache : Redis
- Queue : Celery
- Storage : S3-compatible
- Frontend Web : Next.js, React, TypeScript, Tailwind, shadcn UI
- Mobile : Flutter
- Auth : JWT + OAuth Google
- Infra : Docker / Docker Compose, Kubernetes-ready

Principes d'architecture
- Domain-Driven Design : domaines clairs (Procurement, Catalog, Recipes, Costing, OCR, AI, Analytics, Tenancy).
- Clean Architecture : séparation interface / application / domaine / infrastructure.
- Event-Driven : tout changement de prix, import facture, ou création de recette publie des événements consommés par workers.
- Idempotence et immutabilité : snapshots pour calculs de coût, immuabilité des versions de recette, audit logs.
- Sécurité : RBAC, encryption at-rest/in-transit, scoping tenant, audit trails.

Composants principaux

1) API Gateway / Backend
- FastAPI app (stateless) exposant REST/GraphQL endpoints et WebSocket pour notifications.
- Auth middleware (JWT validation, OAuth2 Google flows).
- RBAC middleware + tenant scoping filter (inject tenant_id depuis token / subdomain / header).
- OpenAPI / Swagger + Redoc.
- Versioning API (`/api/v1/`).

2) Domain Services (dans le Backend)
- Supplier Service (CRUD, search, history).
- Invoice Service (upload, parse, validation, link lines to products).
- OCR Orchestrator (interface provider-agnostic, calls ocr_service via queue or sync).
- Catalog Service (products, aliases, categories, unit conversions).
- Pricing Service (persist price history, compute WAP, moving averages).
- Recipe Service (versions, ingredients, duplication, archiving).
- Cost Engine (compute cost snapshots, triggers on price change).
- Video/Transcription Service (ingest URL, fetch, transcribe, NLP extraction).
- AI Service (RAG, embeddings, LLM suggestions).

3) OCR Service (microservice)
- Interface: extract_invoice(file_url), extract_products(ocr_result), normalize_units(quantities)
- Implementation pluggable: Mistral OCR, Google Document AI, Tesseract fallback.
- Runs as separate container, scalable; communicates via S3 and event queue.

4) Worker Layer (Celery)
- Tasks: run_ocr, parse_invoice, match_products (fuzzy matching), persist_prices, recompute_recipe_costs, generate_transcription, ai_analysis, send_notifications.
- Broker: Redis (or Redis + RabbitMQ if needed).
- Result backend: Redis or PostgreSQL for job tracking.

5) Storage & DB
- PostgreSQL primary (OLTP) with partitioning strategies for large invoice tables.
- S3-compatible object storage for invoices, images, video audio artifacts, and model artifacts.
- pgvector extension for embeddings storage (AI RAG use-cases).
- Redis for cache, rate-limiting, Celery broker.

6) Search & Analytics
- OpenSearch / Elasticsearch for full-text search (products, suppliers), aggregations and dashboards.
- Materialized views in PostgreSQL for aggregated metrics; workers refresh asynchronously.

7) AI / NLP Stack
- Embeddings store: pgvector or vector DB (e.g., Pinecone optional).
- LLMs: OpenAI (or self-hosted Llama 2/ Mistral) via adapter service.
- Transcription: Whisper (local) or cloud STT.
- RAG pipeline: chunking, embeddings, retrieval, prompt engineering.

8) Frontend
- Next.js app: Admin UI, reporting, recipe editor, invoice review UI.
- React components in TypeScript using Tailwind and shadcn UI.
- SSR + client-side for dashboards; SWR/react-query for data fetching.
- Flutter mobile app consumes same API; authentication via OAuth/JWT refresh flows.

9) DevOps & Infra
- Containerized services (Docker). Compose for local dev; Helm charts for k8s.
- Terraform for cloud infra (VPC, buckets, RDS, EKS/GKE/AKS).
- CI/CD: GitHub Actions -> build images -> push to registry -> deploy to staging/prod via CD pipeline.
- Secrets: Vault or cloud secret manager.
- Backups: RDS snapshots + WAL archiving to S3; periodic verification tests.

Domain Model & Data Flow (haute-niveau)

- Upload facture (UI / API): file -> S3 -> emit InvoiceUploaded event.
- OCR worker picks event -> downloads file -> provider OCR -> returns structured text -> store raw OCR result in S3 and DB.
- Parser worker consumes OCR -> extract invoice header (supplier, date, invoice_no) and lines -> create invoice + invoice_lines rows (status=parsed/needs_review).
- For each invoice_line: try fuzzy match on `product_aliases`; if match create purchase + product_price record and emit PriceChanged event if price diff beyond threshold.
- PriceChanged event -> pushed to Celery queue `price_changes`.
- Cost Engine workers consume `price_changes` -> find affected recipes (reverse index or precomputed dependencies) -> recompute cost snapshots per recipe_version -> store `recipe_costs` snapshot and emit DashboardUpdated event.
- Video ingestion: submit URL -> fetch video/audio -> transcribe -> NLP extract ingredients/quantities -> create draft recipe_version for user review.
- AI suggestions: user triggers or periodic job to run analyze_recipe()/suggest_optimizations() using embeddings + LLM; suggestions stored in `ai_suggestions`.

Multi-tenancy strategy

- Single database with tenant_id column on most tables (sargable indices). For large customers, optionally support schema-per-tenant or dedicated DB.
- Tenant isolation enforced at application layer and DB row-level security (RLS) as extra protection.
- Billing & rate-limits per tenant.

Unit conversion system

- Canonical units table with categories (mass, volume, count). Each unit stores conversion factor to canonical base of its category.
- Normalization routines in both Catalog Service and OCR normalizer to convert quantities to canonical units before storing.

Calculation Engine (détails)

- Event: PriceChange {product_id, old_price, new_price, effective_date}
- Worker identifies dependent recipe_versions via `recipe_ingredients` join.
- For each recipe_version: compute cost by summing ingredient_qty_normalized * latest_product_price_at_date * (1 + loss_pct) / yield.
- Persist snapshot with `snapshot_price_source` (list of price ids used) for reproducibility.
- Use batching and rate-limit recomputations for very large fan-outs; provide priority queueing for critical paths.

Customization & Extensibility

- Custom fields/metrics stored as JSON schemas in `custom_fields` and `custom_metrics`; UI renders form generators.
- Custom formulas: use a safe expression language (e.g., exprtk or a sandboxed evaluator) with variables resolved to latest metrics.
- Report builder: pull-based report generator using stored queries and templates; jobs created for heavy reports.

Security & Compliance

- Auth: OAuth2 flows + JWT access tokens (short-lived) + refresh tokens (rotate). Google OAuth as federated login provider.
- RBAC: roles + permissions; admin can manage tenant users.
- Audit: immutable audit_logs for CRUD operations and cost recalculation events.
- RLS in Postgres for defense in depth.
- Rate-limiting at API gateway (per-tenant throttles).
- Encrypt S3 and DB at rest; TLS in transit.
- GDPR: data export and deletion endpoints; data retention policies.

Observability & SLOs

- Metrics: Prometheus scraping; Grafana dashboards for latency, error rate, queue depth, task failure rates.
- Tracing: OpenTelemetry across services to trace OCR -> parser -> price update flows.
- Logging: structured logs to ELK/Cloud logging.
- Alerts: PagerDuty integration on critical SLO breaches.

Operational considerations

- Testing: unit tests, integration tests; end-to-end pipelines using test containers (Postgres, Redis); contract tests for AI adapters.
- Canary releases and feature flags for risky features (parsers, AI suggestions).
- Data migrations via Alembic; perform schema migrations backward-compatible where possible.

Next steps (après validation)

- Générer diagrammes Mermaid (architecture globale, sequence flows: invoice import, price change -> recalculation, video ingestion).
- Générer schéma SQL complet (DDL) et modèles SQLAlchemy.
- Ensuite: scaffolding FastAPI project et tâches Celery.

Validation requise

J'attends votre validation de cette architecture (ou retours précis) avant de générer les diagrammes Mermaid et passer à l'étape 2.
