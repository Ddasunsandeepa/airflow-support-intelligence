"""Source-based eligibility for reviewed, single-file Python task corrections.

Static checks never execute source and are not a Python sandbox. Human review is
mandatory; Airflow runs the approved code with its existing runtime permissions.
"""
import ast

from backend.app.source_review_validation import validate_review_structure

POLICY_VERSION = 2


def task_target(source, dag_id, target_function, failed_task_id=None):
    tree = ast.parse(source)
    dag_ids = []
    tasks = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        keywords = {k.arg: k.value for k in node.keywords}
        if 'dag_id' in keywords:
            value = keywords['dag_id']
            if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
                raise ValueError('Dynamic DAG identity requires manual source review.')
            dag_ids.append(value.value)
        task, callback = keywords.get('task_id'), keywords.get('python_callable')
        if isinstance(callback, ast.Name) and callback.id == target_function:
            if not isinstance(task, ast.Constant) or not isinstance(task.value, str):
                raise ValueError('The target task must have a static task_id.')
            tasks.append(task.value)
    if dag_ids != [dag_id]:
        raise ValueError('Source must declare exactly one matching static DAG identity.')
    if len(tasks) != 1 or (failed_task_id and tasks[0] != failed_task_id):
        raise ValueError('Cannot uniquely map the failed task to the proposed local Python callable.')
    return tasks[0]


def validate_execution_structure(before, proposed, dag_id, target_function, failed_task_id=None):
    validate_review_structure(before, proposed, dag_id, target_function)
    task_id = task_target(before, dag_id, target_function, failed_task_id)
    old, new = [next(n for n in ast.parse(s).body
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == target_function)
                for s in (before, proposed)]
    # Prevent removal/rewriting of literal input datasets to hide a failure.
    def fixtures(function):
        return [ast.dump(n) for n in function.body if isinstance(n, ast.Assign)
                and isinstance(n.value, (ast.List, ast.Dict, ast.Tuple))
                and all(not isinstance(v, (ast.Call, ast.Name)) for v in ast.walk(n.value))]
    for fixture in fixtures(old):
        if fixture not in fixtures(new):
            raise ValueError('Preserve original literal input fixtures; correct their handling instead.')
    dangerous = {'eval', 'exec', 'compile', 'open', '__import__', 'globals', 'locals',
                 'getattr', 'setattr', 'delattr', 'system', 'popen', 'unlink', 'remove',
                 'rmdir', 'rmtree', 'write_text', 'write_bytes'}
    old_calls = {ast.dump(n) for n in ast.walk(old) if isinstance(n, ast.Call)}
    for node in ast.walk(new):
        if isinstance(node, (ast.Import, ast.ImportFrom, ast.Global, ast.Nonlocal)):
            raise ValueError('Imports and global/nonlocal mutations inside the edited function require manual review.')
        if isinstance(node, ast.Attribute) and node.attr.startswith('__'):
            raise ValueError('Dunder attribute access is not permitted in reviewed corrections.')
        if isinstance(node, ast.Name) and node.id.startswith('__'):
            raise ValueError('Dunder names are not permitted in reviewed corrections.')
        if isinstance(node, ast.Call):
            name = node.func.id if isinstance(node.func, ast.Name) else node.func.attr if isinstance(node.func, ast.Attribute) else None
            if name in dangerous and ast.dump(node) not in old_calls:
                raise ValueError('New dynamic-code or filesystem/process operations require manual review.')
    return task_id


def check_record_policy(record):
    if record.execution_policy_version != POLICY_VERSION:
        raise ValueError('This review predates the current execution policy. Start a new investigation and approval.')
    evidence = record.evidence.get('airflow_evidence', record.evidence)
    try:
        return validate_execution_structure(
            record.change.source_code.before_code, record.change.source_code.proposed_code,
            record.dag_id, record.target_function, evidence.get('failed_task_id'),
        )
    except SyntaxError as exc:
        raise ValueError(f'Invalid Python source: {exc}') from exc
