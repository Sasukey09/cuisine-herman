"""OCR runtime configuration, read from environment.

Read fresh on each access so tests (and live re-config) can override env vars
without restarting the process.
"""
import os
from dataclasses import dataclass
from typing import List, Optional


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


@dataclass
class OcrConfig:
    chain: List[str]
    timeout_seconds: float
    max_retries: int
    retry_backoff: float
    cb_fail_threshold: int
    cb_reset_seconds: float
    allow_stub_fallback: bool
    # Mistral OCR
    mistral_api_key: Optional[str]
    mistral_url: str
    mistral_model: str
    # Google Document AI
    gcp_project: Optional[str]
    docai_location: str
    docai_processor_id: Optional[str]
    docai_processor_version: Optional[str]


def get_ocr_config() -> OcrConfig:
    raw_chain = os.getenv("OCR_PROVIDER_CHAIN", "mistral,google")
    chain = [p.strip().lower() for p in raw_chain.split(",") if p.strip()]
    return OcrConfig(
        chain=chain,
        timeout_seconds=_float("OCR_TIMEOUT_SECONDS", 30.0),
        max_retries=_int("OCR_MAX_RETRIES", 2),
        retry_backoff=_float("OCR_RETRY_BACKOFF", 0.5),
        cb_fail_threshold=_int("OCR_CB_FAIL_THRESHOLD", 3),
        cb_reset_seconds=_float("OCR_CB_RESET_SECONDS", 30.0),
        # OFF by default. When every provider fails, the pipeline must raise —
        # never quietly return the canned demo invoice, which would be priced,
        # stored in the purchase ledger and propagated into recipe costs.
        # Set to true only for a local demo without any OCR key.
        allow_stub_fallback=_bool("OCR_ALLOW_STUB_FALLBACK", False),
        mistral_api_key=os.getenv("MISTRAL_API_KEY"),
        mistral_url=os.getenv("MISTRAL_OCR_URL", "https://api.mistral.ai/v1/ocr"),
        mistral_model=os.getenv("MISTRAL_OCR_MODEL", "mistral-ocr-latest"),
        gcp_project=os.getenv("GCP_PROJECT_ID"),
        docai_location=os.getenv("DOCAI_LOCATION", "eu"),
        docai_processor_id=os.getenv("DOCAI_PROCESSOR_ID"),
        docai_processor_version=os.getenv("DOCAI_PROCESSOR_VERSION"),
    )
