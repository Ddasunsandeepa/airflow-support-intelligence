import ast
from dataclasses import dataclass
from typing import Optional

from backend.app.source_resolver import (
    get_relative_dag_path,
    read_dag_source,
)

from backend.app.source_patch_generator import generate_source_patch


@dataclass(frozen=True)
class ControlledSourceChange:
    target: str
    file_path: str
    language: str
    before_code: str
    proposed_code: str
    summary: str
    reason: str


def _load_current_source(
    dag_id: str,
) -> tuple[str, str] | None:
    """
    Load the actual current DAG source from the configured
    read-only Airflow DAG directory.

    Returns:
        (display_path, source_code)

    No file is modified or executed.
    """

    source_code = read_dag_source(dag_id)
    file_path = get_relative_dag_path(dag_id)

    if source_code is None or file_path is None:
        return None

    return file_path, source_code

def _replace_function_source(
    source_code: str,
    function_name: str,
    proposed_function: str,
) -> str:
    """
    Replace one top-level Python function inside the current source.

    The source is parsed with Python's AST only to locate the function.
    Nothing is executed and no file is written.
    """

    try:
        tree = ast.parse(source_code)
    except SyntaxError as exc:
        raise RuntimeError(
            "Current DAG source could not be parsed safely."
        ) from exc

    target_node = None

    for node in tree.body:
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == function_name
        ):
            target_node = node
            break

    if target_node is None:
        raise RuntimeError(
            f"Function '{function_name}' was not found in the DAG source."
        )

    source_lines = source_code.splitlines(keepends=True)

    start_index = target_node.lineno - 1
    end_index = target_node.end_lineno

    replacement = proposed_function.strip() + "\n\n"

    return (
        "".join(source_lines[:start_index])
        + replacement
        + "".join(source_lines[end_index:])
    )


def _supervisor_demo_change() -> ControlledSourceChange:
    before_code = '''def supervisor_demo_incident(**context):
    dag_run = context.get("dag_run")
    mode = "failure"

    if dag_run and dag_run.conf:
        mode = dag_run.conf.get("mode", "failure")

    if mode == "recovery":
        print("SUPERVISOR DEMO RECOVERY: Synthetic incident recovery completed successfully.")
        return "recovered"

    synthetic_pod_status = "CrashLoopBackOff"
    synthetic_restart_count = 5
    synthetic_exit_code = 137

    print("SUPERVISOR DEMO INCIDENT: Controlled synthetic Kubernetes failure.")

    raise RuntimeError(
        "Synthetic supervisor demo failure detected: "
        f"PodStatus={synthetic_pod_status}, "
        f"RestartCount={synthetic_restart_count}, "
        f"ExitCode={synthetic_exit_code}"
    )'''

    proposed_code = '''def supervisor_demo_incident(**context):
    dag_run = context.get("dag_run")
    mode = "failure"

    if dag_run and dag_run.conf:
        mode = dag_run.conf.get("mode", "failure")

    synthetic_pod_status = "Healthy"
    synthetic_restart_count = 0
    synthetic_exit_code = 0

    if mode == "recovery":
        print("SUPERVISOR DEMO RECOVERY: Synthetic incident recovery completed successfully.")
        return "recovered"

    if synthetic_pod_status != "Healthy":
        raise RuntimeError(
            "Synthetic supervisor demo failure detected: "
            f"PodStatus={synthetic_pod_status}, "
            f"RestartCount={synthetic_restart_count}, "
            f"ExitCode={synthetic_exit_code}"
        )

    return "healthy"'''

    return ControlledSourceChange(
        target="support_intelligence_supervisor_demo",
        file_path="dags/support_intelligence_supervisor_demo.py",
        language="python",
        before_code=before_code,
        proposed_code=proposed_code,
        summary=(
            "Propose a reviewed source-level recovery change for the "
            "controlled supervisor demonstration DAG."
        ),
        reason=(
            "The proposal demonstrates how an engineer can inspect the "
            "current source, proposed source, and exact patch before "
            "deciding whether to accept the change."
        ),
    )


def _kubernetes_resource_demo_change() -> ControlledSourceChange:
    before_code = '''def kubernetes_resource_demo(**context):
    dag_run = context.get("dag_run")
    mode = "failure"

    if dag_run and dag_run.conf:
        mode = dag_run.conf.get("mode", "failure")

    if mode == "recovery":
        print(
            "SUPPORT_INTELLIGENCE_K8S: "
            "PodStatus=Running "
            "RestartCount=0 "
            "ExitCode=0"
        )

        print(
            "KUBERNETES RESOURCE DEMO RECOVERY: "
            "Synthetic workload recovered successfully."
        )

        return "recovered"

    synthetic_pod_status = "CrashLoopBackOff"
    synthetic_restart_count = 5
    synthetic_exit_code = 137

    print(
        "SUPPORT_INTELLIGENCE_K8S: "
        f"PodStatus={synthetic_pod_status} "
        f"RestartCount={synthetic_restart_count} "
        f"ExitCode={synthetic_exit_code}"
    )

    print(
        "KUBERNETES RESOURCE DEMO INCIDENT: "
        "Controlled synthetic Kubernetes resource failure."
    )

    raise RuntimeError(
        "Synthetic Kubernetes resource failure detected: "
        f"PodStatus={synthetic_pod_status}, "
        f"RestartCount={synthetic_restart_count}, "
        f"ExitCode={synthetic_exit_code}"
    )'''

    proposed_code = '''def kubernetes_resource_demo(**context):
    dag_run = context.get("dag_run")
    mode = "failure"

    if dag_run and dag_run.conf:
        mode = dag_run.conf.get("mode", "failure")

    synthetic_pod_status = "Running"
    synthetic_restart_count = 0
    synthetic_exit_code = 0

    if mode == "recovery":
        print(
            "SUPPORT_INTELLIGENCE_K8S: "
            f"PodStatus={synthetic_pod_status} "
            f"RestartCount={synthetic_restart_count} "
            f"ExitCode={synthetic_exit_code}"
        )

        print(
            "KUBERNETES RESOURCE DEMO RECOVERY: "
            "Synthetic workload recovered successfully."
        )

        return "recovered"

    if synthetic_pod_status != "Running":
        raise RuntimeError(
            "Synthetic Kubernetes resource failure detected: "
            f"PodStatus={synthetic_pod_status}, "
            f"RestartCount={synthetic_restart_count}, "
            f"ExitCode={synthetic_exit_code}"
        )

    print(
        "KUBERNETES RESOURCE DEMO HEALTHY: "
        "Synthetic Kubernetes workload is healthy."
    )

    return "healthy"'''

    return ControlledSourceChange(
        target="support_intelligence_kubernetes_resource_demo",
        file_path="dags/support_intelligence_kubernetes_resource_demo.py",
        language="python",
        before_code=before_code,
        proposed_code=proposed_code,
        summary=(
            "Propose a reviewed source-level recovery change for the "
            "controlled Kubernetes resource demonstration DAG."
        ),
        reason=(
            "The observed synthetic Kubernetes evidence shows "
            "CrashLoopBackOff, repeated restarts, and exit code 137. "
            "This controlled proposal demonstrates the source changes "
            "that would move the synthetic workload representation "
            "to a healthy state. The proposal is review-only and does "
            "not modify or deploy the DAG automatically."
        ),
    )


def _configuration_review_demo_change() -> ControlledSourceChange:
    dag_id = "support_intelligence_configuration_review_demo"

    current_source = _load_current_source(dag_id)

    if current_source is None:
        raise RuntimeError(
            f"Could not load current DAG source for {dag_id}."
        )

    file_path, before_code = current_source

    suggestion = generate_source_patch(
        dag_id=dag_id,
        incident_class="Configuration",
        failure_message=(
            "Synthetic configuration failure detected: "
            "required service endpoint is missing and "
            "timeout configuration is invalid."
        ),
    )

    if suggestion is None:
        raise RuntimeError(
            f"No safe source patch suggestion is available for {dag_id}."
        )

    proposed_code = _replace_function_source(
        source_code=before_code,
        function_name=suggestion.function_name,
        proposed_function=suggestion.proposed_function,
    )

    return ControlledSourceChange(
        target=dag_id,
        file_path=file_path,
        language="python",
        before_code=before_code,
        proposed_code=proposed_code,
        summary=suggestion.summary,
        reason=suggestion.reason,
    )

def get_controlled_source_change(
    dag_id: str,
) -> Optional[ControlledSourceChange]:
    """
    Return a controlled, review-only source change proposal.

    Only explicitly allowlisted demo changes are returned.

    The Configuration demo now reads its current source dynamically
    from the configured read-only Airflow DAG directory.
    """

    providers = {
        "support_intelligence_supervisor_demo":
            _supervisor_demo_change,

        "support_intelligence_kubernetes_resource_demo":
            _kubernetes_resource_demo_change,

        "support_intelligence_configuration_review_demo":
            _configuration_review_demo_change,
    }

    provider = providers.get(dag_id)

    if provider is None:
        return None

    return provider()