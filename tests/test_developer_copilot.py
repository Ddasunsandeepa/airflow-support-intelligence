from unittest.mock import patch

from backend.app.developer_copilot import analyze_developer_request


def test_developer_copilot_dag_incident():
    with patch(
        "backend.app.developer_copilot.AirflowAdapter"
    ) as mock_adapter, patch(
        "backend.app.developer_copilot.analyze_airflow_with_ml"
    ) as mock_ml, patch(
        "backend.app.developer_copilot.analyze_hybrid"
    ) as mock_hybrid, patch(
        "backend.app.developer_copilot.analyze_with_developer_llm"
    ) as mock_llm:

        mock_adapter.return_value.get_incident_evidence.return_value = (
            type(
                "IncidentEvidence",
                (),
                {
                    "airflow": type(
                        "AirflowEvidence",
                        (),
                        {
                            "latest_dag_run_state": "failed",
                            "failed_task_count": 1,
                            "failed_task_id": "test_task",
                            "failed_task_operator": "PythonOperator",
                            "failure_exception_type": "RuntimeError",
                            "failure_exception_message": (
                                "Synthetic test failure"
                            ),
                        },
                    )(),
                    "kubernetes": None,
                },
            )()
        )

        mock_ml.return_value = {
            "incident_class": "Unknown",
            "confidence": None,
        }

        mock_hybrid.return_value = {
            "final_class": "Unknown",
            "final_confidence": None,
        }

        mock_llm.return_value = {
            "status": "success",
            "summary": "Test diagnosis",
            "reasoning": "Test reasoning",
            "recommended_fix": "Test investigation",
            "code_change_available": False,
            "code_change_summary": "No code change proposed.",
            "tests_to_run": ["Run test"],
        }

        result = analyze_developer_request(
            message="Why is this DAG failing?",
            incident_type="dag",
            dag_id="test_dag",
        )

        assert result.status == "success"
        assert result.incident_type == "dag"
        assert result.dag_id == "test_dag"
        assert result.diagnosis.incident_class == "Unknown"
        assert result.diagnosis.summary == "Test diagnosis"

        mock_adapter.return_value.get_incident_evidence.assert_called_once_with(
            dag_id="test_dag"
        )


def test_developer_copilot_import_error():
    with patch(
        "backend.app.developer_copilot.AirflowAdapter"
    ) as mock_adapter, patch(
        "backend.app.developer_copilot.analyze_with_developer_llm"
    ) as mock_llm:

        mock_adapter.return_value.get_import_error.return_value = {
            "filename": "broken_dag.py",
            "bundle_name": "dags-folder",
            "timestamp": "2026-09-13T00:00:00Z",
            "stack_trace": (
                "ModuleNotFoundError: "
                "No module named 'missing_module'"
            ),
            "import_error_id": 123,
        }

        mock_llm.return_value = {
            "status": "success",
            "summary": "DAG parsing failure detected.",
            "reasoning": "The DAG cannot be imported.",
            "recommended_fix": "Inspect the missing dependency.",
            "code_change_available": False,
            "code_change_summary": (
                "Investigate the import and dependency configuration."
            ),
            "tests_to_run": [
                "Validate DAG import/parsing successfully."
            ],
        }

        result = analyze_developer_request(
            message="Why is this DAG not parsing?",
            incident_type="import_error",
            import_error_id="123",
        )

        assert result.status == "success"
        assert result.incident_type == "import_error"
        assert result.import_error_id == "123"

        assert result.diagnosis.incident_class == "DAG Parsing"
        assert "DAG parsing failure detected." in result.diagnosis.summary

        assert any(
            "broken_dag.py" in item
            for item in result.evidence
        )

        assert any(
            "ModuleNotFoundError" in item
            for item in result.evidence
        )

        mock_adapter.return_value.get_import_error.assert_called_once_with(
            "123"
        )


def test_developer_copilot_requires_dag_id():
    try:
        analyze_developer_request(
            message="Why is this DAG failing?",
            incident_type="dag",
        )
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert "dag_id is required" in str(exc)


def test_developer_copilot_requires_import_error_id():
    try:
        analyze_developer_request(
            message="Why is this DAG not parsing?",
            incident_type="import_error",
        )
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert "import_error_id is required" in str(exc)