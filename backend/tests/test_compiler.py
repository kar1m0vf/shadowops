"""Compiler contracts with TEST-ONLY LLM responses; these are not real AI acceptance."""

import copy
import json
import sqlite3

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from main import create_app
from compiler.models import SkillDraft
from compiler.provider import CompilerError, OllamaCompatibleProvider, OpenAICompatibleProvider


def seed_recording(client, *, missing_value=False):
    target = {
        "tag": "input", "role": "textbox", "label": "Reference ID", "selector": "#reference-id",
        "placeholder": "Enter reference",
        "locator_candidates": [
            {"strategy": "role", "value": "textbox", "name": "Reference ID", "match_count": 1},
            {"strategy": "css", "value": "#reference-id"},
        ],
        "context": {"tag": "main", "role": "main", "selector": "#main", "label": None},
    }
    events = [
        {"action": "navigation", "target": {"tag": "document"}},
        {"action": "input_change", "target": target, **({} if missing_value else {"value": "REF-81001"})},
        {"action": "input_change", "target": {
            "tag": "input", "role": "checkbox", "label": "Reviewed", "selector": "#reviewed",
        }, "checked": True},
        {"action": "click", "target": {
            "tag": "button", "role": "button", "label": "Save", "selector": "#save",
        }},
    ]
    for index, event in enumerate(events):
        # Timestamps are intentionally descending: SQLite recording order remains authoritative.
        event.update(session_id="test-recording", url="http://127.0.0.1:5173/",
                     timestamp=f"2026-10-09T12:00:0{9-index}Z")
        assert client.post("/api/events", json=event).status_code == 201
    return client.get("/api/events/test-recording").json()


def make_test_draft(events):
    first, field, checkbox, button = events
    return {
        "name": "Review a reference", "description": "Proposed workflow from the test demonstration.",
        "steps": [
            {"action": "navigate", "description": "Open the page", "source_event_id": first["id"], "url": first["url"]},
            {"action": "fill", "description": "Enter reference", "source_event_id": field["id"],
             "target": field["target"], "value": "{{reference_id}}",
             "uncertainty": "Future reference must be supplied by a human; a value may not have been recorded."},
            {"action": "set_checked", "description": "Set review state", "source_event_id": checkbox["id"],
             "target": checkbox["target"], "checked": True},
            {"action": "click", "description": "Save", "source_event_id": button["id"], "target": button["target"]},
        ],
        "variables": [{"name": "reference_id", "description": "Reference to process",
                       "source_event_id": field["id"], "example_value": field.get("value"),
                       "source": "human_input", "requires_human_input": True, "default_value": None}],
        "uncertainties": ["Future input source is unknown; the recording does not prove that saving succeeded."],
        "success_conditions": [{"description": "A human verifies that the requested item was saved.",
                                "requires_human_verification": True}],
        "omitted_events": [],
    }


class TestOnlyProvider:
    __test__ = False
    model = "test-only-response-not-real-inference"

    def __init__(self, mutate=None):
        self.mutate = mutate
        self.payloads = []

    def generate(self, system_prompt, user_payload):
        self.payloads.append(user_payload)
        assert "untrusted data" in system_prompt
        draft = make_test_draft(user_payload["events"])
        if self.mutate:
            self.mutate(draft)
        return json.dumps(draft)


@pytest.fixture
def compiled(tmp_path):
    path = tmp_path / "events.sqlite3"
    provider = TestOnlyProvider()
    with TestClient(create_app(path, llm_provider=provider)) as client:
        events = seed_recording(client)
        response = client.post("/api/skills/compile", json={
            "session_id": "test-recording", "task_description": "Review and save a reference",
        })
        assert response.status_code == 201, response.text
        yield client, response.json(), events, provider, path


def test_valid_draft_preserves_evidence_order_variables_and_raw_events(compiled):
    client, record, events, provider, path = compiled
    assert record["status"] == "pending_review"
    fetched = client.get("/api/skill-drafts/" + record["id"])
    assert fetched.json() == record
    assert fetched.headers["content-type"] == "application/json; charset=utf-8"
    skill = record["skill"]
    assert [step["source_event_id"] for step in skill["steps"]] == [event["id"] for event in events]
    assert skill["steps"][1]["target"] == events[1]["target"]
    assert skill["steps"][1]["value"] == "{{reference_id}}"
    assert skill["variables"][0]["example_value"] == "REF-81001"
    assert skill["variables"][0]["requires_human_input"] is True
    assert skill["steps"][2]["checked"] is True
    assert skill["uncertainties"]
    assert all(condition["requires_human_verification"] for condition in skill["success_conditions"])
    assert [event["id"] for event in provider.payloads[0]["events"]] == record["source_event_ids"]
    assert "skill_draft_json_schema" in provider.payloads[0]
    assert client.get("/api/events/test-recording").json() == events
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM skills").fetchone()[0] == 0


def test_human_corrections_confirmation_and_persistence(compiled):
    client, record, events, provider, path = compiled
    corrected = copy.deepcopy(record["skill"])
    corrected["name"] = "Human reviewed reference workflow"
    corrected["variables"][0]["name"] = "item_reference"
    corrected["variables"][0]["default_value"] = "REF-90002"
    corrected["steps"][1]["value"] = "{{item_reference}}"
    corrected["steps"][2]["checked"] = False
    # New events arriving after compilation must not alter the draft's evidence snapshot.
    extra = {key: value for key, value in events[-1].items() if key != "id"}
    assert client.post("/api/events", json=extra).status_code == 201
    response = client.post(f"/api/skill-drafts/{record['id']}/confirm",
                           json={"confirmed": True, "skill": corrected})
    assert response.status_code == 201, response.text
    saved = response.json()
    assert saved["status"] == "confirmed"
    assert saved["skill"] == corrected
    assert client.get("/api/skills/" + saved["id"]).json() == saved
    assert client.get("/api/skill-drafts/" + record["id"]).json() == record
    assert client.post(f"/api/skill-drafts/{record['id']}/confirm",
                       json={"confirmed": True, "skill": corrected}).status_code == 409
    assert len(provider.payloads) == 1  # Review and retrieval never make an inference call.
    with TestClient(create_app(path)) as restarted:
        assert restarted.get("/api/skills/" + saved["id"]).json() == saved


@pytest.mark.parametrize("confirmation", [None, False, "true", 1])
def test_review_requires_an_explicit_json_boolean(compiled, confirmation):
    client, record, *_ = compiled
    payload = {"skill": record["skill"]}
    if confirmation is not None:
        payload["confirmed"] = confirmation
    assert client.post(f"/api/skill-drafts/{record['id']}/confirm", json=payload).status_code == 422


def test_human_review_cannot_erase_evidence_or_invent_locators(compiled):
    client, record, *_ = compiled
    corrected = copy.deepcopy(record["skill"])
    corrected["steps"][1]["target"]["selector"] = "#invented"
    response = client.post(f"/api/skill-drafts/{record['id']}/confirm",
                           json={"confirmed": True, "skill": corrected})
    assert response.status_code == 422
    assert "recorded evidence" in response.json()["detail"]


@pytest.mark.parametrize("case", [
    "unseen_action", "unknown_event", "invented_target", "lost_locators", "reordered",
    "invented_value", "invented_state", "wrong_variable_example", "unseen_variable_source",
    "assumed_default", "not_human_input", "unknown_variable", "duplicate_event", "missing_event",
    "verified_success", "missing_uncertainty", "code", "coerced_boolean",
])
def test_invalid_model_output_is_rejected_without_saving(tmp_path, case):
    def mutate(draft):
        if case == "unseen_action": draft["steps"][3]["action"] = "evaluate"
        elif case == "unknown_event": draft["steps"][3]["source_event_id"] = 999
        elif case == "invented_target": draft["steps"][3]["target"]["label"] = "Unseen result"
        elif case == "lost_locators": draft["steps"][1]["target"]["locator_candidates"] = []
        elif case == "reordered": draft["steps"][0], draft["steps"][3] = draft["steps"][3], draft["steps"][0]
        elif case == "invented_value": draft["steps"][1]["value"] = "invented"
        elif case == "invented_state": draft["steps"][2]["checked"] = False
        elif case == "wrong_variable_example": draft["variables"][0]["example_value"] = "guessed"
        elif case == "unseen_variable_source": draft["variables"][0]["source"] = "crm"
        elif case == "assumed_default": draft["variables"][0]["default_value"] = "guessed"
        elif case == "not_human_input": draft["variables"][0]["requires_human_input"] = False
        elif case == "unknown_variable": draft["steps"][1]["value"] = "{{unknown}}"
        elif case == "duplicate_event": draft["steps"].append(copy.deepcopy(draft["steps"][-1]))
        elif case == "missing_event": draft["steps"].pop()
        elif case == "verified_success": draft["success_conditions"][0]["requires_human_verification"] = False
        elif case == "missing_uncertainty": draft["uncertainties"] = []
        elif case == "code": draft["steps"][3]["code"] = "arbitrary code"
        elif case == "coerced_boolean": draft["steps"][2]["checked"] = "true"

    path = tmp_path / "events.sqlite3"
    with TestClient(create_app(path, llm_provider=TestOnlyProvider(mutate))) as client:
        seed_recording(client)
        response = client.post("/api/skills/compile", json={
            "session_id": "test-recording", "task_description": "Save the reference",
        })
        assert response.status_code == 502, response.text
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM skill_drafts").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM skills").fetchone()[0] == 0


def test_unknown_input_value_requires_human_input(tmp_path):
    with TestClient(create_app(tmp_path / "events.sqlite3", llm_provider=TestOnlyProvider())) as client:
        seed_recording(client, missing_value=True)
        response = client.post("/api/skills/compile", json={
            "session_id": "test-recording", "task_description": "Save the reference",
        })
        assert response.status_code == 201
        assert response.json()["skill"]["variables"][0]["example_value"] is None
        assert response.json()["skill"]["steps"][1]["uncertainty"]


def test_proposed_assertion_and_human_question_are_never_observed_success(compiled):
    client, record, *_ = compiled
    skill = copy.deepcopy(record["skill"])
    button = skill["steps"][-1]
    skill["steps"].extend([
        {"action": "assert_visible", "description": "Possible future visibility check",
         "source_event_id": button["source_event_id"], "target": button["target"],
         "uncertainty": "This target was observed earlier; its final visibility is unknown."},
        {"action": "ask_human", "description": "Check the outcome", "question": "Did saving succeed?"},
    ])
    response = client.post(f"/api/skill-drafts/{record['id']}/confirm",
                           json={"confirmed": True, "skill": skill})
    assert response.status_code == 201, response.text
    skill["steps"][-2].pop("uncertainty")
    with pytest.raises(ValidationError):
        SkillDraft.model_validate(skill)


def test_explicit_omission_is_accounted_for(compiled):
    client, record, *_ = compiled
    skill = copy.deepcopy(record["skill"])
    omitted = skill["steps"].pop()
    skill["omitted_events"] = [{"event_id": omitted["source_event_id"], "reason": "Human excludes this optional final click."}]
    assert client.post(f"/api/skill-drafts/{record['id']}/confirm",
                       json={"confirmed": True, "skill": skill}).status_code == 201


@pytest.mark.parametrize("missing", ["SHADOWOPS_LLM_BASE_URL", "SHADOWOPS_LLM_API_KEY", "SHADOWOPS_LLM_MODEL"])
def test_missing_llm_settings_are_explicit_and_never_fall_back(tmp_path, monkeypatch, missing):
    for name, value in (("SHADOWOPS_LLM_BASE_URL", "https://inference.example/v1"),
                        ("SHADOWOPS_LLM_API_KEY", "test-only-key"), ("SHADOWOPS_LLM_MODEL", "configured-test-model")):
        monkeypatch.setenv(name, value)
    monkeypatch.delenv(missing)
    original = OpenAICompatibleProvider.from_environment
    monkeypatch.setattr(OpenAICompatibleProvider, "from_environment", lambda: original(tmp_path / ".env"))
    with TestClient(create_app(tmp_path / "events.sqlite3")) as client:
        seed_recording(client)
        response = client.post("/api/skills/compile", json={
            "session_id": "test-recording", "task_description": "Review a reference",
        })
        assert response.status_code == 503
        assert missing in response.json()["detail"]


def test_dotenv_configuration_and_environment_precedence(tmp_path, monkeypatch):
    for name in ("SHADOWOPS_LLM_BASE_URL", "SHADOWOPS_LLM_API_KEY", "SHADOWOPS_LLM_MODEL"):
        monkeypatch.delenv(name, raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("SHADOWOPS_LLM_BASE_URL=https://inference.example/v1\n"
                        "SHADOWOPS_LLM_API_KEY=test-only-key\nSHADOWOPS_LLM_MODEL=file-model\n", encoding="utf-8")
    monkeypatch.setenv("SHADOWOPS_LLM_MODEL", "environment-model")
    provider = OpenAICompatibleProvider.from_environment(env_file)
    assert provider.endpoint == "https://inference.example/v1/chat/completions"
    assert provider.model == "environment-model"


def test_http_provider_sends_compatible_json_request_and_preserves_unicode():
    def handler(request):
        assert str(request.url) == "https://inference.example/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer test-only-key"
        body = json.loads(request.content)
        assert body["model"] == "configured-test-model"
        assert body["response_format"] == {"type": "json_object"}
        assert json.loads(body["messages"][1]["content"])["label"] == "Investigate →"
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {"content": '{"label":"→"}'}}]})
    provider = OpenAICompatibleProvider("https://inference.example/v1", "test-only-key", "configured-test-model",
                                        transport=httpx.MockTransport(handler))
    assert provider.generate("Return JSON", {"label": "Investigate →"}) == '{"label":"→"}'


@pytest.mark.parametrize("upstream_status, expected", [(401, 503), (403, 503), (429, 503), (500, 502), (302, 502)])
def test_provider_failures_are_explicit_without_exposing_upstream_body(upstream_status, expected):
    provider = OpenAICompatibleProvider("https://inference.example/v1", "test-only-key", "configured-test-model",
        transport=httpx.MockTransport(lambda request: httpx.Response(upstream_status, text="secret upstream body")))
    with pytest.raises(CompilerError) as error:
        provider.generate("Return JSON", {})
    assert error.value.status_code == expected
    assert "secret upstream body" not in str(error.value)


@pytest.mark.parametrize("body", [
    {}, {"choices": []}, {"choices": [{"finish_reason": "length", "message": {"content": "{}"}}]},
    {"choices": [{"finish_reason": "stop", "message": {"content": None, "refusal": "No"}}]},
    {"choices": ["not an object"]},
    {"choices": [{"finish_reason": "stop", "message": []}]},
    {"choices": [{"finish_reason": "stop", "message": "not an object"}]},
])
def test_malformed_provider_responses_are_rejected(body):
    provider = OpenAICompatibleProvider("https://inference.example/v1", "test-only-key", "configured-test-model",
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=body)))
    with pytest.raises(CompilerError, match="malformed"):
        provider.generate("Return JSON", {})


def test_timeout_returns_explicit_error():
    def handler(request):
        raise httpx.ReadTimeout("private diagnostic", request=request)
    provider = OpenAICompatibleProvider("https://inference.example/v1", "test-only-key", "configured-test-model",
                                        transport=httpx.MockTransport(handler))
    with pytest.raises(CompilerError) as error:
        provider.generate("Return JSON", {})
    assert error.value.status_code == 504
    assert "private diagnostic" not in str(error.value)


def test_unknown_sessions_and_resources_return_404(tmp_path):
    with TestClient(create_app(tmp_path / "events.sqlite3", llm_provider=TestOnlyProvider())) as client:
        assert client.post("/api/skills/compile", json={"session_id": "absent", "task_description": "Review a reference"}).status_code == 404
        assert client.get("/api/skill-drafts/absent").status_code == 404
        assert client.get("/api/skills/absent").status_code == 404
        assert client.post("/api/skill-drafts/absent/confirm", json={
            "confirmed": True, "skill": make_test_draft([
                {"id": 1, "url": "http://127.0.0.1:5173/"},
                {"id": 2, "target": {}, "value": "REF-81001"}, {"id": 3, "target": {}}, {"id": 4, "target": {}},
            ]),
        }).status_code == 404


@pytest.mark.parametrize("output", ["not json", "```json\n{}\n```", "[]", "{}"])
def test_invalid_json_drafts_are_not_repaired_or_substituted(tmp_path, output):
    class InvalidResponseProvider:
        model = "test-only-response-not-real-inference"

        def generate(self, system_prompt, user_payload):
            return output

    with TestClient(create_app(tmp_path / "events.sqlite3", llm_provider=InvalidResponseProvider())) as client:
        seed_recording(client)
        response = client.post("/api/skills/compile", json={
            "session_id": "test-recording", "task_description": "Review a reference",
        })
        assert response.status_code == 502


def test_recording_limit_never_silently_truncates_or_calls_provider(tmp_path):
    provider = TestOnlyProvider()
    with TestClient(create_app(tmp_path / "events.sqlite3", llm_provider=provider)) as client:
        events = seed_recording(client)
        # Bulk insert through the same database format, without 500 unnecessary HTTP requests.
        repeated = {key: value for key, value in events[-1].items() if key != "id"}
        with sqlite3.connect(tmp_path / "events.sqlite3") as connection:
            connection.executemany("INSERT INTO events (session_id, payload) VALUES (?, ?)",
                                   [("test-recording", json.dumps(repeated))] * 497)
        response = client.post("/api/skills/compile", json={
            "session_id": "test-recording", "task_description": "Review a reference",
        })
        assert response.status_code == 413
        assert provider.payloads == []


def test_complete_http_provider_api_flow_with_test_only_transport(tmp_path):
    def handler(request):
        payload = json.loads(json.loads(request.content)["messages"][1]["content"])
        content = json.dumps(make_test_draft(payload["events"]))
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {"content": content}}]})
    provider = OpenAICompatibleProvider("https://inference.example/v1", "test-only-key", "configured-test-model",
                                        transport=httpx.MockTransport(handler))
    with TestClient(create_app(tmp_path / "events.sqlite3", llm_provider=provider)) as client:
        events = seed_recording(client)
        response = client.post("/api/skills/compile", json={
            "session_id": "test-recording", "task_description": "Review a reference",
        })
        assert response.status_code == 201
        assert response.json()["source_event_ids"] == [event["id"] for event in events]


@pytest.mark.parametrize("url", ["http://inference.example/v1", "https://key@inference.example/v1", "https://inference.example/v1?key=secret",
                                 "https://[invalid/v1", "https://inference.example:invalid/v1", "https://inference.example:99999/v1",
                                 "http://127.0.0.2:11434/v1", "http://0.0.0.0:11434/v1", "http://[::1]:11434/v1",
                                 "http://localhost.evil.example:11434/v1", "http://127.0.0.1.evil.example/v1",
                                 "http://key@localhost:11434/v1", "http://localhost:11434/v1?key=secret"])
def test_cloud_base_url_rejects_plaintext_and_embedded_credentials(url):
    with pytest.raises(CompilerError, match="HTTPS API base URL"):
        OpenAICompatibleProvider(url, "test-only-key", "configured-test-model")


@pytest.mark.parametrize("base_url", ["http://127.0.0.1:11434/v1", "http://localhost:11434/v1/"])
def test_explicit_loopback_http_endpoints_use_real_provider_protocol(base_url):
    def handler(request):
        assert str(request.url) == base_url.rstrip("/") + "/chat/completions"
        assert request.headers["authorization"] == "Bearer ollama"
        assert json.loads(request.content)["model"] == "configured-local-model"
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {"content": "{}"}}]})
    provider = OpenAICompatibleProvider(base_url, "ollama", "configured-local-model",
                                        transport=httpx.MockTransport(handler))
    assert provider.generate("Return JSON", {}) == "{}"


def test_ambiguous_targets_require_explicit_uncertainty(tmp_path):
    provider = TestOnlyProvider()
    with TestClient(create_app(tmp_path / "events.sqlite3", llm_provider=provider)) as client:
        events = seed_recording(client)
        target = events[-1]["target"]
        target["selector"] = None
        target["locator_candidates"] = [{"strategy": "role", "value": "button", "name": "Save", "match_count": 3}]
        with sqlite3.connect(tmp_path / "events.sqlite3") as connection:
            updated = {key: value for key, value in events[-1].items() if key != "id"}
            connection.execute("UPDATE events SET payload = ? WHERE id = ?", (json.dumps(updated), events[-1]["id"]))
        payload = {"session_id": "test-recording", "task_description": "Save a reference"}
        assert client.post("/api/skills/compile", json=payload).status_code == 502
        provider.mutate = lambda draft: draft["steps"][-1].update(uncertainty="Three buttons match; human must choose the intended target.")
        assert client.post("/api/skills/compile", json=payload).status_code == 201


def test_legacy_recording_without_new_metadata_can_compile(tmp_path):
    class LegacyTestProvider:
        model = "test-only-response-not-real-inference"

        def generate(self, system_prompt, user_payload):
            event = user_payload["events"][0]
            return json.dumps({
                "name": "Save", "description": "Proposed workflow from a legacy click event",
                "steps": [{"action": "click", "source_event_id": event["id"], "description": "Save",
                           "target": event["target"]}], "variables": [], "omitted_events": [],
                "uncertainties": ["No evidence of a successful outcome."],
                "success_conditions": [{"description": "Human checks that saving succeeded.",
                                        "requires_human_verification": True}],
            })
    with TestClient(create_app(tmp_path / "events.sqlite3", llm_provider=LegacyTestProvider())) as client:
        payload = {"session_id": "legacy", "timestamp": "2026-10-09T12:00:00Z",
                   "url": "http://127.0.0.1:5173/", "action": "click",
                   "target": {"tag": "button", "role": "button", "label": "Save", "selector": "#save"}}
        recorded = client.post("/api/events", json=payload).json()
        response = client.post("/api/skills/compile", json={"session_id": "legacy", "task_description": "Save"})
        assert response.status_code == 201
        assert response.json()["skill"]["steps"][0]["target"] == payload["target"]
        assert client.get("/api/events/legacy").json() == [recorded]


def test_ollama_schema_request_and_complete_json_reasoning_compatibility():
    schema = {"type": "object", "properties": {"status": {"const": "ok"}}}
    def handler(request):
        body = json.loads(request.content)
        assert body["reasoning_effort"] == "none"
        assert body["temperature"] == 0
        assert body["max_tokens"] == 8192
        assert body["response_format"] == {
            "type": "json_schema", "json_schema": {"name": "skill_draft", "strict": True, "schema": schema},
        }
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {
            "content": "", "reasoning": '{"status":"ok"}',
        }}]})
    provider = OllamaCompatibleProvider("http://127.0.0.1:11434/v1", "ollama", "configured-local-model",
                                       transport=httpx.MockTransport(handler))
    assert provider.generate("Return JSON", {"skill_draft_json_schema": schema}) == '{"status":"ok"}'


@pytest.mark.parametrize("reasoning, finish_reason", [
    ('Here is the result: {"status":"ok"}', "stop"), ('{"status":', "stop"),
    ('{"status":"ok"}', "length"), ('[]', "stop"), ('null', "stop"),
])
def test_ollama_never_repairs_prose_or_accepts_incomplete_reasoning(reasoning, finish_reason):
    provider = OllamaCompatibleProvider("http://127.0.0.1:11434/v1", "ollama", "configured-local-model",
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"choices": [{
            "finish_reason": finish_reason, "message": {"content": "", "reasoning": reasoning},
        }]})))
    with pytest.raises(CompilerError) as error:
        provider.generate("Return JSON", {})
    assert error.value.status_code == 502


def test_cloud_provider_does_not_accept_reasoning_as_the_answer():
    provider = OpenAICompatibleProvider("https://inference.example/v1", "test-only-key", "configured-test-model",
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"choices": [{
            "finish_reason": "stop", "message": {"content": "", "reasoning": '{"status":"ok"}'},
        }]})))
    with pytest.raises(CompilerError):
        provider.generate("Return JSON", {})


@pytest.mark.parametrize("invented", [False, True])
def test_ollama_reasoning_drafts_use_the_same_schema_and_evidence_checks(tmp_path, invented):
    def handler(request):
        payload = json.loads(json.loads(request.content)["messages"][1]["content"])
        draft = make_test_draft(payload["events"])
        if invented:
            draft["steps"][-1]["target"]["selector"] = "#invented"
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {
            "content": "", "reasoning": json.dumps(draft),
        }}]})
    provider = OllamaCompatibleProvider("http://127.0.0.1:11434/v1", "ollama", "configured-local-model",
                                       transport=httpx.MockTransport(handler))
    path = tmp_path / "events.sqlite3"
    with TestClient(create_app(path, llm_provider=provider)) as client:
        seed_recording(client)
        response = client.post("/api/skills/compile", json={
            "session_id": "test-recording", "task_description": "Review a reference",
        })
        assert response.status_code == (502 if invented else 201)
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM skill_drafts").fetchone()[0] == (0 if invented else 1)


def test_ollama_profile_is_explicit_local_configuration(tmp_path, monkeypatch):
    for name in ("SHADOWOPS_LLM_PROVIDER", "SHADOWOPS_LLM_BASE_URL", "SHADOWOPS_LLM_API_KEY", "SHADOWOPS_LLM_MODEL"):
        monkeypatch.delenv(name, raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("SHADOWOPS_LLM_PROVIDER=ollama\nSHADOWOPS_LLM_BASE_URL=http://127.0.0.1:11434/v1\n"
                        "SHADOWOPS_LLM_API_KEY=ollama\nSHADOWOPS_LLM_MODEL=configured-local-model\n", encoding="utf-8")
    provider = OpenAICompatibleProvider.from_environment(env_file)
    assert isinstance(provider, OllamaCompatibleProvider)
    assert provider.timeout_seconds == 300
    monkeypatch.setenv("SHADOWOPS_LLM_PROVIDER", "openai")
    monkeypatch.setenv("SHADOWOPS_LLM_BASE_URL", "https://inference.example/v1")
    assert type(OpenAICompatibleProvider.from_environment(env_file)) is OpenAICompatibleProvider
    monkeypatch.setenv("SHADOWOPS_LLM_PROVIDER", "unsupported")
    with pytest.raises(CompilerError, match="SHADOWOPS_LLM_PROVIDER"):
        OpenAICompatibleProvider.from_environment(env_file)


def test_ollama_mode_rejects_remote_hosts():
    with pytest.raises(CompilerError, match="restricted"):
        OllamaCompatibleProvider("https://remote.example/v1", "ollama", "configured-local-model")
