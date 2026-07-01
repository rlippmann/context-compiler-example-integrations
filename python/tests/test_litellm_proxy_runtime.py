import json
import os
import shutil
import socket
import socketserver
import subprocess
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import httpx
import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
RUN_RUNTIME_ENV_VAR = "RUN_LITELLM_PROXY_RUNTIME"
CALLBACK_PATH = (
    "python.reference_integrations.litellm_proxy."
    "context_compiler_precall_hook.proxy_handler_instance"
)
PROXY_MODEL_NAME = "proxy-test-model"
UPSTREAM_MODEL_NAME = "openai/test-upstream"

pytestmark = pytest.mark.skipif(
    os.getenv(RUN_RUNTIME_ENV_VAR) != "1",
    reason=(
        f"Opt-in LiteLLM Proxy runtime smoke test. Set {RUN_RUNTIME_ENV_VAR}=1 to run."
    ),
)


class _OpenAICompatibleStubServer(HTTPServer):
    """Capture proxied requests and return a minimal completion response."""

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


class _ProxyRuntime:
    def __init__(self, process: subprocess.Popen[str], port: int) -> None:
        self.process = process
        self.port = port

    def stop(self) -> None:
        if self.process.poll() is not None:
            return
        self.process.terminate()
        try:
            self.process.wait(timeout=10)
        except subprocess.TimeoutExpired as exc:
            self.process.kill()
            self.process.wait(timeout=5)
            raise AssertionError(
                "LiteLLM Proxy subprocess did not shut down cleanly."
            ) from exc


@pytest.fixture
def litellm_runtime_stub() -> _ThreadedStubServer:
    server = _ThreadedStubServer()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.fixture
def litellm_proxy_runtime(
    tmp_path: Path, litellm_runtime_stub: _ThreadedStubServer
) -> _ProxyRuntime:
    del tmp_path
    litellm_executable = shutil.which("litellm")
    if litellm_executable is None:
        pytest.fail("LiteLLM CLI is not installed in the active environment.")

    proxy_port = _reserve_local_port()
    config_path = REPO_ROOT / f".litellm_runtime_config_{uuid.uuid4().hex}.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "model_list": [
                    {
                        "model_name": PROXY_MODEL_NAME,
                        "litellm_params": {
                            "model": UPSTREAM_MODEL_NAME,
                            "api_base": (
                                f"http://127.0.0.1:{litellm_runtime_stub.server_port}/v1"
                            ),
                            "api_key": "test-key",
                        },
                    }
                ],
                "litellm_settings": {"callbacks": [CALLBACK_PATH]},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT) + os.pathsep + env.get("PYTHONPATH", "")

    process = subprocess.Popen(
        [
            litellm_executable,
            "--config",
            str(config_path),
            "--host",
            "127.0.0.1",
            "--port",
            str(proxy_port),
            "--num_workers",
            "1",
        ],
        cwd=REPO_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    runtime = _ProxyRuntime(process, port=proxy_port)
    try:
        _wait_for_proxy_startup(proxy_port, process)
        litellm_runtime_stub.captured_requests.clear()
        yield runtime
    finally:
        runtime.stop()
        config_path.unlink(missing_ok=True)


def test_litellm_proxy_runtime_blocks_confirmation_before_upstream(
    litellm_proxy_runtime: _ProxyRuntime, litellm_runtime_stub: _ThreadedStubServer
) -> None:
    response = _post_chat_completion(
        port=litellm_proxy_runtime.port,
        messages=[{"role": "user", "content": "use kubectl instead of docker"}],
    )

    assert response.status_code == 400
    assert "Did you mean to use" in response.text
    assert litellm_runtime_stub.captured_requests == []


def test_litellm_proxy_runtime_forwards_allowed_request_with_contract(
    litellm_proxy_runtime: _ProxyRuntime, litellm_runtime_stub: _ThreadedStubServer
) -> None:
    original_messages = [
        {"role": "user", "content": "prohibit peanuts"},
        {"role": "user", "content": "what snack should I bring?"},
    ]

    response = _post_chat_completion(
        port=litellm_proxy_runtime.port, messages=original_messages
    )

    assert response.status_code == 200
    assert response.json()["choices"][0]["message"]["content"] == "stubbed reply"
    assert len(litellm_runtime_stub.captured_requests) == 1

    forwarded_payload = litellm_runtime_stub.captured_requests[0]
    forwarded_messages = forwarded_payload["messages"]
    assert isinstance(forwarded_messages, list)
    assert len(forwarded_messages) == len(original_messages) + 1

    contract_messages = [
        message
        for message in forwarded_messages
        if isinstance(message, dict)
        and message.get("role") == "system"
        and "Host policy contract:" in str(message.get("content"))
    ]
    assert len(contract_messages) == 1
    assert "peanuts" in str(contract_messages[0]["content"])
    assert forwarded_messages[1:] == original_messages


def _post_chat_completion(port: int, messages: list[dict[str, str]]) -> httpx.Response:
    with httpx.Client(timeout=10.0) as client:
        return client.post(
            f"http://127.0.0.1:{port}/v1/chat/completions",
            headers={"Authorization": "Bearer anything"},
            json={"model": PROXY_MODEL_NAME, "messages": messages},
        )


def _reserve_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_proxy_startup(port: int, process: subprocess.Popen[str]) -> None:
    deadline = time.time() + 20
    last_error = ""

    while time.time() < deadline:
        if process.poll() is not None:
            output = process.stdout.read() if process.stdout is not None else ""
            pytest.fail(
                f"LiteLLM Proxy exited before startup completed.\nOutput:\n{output}"
            )

        try:
            response = httpx.get(f"http://127.0.0.1:{port}/health", timeout=1.0)
            if response.status_code == 200:
                return
            last_error = f"health returned {response.status_code}: {response.text}"
        except Exception as exc:
            last_error = str(exc)

        time.sleep(0.25)

    runtime_output = ""
    if process.stdout is not None:
        try:
            runtime_output = process.stdout.read()
        except Exception:
            runtime_output = ""
    pytest.fail(
        "Timed out waiting for LiteLLM Proxy startup.\n"
        f"Last error: {last_error}\n"
        f"Output:\n{runtime_output}"
    )
