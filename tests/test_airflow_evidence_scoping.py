from backend.app.airflow_adapter import AirflowAdapter


def test_registered_dag_does_not_inherit_unrelated_import_errors(monkeypatch):
    adapter = AirflowAdapter()

    monkeypatch.setattr(
        adapter,
        "get_health",
        lambda: {
            "scheduler": {
                "status": "healthy",
            }
        },
    )

    monkeypatch.setattr(
        adapter,
        "get_dags",
        lambda: {
            "dags": [
                {
                    "dag_id": "support_intelligence_kubernetes_failure",
                    "fileloc": (
                        "/opt/airflow/dags/"
                        "support_intelligence_kubernetes_failure.py"
                    ),
                    "bundle_name": "dags-folder",
                    "is_paused": False,
                    "is_stale": False,
                    "last_parse_duration": 0.125,
                }
            ]
        },
    )

    monkeypatch.setattr(
        adapter,
        "get_import_errors",
        lambda: {
            "import_errors": [
                {
                    "filename": (
                        "support_intelligence_dag_parsing_failure.py"
                    ),
                    "bundle_name": "dags-folder",
                    "import_error_id": 1,
                    "stack_trace": "ModuleNotFoundError",
                },
                {
                    "filename": (
                        "support_intelligence_parsing_failure_2.py"
                    ),
                    "bundle_name": "dags-folder",
                    "import_error_id": 2,
                    "stack_trace": "ModuleNotFoundError",
                },
            ]
        },
    )

    monkeypatch.setattr(
        adapter,
        "get_dag_runs",
        lambda dag_id, limit=1: {
            "dag_runs": []
        },
    )

    evidence = adapter.get_evidence(
        "support_intelligence_kubernetes_failure"
    )

    assert evidence.dag_count == 1
    assert evidence.dag_import_error_count == 0