"""Persistence for the PDF recipe-import jobs and their results."""
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.models.models import RecipeImportJob, RecipeImportResult


def create_job(db: Session, tenant_id: str, filename: Optional[str],
               content_type: Optional[str]) -> RecipeImportJob:
    job = RecipeImportJob(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        filename=filename,
        content_type=content_type,
        status="processing",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def get_job(db: Session, tenant_id: str, job_id: str) -> Optional[RecipeImportJob]:
    return (
        db.query(RecipeImportJob)
        .filter(RecipeImportJob.id == job_id, RecipeImportJob.tenant_id == tenant_id)
        .first()
    )


def set_status(db: Session, job: RecipeImportJob, status: str,
               error: Optional[str] = None) -> RecipeImportJob:
    job.status = status
    job.error = error
    job.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(job)
    return job


def save_result(db: Session, job: RecipeImportJob, raw_text: str,
                preview: Dict[str, Any]) -> RecipeImportResult:
    result = RecipeImportResult(
        id=str(uuid.uuid4()),
        job_id=str(job.id),
        tenant_id=str(job.tenant_id),
        raw_text=raw_text,
        recipe_name=preview.get("recipe_name"),
        servings=preview.get("servings"),
        data=preview,
    )
    db.add(result)
    db.commit()
    db.refresh(result)
    return result


def get_result(db: Session, job_id: str) -> Optional[RecipeImportResult]:
    return (
        db.query(RecipeImportResult)
        .filter(RecipeImportResult.job_id == job_id)
        .order_by(RecipeImportResult.created_at.desc())
        .first()
    )


def attach_recipe(db: Session, result: RecipeImportResult, recipe_id: str) -> None:
    result.recipe_id = recipe_id
    db.commit()
