import os
import requests
import re

from backend.app.evidence import AirflowEvidence
from backend.app.kubernetes_evidence import KubernetesEvidence
from backend.app.kubernetes_evidence_parser import parse_kubernetes_evidence
from backend.app.incident_evidence import IncidentEvidence


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

    def _extract_synthetic_telemetry(self, task_log: dict) -> dict:
        """
        Extract explicitly structured synthetic telemetry from a task log.

        This parser does not invent values. It only returns telemetry
        when the task log explicitly contains the corresponding fields.
        """

        extracted = {
            "cpu_usage": None,
            "memory_usage": None,
            "worker_restarts": None,
            "scheduler_pod_status": None,
        }

        log_events = task_log.get("content", [])

        if not isinstance(log_events, list):
            return extracted

        # Combine event/error text into one searchable string.
        text_parts = []

        for event in log_events:
            if not isinstance(event, dict):
                continue

            event_text = event.get("event")
            if isinstance(event_text, str):
                text_parts.append(event_text)

            error_details = event.get("error_detail", [])

            if isinstance(error_details, list):
                for detail in error_details:
                    if not isinstance(detail, dict):
                        continue

                    exc_value = detail.get("exc_value")

                    if isinstance(exc_value, str):
                        text_parts.append(exc_value)

        text = "\n".join(text_parts)

        # ---------------------------------------------------------
        # CPU usage
        # Examples:
        # CPU=96
        # CPU=96%
        # cpu_usage=96
        # ---------------------------------------------------------

        cpu_match = re.search(
            r"(?:CPU|cpu_usage)\s*=\s*(\d+(?:\.\d+)?)\s*%?",
            text,
        )

        if cpu_match:
            extracted["cpu_usage"] = float(cpu_match.group(1))

        # ---------------------------------------------------------
        # Memory usage
        # Examples:
        # Memory=93
        # Memory=93%
        # memory_usage=93
        # ---------------------------------------------------------

        memory_match = re.search(
            r"(?:Memory|memory_usage)\s*=\s*(\d+(?:\.\d+)?)\s*%?",
            text,
        )

        if memory_match:
            extracted["memory_usage"] = float(memory_match.group(1))

        # ---------------------------------------------------------
        # Worker/container restart count
        # Examples:
        # WorkerRestarts=3
        # RestartCount=5
        # worker_restarts=3
        # ---------------------------------------------------------

        restart_match = re.search(
            r"(?:WorkerRestarts|worker_restarts|RestartCount)\s*=\s*(\d+)",
            text,
        )

        if restart_match:
            extracted["worker_restarts"] = int(
                restart_match.group(1)
            )

        # ---------------------------------------------------------
        # Scheduler pod status
        #
        # We only map explicit numeric status values here because
        # AirflowEvidence currently defines this field as Optional[int].
        # Kubernetes text such as CrashLoopBackOff is not converted
        # into a fake numeric value.
        # ---------------------------------------------------------

        scheduler_status_match = re.search(
            r"(?:SchedulerPodStatus|scheduler_pod_status)\s*=\s*(\d+)",
            text,
        )

        if scheduler_status_match:
            extracted["scheduler_pod_status"] = int(
                scheduler_status_match.group(1)
            )

        return extracted


    def _action_request(
        self,
        method: str,
        endpoint: str,
        payload: dict | None = None,
    ) -> dict:
        """
        Send an authenticated request for a controlled Airflow action.

        This method is intentionally kept inside AirflowAdapter so
        authentication and Airflow API communication remain centralized.
        """

        url = f"{self.base_url}{endpoint}"

        response = requests.request(
            method=method,
            url=url,
            headers=self._auth_headers(),
            json=payload,
            timeout=15,
        )

        response.raise_for_status()

        if not response.content:
            return {}

        return response.json()


    def trigger_dag(
        self,
        dag_id: str,
        logical_date: str | None = None,
        conf: dict | None = None,
    ) -> dict:
        """
        Trigger a DAG through the Airflow REST API.

        If logical_date is not supplied, Airflow-compatible current UTC
        time is generated automatically.

        Only structured parameters are accepted.
        """

        from datetime import datetime, timezone

        if logical_date is None:
            logical_date = (
                datetime.now(timezone.utc)
                .isoformat()
                .replace("+00:00", "Z")
            )

        payload = {
            "logical_date": logical_date,
        }

        if conf is not None:
            payload["conf"] = conf

        return self._action_request(
            "POST",
            f"/api/v2/dags/{dag_id}/dagRuns",
            payload,
        )


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
        #
        # When a specific DAG is requested, count only import errors
        # belonging to that DAG's file and bundle. Import-error records
        # do not expose dag_id directly, so we match against the
        # registered DAG's fileloc and bundle_name.
        if dag_id:
            selected_dag = next(
                (
                    dag
                    for dag in dag_list
                    if dag.get("dag_id") == dag_id
                ),
                None,
            )

            if selected_dag:
                selected_fileloc = selected_dag.get("fileloc")
                selected_filename = (
                    selected_fileloc.rsplit("/", 1)[-1]
                    if selected_fileloc
                    else None
                )
                selected_bundle_name = selected_dag.get(
                    "bundle_name"
                )

                import_error_count = sum(
                    1
                    for error in import_errors
                    if (
                        error.get("filename") == selected_filename
                        and error.get("bundle_name")
                        == selected_bundle_name
                    )
                )
            else:
                # The requested DAG is not registered, so it should
                # be handled through the import-error path instead.
                import_error_count = 0
        else:
            # No DAG filter: preserve the global catalog count.
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

        extracted_cpu_usage = None
        extracted_memory_usage = None
        extracted_worker_restarts = None
        extracted_scheduler_pod_status = None

        kubernetes_evidence = KubernetesEvidence()

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
                    synthetic_telemetry = (
                        self._extract_synthetic_telemetry(task_log)
                    )
                                        # -------------------------------------------------
                    # Kubernetes evidence extraction
                    # -------------------------------------------------

                    log_text_parts = []

                    for event in task_log.get("content", []):
                        if not isinstance(event, dict):
                            continue

                        event_text = event.get("event")

                        if isinstance(event_text, str):
                            log_text_parts.append(event_text)

                        error_details = event.get(
                            "error_detail",
                            [],
                        )

                        if isinstance(error_details, list):
                            for detail in error_details:
                                if not isinstance(detail, dict):
                                    continue

                                exc_value = detail.get("exc_value")

                                if isinstance(exc_value, str):
                                    log_text_parts.append(exc_value)

                    log_text = "\n".join(log_text_parts)

                    kubernetes_evidence = (
                        parse_kubernetes_evidence(log_text)
                    )
                    extracted_cpu_usage = (
                        synthetic_telemetry["cpu_usage"]
                    )

                    extracted_memory_usage = (
                        synthetic_telemetry["memory_usage"]
                    )

                    extracted_worker_restarts = (
                        synthetic_telemetry["worker_restarts"]
                    )

                    extracted_scheduler_pod_status = (
                        synthetic_telemetry["scheduler_pod_status"]
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

            # Values are populated only when explicitly present in
            # controlled synthetic task logs. Real infrastructure
            # telemetry will be connected separately later.
            scheduler_pod_status=extracted_scheduler_pod_status,
            worker_restarts=extracted_worker_restarts,
            cpu_usage=extracted_cpu_usage,
            memory_usage=extracted_memory_usage,
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

    def get_incident_evidence(
        self,
        dag_id: str,
    ) -> IncidentEvidence:
        """
        Collect unified evidence for a selected Airflow incident.

        Airflow evidence remains available through AirflowEvidence,
        while Kubernetes-related evidence is represented separately
        through KubernetesEvidence.

        The current Kubernetes source is controlled synthetic task-log
        evidence. A real Kubernetes adapter can replace this later.
        """

        airflow_evidence = self.get_evidence(dag_id)

        kubernetes_evidence = self.get_kubernetes_evidence(dag_id)

        return IncidentEvidence(
            airflow=airflow_evidence,
            kubernetes=kubernetes_evidence,
        )
    
    def get_kubernetes_evidence(
        self,
        dag_id: str,
    ) -> KubernetesEvidence:
        """
        Retrieve Kubernetes-related evidence from the latest
        failed task log of the selected DAG.

        This currently supports controlled synthetic evidence.
        Real Kubernetes API telemetry can replace this source later.
        """

        evidence = self.get_evidence(dag_id)

        message = evidence.failure_exception_message or ""

        return parse_kubernetes_evidence(message)


if __name__ == "__main__":
    adapter = AirflowAdapter()

    evidence = adapter.get_evidence()

    print("Airflow Operational Evidence")
    print("============================")
    print(evidence)
