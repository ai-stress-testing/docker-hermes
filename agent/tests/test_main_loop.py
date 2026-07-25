import httpx
import pytest

import agent.main as main_mod
from agent.config import Config


def _config(tmp_path, **overrides):
    defaults = dict(
        lmstudio_url="http://fake-lmstudio/v1",
        model_name="local-model",
        workspace_dir=str(tmp_path),
        max_iterations=3,
        request_timeout=5.0,
        task_prompt="do the thing",
    )
    defaults.update(overrides)
    return Config(**defaults)


def _patch_client(monkeypatch, transport):
    """Make agent.main's `httpx.Client(...)` construction use a MockTransport
    instead of hitting real network, regardless of the kwargs run() passes.

    `main_mod.httpx` is the very same module object as the `httpx` imported
    in this test file, so the replacement below must be built from the
    *original* Client class captured before patching — otherwise the
    replacement closes over the (already patched) `httpx.Client` name and
    recurses into itself.
    """
    real_client_cls = httpx.Client
    monkeypatch.setattr(
        main_mod.httpx,
        "Client",
        lambda **kwargs: real_client_cls(transport=transport, timeout=kwargs.get("timeout")),
    )


def _chat_response(content: str) -> httpx.Response:
    return httpx.Response(
        200,
        json={"choices": [{"message": {"role": "assistant", "content": content}}]},
    )


# --- Final answer / zero tool calls -------------------------------------


def test_final_answer_with_no_tool_calls_returns_zero(monkeypatch, tmp_path, capsys):
    def handler(request):
        return _chat_response("The final answer is 42.")

    _patch_client(monkeypatch, httpx.MockTransport(handler))
    exit_code = main_mod.run(_config(tmp_path))
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "The final answer is 42." in out


# --- Iteration limit -------------------------------------------------


def test_iteration_limit_reached_returns_nonzero(monkeypatch, tmp_path, capsys):
    def handler(request):
        # The model keeps calling a tool forever and never gives a final answer.
        return _chat_response(
            '<tool_call>{"name": "list_files", "arguments": {"path": "."}}</tool_call>'
        )

    _patch_client(monkeypatch, httpx.MockTransport(handler))
    exit_code = main_mod.run(_config(tmp_path, max_iterations=2))
    assert exit_code == 1
    out = capsys.readouterr().out
    assert "iteration limit reached" in out.lower()


def test_loop_bounded_even_with_malformed_replies(monkeypatch, tmp_path):
    # Malformed tool_call JSON must not crash the harness and must still
    # count against MAX_ITERATIONS.
    call_count = {"n": 0}

    def handler(request):
        call_count["n"] += 1
        return _chat_response("<tool_call>{not valid json</tool_call>")

    _patch_client(monkeypatch, httpx.MockTransport(handler))
    exit_code = main_mod.run(_config(tmp_path, max_iterations=3))
    assert exit_code == 1
    assert call_count["n"] == 3


# --- Malformed tool call self-correction --------------------------------


def test_malformed_tool_call_then_final_answer(monkeypatch, tmp_path, capsys):
    responses = [
        "<tool_call>{bad json</tool_call>",
        "All good now, here is your answer.",
    ]
    seen_requests = []

    def handler(request):
        seen_requests.append(request)
        content = responses[len(seen_requests) - 1]
        return _chat_response(content)

    _patch_client(monkeypatch, httpx.MockTransport(handler))
    exit_code = main_mod.run(_config(tmp_path, max_iterations=5))
    assert exit_code == 0
    assert "All good now" in capsys.readouterr().out
    # The second request should carry the tool_response error back to the model.
    assert len(seen_requests) == 2


# --- Unknown tool name ---------------------------------------------------


def test_unknown_tool_name_reports_error_and_continues(monkeypatch, tmp_path):
    responses = [
        '<tool_call>{"name": "delete_everything", "arguments": {}}</tool_call>',
        "done",
    ]
    call_count = {"n": 0}

    def handler(request):
        content = responses[call_count["n"]]
        call_count["n"] += 1
        return _chat_response(content)

    _patch_client(monkeypatch, httpx.MockTransport(handler))
    exit_code = main_mod.run(_config(tmp_path, max_iterations=5))
    assert exit_code == 0
    assert call_count["n"] == 2


# --- Timeout / connection failure handling --------------------------------


def test_timeout_stops_loop_and_reports_error(monkeypatch, tmp_path, capsys):
    def handler(request):
        raise httpx.TimeoutException("simulated timeout", request=request)

    _patch_client(monkeypatch, httpx.MockTransport(handler))
    exit_code = main_mod.run(_config(tmp_path, request_timeout=0.5))
    assert exit_code == 1
    err = capsys.readouterr().err
    assert "timed out" in err.lower()


def test_connect_error_stops_loop_and_reports_error(monkeypatch, tmp_path, capsys):
    def handler(request):
        raise httpx.ConnectError("simulated connection failure", request=request)

    _patch_client(monkeypatch, httpx.MockTransport(handler))
    exit_code = main_mod.run(_config(tmp_path))
    assert exit_code == 1
    err = capsys.readouterr().err
    assert "could not connect" in err.lower()


def test_missing_task_prompt_returns_usage_error(tmp_path, capsys):
    config = _config(tmp_path, task_prompt="")
    exit_code = main_mod.run(config)
    assert exit_code == 2
    assert "no task provided" in capsys.readouterr().err.lower()
