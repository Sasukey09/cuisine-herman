"""Safe arithmetic formula evaluator (no-code custom metrics).

User-defined formulas must NEVER be run through ``eval()``. This module parses an
expression with ``ast`` and walks a strict whitelist of node types, so the only
things a formula can do are:

  - reference variables provided in the context dict (e.g. cost_per_portion)
  - numeric literals
  - + - * / // % ** (exponent magnitude capped to avoid DoS)
  - unary +/- and ``not``
  - comparisons (< <= > >= == !=) and and/or
  - ternary  ``a if cond else b``
  - calls to a small whitelist of functions: min, max, round, abs

No attribute access, no subscripts, no arbitrary calls, no names outside the
context, no strings/containers. Unknown names or disallowed syntax raise
``FormulaError``. ``None`` operands propagate to ``None`` (a missing variable
yields no result rather than crashing).
"""
import ast
import operator
from typing import Any, Dict, Iterable, List, Optional, Tuple

_MAX_POW = 8  # cap exponent magnitude to prevent CPU/memory blowups


class FormulaError(Exception):
    pass


_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY_OPS = {ast.UAdd: operator.pos, ast.USub: operator.neg, ast.Not: operator.not_}
_CMP_OPS = {
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
}
_FUNCS = {"min": min, "max": max, "round": round, "abs": abs}


def _parse(expression: str) -> ast.Expression:
    if not expression or not expression.strip():
        raise FormulaError("Formule vide")
    try:
        return ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise FormulaError(f"Syntaxe invalide : {exc.msg}") from exc


def collect_names(expression: str) -> List[str]:
    """Variable names referenced by the expression (excludes function names)."""
    tree = _parse(expression)
    names: set = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            # a Name used as a call target is a function, not a variable
            names.add(node.id)
    # remove whitelisted function names
    return sorted(n for n in names if n not in _FUNCS)


def validate(expression: str, allowed_names: Iterable[str]) -> Tuple[bool, Optional[str]]:
    """Structurally validate a formula. Returns (ok, error_message)."""
    allowed = set(allowed_names)
    try:
        tree = _parse(expression)
    except FormulaError as exc:
        return False, str(exc)

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in _FUNCS:
                return False, "Seules les fonctions min, max, round, abs sont autorisées"
            if node.keywords:
                return False, "Arguments nommés non autorisés"
        elif isinstance(node, ast.Name):
            if node.id not in allowed and node.id not in _FUNCS:
                return False, f"Variable inconnue : {node.id}"
        elif isinstance(
            node,
            (
                ast.Attribute,
                ast.Subscript,
                ast.Lambda,
                ast.comprehension,
                ast.ListComp,
                ast.DictComp,
                ast.SetComp,
                ast.GeneratorExp,
                ast.Starred,
                ast.Dict,
                ast.List,
                ast.Set,
                ast.Tuple,
                ast.JoinedStr,
            ),
        ):
            return False, "Élément non autorisé dans une formule"
        elif isinstance(node, ast.Constant) and not isinstance(node.value, (int, float, bool)):
            return False, "Seules les valeurs numériques sont autorisées"
    return True, None


def _eval(node: ast.AST, ctx: Dict[str, Any]) -> Any:
    if isinstance(node, ast.Expression):
        return _eval(node.body, ctx)

    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float, bool)):
            return node.value
        raise FormulaError("Valeur non numérique")

    if isinstance(node, ast.Name):
        if node.id not in ctx:
            raise FormulaError(f"Variable inconnue : {node.id}")
        return ctx[node.id]

    if isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in _BIN_OPS:
            raise FormulaError("Opérateur non autorisé")
        left, right = _eval(node.left, ctx), _eval(node.right, ctx)
        if left is None or right is None:
            return None
        if op_type is ast.Pow and (abs(right) > _MAX_POW):
            raise FormulaError(f"Exposant trop grand (max {_MAX_POW})")
        try:
            return _BIN_OPS[op_type](left, right)
        except ZeroDivisionError:
            return None

    if isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in _UNARY_OPS:
            raise FormulaError("Opérateur unaire non autorisé")
        val = _eval(node.operand, ctx)
        if val is None:
            return None
        return _UNARY_OPS[op_type](val)

    if isinstance(node, ast.BoolOp):
        is_and = isinstance(node.op, ast.And)
        result = is_and  # and -> start True, or -> start False
        for value_node in node.values:
            v = bool(_eval(value_node, ctx))
            result = (result and v) if is_and else (result or v)
        return result

    if isinstance(node, ast.Compare):
        left = _eval(node.left, ctx)
        for op, comparator in zip(node.ops, node.comparators):
            right = _eval(comparator, ctx)
            op_type = type(op)
            if op_type not in _CMP_OPS:
                raise FormulaError("Comparateur non autorisé")
            if left is None or right is None:
                return None
            if not _CMP_OPS[op_type](left, right):
                return False
            left = right
        return True

    if isinstance(node, ast.IfExp):
        test = _eval(node.test, ctx)
        return _eval(node.body, ctx) if test else _eval(node.orelse, ctx)

    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in _FUNCS:
            raise FormulaError("Fonction non autorisée")
        if node.keywords:
            raise FormulaError("Arguments nommés non autorisés")
        args = [_eval(a, ctx) for a in node.args]
        if any(a is None for a in args):
            return None
        try:
            return _FUNCS[node.func.id](*args)
        except (TypeError, ValueError) as exc:
            raise FormulaError(f"Appel invalide : {exc}") from exc

    raise FormulaError("Élément non autorisé dans une formule")


def evaluate(expression: str, variables: Dict[str, Any]) -> Any:
    """Evaluate ``expression`` against ``variables``. Raises FormulaError."""
    tree = _parse(expression)
    return _eval(tree, variables)
