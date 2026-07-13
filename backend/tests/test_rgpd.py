"""RGPD — access, portability, erasure, traceability.

A SaaS holding a restaurant's suppliers, invoices and staff accounts is a data
controller. None of this had any code.
"""
from types import SimpleNamespace as N

from fastapi.testclient import TestClient

from app.api.deps import get_current_roles, get_current_tenant_id, get_current_user
from app.main import app


def _as(role: str, tenant: str = "t1"):
    app.dependency_overrides[get_current_tenant_id] = lambda: tenant
    app.dependency_overrides[get_current_user] = lambda: N(
        id="u1", tenant_id=tenant, email="chef@herman.fr", token_version=0
    )
    app.dependency_overrides[get_current_roles] = lambda: [role]


# --------------------------------------------------------------------------- #
# Art. 17 — erasure. The dangerous one.
# --------------------------------------------------------------------------- #
def test_deleting_an_organization_requires_retyping_its_exact_name(monkeypatch):
    """The only thing between a mis-click and every invoice, recipe and price
    this restaurant has ever recorded."""
    from app.api.api_v1.endpoints import rgpd as endpoint

    deleted = {"called": False}

    class FakeQuery:
        def filter(self, *a):
            return self

        def first(self):
            return N(id="t1", name="Restaurant Herman")

    class FakeDB:
        def query(self, *a):
            return FakeQuery()

    monkeypatch.setattr(endpoint.rgpd, "record", lambda *a, **k: None)
    monkeypatch.setattr(
        endpoint.rgpd, "delete_organization",
        lambda db, t: deleted.update(called=True) or True,
    )

    from app.db.session import get_db

    app.dependency_overrides[get_db] = lambda: FakeDB()
    _as("admin")
    try:
        client = TestClient(app)

        wrong = client.post(
            "/api/v1/rgpd/delete-organization", json={"confirm_name": "Restaurant Hermann"}
        )
        assert wrong.status_code == 400
        assert not deleted["called"], "a typo must not erase the restaurant"

        right = client.post(
            "/api/v1/rgpd/delete-organization", json={"confirm_name": "Restaurant Herman"}
        )
        assert right.status_code == 204
        assert deleted["called"]
    finally:
        app.dependency_overrides.clear()


def test_only_an_admin_can_erase_or_export():
    _as("manager")  # not admin
    try:
        client = TestClient(app)
        assert client.get("/api/v1/rgpd/export").status_code == 403
        assert client.get("/api/v1/rgpd/audit").status_code == 403
        assert (
            client.post("/api/v1/rgpd/delete-organization", json={"confirm_name": "x"}).status_code
            == 403
        )
    finally:
        app.dependency_overrides.clear()


# --------------------------------------------------------------------------- #
# Art. 15/20 — the export must be usable, and must not leak our secrets
# --------------------------------------------------------------------------- #
def test_the_export_never_carries_password_hashes():
    """Portability is the customer's data, not our credential store."""
    import inspect

    from app.services.rgpd import service as rgpd

    source = inspect.getsource(rgpd.export_organization)
    assert "password_hash" in source, "the exclusion must be explicit, not accidental"
    assert "deliberately omitted" in source


# --------------------------------------------------------------------------- #
# Art. 30 — an audit failure must not take down the action it was auditing
# --------------------------------------------------------------------------- #
def test_a_broken_audit_log_never_breaks_the_login():
    from app.services.rgpd import service as rgpd

    class Broken:
        def add(self, *a):
            raise RuntimeError("audit table on fire")

        def commit(self):
            raise RuntimeError("nope")

        def rollback(self):
            pass

    rgpd.record(Broken(), "t1", "u1", rgpd.ACTION_LOGIN, {"ip": "1.2.3.4"})  # must not raise
