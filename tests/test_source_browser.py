"""Optional full source editor UI integration, isolated API stores and fake Airflow."""
import os
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import urlsplit

import pytest

from test_source_remediation import source_demo, DEMO_DAG_ID  # noqa: F401
from test_customer_discount_remediation import customer_demo  # noqa: F401
from test_general_source_execution import new_workload  # noqa: F401


@pytest.mark.skipif(os.getenv("RUN_BROWSER_TESTS") != "1", reason="Opt-in browser smoke test")
@pytest.mark.parametrize("demo_kind", ["source_demo", "customer_demo", "new_workload"])
def test_source_editor_approval_execution_feedback(request, demo_kind, monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    from playwright.sync_api import sync_playwright, expect
    from backend.app import main, developer_copilot, source_remediation
    from backend.app.evidence import AirflowEvidence
    from backend.app.incident_evidence import IncidentEvidence

    service, record, source, adapter = request.getfixturevalue(demo_kind)
    dag_id = record.dag_id
    from backend.app.source_execution_policy import check_record_policy
    failed_task = check_record_policy(record)
    if demo_kind == "new_workload":
        import ast
        from backend.app import source_patch_generator
        from test_general_source_investigation import model_response
        proposed = record.original_proposed_source
        function = next(n for n in ast.parse(proposed).body if isinstance(n, ast.FunctionDef))
        monkeypatch.setattr(source_patch_generator, "request_structured_llm", lambda *a, **kw:
                            model_response(function.name, ast.get_source_segment(proposed, function)))
    monkeypatch.setenv("LLM_PROVIDER", "none")
    adapter.get_catalog = lambda: {"dags": [{"dag_id": dag_id, "is_paused": False}], "import_errors": []}
    adapter.get_dags = lambda: {"dags": [{"dag_id": dag_id}]}
    adapter.get_incident_evidence = lambda dag_id=None: IncidentEvidence(airflow=AirflowEvidence(
        latest_dag_run_state="failed", failed_task_count=1, failed_task_id=failed_task,
        failure_exception_type="AttributeError" if demo_kind == "customer_demo" else "TypeError",
        failure_exception_message="'NoneType' object has no attribute 'lower'" if demo_kind == "customer_demo" else "unsupported operand type(s) for +: float and NoneType",
    ), kubernetes=None)
    adapter.get_incident_timeline_data = lambda dag_id=None: {"dag_run": {"dag_id": dag_id,
        "dag_run_id": "failed-1", "state": "failed"}, "task_instances": [], "task_logs": []}
    for module in (main, developer_copilot, source_remediation):
        monkeypatch.setattr(module, "AirflowAdapter", lambda: adapter)
    client = TestClient(main.app)
    dist = Path(__file__).resolve().parents[1] / "frontend" / "dist"
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(SimpleHTTPRequestHandler, directory=str(dist)))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    original = source.read_bytes()
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel="chrome", headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            def api(route):
                request = route.request
                url = urlsplit(request.url)
                response = client.request(request.method, url.path.removeprefix("/api") + (f"?{url.query}" if url.query else ""),
                                          content=request.post_data, headers={"Content-Type": "application/json"})
                route.fulfill(status=response.status_code, content_type="application/json", body=response.text)
            page.route("**/api/**", api)
            page.goto(f"http://127.0.0.1:{server.server_port}")
            page.goto(f"http://127.0.0.1:{server.server_port}/#/incidents/dag/{dag_id}/investigation")
            page.get_by_role("button", name="Analyze Live Airflow", exact=True).click()
            page.get_by_role("navigation", name="Incident workspace").get_by_role("link", name="Developer Copilot").click()
            page.get_by_placeholder("Ask about this DAG failure...").fill("Fix the None input using the real source and failure evidence.")
            page.get_by_text("Demo testing options", exact=True).click()
            page.get_by_label("Allow labelled demo fallback", exact=False).check()
            page.get_by_role("button", name="Send", exact=True).click()
            page.get_by_role("link", name="Review Proposed Change", exact=True).click()
            workspace = page.get_by_role("region", name="Source Remediation Workspace")
            expect(workspace).to_be_visible()
            editor = workspace.get_by_role("textbox", name="Proposed source", exact=True)
            first = editor.input_value()
            editor.fill(first.replace('else ""', 'else "standard"') if demo_kind == "customer_demo"
                        else first.replace('record["amount"] for record in records', 'record.get("amount") for record in records')
                        if demo_kind == "source_demo" else first + "\n# Engineer reviewed missing-region handling\n")
            expect(workspace.get_by_role("button", name="Execute Approved Remediation", include_hidden=True)).to_be_disabled()
            workspace.get_by_role("button", name="Save Reviewed Version").click()
            expect(workspace.get_by_text("Revision 2 · Saved reviewed source", exact=True)).to_be_visible()
            workspace.get_by_role("button", name="Validate Changes").click()
            workspace.get_by_role("tab", name="Validation & approval").click()
            workspace.get_by_role("textbox", name="Reviewer name").fill("Browser Engineer")
            workspace.get_by_role("button", name="Approve Reviewed Change", include_hidden=True).click()
            if demo_kind == "customer_demo":
                qa = Path('.test-runs/ui-qa'); qa.mkdir(parents=True, exist_ok=True)
                expect(page.get_by_role("dialog").get_by_role("button", name="Cancel")).to_be_focused()
                for width, height in [(1920, 1080), (1440, 900), (1366, 768)]:
                    page.set_viewport_size({"width": width, "height": height})
                    page.screenshot(path=str(qa / f'approval-{width}.png'), full_page=True)
                page.set_viewport_size({"width": 1440, "height": 900})
            page.get_by_role("dialog").get_by_role("button", name="Confirm approve reviewed change").click()
            expect(workspace.get_by_role("button", name="Execute Approved Remediation", include_hidden=True)).to_be_enabled()
            # Local unsaved edits immediately disable execution of the stored approval.
            workspace.get_by_role("tab", name="Source & diff").click()
            editor.fill(editor.input_value() + "\n# reviewed again\n")
            expect(workspace.get_by_role("button", name="Execute Approved Remediation", include_hidden=True)).to_be_disabled()
            workspace.get_by_role("button", name="Save Reviewed Version").click()
            expect(workspace.get_by_role("button", name="Approve Reviewed Change", include_hidden=True)).to_be_disabled()
            assert source.read_bytes() == original
            workspace.get_by_role("button", name="Validate Changes").click()
            workspace.get_by_role("tab", name="Validation & approval").click()
            workspace.get_by_role("button", name="Approve Reviewed Change", include_hidden=True).click()
            page.get_by_role("dialog").get_by_role("button", name="Confirm approve reviewed change").click()
            workspace.get_by_role("tab", name="Execution & feedback").click()
            workspace.get_by_role("button", name="Execute Approved Remediation", include_hidden=True).click()
            page.get_by_role("dialog").get_by_role("button", name="Confirm execute reviewed change").click()
            expect(workspace.get_by_text("Verification: verified", exact=True)).to_be_visible()
            feedback = workspace.locator(".feedback-card")
            feedback.get_by_label("Useful", exact=True).check()
            feedback.get_by_label("Change quality", exact=True).select_option("correct")
            feedback.get_by_role("button", name="Submit Feedback").click()
            expect(feedback.get_by_text("Feedback saved successfully.", exact=True)).to_be_visible()
            assert source.read_bytes() != original
            assert len(adapter.triggered) == 1 and adapter.triggered[0]["conf"] == {}
            assert not errors
            # Persisted results remain reachable even after the corrected DAG no longer fails.
            persisted_url = page.url
            page.get_by_role("navigation", name="Primary navigation").get_by_role("link", name="Source Reviews").click()
            page.get_by_role("link", name="View Result").click()
            expect(page).to_have_url(persisted_url)
            page.reload()
            workspace.get_by_role("tab", name="Execution & feedback").click()
            expect(workspace.get_by_text("Verification: verified", exact=True)).to_be_visible()
            expect(workspace.get_by_text("Feedback saved successfully.", exact=True)).to_be_visible()
            page.screenshot(path=str(tmp_path / "source-remediation.png"), full_page=True)
            # Repeated demos start a fresh incident, not a reused terminal approval.
            expect(workspace.get_by_text("Saved result from a previous remediation")).to_be_visible()
            completed_id = persisted_url.rsplit("/", 1)[-1]
            saved_state = service.store.get(completed_id).state
            page.get_by_role("link", name="Start a new investigation").click()
            expect(page.get_by_role("heading", name=dag_id, exact=True)).to_be_visible()
            expect(page.locator(".source-remediation-workspace")).to_have_count(0)
            expect(page.locator(".feedback-card")).to_have_count(0)
            page.get_by_role("button", name="Analyze Live Airflow").click()
            expect(page.get_by_role("heading", name="Failure summary")).to_be_visible()
            assert service.store.get(completed_id).state == saved_state
            assert len(adapter.triggered) == 1
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
