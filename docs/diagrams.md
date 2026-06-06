# Diagrammes Mermaid — Architecture & séquences

## Architecture globale
```mermaid
flowchart TD
  subgraph Clients
    A[Next.js Web UI]
    B[Flutter Mobile App]
  end

  subgraph API
    G[FastAPI Backend (API Gateway)]
  end

  subgraph Services
    OCR[OCR Service]
    AI[AI Service (RAG, LLM)]
    CAT[Catalog Service]
    INV[Invoice Parser Service]
    REC[Recipe Service]
    CALC[Calculation Engine]
    TRANS[Video/Transcription Service]
    WORKERS[Celery Workers]
  end

  subgraph Infra
    PG[(PostgreSQL)]
    REDIS[(Redis)]
    S3[(S3-compatible Storage)]
    ES[(OpenSearch/Elasticsearch)]
    OBJ[(Object Storage)]
  end

  A -->|REST / GraphQL| G
  B -->|REST / GraphQL| G
  G --> CAT
  G --> INV
  G --> REC
  G --> AI
  G --> TRANS
  G --> WORKERS

  INV -->|store file| S3
  INV -->|enqueue OCR job| WORKERS
  WORKERS --> OCR
  OCR -->|ocr result| S3
  OCR --> INV

  WORKERS --> CALC
  CALC --> REC
  CALC --> PG

  AI -->|embeddings| PG
  TRANS -->|audio| S3
  TRANS --> AI

  G --> PG
  G --> REDIS
  G --> ES

  style G fill:#f9f,stroke:#333,stroke-width:1px
```

## Sequence: Importer une facture
```mermaid
sequenceDiagram
  participant User
  participant WebUI
  participant API as FastAPI
  participant S3
  participant Worker as Celery
  participant OCR
  participant Parser
  participant DB as PostgreSQL

  User->>WebUI: Upload PDF/photo
  WebUI->>API: POST /invoices/upload
  API->>S3: Store file
  API->>DB: Create invoice record (status: uploaded)
  API->>Worker: enqueue task invoice.process(invoice_id)
  Worker->>S3: Download file
  Worker->>OCR: extract_text(file)
  OCR-->>Worker: ocr_result
  Worker->>Parser: parse_invoice(ocr_result)
  Parser-->>Worker: {header, lines}
  Worker->>DB: update invoice, create invoice_lines
  Worker->>Worker: enqueue match_products for lines
  Note right of DB: Invoice ready for manual review if needed
```

## Sequence: Changement de prix -> Recalcul recettes
```mermaid
sequenceDiagram
  participant PriceUpdate
  participant Worker as Celery
  participant CalcEngine
  participant DB as PostgreSQL
  participant RecipeService
  participant Dashboard

  PriceUpdate->>Worker: publish price_changed(product_id)
  Worker->>CalcEngine: compute_affected_recipes(product_id)
  CalcEngine->>DB: query affected recipe_versions
  loop for each recipe_version
    CalcEngine->>RecipeService: compute_cost(recipe_version_id)
    RecipeService-->>DB: persist recipe_cost snapshot
    RecipeService->>Dashboard: emit dashboard_update(recipe_id)
  end
  Dashboard->>DB: update aggregated metrics (async)
```

## Sequence: Ingestion vidéo -> création brouillon recette
```mermaid
sequenceDiagram
  participant User
  participant UI
  participant API
  participant Fetcher
  participant Transcriber
  participant NLP
  participant DB
  participant AI

  User->>UI: Submit video URL
  UI->>API: POST /video/submit {url}
  API->>Fetcher: enqueue fetch_video(url)
  Fetcher->>S3: store audio/video
  Fetcher->>Transcriber: enqueue transcribe(audio)
  Transcriber->>AI: transcribe(audio)
  AI-->>Transcriber: transcription text
  Transcriber->>NLP: extract_entities(transcription)
  NLP-->>API: {ingredients, quantities, steps}
  API->>DB: create draft recipe_version with ingredients
  API->>User: notify draft ready (UI)
```
