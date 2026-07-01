import json
import socketserver
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from types import SimpleNamespace

import pytest
from context_compiler import create_engine

from python.examples.schema_selection.litellm_response_format.response_format import (
    ACTION_PLAN_RESPONSE_FORMAT,
    COMPACT_SUMMARY_RESPONSE_FORMAT,
    optional_litellm_call,
    plan_turn,
)


class _OpenAICompatibleStubServer(HTTPServer):
    """Capture one LiteLLM request and return a minimal chat completion."""

    def __init__(self) -> None:
        super().__init__(("127.0.0.1", 0), _OpenAICompatibleStubHandler)
        self.captured_requests: list[dict[str, object]] = []


class _OpenAICompatibleStubHandler(BaseHTTPRequestHandler):
    server: _OpenAICompatibleStubServer

    def do_POST(self) -> None:  # noqa: N802
        content_length = int(self.headers.get("Content-Length", "0"))
        request_body = self.rfile.read(content_length)
        self.server.captured_requests.append(json.loads(request_body.decode("utf-8")))

        response = {
            "id": "chatcmpl-stub",
            "object": "chat.completion",
            "created": 0,
            "model": "stub-model",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "stubbed reply"},
                    "finish_reason": "stop",
                }
            ],
        }
        encoded = json.dumps(response).encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format: str, *args: object) -> None:
        del format, args


class _ThreadedStubServer(socketserver.ThreadingMixIn, _OpenAICompatibleStubServer):
    daemon_threads = True
    allow_reuse_address = True


@pytest.fixture
def litellm_runtime_stub():
    server = _ThreadedStubServer()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_no_matching_policy_selects_no_response_format() -> None:
    plan = plan_turn("Summarize this.", create_engine())

    assert plan["decision_kind"] == "passthrough"
    assert plan["selected_response_format_item"] is None
    assert plan["response_format"] is None


def test_use_compact_summary_selects_compact_summary_response_format() -> None:
    engine = create_engine()
    engine.step("use compact_summary")

    plan = plan_turn("Summarize this.", engine)

    assert plan["selected_response_format_item"] == "compact_summary"
    assert plan["response_format"] == COMPACT_SUMMARY_RESPONSE_FORMAT


def test_use_action_plan_selects_action_plan_response_format() -> None:
    engine = create_engine()
    engine.step("use action_plan")

    plan = plan_turn("What should I do next?", engine)

    assert plan["selected_response_format_item"] == "action_plan"
    assert plan["response_format"] == ACTION_PLAN_RESPONSE_FORMAT


def test_prohibit_compact_summary_selects_no_response_format() -> None:
    engine = create_engine()
    engine.step("prohibit compact_summary")

    plan = plan_turn("Summarize this.", engine)

    assert plan["selected_response_format_item"] is None
    assert plan["response_format"] is None


def test_contradiction_clarify_path_selects_no_schema() -> None:
    engine = create_engine()
    engine.step("use compact_summary")

    plan = plan_turn("prohibit compact_summary", engine)

    assert plan["decision_kind"] == "clarify"
    assert plan["selected_response_format_item"] is None
    assert plan["response_format"] is None


def test_optional_litellm_call_preserves_selected_response_format(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, object]] = []

    def fake_completion(**kwargs):
        calls.append(kwargs)
        return {"choices": [{"message": {"content": "stubbed reply"}}]}

    monkeypatch.setattr(
        "python.examples.schema_selection.litellm_response_format.response_format._get_litellm_completion",
        lambda: fake_completion,
    )
    monkeypatch.setattr(
        "python.examples.schema_selection.litellm_response_format.response_format.resolve_provider_config",
        lambda default_model: SimpleNamespace(
            model=default_model,
            base_url="https://example.invalid/v1",
            api_key="test-key",
        ),
    )
    monkeypatch.setattr(
        "python.examples.schema_selection.litellm_response_format.response_format.print_startup_config",
        lambda config: None,
    )

    reply = optional_litellm_call(
        user_input="Summarize this.",
        response_format=COMPACT_SUMMARY_RESPONSE_FORMAT,
    )

    assert reply == "stubbed reply"
    assert calls[0]["response_format"] == COMPACT_SUMMARY_RESPONSE_FORMAT


def test_optional_litellm_call_omits_response_format_when_none_selected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, object]] = []

    def fake_completion(**kwargs):
        calls.append(kwargs)
        return {"choices": [{"message": {"content": "stubbed reply"}}]}

    monkeypatch.setattr(
        "python.examples.schema_selection.litellm_response_format.response_format._get_litellm_completion",
        lambda: fake_completion,
    )
    monkeypatch.setattr(
        "python.examples.schema_selection.litellm_response_format.response_format.resolve_provider_config",
        lambda default_model: SimpleNamespace(
            model=default_model,
            base_url="https://example.invalid/v1",
            api_key="test-key",
        ),
    )
    monkeypatch.setattr(
        "python.examples.schema_selection.litellm_response_format.response_format.print_startup_config",
        lambda config: None,
    )

    reply = optional_litellm_call(user_input="Summarize this.", response_format=None)

    assert reply == "stubbed reply"
    assert "response_format" not in calls[0]


def test_litellm_runtime_sends_selected_response_format(
    monkeypatch: pytest.MonkeyPatch,
    litellm_runtime_stub: _ThreadedStubServer,
) -> None:
    engine = create_engine()
    engine.step("use compact_summary")
    plan = plan_turn("Summarize this.", engine)

    assert plan["selected_response_format_item"] == "compact_summary"
    assert plan["response_format"] == COMPACT_SUMMARY_RESPONSE_FORMAT

    monkeypatch.setattr(
        "python.examples.schema_selection.litellm_response_format.response_format.resolve_provider_config",
        lambda default_model: SimpleNamespace(
            model=default_model,
            base_url=f"http://127.0.0.1:{litellm_runtime_stub.server_port}/v1",
            api_key="test-key",
        ),
    )
    monkeypatch.setattr(
        "python.examples.schema_selection.litellm_response_format.response_format.print_startup_config",
        lambda config: None,
    )

    reply = optional_litellm_call(
        user_input="Summarize this.",
        response_format=plan["response_format"],
    )

    assert reply == "stubbed reply"
    assert len(litellm_runtime_stub.captured_requests) == 1
    request_payload = litellm_runtime_stub.captured_requests[0]
    assert request_payload["response_format"] == COMPACT_SUMMARY_RESPONSE_FORMAT


def test_litellm_runtime_omits_response_format_when_unselected(
    monkeypatch: pytest.MonkeyPatch,
    litellm_runtime_stub: _ThreadedStubServer,
) -> None:
    plan = plan_turn("Summarize this.", create_engine())

    assert plan["selected_response_format_item"] is None
    assert plan["response_format"] is None

    monkeypatch.setattr(
        "python.examples.schema_selection.litellm_response_format.response_format.resolve_provider_config",
        lambda default_model: SimpleNamespace(
            model=default_model,
            base_url=f"http://127.0.0.1:{litellm_runtime_stub.server_port}/v1",
            api_key="test-key",
        ),
    )
    monkeypatch.setattr(
        "python.examples.schema_selection.litellm_response_format.response_format.print_startup_config",
        lambda config: None,
    )

    reply = optional_litellm_call(
        user_input="Summarize this.",
        response_format=plan["response_format"],
    )

    assert reply == "stubbed reply"
    assert len(litellm_runtime_stub.captured_requests) == 1
    request_payload = litellm_runtime_stub.captured_requests[0]
    assert "response_format" not in request_payload
