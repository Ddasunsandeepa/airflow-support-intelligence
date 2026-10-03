import difflib
import json
from typing import Any

from backend.app.action_models import ActionRequest
from backend.app.change_models import (
    ChangeEntry,
    ChangeProposal,
    ChangeType,
    SourceCodeChange,
)


def _normalise_configuration(
    parameters: dict[str, Any],
) -> dict[str, Any]:
    """
    Convert remediation parameters into the effective runtime
    configuration that will be sent to Airflow.

    For trigger_dag actions, configuration may either be supplied
    explicitly under `conf` or through the currently allowlisted
    `mode` parameter.
    """

    conf = parameters.get("conf")

    if isinstance(conf, dict):
        return dict(conf)

    configuration = {}

    if "mode" in parameters:
        configuration["mode"] = parameters["mode"]

    return configuration


def _build_entries(
    before: dict[str, Any],
    after: dict[str, Any],
) -> list[ChangeEntry]:
    """
    Build structured before/after entries for every changed field.
    """

    entries = []

    keys = sorted(set(before) | set(after))

    for key in keys:
        before_value = before.get(key)
        after_value = after.get(key)

        if before_value == after_value:
            continue

        entries.append(
            ChangeEntry(
                path=key,
                before=before_value,
                after=after_value,
            )
        )

    return entries


def _build_unified_diff(
    before: dict[str, Any],
    after: dict[str, Any],
) -> tuple[str, int, int]:
    """
    Produce a Git-style unified diff for human review.
    """

    before_text = json.dumps(
        before,
        indent=2,
        sort_keys=True,
    ).splitlines()

    after_text = json.dumps(
        after,
        indent=2,
        sort_keys=True,
    ).splitlines()

    diff_lines = list(
        difflib.unified_diff(
            before_text,
            after_text,
            fromfile="before",
            tofile="proposed",
            lineterm="",
        )
    )

    additions = sum(
        1
        for line in diff_lines
        if line.startswith("+")
        and not line.startswith("+++")
    )

    deletions = sum(
        1
        for line in diff_lines
        if line.startswith("-")
        and not line.startswith("---")
    )

    return (
        "\n".join(diff_lines),
        additions,
        deletions,
    )


def build_runtime_change_proposal(
    action: ActionRequest,
    previous_configuration: dict[str, Any] | None = None,
) -> ChangeProposal:
    """
    Build a reviewable runtime-configuration change proposal.

    No Airflow operation is executed here.
    """

    before = dict(previous_configuration or {})

    after = _normalise_configuration(
        action.parameters
    )

    changes = _build_entries(
        before=before,
        after=after,
    )

    unified_diff, additions, deletions = (
        _build_unified_diff(
            before=before,
            after=after,
        )
    )

    return ChangeProposal(
        change_type=ChangeType.RUNTIME_CONFIGURATION,
        target=action.dag_id,
        title="Airflow Runtime Configuration Change",
        description=action.reason,
        before=before,
        after=after,
        changes=changes,
        unified_diff=unified_diff,
        additions=additions,
        deletions=deletions,
    )

def build_source_code_change_proposal(
    target: str,
    file_path: str,
    before_code: str,
    proposed_code: str,
    description: str,
    language: str = "python",
    generated_by: str | None = None,
) -> ChangeProposal:
    """
    Build a reviewable source-code change proposal.

    This function does NOT modify the source file.
    It only compares the current code with the proposed code
    and creates a human-reviewable diff.
    """

    before_lines = before_code.splitlines()
    proposed_lines = proposed_code.splitlines()

    diff_lines = list(
        difflib.unified_diff(
            before_lines,
            proposed_lines,
            fromfile=file_path,
            tofile=f"{file_path} (proposed)",
            lineterm="",
        )
    )

    additions = sum(
        1
        for line in diff_lines
        if line.startswith("+") and not line.startswith("+++")
    )

    deletions = sum(
        1
        for line in diff_lines
        if line.startswith("-") and not line.startswith("---")
    )

    return ChangeProposal(
        change_type=ChangeType.SOURCE_CODE,
        target=target,
        title="Source Code Change Proposal",
        description=description,
        source_code=SourceCodeChange(
            file_path=file_path,
            language=language,
            before_code=before_code,
            proposed_code=proposed_code,
            generated_by=generated_by,
        ),
        unified_diff="\n".join(diff_lines),
        additions=additions,
        deletions=deletions,
    )
