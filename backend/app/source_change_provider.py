import ast
import logging
from dataclasses import dataclass

from backend.app.source_resolver import get_relative_dag_path, read_dag_source
from backend.app.source_patch_generator import generate_source_patch


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ControlledSourceChange:
    target: str
    file_path: str
    language: str
    before_code: str
    proposed_code: str
    summary: str
    reason: str
    generated_by: str = "controlled_fallback"


def _replace_function_source(source_code: str, function_name: str, proposed_function: str) -> str:
    """Validate and replace exactly one top-level function in memory, never execute."""
    tree = ast.parse(source_code)
    replacement_tree = ast.parse(proposed_function.strip())
    targets = [node for node in tree.body
               if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
               and node.name == function_name]
    if len(targets) != 1 or len(replacement_tree.body) != 1:
        raise ValueError("Expected one target and one replacement function.")
    target = targets[0]
    replacement = replacement_tree.body[0]
    if type(replacement) is not type(target) or replacement.name != function_name:
        raise ValueError("Replacement must match the expected function.")
    if replacement.decorator_list:
        raise ValueError("Replacement cannot introduce decorators.")
    if ast.dump(target.args) != ast.dump(replacement.args):
        raise ValueError("Replacement must preserve the function signature.")

    # Preserve imports, existing decorators, DAG/task declarations and every
    # character outside the function body. Match the source newline convention.
    lines = source_code.splitlines(keepends=True)
    newline = "\r\n" if "\r\n" in source_code else "\n"
    replacement_text = proposed_function.strip().replace("\r\n", "\n").replace("\n", newline)
    if lines[target.end_lineno - 1].endswith(("\n", "\r")):
        replacement_text += newline
    proposed = ("".join(lines[:target.lineno - 1]) + replacement_text
                + "".join(lines[target.end_lineno:]))
    ast.parse(proposed)
    # Compile for syntax validation (e.g. invalid break/continue), never execute.
    compile(proposed, "<review-only-proposal>", "exec")
    return proposed


def get_controlled_source_change(
    dag_id: str,
    incident_class: str | None = None,
    failure_message: str | None = None,
) -> ControlledSourceChange | None:
    """Compose actual source + deterministic suggestion. Failure is advisory only."""
    try:
        suggestion = generate_source_patch(
            dag_id=dag_id, incident_class=incident_class, failure_message=failure_message,
        )
        if suggestion is None:
            return None
        before_code = read_dag_source(dag_id)
        file_path = get_relative_dag_path(dag_id)
        if before_code is None or file_path is None:
            return None
        proposed_code = _replace_function_source(
            before_code, suggestion.function_name, suggestion.proposed_function,
        )
        if proposed_code == before_code:
            return None
        return ControlledSourceChange(
            target=dag_id, file_path=file_path, language="python",
            before_code=before_code, proposed_code=proposed_code,
            summary=suggestion.summary, reason=suggestion.reason,
            generated_by=suggestion.generated_by,
        )
    except (SyntaxError, ValueError, TypeError, AttributeError, OSError):
        logger.warning("No reviewed source proposal available: source or suggestion could not be validated.")
        return None
