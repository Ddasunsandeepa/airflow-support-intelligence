"""Airflow 3 source recognition checks; an existing DAG alone is insufficient."""
import time
from urllib.parse import quote

from backend.app.source_execution_policy import check_record_policy


def normalized(source: str) -> str:
    return source.replace("\r\n", "\n")


class SourceAirflowVerifier:
    def __init__(self, adapter, attempts=40, poll_interval=3):
        self.adapter = adapter
        self.attempts = attempts
        self.poll_interval = poll_interval

    def snapshot(self, dag_id):
        encoded = quote(dag_id, safe='')
        details = self.adapter._action_request("GET", f"/api/v2/dags/{encoded}/details")
        source = self.adapter._action_request("GET", f"/api/v2/dagSources/{encoded}")
        if details.get("relative_fileloc") != f"{dag_id}.py":
            raise ValueError("Airflow's DAG filename does not match the local source target.")
        if not isinstance(source.get("content"), str):
            raise ValueError("Airflow does not expose its parsed source; execution is blocked.")
        return {"content": source["content"],
                "last_parsed": details.get("last_parsed") or details.get("last_parsed_time"),
                "version": details.get("latest_dag_version"),
                "has_import_errors": details.get("has_import_errors", True),
                "is_stale": details.get("is_stale", True),
                "is_paused": details.get("is_paused", True)}

    def wait_for_source(self, record, previous):
        for attempt in range(self.attempts):
            current = self.snapshot(record.dag_id)
            if current["has_import_errors"]:
                raise ValueError("Airflow reports an import error after source application.")
            if (normalized(current["content"]) == normalized(record.change.source_code.proposed_code)
                    and current["last_parsed"] and previous["last_parsed"]
                    and current["last_parsed"] > previous["last_parsed"]
                    and not current["is_stale"] and not current["is_paused"]):
                return {k: v for k, v in current.items() if k != "content"} | {"status": "recognized"}
            if attempt + 1 < self.attempts:
                time.sleep(self.poll_interval)
        raise ValueError("Airflow did not confirm the reviewed source and a newer parse within the timeout.")

    def verify_run(self, record):
        run = self.adapter._action_request(
            "GET", f"/api/v2/dags/{quote(record.dag_id, safe='')}/dagRuns/{quote(record.dag_run_id, safe='')}"
        )
        tasks_response = self.adapter.get_task_instances(record.dag_id, record.dag_run_id)
        tasks = tasks_response.get("task_instances", [])
        version_id = (record.airflow_parse.get("version") or {}).get("id")
        versions = run.get("dag_versions", [])
        if not version_id or not any(v.get("id") == version_id for v in versions):
            raise ValueError("Run DAG version could not be matched to the recognized source version.")
        expected_task = check_record_policy(record)
        target_tasks = [t for t in tasks if t.get("task_id") == expected_task]
        if (run.get("state") != "success" or not target_tasks
                or any(t.get("state") != "success" for t in target_tasks)
                or any(t.get("state") not in {"success", "skipped"} for t in tasks)):
            raise ValueError("The expected task and DAG must both complete successfully.")
        current = self.snapshot(record.dag_id)
        if normalized(current["content"]) != normalized(record.change.source_code.proposed_code):
            raise ValueError("Airflow source changed during verification.")
        return {"task_states": [{"task_id": t["task_id"], "state": t["state"]} for t in tasks],
                "dag_version_id": version_id, "source_match": True}
