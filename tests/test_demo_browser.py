"""Optional headless UI smoke test. Run with RUN_BROWSER_TESTS=1 after npm run build.

Uses the real FastAPI routes, temporary stores, and simulated Airflow boundary.
No live DAG, LLM provider, or production backend is contacted.
"""

import os
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import urlsplit

import pytest

from test_supervisor_demo import demo_backend, DAG  # noqa: F401 - shared pytest fixture


@pytest.mark.skipif(os.getenv("RUN_BROWSER_TESTS") != "1", reason="Opt-in browser smoke test")
@pytest.mark.parametrize("execution_fails", [False, True])
def test_demo_ui(demo_backend, tmp_path, monkeypatch, execution_fails):
    from playwright.sync_api import sync_playwright, expect

    client, source, adapter = demo_backend
    original = source.read_bytes()
    if execution_fails:
        def fail_trigger(**kwargs):
            raise RuntimeError("Controlled test execution failure")
        monkeypatch.setattr(adapter, "trigger_dag", fail_trigger)
    dist = Path(__file__).resolve().parents[1] / "frontend" / "dist"
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(SimpleHTTPRequestHandler, directory=str(dist)))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel="chrome", headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            page.set_default_timeout(10000)
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            feedback_posts = []

            def api(route):
                request = route.request
                url = urlsplit(request.url)
                path = url.path.removeprefix("/api") + (f"?{url.query}" if url.query else "")
                if request.method == "POST" and path.endswith("/feedback"):
                    feedback_posts.append(request.post_data_json)
                response = client.request(request.method, path, content=request.post_data,
                                          headers={"Content-Type": "application/json"})
                route.fulfill(status=response.status_code, content_type="application/json", body=response.text)

            page.route("**/api/**", api)
            page.goto(f"http://127.0.0.1:{server.server_port}")
            expect(page.locator("#dag-select")).to_have_value(f"dag:{DAG}")
            page.get_by_role("button", name="Analyze Live Airflow", exact=True).click()
            expect(page.get_by_role("heading", name="Supporting Evidence", exact=True)).to_be_visible()
            expect(page.get_by_role("heading", name="Engineer Feedback", exact=True)).to_have_count(0)
            page.get_by_placeholder("Ask about this DAG failure...").fill("What should I investigate and review?")
            page.get_by_role("button", name="Send", exact=True).click()
            page.get_by_role("button", name="Review Proposed Change", exact=True).click()
            review = page.locator(".source-change-review")
            expect(review.get_by_role("heading", name="Source Code Change Review", exact=True)).to_be_visible()
            expect(review.locator(".diff-code")).to_have_count(1)
            expect(review.get_by_role("button")).to_have_count(0)
            expect(review.locator("pre").first).to_contain_text("from airflow import DAG")
            expect(review.locator("pre").nth(1)).to_contain_text("task = PythonOperator")
            page.get_by_role("button", name="Create Remediation Action", exact=True).click()
            page.get_by_role("button", name="Edit Action", exact=True).click()
            page.get_by_label("Recovery Mode", exact=True).select_option("recovery")
            page.get_by_role("button", name="Save Changes", exact=True).click()
            expect(page.get_by_role("heading", name="Runtime Configuration Change", exact=True)).to_be_visible()
            expect(page.locator(".remediation-card .diff-code")).to_contain_text('-  "mode": "failure"')
            expect(page.get_by_role("button", name="Execute Approved Action", exact=True)).to_have_count(0)
            page.get_by_role("button", name="Approve Action", exact=True).click()
            page.get_by_role("button", name="Execute Approved Action", exact=True).click()
            feedback = page.locator(".feedback-card")
            expect(feedback).to_be_visible()
            expect(feedback.get_by_role("button", name="Submit Feedback")).to_be_disabled()
            feedback.get_by_label("Not Useful" if execution_fails else "Useful", exact=True).check()
            feedback.get_by_label("Change quality", exact=True).select_option("incorrect" if execution_fails else "correct")
            feedback.get_by_label("Optional comment", exact=True).fill("Browser smoke test")
            feedback.get_by_role("button", name="Submit Feedback", exact=True).click()
            expect(feedback.get_by_text("Feedback saved successfully.", exact=True)).to_be_visible()
            expect(feedback.get_by_role("button", name="Submit Feedback")).to_have_count(0)
            assert len(feedback_posts) == 1
            assert feedback_posts[0]["useful"] is (not execution_fails)
            assert not errors
            assert source.read_bytes() == original
            page.screenshot(path=str(tmp_path / "demo-feedback.png"), full_page=True)
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
