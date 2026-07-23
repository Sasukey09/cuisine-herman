"""Toute référence `Modele.attribut` dans le code doit exister.

Ce garde-fou existe parce que le renommage `qty_received` → `qty_delivered` a
laissé trois appelants derrière lui. Aucun ne s'est vu en local : ils vivaient
dans des chemins couverts uniquement par les tests `real_db`, ignorés hors CI.
Deux cycles de CI pour trouver une faute de frappe.

Python ne vérifie pas les attributs à l'écriture, et SQLAlchemy ne se plaint
qu'à l'exécution de la requête. Cette analyse statique rend l'erreur immédiate,
sans base de données.
"""

import ast
import pathlib

import pytest

from app.models import models as models_module

ROOT = pathlib.Path(models_module.__file__).parent.parent.parent
# app/ ET tests/ : les trois appelants oubliés lors du renommage
# vivaient dans les tests, pas dans le code applicatif.
SCANNED = [ROOT / "app", ROOT / "tests"]


def _model_classes():
    from app.models.models import Base

    return {
        cls.__name__: cls
        for cls in Base.registry._class_registry.values()
        if hasattr(cls, "__tablename__")
    }


def _allowed_names(cls) -> set:
    """Colonnes, relations, et tout ce que la classe expose par ailleurs."""
    names = set(dir(cls))
    names.update(c.name for c in cls.__table__.columns)
    names.update(c.key for c in cls.__table__.columns)
    return names


@pytest.mark.parametrize(
    "path",
    sorted(
        p
        for root in SCANNED
        for p in root.rglob("*.py")
        if "__pycache__" not in str(p) and p.name != "models.py"
    ),
    ids=lambda p: str(p.relative_to(ROOT)),
)
def test_every_model_attribute_referenced_in_the_code_exists(path):
    classes = _model_classes()
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    problems = []
    for node in ast.walk(tree):
        # Modele.attribut
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            cls = classes.get(node.value.id)
            if cls is not None and node.attr not in _allowed_names(cls):
                problems.append(
                    f"{path.name}:{node.lineno} — {node.value.id}.{node.attr} n'existe pas"
                )
        # Modele(attribut=...)
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in classes
        ):
            cls = classes[node.func.id]
            allowed = _allowed_names(cls)
            for kw in node.keywords:
                if kw.arg and kw.arg not in allowed:
                    problems.append(
                        f"{path.name}:{node.lineno} — "
                        f"{node.func.id}({kw.arg}=…) n'est pas un champ du modèle"
                    )

    assert not problems, "\n".join(problems)
