"""Cross-tenant isolation of PDF-import results, against a real PostgreSQL.

`import-save` takes a client-supplied `job_id` and used to look the result up by
id alone. This asserts, against a real DB, that `get_result` now refuses to hand
one tenant another tenant's import result (the fix keys on tenant_id too).

Skips when no DATABASE_URL is set, so a laptop without Postgres stays usable.
"""
import uuid

import pytest

from app.crud import crud_recipe_import
from app.models.models import Organization, RecipeImportJob, RecipeImportResult


@pytest.fixture
def two_tenants_with_a_job(db):
    tenant_a = str(uuid.uuid4())
    tenant_b = str(uuid.uuid4())
    db.add(Organization(id=tenant_a, name="Tenant A"))
    db.add(Organization(id=tenant_b, name="Tenant B"))
    db.commit()

    job_id = str(uuid.uuid4())
    db.add(RecipeImportJob(id=job_id, tenant_id=tenant_a, status="done"))
    db.commit()
    db.add(
        RecipeImportResult(
            id=str(uuid.uuid4()),
            job_id=job_id,
            tenant_id=tenant_a,
            raw_text="secret recipe of tenant A",
            data={"recipe_name": "Secret A"},
        )
    )
    db.commit()

    yield tenant_a, tenant_b, job_id

    # ON DELETE CASCADE on tenant_id removes the job + result with the org.
    for t in (tenant_a, tenant_b):
        org = db.query(Organization).filter(Organization.id == t).first()
        if org is not None:
            db.delete(org)
    db.commit()


def test_a_tenant_cannot_read_another_tenants_import_result(two_tenants_with_a_job, db):
    tenant_a, tenant_b, job_id = two_tenants_with_a_job

    # Tenant B knows/guesses the job_id — it must still get nothing.
    assert crud_recipe_import.get_result(db, tenant_b, job_id) is None


def test_the_owning_tenant_still_reads_its_own_import_result(two_tenants_with_a_job, db):
    tenant_a, _tenant_b, job_id = two_tenants_with_a_job

    result = crud_recipe_import.get_result(db, tenant_a, job_id)
    assert result is not None
    assert result.raw_text == "secret recipe of tenant A"
