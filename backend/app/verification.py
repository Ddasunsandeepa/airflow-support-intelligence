import time
from typing import Optional

from backend.app.airflow_adapter import AirflowAdapter


class VerificationEngine:
    def __init__(
        self,
        adapter: Optional[AirflowAdapter] = None,
        poll_interval: int = 3,
        max_attempts: int = 20,
    ):
        self.adapter = adapter or AirflowAdapter()
        self.poll_interval = poll_interval
        self.max_attempts = max_attempts

    def verify_dag_run(
        self,
        dag_id: str,
        dag_run_id: str,
    ) -> dict:
        for attempt in range(1, self.max_attempts + 1):
            response = self.adapter.get_dag_runs(
                dag_id=dag_id,
                limit=20,
            )

            if isinstance(response, dict):
                runs = response.get("dag_runs", [])
            elif isinstance(response, list):
                runs = response
            else:
                runs = []

            matching_run = None

            for run in runs:
                if not isinstance(run, dict):
                    continue

                if run.get("dag_run_id") == dag_run_id:
                    matching_run = run
                    break

            if matching_run is None:
                return {
                    "status": "verification_failed",
                    "dag_id": dag_id,
                    "dag_run_id": dag_run_id,
                    "reason": "Triggered DAG run could not be found.",
                    "attempt": attempt,
                }

            state = matching_run.get("state")

            if state == "success":
                return {
                    "status": "verified",
                    "dag_id": dag_id,
                    "dag_run_id": dag_run_id,
                    "airflow_state": state,
                    "message": "DAG run completed successfully.",
                    "attempt": attempt,
                }

            if state in {"failed", "upstream_failed"}:
                return {
                    "status": "verification_failed",
                    "dag_id": dag_id,
                    "dag_run_id": dag_run_id,
                    "airflow_state": state,
                    "message": "DAG run completed with failure.",
                    "attempt": attempt,
                }

            if attempt < self.max_attempts:
                time.sleep(self.poll_interval)

        return {
            "status": "verification_timeout",
            "dag_id": dag_id,
            "dag_run_id": dag_run_id,
            "message": "DAG run did not reach a terminal state within the verification window.",
            "attempt": self.max_attempts,
        }