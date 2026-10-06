"""Compose a model-proposed function into source in memory; never write or execute."""
import ast


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
