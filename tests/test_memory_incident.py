from backend.app.evidence_signals import extract_evidence_signals
from backend.app.main import build_remediation_recommendation


def memory_evidence():
    return {'failed_task_id': 'process_customer_events', 'failed_task_count': 1,
            'latest_dag_run_state': 'failed', 'failure_exception_type': 'MemoryError',
            'failure_exception_message': 'Resource limit exceeded: estimated memory usage 139.42 MB exceeds configured task limit 64 MB'}


def test_memory_failure_overrides_configured_substring():
    evidence = memory_evidence()
    signal = extract_evidence_signals(evidence)
    assert signal.incident_class == 'Resource'
    assert 'runtime_memory_error' in signal.matched_signals
    assert '139.42' in signal.supporting_evidence[-1]
    assert not build_remediation_recommendation('Resource', evidence)['available']


def test_memory_preserves_stronger_kubernetes_and_import_evidence():
    evidence = memory_evidence()
    assert extract_evidence_signals(evidence, {'pod_status': 'OOMKilled'}).incident_class == 'Kubernetes'
    assert extract_evidence_signals({**evidence, 'incident_type': 'import_error'}).incident_class == 'DAG Parsing'


def test_configuration_valueerror_and_other_runtime_recommendations_unchanged():
    assert extract_evidence_signals({'failure_exception_type': 'ValueError', 'failure_exception_message': 'invalid timeout configuration'}).incident_class == 'Configuration'
    assert build_remediation_recommendation('Configuration')['available']
    assert build_remediation_recommendation('Resource')['available']


def test_memory_api_uses_resource_runbook_without_runtime_recovery(monkeypatch):
    from unittest.mock import Mock
    from fastapi.testclient import TestClient
    from backend.app import main
    from backend.app.evidence import AirflowEvidence
    from backend.app.incident_evidence import IncidentEvidence
    monkeypatch.setenv('LLM_PROVIDER', 'none')
    adapter = Mock()
    adapter.get_incident_evidence.return_value = IncidentEvidence(airflow=AirflowEvidence(**memory_evidence()), kubernetes=None)
    adapter.get_incident_timeline_data.return_value = {'dag_run': None, 'task_instances': [], 'task_logs': []}
    monkeypatch.setattr(main, 'AirflowAdapter', lambda: adapter)
    result = TestClient(main.app).post('/analyze-airflow?dag_id=arbitrary_memory_workload')
    assert result.status_code == 200
    body = result.json()
    assert body['incident']['class'] == 'Resource'
    assert body['incident']['decision_mode'] == 'EVIDENCE_SIGNAL_FALLBACK'
    assert body['guidance']['runbook'] == 'resource.md'
    assert body['remediation_recommendation']['available'] is False
    adapter.trigger_dag.assert_not_called()
