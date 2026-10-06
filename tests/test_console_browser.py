"""Console UX coverage with real FastAPI contracts, fake providers and temporary stores."""
import os
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import urlsplit

import pytest
from test_supervisor_demo import demo_backend, DAG  # noqa: F401
from test_source_remediation import source_demo  # noqa: F401

pytestmark = pytest.mark.skipif(os.getenv('RUN_BROWSER_TESTS') != '1', reason='Opt-in browser QA')


@pytest.fixture
def console_page(demo_backend):
    from playwright.sync_api import sync_playwright
    client, source, adapter = demo_backend
    Path('.test-runs/ui-qa').mkdir(parents=True, exist_ok=True)
    dist = Path(__file__).resolve().parents[1] / 'frontend' / 'dist'
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(SimpleHTTPRequestHandler, directory=str(dist)))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    faults = {}
    calls = []
    errors = []
    before = source.read_bytes()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(channel='chrome', headless=True)
            page = browser.new_page(viewport={'width': 1440, 'height': 900})
            page.on('pageerror', lambda error: errors.append(str(error)))
            def route_api(route):
                request = route.request
                url = urlsplit(request.url)
                path = url.path.removeprefix('/api')
                calls.append((request.method, path))
                if faults.get((request.method, path)):
                    route.fulfill(status=503, content_type='application/json', body='{"detail":"Simulated service unavailable. Retry."}')
                    return
                response = client.request(request.method, path + (f'?{url.query}' if url.query else ''),
                    content=request.post_data, headers={'Content-Type': 'application/json'})
                route.fulfill(status=response.status_code, content_type='application/json', body=response.text)
            page.route('**/api/**', route_api)
            yield page, f'http://127.0.0.1:{server.server_port}', client, adapter, faults, calls
            assert not errors
            assert source.read_bytes() == before
            browser.close()
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=5)


def test_incident_navigation_persistence_and_visual_qa(console_page):
    from playwright.sync_api import expect
    page, base, client, adapter, _, calls = console_page
    other = 'warehouse_resource_processing_pipeline_with_a_long_descriptive_identifier'
    adapter.get_catalog = lambda: {'dags': [{'dag_id': DAG}, {'dag_id': other}], 'import_errors': []}
    original_timeline = adapter.get_incident_timeline_data
    def long_run_timeline(dag_id=None):
        result = original_timeline(dag_id)
        result['dag_run']['dag_run_id'] = 'manual__2026-10-06T06:54:26.667138+00:00__customer_events_processing_investigation'
        return result
    adapter.get_incident_timeline_data = long_run_timeline
    qa = Path('.test-runs/ui-qa'); qa.mkdir(parents=True, exist_ok=True)
    for width, height in [(1920, 1080), (1440, 900), (1366, 768)]:
        page.set_viewport_size({'width': width, 'height': height})
        page.goto(base + '/#/overview')
        expect(page.get_by_role('heading', name='Operations overview')).to_be_visible()
        expect(page.get_by_text('API healthy', exact=True)).to_be_visible()
        page.screenshot(path=str(qa / f'overview-{width}.png'), full_page=True)
        page.goto(base + '/#/incidents')
        expect(page.get_by_role('link', name='Open incident')).to_have_count(2)
        page.screenshot(path=str(qa / f'incidents-{width}.png'), full_page=True)
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        page.get_by_label('Search incidents').fill('configuration_review')
        page.get_by_role('link', name='Open incident').click()
        page.get_by_role('button', name='Analyze Live Airflow').click()
        expect(page.get_by_role('heading', name='Failure summary')).to_be_visible()
        page.screenshot(path=str(qa / f'investigation-{width}.png'), full_page=True)
        for tab, heading in [('Timeline', 'Incident timeline'), ('Evidence', 'Airflow evidence'), ('Intelligence', 'Hybrid decision'), ('Runbook', 'configuration.md')]:
            page.get_by_role('tab', name=tab, exact=True).click()
            expect(page.get_by_role('heading', name=heading, exact=True)).to_be_visible()
            page.screenshot(path=str(qa / f'{tab.lower()}-{width}.png'), full_page=True)
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        page.get_by_role('navigation', name='Incident workspace').get_by_role('link', name='Developer Copilot').click()
        page.get_by_role('button', name='Why did this task fail?', exact=True).click()
        page.get_by_role('button', name='Send', exact=True).click()
        expect(page.get_by_role('link', name='Review Proposed Change')).to_be_visible()
        page.screenshot(path=str(qa / f'copilot-{width}.png'), full_page=True)
        page.get_by_role('link', name='Review Proposed Change').click()
        editor = page.get_by_role('textbox', name='Proposed source', exact=True)
        expect(editor).to_be_visible()
        assert editor.bounding_box()['height'] >= 350
        page.screenshot(path=str(qa / f'source-review-{width}.png'), full_page=True)
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        saved_url = page.url
        proposal_id = saved_url.rsplit('/', 1)[-1]
        stored = client.get(f'/source-remediations/{proposal_id}').json()
        # HTML textarea values normalize Windows source CRLF to LF.
        expected_source = stored['change']['source_code']['proposed_code'].replace('\r\n', '\n')
        expect(editor).to_have_value(expected_source)
        page.get_by_role('navigation', name='Primary navigation').get_by_role('link', name='Source Reviews', exact=True).click()
        expect(page.locator('tbody tr')).to_have_count(len(client.get('/source-remediations').json()))
        page.screenshot(path=str(qa / f'reviews-{width}.png'), full_page=True)
        page.goto(saved_url)
        expect(editor).to_be_visible()
        expect(editor).to_have_value(expected_source)
        assert client.get(f'/source-remediations/{proposal_id}').json()['revision'] == stored['revision']
        page.go_back()
        expect(page.get_by_role('heading', name='Source Reviews', exact=True)).to_be_visible()
    # Switching DAGs never carries over chat/proposal/action/feedback state.
    page.goto(base + f'/#/incidents/dag/{other}/remediation')
    expect(page.get_by_role('heading', name=other)).to_be_visible()
    expect(page.get_by_role('link', name='Review Proposed Change')).to_have_count(0)
    expect(page.get_by_role('button', name='Approve Action')).to_have_count(0)
    expect(page.locator('.feedback-card')).to_have_count(0)
    assert not any(path.endswith('/execute') for _, path in calls)


def test_api_errors_and_no_ai_proposal_are_visible(console_page, monkeypatch):
    from playwright.sync_api import expect
    from backend.app import source_patch_generator
    page, base, _, _, faults, _ = console_page
    pending = []
    page.route('**/api/source-remediations', lambda route: pending.append(route))
    page.goto(base + '/#/reviews')
    expect(page.get_by_text('Loading records...', exact=True)).to_be_visible()
    page.screenshot(path='.test-runs/ui-qa/reviews-loading.png', full_page=True)
    page.unroute('**/api/source-remediations')
    for route in pending:
        route.fulfill(status=200, content_type='application/json', body='[]')
    expect(page.get_by_role('heading', name='No source reviews for this selection')).to_be_visible()
    page.screenshot(path='.test-runs/ui-qa/reviews-empty.png', full_page=True)
    faults[('GET', '/source-remediations')] = True
    page.get_by_role('button', name='Refresh', exact=True).click()
    expect(page.get_by_role('alert')).to_contain_text('Simulated service unavailable')
    page.screenshot(path='.test-runs/ui-qa/reviews-error.png', full_page=True)
    faults.clear()
    page.get_by_role('button', name='Retry', exact=True).click()
    expect(page.get_by_role('alert')).to_have_count(0)
    faults[('GET', '/airflow-catalog')] = True
    page.goto(base + '/#/incidents')
    page.get_by_role('button', name='Refresh catalog').click()
    expect(page.get_by_role('alert')).to_contain_text('Simulated service unavailable')
    page.screenshot(path='.test-runs/ui-qa/api-unavailable.png', full_page=True)
    faults.clear()
    page.get_by_role('button', name='Retry', exact=True).click()
    page.get_by_role('link', name='Open incident').click()
    page.get_by_role('navigation', name='Incident workspace').get_by_role('link', name='Developer Copilot').click()
    monkeypatch.setattr(source_patch_generator, 'request_structured_llm', lambda *a, **kw: {'status': 'provider_unavailable', 'provider_attempts': [{'provider': 'gemini', 'model': 'test', 'status': 'provider_unavailable', 'http_status': 503, 'error_category': 'UNAVAILABLE'}]})
    page.get_by_placeholder('Ask about this DAG failure...').fill('Inspect this failure')
    page.get_by_role('button', name='Send', exact=True).click()
    expect(page.get_by_text('No AI source proposal:', exact=False)).to_be_visible()
    expect(page.get_by_role('link', name='Review Proposed Change')).to_have_count(0)
    expect(page.get_by_text('gemini / test:', exact=False)).to_be_visible()
    page.screenshot(path='.test-runs/ui-qa/provider-unavailable.png', full_page=True)


def test_source_feedback_required_failure_retry_duplicate_reload(console_page, source_demo):
    from playwright.sync_api import expect
    from backend.app.change_models import SourceRemediationState
    page, base, client, _, faults, calls = console_page
    service, record, _, _ = source_demo
    # Terminal test fixture, without source application or a DAG trigger.
    record.state = SourceRemediationState.EXECUTION_FAILED
    service.store.save(record)
    path = f'/source-remediations/{record.proposal_id}/feedback'
    page.goto(base + f'/#/reviews/{record.proposal_id}')
    page.get_by_role('tab', name='Execution & feedback').click()
    feedback = page.locator('.feedback-card')
    expect(feedback.get_by_role('button', name='Submit Feedback')).to_be_disabled()
    feedback.get_by_label('Useful', exact=True).check()
    expect(feedback.get_by_text('Select change quality before submitting.')).to_be_visible()
    expect(feedback.get_by_role('button', name='Submit Feedback')).to_be_disabled()
    feedback.get_by_label('Change quality', exact=True).select_option('correct')
    feedback.get_by_label('Optional comment', exact=True).fill('Final browser feedback verification')
    expect(feedback.get_by_role('button', name='Submit Feedback')).to_be_enabled()
    faults[('POST', path)] = True
    feedback.get_by_role('button', name='Submit Feedback').click()
    expect(feedback.get_by_role('alert')).to_contain_text('Simulated service unavailable')
    page.evaluate('window.scrollTo(0, 0)')
    page.screenshot(path='.test-runs/ui-qa/feedback-error.png', full_page=True)
    faults.clear()
    feedback.get_by_role('button', name='Retry feedback').click()
    feedback.get_by_role('button', name='Submit Feedback').click()
    expect(feedback.get_by_text('Feedback saved successfully.')).to_be_visible()
    page.evaluate('window.scrollTo(0, 0)')
    page.screenshot(path='.test-runs/ui-qa/feedback-saved.png', full_page=True)
    saved = client.get(path).json()
    assert saved['comment'] == 'Final browser feedback verification'
    duplicate = client.post(path, json={'useful': False, 'change_quality': 'incorrect'}).json()
    assert duplicate == saved
    page.reload()
    page.get_by_role('tab', name='Execution & feedback').click()
    expect(feedback.get_by_text('Feedback saved successfully.')).to_be_visible()
    expect(feedback.get_by_role('button', name='Submit Feedback')).to_have_count(0)
    assert len([1 for method, endpoint in calls if method == 'POST' and endpoint == path]) == 2


def test_feedback_load_failure_and_nonterminal_explanation(console_page, source_demo):
    from playwright.sync_api import expect
    page, base, _, _, faults, _ = console_page
    _, record, _, _ = source_demo
    path = f'/source-remediations/{record.proposal_id}/feedback'
    faults[('GET', path)] = True
    page.goto(base + f'/#/reviews/{record.proposal_id}')
    page.get_by_role('tab', name='Execution & feedback').click()
    feedback = page.locator('.feedback-card')
    expect(feedback.get_by_role('alert')).to_be_visible()
    faults.clear()
    feedback.get_by_role('button', name='Retry feedback').click()
    expect(feedback.get_by_text('Feedback becomes available after remediation execution completes.')).to_be_visible()
    expect(feedback.get_by_role('button', name='Submit Feedback')).to_have_count(0)


def test_incident_switch_discards_runtime_state_and_late_analysis(console_page, monkeypatch):
    from playwright.sync_api import expect
    page, base, _, adapter, _, _ = console_page
    page.goto(base + f'/#/incidents/dag/{DAG}/remediation')
    page.get_by_role('button', name='Analyze Live Airflow').click()
    page.get_by_role('button', name='Create Remediation Action').click()
    expect(page.get_by_role('heading', name='Runtime action review')).to_be_visible()
    page.get_by_role('button', name='Approve Action', exact=True).click()
    page.get_by_role('dialog').get_by_role('button', name='Confirm approve action').click()
    page.get_by_role('button', name='Execute Approved Action', exact=True).click()
    page.get_by_role('dialog').get_by_role('button', name='Confirm execute action').click()
    feedback = page.locator('.feedback-card')
    feedback.get_by_label('Useful', exact=True).check()
    feedback.get_by_label('Change quality', exact=True).select_option('correct')
    feedback.get_by_role('button', name='Submit Feedback').click()
    expect(feedback.get_by_text('Feedback saved successfully.')).to_be_visible()
    page.goto(base + '/#/incidents/dag/another_independent_dag/remediation')
    expect(page.get_by_role('heading', name='Runtime action review')).to_have_count(0)
    expect(page.locator('.feedback-card')).to_have_count(0)
    expect(page.get_by_text('Feedback saved successfully.')).to_have_count(0)
    expect(page.get_by_text('demo-recovery', exact=False)).to_have_count(0)
    expect(page.get_by_text('Configuration', exact=True)).to_have_count(0)
    # Use the actual analysis API for MemoryError; no cloud or real Airflow calls.
    from backend.app.evidence import AirflowEvidence
    from backend.app.incident_evidence import IncidentEvidence
    from test_memory_incident import memory_evidence
    monkeypatch.setattr(adapter, 'get_incident_evidence', lambda dag_id=None:
        IncidentEvidence(airflow=AirflowEvidence(**memory_evidence()), kubernetes=None))
    page.get_by_role('button', name='Analyze Live Airflow').click()
    expect(page.locator('.incident-header').get_by_text('Resource', exact=True)).to_be_visible()
    expect(page.get_by_role('heading', name='No operational remediation recommended')).to_be_visible()
    expect(page.get_by_role('button', name='Create Remediation Action')).to_have_count(0)
    expect(page.get_by_label('Configuration JSON')).to_have_count(0)
    expect(page.get_by_role('heading', name='Investigate before changing source')).to_be_visible()
    page.screenshot(path='.test-runs/ui-qa/memory-remediation.png', full_page=True)
    pending = []
    page.route('**/api/analyze-airflow?*', lambda route: pending.append(route))
    page.get_by_role('button', name='Analyze Live Airflow').click()
    expect(page.get_by_role('button', name='Analyzing...')).to_be_visible()
    page.goto(base + '/#/incidents/dag/third_independent_dag/investigation')
    for route in pending:
        route.fulfill(status=200, content_type='application/json', body='{"incident":{"class":"STALE WRONG DAG"},"evidence":{}}')
    expect(page.get_by_role('heading', name='third_independent_dag')).to_be_visible()
    expect(page.get_by_text('STALE WRONG DAG')).to_have_count(0)
