MVP Backlog — Sprint-by-sprint (estimation en jours)

Hypothèses:
- Sprint = 2 semaines (10 working days). Estimations en jours ouvrés.
- Équipe MVP: 2 backend devs, 1 frontend dev, 1 product/designer (part-time), 0.5 DevOps, 0.5 QA.

Sprint 0 (10d): Spécs & infra minimal
- Spécification détaillée des flux critiques (2d)
- UX flows clés + wireframes (3d)
- Setup repo, CI, IaC minimal (Terraform) et k8s dev (3d)
- DB schema initial & migrations (2d)

Sprint 1 (10d): Auth, organisations, produits de base
- Auth (JWT + RBAC) endpoints, migration users/roles (3d)
- Organisations CRUD & settings (1d)
- Units & product model, product CRUD (3d)
- Frontend: auth + product list basic (3d)

Sprint 2 (10d): Suppliers & prices history
- Suppliers CRUD, supplier contacts (2d)
- Product price history model & endpoints (3d)
- UI: supplier/product price history screens (3d)
- Tests & QA (2d)

Sprint 3 (10d): Invoice upload + storage + OCR pipeline (MVP)
- File upload service, S3 storage + signed URLs (2d)
- OCR integration (Google Vision/Textract) worker + queue (3d)
- Minimal parser heuristics to extract lines (3d)
- UI: upload invoice flow + review extracted lines (2d)

Sprint 4 (10d): Invoice parse → pricing → purchases
- Mapping invoice lines to products (manual + fuzzy match) (3d)
- Create purchases & product_prices from parsed lines (3d)
- Worker: update price history and trigger recipe recalcs (2d)
- UI: invoice detail, manual mapping editor (2d)

Sprint 5 (10d): Recipes & cost engine
- Recipes CRUD + versioning baseline (4d)
- Recipe ingredients and units, yield/loss fields (2d)
- Cost engine: compute cost total, cost per portion, food cost (3d)
- UI: recipe editor + cost display (1d)

Sprint 6 (10d): Dashboards & recalculation flows
- Async recalculation job + scheduling (2d)
- Basic dashboards: evolution cost matière, top products (4d)
- Alerts framework (low margin) (2d)
- QA, hardening, backups (2d)

Sprint 7 (6–10d): Polish & release
- End-to-end tests, bugfixes (4d)
- Documentation API minimal + deployment (2d)
- Release & handoff (1–2d)

Total MVP effort (dev days): ~66–70 developer-days (≈3–5 months depending on parallelization).

Phase 2 (priorités):
- Advanced invoice ML parser and training dataset (40–60d)
- Video transcription + NLP pipeline (Whisper + entity extraction) (30–50d)
- AI assistant & suggestion engine (embeddings + LLM integration) (30–60d)
- No-code report builder / custom fields UI (30–50d)

Remarques:
- Estimations hautes/basses dépendent du niveau d'automatisation OCR/NLP et de la qualité des parsers.
- Si l'on sous-traitent OCR/LLM (API payantes), le développement diminue mais coûts d'exploitation augmentent.
