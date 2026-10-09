"""Actual Chromium on a generic fixture. Test skills are not real AI acceptance."""

import functools
import json
import sqlite3
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import Error as PlaywrightError, sync_playwright

from compiler.models import DraftRecord, SavedSkill, SkillDraft, SkillStep
from event_models import TargetMetadata
from main import create_app
from recorder.config import RecorderConfig
from replay.browser import BrowserExecutor, ExecutionFailure, PauseReplay, unique_target
from replay.models import ContextHint, ReplayInput
from replay.policy import ReplayPolicy, preflight, resolve_value
from replay.shadowbank import ShadowBankVerifier


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


@pytest.fixture(scope="module")
def website():
    handler = functools.partial(QuietHandler, directory=str(Path(__file__).parent / "fixtures"))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def policy_for(origin):
    return ReplayPolicy(RecorderConfig(start_url=origin + "/replay.html", allowed_origins=[origin],
        value_allowlist=[{"origin": origin, "selector": "#reference-id", "synthetic_identifier": True},
                         {"origin": origin, "selector": "#secret"},
                         {"origin": origin, "selector": "#hidden"}]),
        timeout_ms=350, pause_seconds=15, headless=True)


def target(selector=None, role=None, label=None):
    return TargetMetadata(selector=selector, role=role, label=label)


def step(action, **kwargs):
    return SkillStep(action=action, description="Test " + action, source_event_id=1, **kwargs)


def fixture_skill(origin):
    return SkillDraft(name="Generic fixture test", description="Test-only human reviewed fixture workflow.",
        steps=[step("navigate", url=origin + "/replay.html"),
               step("fill", target=target("#reference-id", "textbox", "Reference ID"), value="{{reference_id}}"),
               step("set_checked", target=target("#reviewed", "checkbox", "Reviewed"), checked=True),
               step("click", target=target("#save", "button", "Save")),
               step("assert_visible", target=target("#result"), uncertainty="Proposed outcome visibility check.")],
        variables=[{"name": "reference_id", "description": "New human input", "source_event_id": 1,
                    "example_value": "REF-OLD", "source": "human_input", "requires_human_input": True}],
        uncertainties=["Test-only fixture; not a real learned workflow."],
        success_conditions=[{"description": "Human checks saved result", "requires_human_verification": True}],
        omitted_events=[])


@pytest.fixture
def browser_page(website):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_default_timeout(350)
        page.goto(website + "/replay.html")
        try:
            yield page
        finally:
            browser.close()


@pytest.fixture
def replay_api(tmp_path, website):
    path = tmp_path / "events.sqlite3"
    app = create_app(path, replay_policy=policy_for(website))
    skill = fixture_skill(website)
    saved = SavedSkill(id="skill-test", draft_id="draft-test", session_id="test-session", confirmed_at="test", skill=skill)
    draft = DraftRecord(id="draft-test", session_id="test-session", task_description="Fixture only", created_at="test",
                        model="test-only-not-real-learning", source_event_ids=[1], skill=skill)
    with TestClient(app, base_url="http://127.0.0.1:8000", client=("127.0.0.1", 50000)) as client:
        with sqlite3.connect(path) as connection:
            connection.execute("INSERT INTO skills VALUES (?,?,?)", (saved.id, saved.draft_id, saved.model_dump_json()))
            connection.execute("INSERT INTO skill_drafts VALUES (?,?,?)", (draft.id, draft.model_dump_json(), "[]"))
        yield client, app, saved, path


def wait_for(client, replay_id, status, current_step=None):
    deadline = time.monotonic() + 12
    while time.monotonic() < deadline:
        record = client.get("/api/replays/" + replay_id).json()
        if record["status"] == status and (current_step is None or record["current_step"] == current_step):
            return record
        if record["status"] == "failed" and status != "failed":
            pytest.fail(str(record))
        time.sleep(0.03)
    pytest.fail("Replay did not reach expected state: " + str(record))


def start_body(**extra):
    return {"skill_id": "skill-test", "parameters": {"reference_id": "REF-NEW"}, "approved": True, **extra}


def test_variables_never_reuse_examples_or_defaults(website):
    skill = fixture_skill(website)
    skill.variables[0].default_value = "REF-DEFAULT"
    report = preflight(skill, ReplayInput(skill_id="skill-test"), policy_for(website), confirmed=True)
    assert report["can_start"] and not report["ready"]
    assert report["missing_parameters"] == ["reference_id"]
    with pytest.raises(ValueError, match="Missing required"):
        resolve_value(skill.steps[1], {})
    assert resolve_value(skill.steps[1], {"reference_id": "REF-NEW"}) == "REF-NEW"


def test_missing_parameters_pause_before_launch_and_resume(replay_api):
    client, app, saved, _ = replay_api
    response = client.post("/api/replays", json=start_body(parameters={}))
    assert response.status_code == 202
    replay_id = response.json()["id"]
    record = wait_for(client, replay_id, "paused", 0)
    assert [r["action"] for r in record["results"]] == ["parameters"]
    assert client.post(f"/api/replays/{replay_id}/resume", json={"parameters": {"reference_id": "REF-NEW"}}).status_code == 200
    wait_for(client, replay_id, "paused", 3)
    client.post(f"/api/replays/{replay_id}/stop")
    wait_for(client, replay_id, "failed")


def test_pending_draft_preview_rejects_execution(replay_api):
    client, *_ = replay_api
    preview = client.post("/api/replays/preflight", json={"skill_id": "draft-test", "parameters": {"reference_id": "REF-NEW"}})
    assert preview.status_code == 200
    assert not preview.json()["confirmed"] and not preview.json()["can_start"]
    assert client.post("/api/replays", json=start_body(skill_id="draft-test")).status_code == 409


def test_unsupported_action_in_stored_skill_rejected(replay_api):
    client, _, saved, path = replay_api
    invalid = saved.model_dump()
    invalid["skill"]["steps"][0]["action"] = "shell"
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE skills SET payload=?", (json.dumps(invalid),))
    assert client.post("/api/replays", json=start_body()).status_code == 422


def test_ambiguous_buttons_are_not_clicked(browser_page):
    button = target(role="button", label="Open")
    with pytest.raises(PauseReplay, match="2 visible matches"):
        unique_target(browser_page, button, timeout_ms=100)
    chosen = unique_target(browser_page, button, ContextHint(selector=".row", text="REQ-B"))
    assert chosen.count() == 1
    assert "REQ-B" in chosen.locator("..").inner_text()


def test_conflicting_candidates_pause(browser_page):
    with pytest.raises(PauseReplay, match="conflicting"):
        unique_target(browser_page, target("#save", "button", "Open"), timeout_ms=100)


def test_missing_element_fails(browser_page):
    with pytest.raises(ExecutionFailure, match="not found"):
        unique_target(browser_page, target("#absent"), timeout_ms=100)


def test_context_must_be_unique(browser_page):
    with pytest.raises(PauseReplay, match="multiple containers"):
        unique_target(browser_page, target(role="button", label="Open"), ContextHint(selector=".row"))


def test_runtime_privacy_overrides_allowlist(browser_page, website):
    executor = BrowserExecutor(browser_page, policy_for(website), fixture_skill(website))
    for selector in ("#secret", "#hidden"):
        with pytest.raises(ExecutionFailure, match="forbidden"):
            executor.check_input(browser_page.locator(selector), target(selector), "REF-NEW")
        assert browser_page.locator(selector).input_value() == ""


def test_fill_checks_value_and_react_style_update(browser_page, website):
    executor = BrowserExecutor(browser_page, policy_for(website), fixture_skill(website))
    request = ReplayInput(skill_id="skill-test", parameters={"reference_id": "REF-NEW"}, approved_steps=[1])
    executor.execute(2, fixture_skill(website).steps[1], request)
    assert browser_page.locator("#reference-id").input_value() == "REF-NEW"
    executor.execute(1, step("click", target=target("#react")), request)
    assert unique_target(browser_page, target("#next"), timeout_ms=600).inner_text() == "Next screen"


def test_incorrect_checkbox_state_is_not_success(browser_page, website):
    executor = BrowserExecutor(browser_page, policy_for(website), fixture_skill(website))
    with pytest.raises((PlaywrightError, AssertionError)):
        executor.execute(1, step("set_checked", target=target("#broken"), checked=True), ReplayInput(skill_id="test"), human_verified=True)
    assert not browser_page.locator("#broken").is_checked()


def test_checkbox_attestation_and_false_state(browser_page, website):
    executor = BrowserExecutor(browser_page, policy_for(website), fixture_skill(website))
    request = ReplayInput(skill_id="skill-test")
    checked = step("set_checked", target=target("#reviewed"), checked=True)
    with pytest.raises(PauseReplay, match="attestation"):
        executor.execute(1, checked, request)
    assert not browser_page.locator("#reviewed").is_checked()
    executor.execute(1, checked, request, human_verified=True)
    assert browser_page.locator("#reviewed").is_checked()
    executor.execute(2, step("set_checked", target=target("#reviewed"), checked=False), request)
    assert not browser_page.locator("#reviewed").is_checked()


def test_failed_visibility_assertion(browser_page, website):
    executor = BrowserExecutor(browser_page, policy_for(website), fixture_skill(website))
    with pytest.raises(ExecutionFailure):
        executor.execute(1, step("assert_visible", target=target("#invisible"), uncertainty="Future check"), ReplayInput(skill_id="test"))


def test_click_requires_explicit_approval(browser_page, website):
    executor = BrowserExecutor(browser_page, policy_for(website), fixture_skill(website))
    with pytest.raises(PauseReplay, match="approval"):
        executor.execute(1, step("click", target=target("#save")), ReplayInput(skill_id="test"))
    assert not browser_page.locator("#result").is_visible()


def test_full_real_browser_api_logging_and_human_outcome(replay_api):
    client, app, saved, path = replay_api
    replay_id = client.post("/api/replays", json=start_body()).json()["id"]
    paused = wait_for(client, replay_id, "paused", 3)
    assert paused["parameters"] == {"reference_id": "REF-NEW"}
    assert client.post(f"/api/replays/{replay_id}/resume", json={"human_verified_step": 4}).status_code == 409
    assert client.post(f"/api/replays/{replay_id}/resume", json={"human_verified_step": 3}).status_code == 200
    wait_for(client, replay_id, "paused", 4)
    assert client.post(f"/api/replays/{replay_id}/resume", json={"approved_steps": [4]}).status_code == 200
    paused = wait_for(client, replay_id, "paused", 6)
    assert not paused["outcome_verified"]
    assert client.post(f"/api/replays/{replay_id}/resume", json={"outcome_verified": True}).status_code == 200
    completed = wait_for(client, replay_id, "completed")
    assert [r["step"] for r in completed["results"] if r["status"] == "succeeded"] == [1, 2, 3, 4, 5, 6]
    assert completed["outcome_verified"]
    assert client.get(f"/api/replays/{replay_id}/steps").json() == completed["results"]
    with sqlite3.connect(path) as connection:
        payload = connection.execute("SELECT payload FROM replays WHERE id=?", (replay_id,)).fetchone()[0]
        assert "REF-NEW" in payload and "REF-OLD" not in payload
    assert client.get("/health").json() == {"status": "ok", "service": "shadowops-backend"}
    assert client.get("/api/events/test-session").json() == []
    assert client.get("/api/skills/skill-test").json() == saved.model_dump(mode="json")


def test_no_blanket_approval_or_premature_outcome(replay_api):
    client, *_ = replay_api
    assert client.post("/api/replays", json=start_body(approved=False)).status_code == 422
    replay_id = client.post("/api/replays", json=start_body()).json()["id"]
    wait_for(client, replay_id, "paused", 3)
    assert client.post(f"/api/replays/{replay_id}/resume", json={"outcome_verified": True}).status_code == 409
    assert client.post(f"/api/replays/{replay_id}/resume", json={"parameters": {"reference_id": "OTHER"}}).status_code == 409
    assert client.post("/api/replays", json=start_body()).status_code == 409


@pytest.mark.parametrize("parameters", [{"password": "secret"}, {"reference_id": "bearer abc"}, {"reference_id": "email@example.com"}])
def test_secrets_rejected_without_storage(replay_api, parameters):
    client, _, _, path = replay_api
    assert client.post("/api/replays", json=start_body(parameters=parameters)).status_code == 422
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM replays").fetchone()[0] == 0


@pytest.mark.parametrize("url", ["https://example.com/", "http://127.0.0.1:8000/", "http://localhost:5173/",
                                "http://127.0.0.1:5173/?token=secret", "file:///C:/Windows"])
def test_preflight_blocks_unconfigured_destinations(website, url):
    skill = fixture_skill(website)
    skill.steps[0].url = url
    report = preflight(skill, ReplayInput(skill_id="test", parameters={"reference_id": "REF-NEW"}), policy_for(website), confirmed=True)
    assert not report["can_start"]


def test_preflight_rejects_missing_locator_and_unsafe_css(website):
    skill = fixture_skill(website)
    skill.steps[3].target = target()
    assert preflight(skill, ReplayInput(skill_id="test"), policy_for(website), confirmed=True)["errors"]
    skill.steps[3].target = target("button:first-child")
    assert preflight(skill, ReplayInput(skill_id="test"), policy_for(website), confirmed=True)["errors"]


def test_replay_api_blocks_remote_and_cross_origin(replay_api):
    client, app, *_ = replay_api
    assert client.post("/api/replays/preflight", json={"skill_id": "skill-test"}, headers={"Origin": "http://evil.example"}).status_code == 403
    with TestClient(app, base_url="http://127.0.0.1:8000", client=("192.168.1.4", 60000)) as remote:
        assert remote.post("/api/replays/preflight", json={"skill_id": "skill-test"}).status_code == 403


def test_restart_does_not_repeat_execution(replay_api):
    client, app, *_ = replay_api
    replay_id = client.post("/api/replays", json=start_body(parameters={})).json()["id"]
    wait_for(client, replay_id, "paused", 0)
    app.state.replay_manager.stop(replay_id)
    app.state.replay_manager.thread.join(timeout=5)
    record = app.state.replay_manager.get(replay_id)
    record.status = "running"
    app.state.replay_manager.save(record)
    app.state.replay_manager.recover()
    failed = client.get("/api/replays/" + replay_id).json()
    assert failed["status"] == "failed" and "restarted" in failed["error"]


def test_ask_human_is_not_automatically_acknowledged(browser_page, website):
    executor = BrowserExecutor(browser_page, policy_for(website), fixture_skill(website))
    question = step("ask_human", question="Is this the intended request?")
    with pytest.raises(PauseReplay, match="Human response"):
        executor.execute(1, question, ReplayInput(skill_id="test"))
    assert "acknowledged" in executor.execute(1, question, ReplayInput(skill_id="test"), acknowledged=True)


def test_context_selection_is_explicit_and_separate(browser_page, website):
    executor = BrowserExecutor(browser_page, policy_for(website), fixture_skill(website))
    request = ReplayInput(skill_id="test", context_selection={"selector": ".row button"})
    with pytest.raises(PauseReplay, match="approval"):
        executor.select_context(request)
    request.approved_steps = [0]
    with pytest.raises(PauseReplay, match="2 visible matches"):
        executor.select_context(request)
    request.context_selection = ContextHint(selector="#save")
    assert "separate" in executor.select_context(request)
    assert browser_page.locator("#result").is_visible()


def test_failed_action_is_logged_and_never_completed(replay_api):
    client, _, saved, path = replay_api
    saved.skill.steps[2] = step("assert_visible", target=target("#absent"), uncertainty="Missing future result")
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE skills SET payload=?", (saved.model_dump_json(),))
    replay_id = client.post("/api/replays", json=start_body()).json()["id"]
    failed = wait_for(client, replay_id, "failed")
    assert failed["results"][-1]["status"] == "failed"
    assert failed["results"][-1]["step"] == 3
    assert not failed["outcome_verified"]


def test_sensitive_resume_is_not_saved_or_echoed(replay_api):
    client, _, _, path = replay_api
    replay_id = client.post("/api/replays", json=start_body(parameters={})).json()["id"]
    wait_for(client, replay_id, "paused", 0)
    response = client.post(f"/api/replays/{replay_id}/resume", json={"parameters": {"reference_id": "bearer private-value"}})
    assert response.status_code == 422 and "private-value" not in response.text
    assert client.get("/api/replays/" + replay_id).json()["parameters"] == {}


@pytest.mark.parametrize("key, value", [("Customer ID", "CUS-WRONG"), ("Transaction ID", "TXN-WRONG"),
                                     ("Amount", "$49.50 USD"), ("Amount", "€48.50 EUR")])
def test_visible_data_verifier_rejects_independent_mismatches(browser_page, key, value):
    # Intercept an exact demo URL with an isolated fixture. This does not touch
    # the running React app and is not the real acceptance recording/replay.
    fixture = (Path(__file__).parent / "fixtures" / "shadowbank-verification.html").read_text(encoding="utf-8")
    browser_page.route("http://127.0.0.1:5173/verifier-fixture", lambda route: route.fulfill(body=fixture, content_type="text/html"))
    browser_page.goto("http://127.0.0.1:5173/verifier-fixture")
    verifier = ShadowBankVerifier()
    assert verifier.verify_details(browser_page, "TXN-TEST")
    review = verifier.review_evidence(browser_page)
    assert all(review["field_matches"].values())
    assert review["request"]["Customer ID"] == review["transaction"]["Customer ID"] == "CUS-TEST"
    assert review["independently_verified_before_attestation"]
    assert verifier.observe_outcome(browser_page) and verifier.confirmation == "DSP-1234"
    row = browser_page.locator("section.panel dl > div").filter(has=browser_page.get_by_text(key, exact=True))
    row.locator("dd").evaluate("(element, value) => element.textContent = value", value)
    assert not verifier.verify_details(browser_page, "TXN-TEST")
    assert not verifier.observe_outcome(browser_page)
    blocked_review = verifier.review_evidence(browser_page)
    if value == "€48.50 EUR":
        assert blocked_review is None  # Unsupported format supplies no verification evidence.
    else:
        assert blocked_review is not None
        assert not blocked_review["independently_verified_before_attestation"]


def test_verifier_rejects_wrong_intended_transaction_and_origin(browser_page, website):
    fixture = (Path(__file__).parent / "fixtures" / "shadowbank-verification.html").read_text(encoding="utf-8")
    browser_page.set_content(fixture)
    assert not ShadowBankVerifier().verify_details(browser_page, "TXN-TEST")
    browser_page.route("http://127.0.0.1:5173/verifier-fixture", lambda route: route.fulfill(body=fixture, content_type="text/html"))
    browser_page.goto("http://127.0.0.1:5173/verifier-fixture")
    assert not ShadowBankVerifier().verify_details(browser_page, "TXN-OTHER")


def test_outcome_verifier_rejects_ambiguous_confirmation_regions(browser_page):
    fixture = (Path(__file__).parent / "fixtures" / "shadowbank-verification.html").read_text(encoding="utf-8")
    browser_page.route("http://127.0.0.1:5173/verifier-fixture", lambda route: route.fulfill(body=fixture, content_type="text/html"))
    browser_page.goto("http://127.0.0.1:5173/verifier-fixture")
    verifier = ShadowBankVerifier()
    assert verifier.verify_details(browser_page, "TXN-TEST")
    assert browser_page.get_by_role("status").count() == 2
    assert verifier.observe_outcome(browser_page)
    browser_page.get_by_role("status").filter(
        has=browser_page.get_by_role("heading", name="Dispute case created", exact=True)
    ).evaluate("element => element.after(element.cloneNode(true))")
    assert not verifier.observe_outcome(browser_page)


def test_preflight_preserves_checkbox_order_and_flags_false_confirmation(website):
    skill = fixture_skill(website)
    checkbox = skill.steps[2]
    unchecked = checkbox.model_copy(update={"checked": False, "description": "Uncheck to confirm verification"})
    skill.steps[2:3] = [checkbox, unchecked, checkbox]
    report = preflight(skill, ReplayInput(skill_id="test"), policy_for(website), confirmed=True)
    assert [s.checked for s in skill.steps if s.action == "set_checked"] == [True, False, True]
    assert any("unchecked=false" in warning for warning in report["warnings"])
    unchecked.description = "Uncheck the verification checkbox; this clears the attestation and does not confirm verification."
    corrected = preflight(skill, ReplayInput(skill_id="test"), policy_for(website), confirmed=True)
    assert not any("unchecked=false" in warning for warning in corrected["warnings"])


@pytest.mark.parametrize("selector", ["#", "[name=", 'input[name="x]', "button:first-child", "xpath=//button"])
def test_invalid_locator_structure_is_rejected_before_browser(website, selector):
    skill = fixture_skill(website)
    skill.steps[3].target = target(selector)
    report = preflight(skill, ReplayInput(skill_id="test"), policy_for(website), confirmed=True)
    assert report["errors"]
