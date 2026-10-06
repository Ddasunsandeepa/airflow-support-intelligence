"""No registered demo identity is needed; never write or trigger real DAGs."""
from uuid import uuid4
from pathlib import Path

import pytest

from backend.app import source_resolver
from backend.app.source_patch_generator import StructuredSourcePatch
from backend.app.source_remediation import SourceRemediationService
from backend.app.source_execution_policy import validate_execution_structure
from backend.app.source_review_validation import resolve_review_source
from backend.app.source_airflow import SourceAirflowVerifier
from backend.app.change_models import SourceRemediationState as State
from test_source_remediation import FakeAirflow, validated_approved


@pytest.fixture
def new_workload(tmp_path, monkeypatch):
    dag_id = 'new_shipments_' + uuid4().hex
    monkeypatch.setattr(source_resolver, 'DAG_SOURCE_ROOT', tmp_path)
    path = tmp_path / f'{dag_id}.py'
    before = ('from airflow.sdk import DAG\n'
              'from airflow.providers.standard.operators.python import PythonOperator\n'
              'def summarize():\n'
              '    shipments = [{"region": "APAC"}, {}]\n'
              '    return [r["region"].upper() for r in shipments]\n'
              f'with DAG(dag_id="{dag_id}", schedule=None) as dag:\n'
              '    task = PythonOperator(task_id="count_regions", python_callable=summarize)\n')
    proposed = before.replace('r["region"].upper()', 'r.get("region", "UNKNOWN").upper()')
    path.write_text(before, encoding='utf-8')
    # Match actual Windows bytes, including newline convention.
    before = path.read_bytes().decode()
    proposed = before.replace('r["region"].upper()', 'r.get("region", "UNKNOWN").upper()')
    class Adapter(FakeAirflow):
        def get_task_instances(self, *args):
            return {'task_instances': [{'task_id': 'count_regions', 'state': self.task_state},
                                      {'task_id': 'report', 'state': 'success'}]}
    adapter = Adapter(path)
    service = SourceRemediationService(adapter=adapter)
    patch = StructuredSourcePatch(target_function='summarize', summary='Handle missing region',
                                  reasoning='KeyError in observed input', proposed_function='unused', tests_to_run=['Check unknown region'])
    record = service.create(before, proposed, patch, 'developer_llm',
                            {'airflow_evidence': {'failed_task_id': 'count_regions'}}, dag_id=dag_id)
    return service, record, path, adapter


def test_new_random_dag_end_to_end(new_workload):
    service, record, path, adapter = new_workload
    before = path.read_bytes()
    assert record.execution_allowed and record.execution_policy_version == 2
    record = validated_approved(service, record)
    result = service.execute(record.proposal_id, record.revision, record.proposal_hash)
    assert result.state == State.SUCCEEDED, result.audit
    assert len(result.verification['task_states']) == 2
    assert path.read_bytes() == result.change.source_code.proposed_code.encode()
    assert Path(result.backup_path).read_bytes() == before
    assert len(adapter.triggered) == 1


def test_legacy_approval_cannot_gain_new_policy_permissions(new_workload):
    service, record, path, adapter = new_workload
    before = path.read_bytes()
    record = validated_approved(service, record)
    record.execution_policy_version = 1
    service.store.save(record)
    loaded = service.store.get(record.proposal_id)
    assert not loaded.execution_allowed and 'predates' in loaded.execution_block_reason
    with pytest.raises(ValueError, match='predates'):
        service.execute(record.proposal_id, record.revision, record.proposal_hash)
    assert path.read_bytes() == before and not adapter.triggered


@pytest.mark.parametrize('mutation', ['different_dag', 'shared_callable', 'dynamic_task', 'wrong_task', 'helper'])
def test_ambiguous_or_unrelated_source_is_not_writable(new_workload, mutation):
    _, record, _, _ = new_workload
    before = record.change.source_code.before_code
    task = 'count_regions'
    if mutation == 'different_dag':
        before = before.replace(record.dag_id, 'different')
    elif mutation == 'shared_callable':
        before += '\nother = PythonOperator(task_id="other", python_callable=summarize)\n'
    elif mutation == 'dynamic_task':
        before = before.replace('task_id="count_regions"', 'task_id=task_name')
    elif mutation == 'wrong_task':
        task = 'unrelated'
    elif mutation == 'helper':
        before = before.replace('python_callable=summarize', 'python_callable=imported_helper')
    proposed = before.replace('r["region"].upper()', 'r.get("region", "UNKNOWN").upper()')
    with pytest.raises(ValueError):
        validate_execution_structure(before, proposed, record.dag_id, 'summarize', task)


def test_general_policy_rechecks_mapping_even_with_forged_flag(new_workload):
    service, record, path, adapter = new_workload
    before = path.read_bytes()
    record = validated_approved(service, record)
    record.evidence['airflow_evidence']['failed_task_id'] = 'other'
    record.execution_allowed = True
    service.store.save(record)
    with pytest.raises(ValueError, match='map'):
        service.execute(record.proposal_id, record.revision, record.proposal_hash)
    assert path.read_bytes() == before and not adapter.triggered


def test_general_parse_failure_rolls_back(new_workload):
    service, record, path, adapter = new_workload
    before = path.read_bytes()
    adapter.parse_failure = True
    record = validated_approved(service, record)
    result = service.execute(record.proposal_id, record.revision, record.proposal_hash)
    assert result.state == State.APPLY_FAILED_ROLLED_BACK
    assert path.read_bytes() == before and not adapter.triggered


@pytest.mark.parametrize('identity', ['../outside', '..\\outside', '/absolute', 'C:\\outside', ' x '])
def test_general_path_policy_rejects_unsafe_identity(new_workload, identity):
    with pytest.raises(ValueError):
        resolve_review_source(identity)
