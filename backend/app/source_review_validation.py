"""General read/review validation, independent of permission to apply source."""
import ast

from backend.app import source_resolver


def resolve_review_source(dag_id):
    if not isinstance(dag_id, str) or dag_id != dag_id.strip():
        raise ValueError("Use the exact DAG identity without surrounding whitespace.")
    path = source_resolver.resolve_dag_source(dag_id)
    if path is None:
        raise ValueError("DAG source cannot be safely resolved under the configured root.")
    # Inspect the unresolved candidate as well, so resolving cannot hide a link.
    candidate = source_resolver.DAG_SOURCE_ROOT.absolute() / f"{dag_id}.py"
    for part in (candidate, *candidate.parents):
        if part.is_symlink() or (hasattr(part, "is_junction") and part.is_junction()):
            raise ValueError("Symlink/junction source targets are not permitted.")
    return path


def source_context(source, task_id):
    tree = ast.parse(source)
    functions = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
    mapped = None
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        args = {k.arg: k.value for k in node.keywords}
        task = args.get("task_id")
        callback = args.get("python_callable")
        if isinstance(task, ast.Constant) and task.value == task_id and isinstance(callback, ast.Name):
            mapped = callback.id
    if mapped is None and task_id in {n.name for n in functions}:
        mapped = task_id
    return {"mapped_target_function": mapped, "functions": [
        {"name": node.name, "line": node.lineno, "source": ast.get_source_segment(source, node)} for node in functions
    ]}


def validate_review_structure(before, proposed, dag_id, target_function):
    trees = [ast.parse(s) for s in (before, proposed)]
    compile(trees[1], "<untrusted-source-review>", "exec")
    found = []
    for tree in trees:
        matches = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == target_function]
        if len(matches) != 1:
            raise ValueError("Expected exactly one existing top-level target function.")
        node = matches[0]
        found.append(node)
        tree.body[tree.body.index(node)] = ast.Pass()
    if ast.dump(trees[0]) != ast.dump(trees[1]):
        raise ValueError("Preserve DAG identity, imports, task declarations and all code outside the target function.")
    original, replacement = found
    if type(original) is not type(replacement) or ast.dump(original.args) != ast.dump(replacement.args):
        raise ValueError("Preserve the target function signature.")
    if ast.dump(original.returns or ast.Constant(None)) != ast.dump(replacement.returns or ast.Constant(None)):
        raise ValueError("Preserve the return annotation.")
    if [ast.dump(n) for n in original.decorator_list] != [ast.dump(n) for n in replacement.decorator_list]:
        raise ValueError("Preserve decorators.")
    if ast.dump(ast.Module(body=[original], type_ignores=[])) == ast.dump(ast.Module(body=[replacement], type_ignores=[])):
        raise ValueError("The proposal must contain an actual code change.")
    # General proposals may be reviewed but never executed during validation.
    # Execution policy independently checks task mapping and change constraints.
