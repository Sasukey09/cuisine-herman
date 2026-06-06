import pytest
from fastapi import HTTPException

from app.api.deps import require_roles


def test_writer_allows_manager():
    checker = require_roles("admin", "manager")
    assert checker(roles=["manager"]) == ["manager"]


def test_writer_allows_admin():
    checker = require_roles("admin", "manager")
    assert checker(roles=["admin", "viewer"]) == ["admin", "viewer"]


def test_writer_rejects_viewer():
    checker = require_roles("admin", "manager")
    with pytest.raises(HTTPException) as exc:
        checker(roles=["viewer"])
    assert exc.value.status_code == 403


def test_writer_rejects_no_roles():
    checker = require_roles("admin", "manager")
    with pytest.raises(HTTPException) as exc:
        checker(roles=[])
    assert exc.value.status_code == 403
