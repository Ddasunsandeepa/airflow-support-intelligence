from backend.app.action_models import (
    ActionRequest,
    ActionStatus,
    ApprovalDecision,
    RemediationAction,
    RequiredRole,
)

from backend.app.action_validator import validate_action
from backend.app.actions.airflow import AirflowActionExecutor
from backend.app.verification import VerificationEngine


class ActionService:
    def __init__(
        self,
        airflow_executor: AirflowActionExecutor,
        verification_engine: VerificationEngine | None = None,
    ):
        self.airflow_executor = airflow_executor
        self.verification_engine = verification_engine or VerificationEngine()

    def create_action(
        self,
        action: ActionRequest,
        created_by: str,
        created_by_role: str = "L1",
    ) -> RemediationAction:
        resolved_role = created_by_role.strip().upper()

        try:
            role = RequiredRole(resolved_role)
        except ValueError as exc:
            raise ValueError(
                f"Unsupported user role: {created_by_role}"
            ) from exc

        return RemediationAction(
            request=action,
            created_by=created_by,
            created_by_role=role,
        )
        
    def edit(
        self,
        remediation: RemediationAction,
        parameters: dict,
        reason: str | None = None,
    ) -> RemediationAction:
        if remediation.status not in {
            ActionStatus.PROPOSED,
            ActionStatus.PENDING_APPROVAL,
        }:
            raise ValueError(
                f"Action cannot be edited from status "
                f"'{remediation.status.value}'."
            )

        if not isinstance(parameters, dict):
            raise ValueError("Action parameters must be a dictionary.")

        remediation.request.parameters = parameters

        if reason is not None and reason.strip():
            remediation.request.reason = reason.strip()

        # Editing invalidates the previous validation/approval.
        remediation.validation = None
        remediation.approval = None
        remediation.status = ActionStatus.PROPOSED

        return remediation

    def validate(
        self,
        remediation: RemediationAction,
        user_role: str,
        available_dags: set[str] | None = None,
        available_tasks: dict[str, set[str]] | None = None,
    ) -> RemediationAction:

        validation = validate_action(
            action=remediation.request,
            user_role=user_role,
            available_dags=available_dags,
            available_tasks=available_tasks,
        )

        remediation.validation = validation

        if not validation.valid:
            remediation.status = ActionStatus.PROPOSED
            return remediation

        if validation.approval_required:
            remediation.status = ActionStatus.PENDING_APPROVAL
        else:
            remediation.status = ActionStatus.VALIDATED

        return remediation

    def execute(
        self,
        remediation: RemediationAction,
    ) -> dict:

        if remediation.validation is None:
            raise ValueError(
                "Action has not been validated."
            )

        if not remediation.validation.valid:
            raise ValueError(
                "Action cannot execute because validation failed."
            )

        if remediation.validation.approval_required:

            if remediation.approval is None:
                raise PermissionError(
                    "Action requires human approval before execution."
                )

            if (
                remediation.approval.decision
                != ApprovalDecision.APPROVED
            ):
                raise PermissionError(
                    "Action was not approved for execution."
                )

            if remediation.status != ActionStatus.APPROVED:
                raise PermissionError(
                    "Action is not in the approved state."
                )

        if not self.airflow_executor.supports(
            remediation.request
        ):
            raise ValueError(
                "No executor supports action: "
                f"{remediation.request.action_type.value}"
            )

        remediation.status = ActionStatus.EXECUTING

        try:
            execution_result = self.airflow_executor.execute(
                remediation.request
            )

            # -------------------------------------------------
            # Verification for DAG-triggering actions
            # -------------------------------------------------

            if (
                remediation.request.action_type.value
                == "trigger_dag"
            ):

                dag_run_id = execution_result.get(
                    "dag_run_id"
                )

                if not dag_run_id:
                    remediation.status = ActionStatus.FAILED

                    return {
                        "action_id": remediation.action_id,
                        "status": remediation.status.value,
                        "execution": execution_result,
                        "verification": {
                            "status": "verification_failed",
                            "reason": (
                                "Airflow did not return a DAG run ID."
                            ),
                        },
                    }

                verification_result = (
                    self.verification_engine.verify_dag_run(
                        dag_id=remediation.request.dag_id,
                        dag_run_id=dag_run_id,
                    )
                )

                verification_status = verification_result.get(
                    "status"
                )

                if verification_status == "verified":
                    remediation.status = ActionStatus.SUCCEEDED

                else:
                    remediation.status = ActionStatus.FAILED

                return {
                    "action_id": remediation.action_id,
                    "status": remediation.status.value,
                    "execution": execution_result,
                    "verification": verification_result,
                }

            # -------------------------------------------------
            # Other actions
            # -------------------------------------------------

            remediation.status = ActionStatus.SUCCEEDED

            return {
                "action_id": remediation.action_id,
                "status": remediation.status.value,
                "execution": execution_result,
            }

        except Exception:
            remediation.status = ActionStatus.FAILED
            raise