"""Traduction d'une erreur OCR en reponse HTTP — partagee factures / devis.

Vivait en local dans `endpoints/invoices.py`. L'import de devis reutilise le
meme pipeline OCR, donc la meme semantique d'erreur : un provider a tourne mais
n'a pas su lire le document (photo floue -> l'utilisateur peut corriger) = 422,
une vraie panne (aucun provider configure / tous KO) = 502.
"""
from fastapi import HTTPException

from .errors import OcrError, AllProvidersFailedError


def ocr_http_error(exc: OcrError, document: str = "document") -> HTTPException:
    """422 si le document est illisible (l'utilisateur peut refaire la photo),
    502 si le service OCR est indisponible. ``document`` personnalise le message
    ("facture", "devis") pour que l'erreur parle la langue de l'ecran."""
    if isinstance(exc, AllProvidersFailedError) and not exc.all_configuration_errors:
        return HTTPException(
            status_code=422,
            detail=(
                f"Impossible de lire ce {document}. Vérifiez que l'image est nette "
                "et bien cadrée, ou essayez un PDF."
            ),
        )
    return HTTPException(
        status_code=502,
        detail=(
            f"Service OCR indisponible : impossible d'analyser le {document} "
            "pour le moment."
        ),
    )
