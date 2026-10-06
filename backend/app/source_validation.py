"""Legacy synthetic fixtures for opt-in fallback/reset tests, not execution policy.

Production review/apply eligibility lives in source_execution_policy.py.
AST validation here never imports or executes a DAG.
"""
import ast
import hashlib
from pathlib import Path

from backend.app import source_resolver

DEMO_DAG_ID = "support_intelligence_code_remediation_demo"
TARGET_FUNCTION = "summarize_transactions"
BASELINE = Path(__file__).resolve().parents[2] / "demo_dags" / f"{DEMO_DAG_ID}.py"
CUSTOMER_DAG_ID = "support_intelligence_customer_discount_remediation_demo"
# Finite policy registry, never derived from a user path or arbitrary DAG source.
DEMO_POLICIES = {
    DEMO_DAG_ID: {"function": TARGET_FUNCTION, "fixture": "records", "task": TARGET_FUNCTION},
    CUSTOMER_DAG_ID: {"function": "calculate_customer_discounts", "fixture": "customers", "task": "calculate_customer_discounts"},
}


def get_demo_policy(dag_id: str) -> dict:
    if dag_id not in DEMO_POLICIES:
        raise ValueError("Source application is allowlisted only for explicitly supported synthetic demos.")
    return DEMO_POLICIES[dag_id]


def demo_baseline(dag_id: str) -> Path:
    get_demo_policy(dag_id)
    return BASELINE.parent / f"{dag_id}.py"


def source_hash(source: str) -> str:
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def resolve_writable_demo(dag_id: str, *, must_exist: bool = True) -> Path:
    get_demo_policy(dag_id)
    root = source_resolver.DAG_SOURCE_ROOT.absolute()
    # Reject symlinks/junctions along the configured path as well as the file.
    candidate = root / f"{dag_id}.py"
    for part in (candidate, *candidate.parents):
        if part.is_symlink() or (hasattr(part, "is_junction") and part.is_junction()):
            raise ValueError("Symlink/junction targets are not permitted for source application.")
    candidate.resolve().relative_to(root.resolve())
    if must_exist and not candidate.is_file():
        raise ValueError("Demo source does not exist; install the intentional demo baseline first.")
    return candidate


def validate_structure(before: str, proposed: str, dag_id: str = DEMO_DAG_ID) -> None:
    """Only the body of the known demo function may change; keep the input fixture.

    This is a conservative allowlist for a local PoC, not a Python sandbox.
    Human review is still required. All other DAG declarations match the baseline.
    """
    policy = get_demo_policy(dag_id)
    trees = [ast.parse(text) for text in (demo_baseline(dag_id).read_text(encoding="utf-8"), before, proposed)]
    compile(trees[-1], "<reviewed-demo>", "exec")
    functions = []
    for tree in trees:
        matches = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == policy["function"]]
        if len(matches) != 1:
            raise ValueError(f"Expected exactly one {policy['function']} function.")
        function = matches[0]
        functions.append(function)
        tree.body[tree.body.index(function)] = ast.Pass()
    if not ast.dump(trees[0]) == ast.dump(trees[1]) == ast.dump(trees[2]):
        raise ValueError("Only the demo function body may change; preserve imports, DAG ID and task declarations.")
    baseline, original, candidate = functions
    for function in (original, candidate):
        if (ast.dump(function.args) != ast.dump(baseline.args)
                or function.decorator_list or function.returns):
            raise ValueError("Preserve the target function signature.")
        # Preserve the leading docstring (if any) and literal input assignment.
        fixture_index = next(i for i, n in enumerate(baseline.body) if isinstance(n, ast.Assign)
                             and any(isinstance(t, ast.Name) and t.id == policy["fixture"] for t in n.targets))
        if [ast.dump(n) for n in function.body[:fixture_index + 1]] != [ast.dump(n) for n in baseline.body[:fixture_index + 1]]:
            raise ValueError("Preserve the original input fixture and leading declarations.")
    allowed_nodes = (ast.FunctionDef, ast.arguments, ast.Assign, ast.Name, ast.Store, ast.Load,
                     ast.List, ast.Tuple, ast.Dict, ast.Constant, ast.Call, ast.Subscript,
                     ast.GeneratorExp, ast.ListComp, ast.comprehension, ast.Expr, ast.JoinedStr,
                     ast.FormattedValue, ast.Return, ast.If, ast.Raise, ast.UnaryOp, ast.Not,
                     ast.Compare, ast.IsNot, ast.Is, ast.Eq, ast.NotEq, ast.BoolOp, ast.And,
                     ast.Or, ast.Attribute, ast.For, ast.AugAssign, ast.Add, ast.BinOp,
                     ast.IfExp, ast.USub)
    builtins = {"sum", "isinstance", "int", "float", "ValueError", "print", "len"}
    methods = {"get", "append"}
    if dag_id == CUSTOMER_DAG_ID:
        # Only this policy supports string normalization and discount arithmetic.
        allowed_nodes += (ast.Mult, ast.Sub)
        builtins |= {"str"}
        methods |= {"lower", "strip"}
    for node in ast.walk(candidate):
        if not isinstance(node, allowed_nodes):
            raise ValueError(f"Unsupported construct in controlled demo: {type(node).__name__}.")
        if isinstance(node, ast.Name) and node.id.startswith("__"):
            raise ValueError("Dunder names are not allowed.")
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store) and node.id in builtins:
            raise ValueError("Rebinding allowlisted builtins is not permitted.")
        if isinstance(node, ast.Attribute) and node.attr not in methods:
            raise ValueError("Only data get/append attributes are allowed.")
        if isinstance(node, ast.Call) and not (
            isinstance(node.func, ast.Name) and node.func.id in builtins
            or isinstance(node.func, ast.Attribute) and node.func.attr in methods
        ):
            raise ValueError("Only allowlisted data-processing calls are permitted.")
    if source_hash(before) == source_hash(proposed):
        raise ValueError("There is no source change to review.")
