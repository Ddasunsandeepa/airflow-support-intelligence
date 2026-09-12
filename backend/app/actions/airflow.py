from backend.app.action_models import ActionRequest, ActionType
from backend.app.actions.base import ActionExecutor
from backend.app.airflow_adapter import AirflowAdapter


class AirflowActionExecutor(ActionExecutor):
    """
    Executes explicitly allowlisted Airflow remediation actions
    through AirflowAdapter.

    No arbitrary commands are accepted.
    """

    SUPPORTED_ACTIONS = {
        ActionType.RETRY_FAILED_TASK,
        ActionType.CLEAR_TASK,
        ActionType.TRIGGER_DAG,
        ActionType.PAUSE_DAG,
        ActionType.UNPAUSE_DAG,
    }

    def __init__(
        self,
        adapter: AirflowAdapter | None = None,
    ):
        self.adapter = adapter or AirflowAdapter()

    def supports(self, action: ActionRequest) -> bool:
        """
        Return True when this executor supports the requested action.
        """

        return action.action_type in self.SUPPORTED_ACTIONS

    def execute(self, action: ActionRequest) -> dict:
        """
        Execute one explicitly supported Airflow action.
        """

        if not self.supports(action):
            raise ValueError(
                f"Unsupported Airflow action: "
                f"{action.action_type.value}"
            )

        if action.action_type == ActionType.TRIGGER_DAG:
            return self._trigger_dag(action)

        if action.action_type == ActionType.RETRY_FAILED_TASK:
            return self._retry_failed_task(action)

        if action.action_type == ActionType.CLEAR_TASK:
            return self._clear_task(action)

        if action.action_type == ActionType.PAUSE_DAG:
            return self._pause_dag(action)

        if action.action_type == ActionType.UNPAUSE_DAG:
            return self._unpause_dag(action)

        raise ValueError(
            f"No executor implementation exists for "
            f"{action.action_type.value}"
        )

    def _trigger_dag(self, action: ActionRequest) -> dict:
        logical_date = action.parameters.get("logical_date")
        conf = action.parameters.get("conf")

        if conf is None:
            supported_parameter_keys = {"mode"}

            filtered_parameters = {
                key: value
                for key, value in action.parameters.items()
                if key in supported_parameter_keys
            }

            conf = filtered_parameters or None

        result = self.adapter.trigger_dag(
            dag_id=action.dag_id,
            logical_date=logical_date,
            conf=conf,
        )

        return {
            "status": "submitted",
            "action": action.action_type.value,
            "dag_id": action.dag_id,
            "dag_run_id": result.get("dag_run_id"),
            "airflow_state": result.get("state"),
            "triggered_by": result.get("triggered_by"),
            "response": result,
        }

    def _retry_failed_task(
        self,
        action: ActionRequest,
    ) -> dict:
        """
        Retry a failed task.

        This action remains disabled at the execution layer until
        the exact Airflow 3.3.1 operation is verified.
        """

        if not action.task_id:
            raise ValueError(
                "retry_failed_task requires task_id."
            )

        raise NotImplementedError(
            "retry_failed_task execution is not enabled yet."
        )

    def _clear_task(
        self,
        action: ActionRequest,
    ) -> dict:
        """
        Clear a task.

        This action remains disabled until its Airflow 3.3.1
        operation is verified.
        """

        if not action.task_id:
            raise ValueError(
                "clear_task requires task_id."
            )

        raise NotImplementedError(
            "clear_task execution is not enabled yet."
        )

    def _pause_dag(
        self,
        action: ActionRequest,
    ) -> dict:
        """
        Pause a DAG.

        This action remains disabled until its Airflow 3.3.1
        operation is verified.
        """

        raise NotImplementedError(
            "pause_dag execution is not enabled yet."
        )

    def _unpause_dag(
        self,
        action: ActionRequest,
    ) -> dict:
        """
        Unpause a DAG.

        This action remains disabled until its Airflow 3.3.1
        operation is verified.
        """

        raise NotImplementedError(
            "unpause_dag execution is not enabled yet."
        )