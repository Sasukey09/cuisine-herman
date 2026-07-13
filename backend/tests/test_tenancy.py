"""Cross-tenant reference guard.

Protects the write paths that accept a client-supplied ``product_id``: mapping
an invoice line, adding a recipe ingredient, validating an imported recipe.
"""
import pytest

from app.core.tenancy import (
    CrossTenantReferenceError,
    assert_product_in_tenant,
    assert_products_in_tenant,
    owned_product_ids,
)

TENANT_A = "aaaaaaaa-0000-0000-0000-000000000001"
TENANT_B = "bbbbbbbb-0000-0000-0000-000000000002"

A_PRODUCT = "11111111-1111-1111-1111-111111111111"
B_PRODUCT = "22222222-2222-2222-2222-222222222222"


class FakeQuery:
    """Just enough of the SQLAlchemy query chain used by the guard."""

    def __init__(self, rows):
        self._rows = rows
        self._tenant = None
        self._ids = set()

    def filter(self, *criteria):
        # The guard always filters on (tenant_id ==, id.in_()); we read the
        # bound values straight off the compiled criteria.
        for crit in criteria:
            right = getattr(crit, "right", None)
            value = getattr(right, "value", None)
            if value is not None and isinstance(value, str):
                self._tenant = value
            elif hasattr(crit, "right") and hasattr(crit.right, "element"):
                self._ids = {str(v) for v in crit.right.element.clauses} if crit.right.element else set()
        return self

    def all(self):
        return [(pid,) for tid, pid in self._rows if tid == self._tenant]


class FakeSession:
    def __init__(self, rows):
        self._rows = rows

    def query(self, *_cols):
        return FakeQuery(self._rows)


@pytest.fixture
def db():
    # Tenant A owns A_PRODUCT, tenant B owns B_PRODUCT.
    return FakeSession([(TENANT_A, A_PRODUCT), (TENANT_B, B_PRODUCT)])


def test_owned_products_are_accepted(db):
    assert_product_in_tenant(db, TENANT_A, A_PRODUCT)  # must not raise
    assert_products_in_tenant(db, TENANT_A, [A_PRODUCT])


def test_a_foreign_product_is_rejected(db):
    """Tenant A must not be able to reference tenant B's product."""
    with pytest.raises(CrossTenantReferenceError) as err:
        assert_product_in_tenant(db, TENANT_A, B_PRODUCT)
    assert err.value.kind == "product"
    assert B_PRODUCT in err.value.ids


def test_an_unknown_product_is_rejected(db):
    with pytest.raises(CrossTenantReferenceError):
        assert_product_in_tenant(db, TENANT_A, "99999999-9999-9999-9999-999999999999")


def test_a_batch_is_rejected_as_soon_as_one_id_is_foreign(db):
    """A recipe whose ingredients mix owned and foreign products is refused whole."""
    with pytest.raises(CrossTenantReferenceError):
        assert_products_in_tenant(db, TENANT_A, [A_PRODUCT, B_PRODUCT])


def test_empty_and_none_ids_are_a_no_op(db):
    assert_products_in_tenant(db, TENANT_A, [])
    assert_products_in_tenant(db, TENANT_A, [None, ""])
    assert_product_in_tenant(db, TENANT_A, None)


def test_owned_product_ids_only_returns_the_tenants_rows(db):
    assert owned_product_ids(db, TENANT_A, [A_PRODUCT, B_PRODUCT]) == {A_PRODUCT}
    assert owned_product_ids(db, TENANT_B, [A_PRODUCT, B_PRODUCT]) == {B_PRODUCT}
