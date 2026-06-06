API REST — MVP (esquisse)

Authentification
- POST /api/v1/auth/login
  - body: {email, password}
  - resp: {access_token, token_type, expires_in, user}
- POST /api/v1/auth/refresh

Orgs & users
- GET /api/v1/orgs/:orgId (admin)
- POST /api/v1/orgs
- GET /api/v1/users (filter by org)
- POST /api/v1/users

Suppliers
- GET /api/v1/suppliers
- POST /api/v1/suppliers
- GET /api/v1/suppliers/:id
- PUT /api/v1/suppliers/:id

Products & units
- GET /api/v1/products
- POST /api/v1/products
- GET /api/v1/products/:id
- PUT /api/v1/products/:id
- GET /api/v1/units
- POST /api/v1/units

Product prices / purchases
- GET /api/v1/products/:id/prices
- POST /api/v1/products/:id/prices
- GET /api/v1/purchases
- POST /api/v1/purchases

Invoices & upload
- POST /api/v1/invoices/upload
  - multipart: file; returns invoice_id, upload_status
- GET /api/v1/invoices/:id
- POST /api/v1/invoices/:id/parse
  - triggers OCR + parsing (async)
- GET /api/v1/invoices/:id/lines
- POST /api/v1/invoices/:id/lines/:lineId/map-product
  - body: {product_id}

Recipes
- GET /api/v1/recipes
- POST /api/v1/recipes
- GET /api/v1/recipes/:id
- POST /api/v1/recipes/:id/versions
- GET /api/v1/recipes/:id/versions/:vid
- POST /api/v1/recipes/:id/versions/:vid/compute-cost
  - returns snapshot with cost breakdown

Video / transcription
- POST /api/v1/video/submit
  - body: {url}
- GET /api/v1/transcriptions/:id

AI suggestions
- GET /api/v1/ai/recipes/:recipeId/suggestions
- POST /api/v1/ai/suggest-replacement
  - body: {recipe_id, ingredient_id}

Dashboards
- GET /api/v1/dashboard/cost-trends?from=YYYY-MM-DD&to=YYYY-MM-DD
- GET /api/v1/dashboard/top-products?limit=10

Webhooks
- POST /api/v1/webhooks/invoice-parsed (for integrations)

Security
- All endpoints under /api/v1 require Authorization: Bearer <token> except auth routes.
- Role-based access control enforced by middleware.

Notes on contracts
- Use JSON:API-like shapes (resource, attributes) or simple REST JSON depending on frontend preference.
- Endpoints that trigger long processing return 202 with `job_id` and job status endpoint: GET /api/v1/jobs/:id

Errors
- Standard error envelope: {code, message, details?}

This is a concise spec for frontend + mobile to implement UI and for backend to stub routes. Further: add OpenAPI schema generation once models are stable.
