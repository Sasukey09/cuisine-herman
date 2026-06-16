"""Purchase & price tracking: records each invoice line as a purchase, detects
price variations and recipe margin pressure, and exposes price-history /
supplier-comparison / dashboard analytics.

Built on the existing ``product_prices`` (cost engine source) — purchase_history
is the richer analytics ledger written in the same import step.
"""
