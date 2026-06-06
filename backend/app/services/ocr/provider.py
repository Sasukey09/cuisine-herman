from abc import ABC, abstractmethod
from typing import Optional

from .schemas import OcrResult


class OCRProvider(ABC):
    """Provider-agnostic OCR interface.

    Implementations must support PDF and image inputs and return an OcrResult
    (raw text + optional tables + optional structured invoice fields).
    """

    name: str = "base"

    def is_configured(self) -> bool:
        """True if the provider has everything it needs (keys, SDK) to run."""
        return True

    @abstractmethod
    def extract_document(self, file_bytes: bytes, content_type: Optional[str] = None) -> OcrResult:
        raise NotImplementedError()


def is_pdf(file_bytes: bytes, content_type: Optional[str]) -> bool:
    if content_type and "pdf" in content_type.lower():
        return True
    return file_bytes[:5] == b"%PDF-"
