"""Import a recipe from a PDF: OCR -> AI structured extraction -> product
matching -> cost preview -> validated save.

Reuses the existing OCR chain (``services.ocr``), the product matcher
(``services.matching``) and the cost engine (``services.costing``) so an imported
recipe is costed exactly like one created by hand or by the assistant.
"""
