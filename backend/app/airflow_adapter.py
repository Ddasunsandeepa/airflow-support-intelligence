import os
import requests

from backend.app.evidence import AirflowEvidence


class AirflowAdapter:
    def __init__(self):
        self.base_url = os.getenv(
            "AIRFLOW_API_URL",
            "http://localhost:8088",
        ).rstrip("/")

        self.username = os.getenv("AIRFLOW_USERNAME", "airflow")
        self.password = os.getenv("AIRFLOW_PASSWORD", "airflow")

    def get_token(self):
        response = requests.post(
            f"{self.base_url}/auth/token",
            json={
                "username": self.username,
                "password": self.password,
            },
            timeout=10,
        )

        response.raise_for_status()
        return response.json()["access_token"]

    def _auth_headers(self):
        token = self.get_token()
        return {
            "Authorization": f"Bearer {token}",
        }

    def get_health(self):
        response = requests.get(
            f"{self.base_url}/api/v2/monitor/health",
            timeout=10,
        )

        response.raise_for_status()
        return response.json()

    def get_dags(self):
        response = requests.get(
            f"{self.base_url}/api/v2/dags",
            headers=self._auth_headers(),
            timeout=10,
        )

        response.raise_for_status()
        return response.json()

    def get_import_errors(self, limit=100):
        """
        Retrieve DAG import/parsing errors from Airflow.

        Important:
        A DAG that fails during parsing is not registered as a DAG,
        so it will not appear in /api/v2/dags. Import errors therefore
        have to be queried separately.
        """
        response = requests.get(
            f"{self.base_url}/api/v2/importErrors",
            headers=self._auth_headers(),
            params={"limit": limit},
            timeout=10,
        )

        response.raise_for_status()
        return response.json()

    def get_import_error(self, import_error_id):
        response = requests.get(
            f"{self.base_url}/api/v2/importErrors/{import_error_id}",
            headers=self._auth_headers(),
            timeout=10,
        )

        response.raise_for_status()
        return response.json()

    def get_dag_runs(self, dag_id, limit=5):
        response = requests.get(
            f"{self.base_url}/api/v2/dags/{dag_id}/dagRuns",
            headers=self._auth_headers(),
            params={
                "limit": limit,
                "order_by": "-logical_date",
            },
            timeout=10,
        )

        response.raise_for_status()
        return response.json()

    def get_task_instances(self, dag_id, dag_run_id):
        response = requests.get(
            f"{self.base_url}/api/v2/dags/{dag_id}/dagRuns/{dag_run_id}/taskInstances",
            headers=self._auth_headers(),
            timeout=10,
        )

        response.raise_for_status()
        return response.json()

    def get_task_logs(self, dag_id, dag_run_id, task_id, try_number=1):
        response = requests.get(
            f"{self.base_url}/api/v2/dags/{dag_id}/dagRuns/"
            f"{dag_run_id}/taskInstances/{task_id}/logs/{try_number}",
            headers=self._auth_headers(),
            timeout=10,
        )

        response.raise_for_status()
        return response.json()

    def get_catalog(self):
        """
        Return the current Airflow incident-selection catalog.

        Registered DAGs and parsing/import errors are deliberately kept
        separate because parsing-failed DAGs are not registered.
        """
        dags_response = self.get_dags()
        import_errors_response = self.get_import_errors()

        dags = dags_response.get("dags", [])
        import_errors = import_errors_response.get("import_errors", [])

        return {
            "dags": dags,
            "import_errors": import_errors,
        }

    def get_evidence(self, dag_id=None):
        health = self.get_health()
        dags_response = self.get_dags()
        import_errors_response = self.get_import_errors()

        dag_list = dags_response.get("dags", [])
        import_errors = import_errors_response.get("import_errors", [])

        # If a specific registered DAG was requested, analyze only that DAG.
        if dag_id:
            dag_list = [
                dag
                for dag in dag_list
                if dag.get("dag_id") == dag_id
            ]

        scheduler_healthy = (
            health.get("scheduler", {}).get("status") == "healthy"
        )

        paused_dags = sum(
            1
            for dag in dag_list
            if dag.get("is_paused") is True
        )

        stale_dags = sum(
            1
            for dag in dag_list
            if dag.get("is_stale") is True
        )

        dag_parse_times = [
            dag.get("last_parse_duration")
            for dag in dag_list
            if dag.get("last_parse_duration") is not None
        ]

        average_parse_time = (
            sum(dag_parse_times) / len(dag_parse_times)
            if dag_parse_times
            else None
        )

        # Import errors are separate from registered DAGs.
        import_error_count = len(import_errors)

        # ---------------------------------------------------------
        # Inspect the latest run of EVERY selected DAG
        # ---------------------------------------------------------

        latest_runs = []

        total_tasks = 0
        failed_tasks = 0
        successful_tasks = 0
        failed_task_id = None
        failed_task_operator = None
        failed_task_duration = None
        failed_task_try_number = None

        failure_log_event = None
        failure_exception_type = None
        failure_exception_message = None

        for dag in dag_list:
            current_dag_id = dag.get("dag_id")

            if not current_dag_id:
                continue

            runs_response = self.get_dag_runs(
                current_dag_id,
                limit=1,
            )

            runs = runs_response.get("dag_runs", [])

            if not runs:
                continue

            latest_run = runs[0]

            latest_runs.append(
                {
                    "dag_id": current_dag_id,
                    "run": latest_run,
                }
            )

            run_id = latest_run.get("dag_run_id")

            if not run_id:
                continue

            task_response = self.get_task_instances(
                current_dag_id,
                run_id,
            )

            tasks = task_response.get(
                "task_instances",
                [],
            )

            # Inspect failed task details and logs.
            for task in tasks:
                if task.get("state") != "failed":
                    continue

                failed_task_id = task.get("task_id")
                failed_task_operator = (
                    task.get("operator_name")
                    or task.get("operator")
                )

                failed_task_duration = task.get("duration")
                failed_task_try_number = task.get(
                    "try_number",
                    1,
                )

                try:
                    task_log = self.get_task_logs(
                        current_dag_id,
                        run_id,
                        failed_task_id,
                        failed_task_try_number,
                    )

                    log_events = task_log.get(
                        "content",
                        [],
                    )

                    error_events = [
                        event
                        for event in log_events
                        if event.get("level") == "error"
                    ]

                    if error_events:
                        error_event = error_events[-1]

                        failure_log_event = error_event.get(
                            "event"
                        )

                        error_details = error_event.get(
                            "error_detail",
                            [],
                        )

                        if error_details:
                            first_error = error_details[0]

                            failure_exception_type = (
                                first_error.get("exc_type")
                            )

                            failure_exception_message = (
                                first_error.get("exc_value")
                            )

                except requests.RequestException:
                    # Log retrieval should not prevent the rest of
                    # the Airflow evidence from being used.
                    pass

                break

            total_tasks += len(tasks)

            failed_tasks += sum(
                1
                for task in tasks
                if task.get("state") == "failed"
            )

            successful_tasks += sum(
                1
                for task in tasks
                if task.get("state") == "success"
            )

        # ---------------------------------------------------------
        # Select the most recent DAG run across selected DAGs
        # ---------------------------------------------------------

        latest_dag_run_state = None
        latest_dag_run_duration = None

        if latest_runs:

            def run_sort_key(entry):
                run = entry["run"]

                # Airflow 3 may return logical_date=None for some
                # manual runs, so use reliable fallbacks.
                return (
                    run.get("logical_date")
                    or run.get("run_after")
                    or run.get("start_date")
                    or ""
                )

            latest_entry = max(
                latest_runs,
                key=run_sort_key,
            )

            latest_run = latest_entry["run"]

            latest_dag_run_state = latest_run.get("state")
            latest_dag_run_duration = latest_run.get("duration")

        return AirflowEvidence(
            heartbeat_status=1 if scheduler_healthy else 0,
            dag_parse_time=average_parse_time,

            # These are intentionally left as None until real
            # infrastructure telemetry is connected.
            scheduler_pod_status=None,
            worker_restarts=None,
            cpu_usage=None,
            memory_usage=None,
            recent_changes=None,

            dag_count=len(dag_list),
            paused_dag_count=paused_dags,
            stale_dag_count=stale_dags,
            dag_import_error_count=import_error_count,

            latest_dag_run_state=latest_dag_run_state,
            latest_dag_run_duration=latest_dag_run_duration,

            task_count=total_tasks,
            failed_task_count=failed_tasks,
            successful_task_count=successful_tasks,

            failed_task_id=failed_task_id,
            failed_task_operator=failed_task_operator,
            failed_task_duration=failed_task_duration,
            failed_task_try_number=failed_task_try_number,

            failure_log_event=failure_log_event,
            failure_exception_type=failure_exception_type,
            failure_exception_message=failure_exception_message,
        )


if __name__ == "__main__":
    adapter = AirflowAdapter()

    evidence = adapter.get_evidence()

    print("Airflow Operational Evidence")
    print("============================")
    print(evidence)
