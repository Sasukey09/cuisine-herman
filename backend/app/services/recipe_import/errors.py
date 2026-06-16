class RecipeImportError(Exception):
    """Base error for the PDF recipe-import pipeline."""


class PdfUnreadableError(RecipeImportError):
    """OCR returned no usable text from the document."""


class RecipeExtractionError(RecipeImportError):
    """The model could not produce a usable recipe from the text."""
