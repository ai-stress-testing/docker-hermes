"""Entrypoint for the Hermes tool-calling agent harness.

Runnable as `python -m agent.main "task text"` (works regardless of whether
the process cwd/WORKDIR is the repo root or `agent/`, since this module only
uses relative imports within the `agent` package and reads all config from
the environment).

Exit codes:
  0  - clean final answer produced.
  1  - unrecoverable error (LM Studio unreachable/timeout, bad response shape)
       or the iteration cap was hit without a final answer.
  2  - usage error (no task provided via CLI arg or TASK_PROMPT).

stdout carries only the human-readable final answer (or the iteration-limit
partial output). Per-iteration progress lines go to stderr so stdout stays
clean for scripting/piping.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from typing import Any

import httpx

from agent.config import Config, load_config
from agent.hermes_protocol import (
    format_tool_error_response,
    format_tool_response,
    has_tool_calls,
    parse_tool_calls,
)
from agent.prompt import build_system_prompt
from agent.tools import TOOL_FUNCTIONS

logger = logging.getLogger("agent")


class LMStudioError(Exception):
    """Raised for any unrecoverable problem talking to LM Studio (timeout,
    connection failure, HTTP error, or an unexpected response shape).
    """


def _setup_logging() -> None:
    level = logging.DEBUG if os.environ.get("LOG_LEVEL", "").upper() == "DEBUG" else logging.INFO
    logging.basicConfig(stream=sys.stderr, level=level, format="%(message)s")


def call_lmstudio(client: httpx.Client, config: Config, messages: list[dict[str, Any]]) -> str:
    """POST the conversation to LM Studio's OpenAI-compatible chat completions
    endpoint and return the assistant's reply text. Never logs full request
    or response bodies unless LOG_LEVEL=DEBUG.
    """
    url = config.lmstudio_url.rstrip("/") + "/chat/completions"
    body = {"model": config.model_name, "messages": messages}
    logger.debug("POST %s body=%r", url, body)

    try:
        resp = client.post(url, json=body, timeout=config.request_timeout)
    except httpx.TimeoutException as exc:
        raise LMStudioError(
            f"request to LM Studio timed out after {config.request_timeout}s: {exc}"
        ) from exc
    except httpx.ConnectError as exc:
        raise LMStudioError(
            f"could not connect to LM Studio at {config.lmstudio_url}: {exc}"
        ) from exc
    except httpx.HTTPError as exc:
        raise LMStudioError(f"HTTP error talking to LM Studio: {exc}") from exc

    if resp.status_code >= 400:
        raise LMStudioError(f"LM Studio returned HTTP {resp.status_code}: {resp.text[:500]}")

    try:
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise LMStudioError(f"unexpected response shape from LM Studio: {exc}") from exc

    logger.debug("response content=%r", content)
    return content or ""


def _summarize_arguments(arguments: dict[str, Any]) -> str:
    """A terse, content-free summary of tool arguments for the stderr log
    line — deliberately omits `content` so file bodies never hit the logs
    at default verbosity.
    """
    parts = []
    for key, value in arguments.items():
        if key == "content":
            parts.append(f"content=<{len(value) if isinstance(value, str) else '?'} chars>")
        else:
            parts.append(f"{key}={value!r}")
    return ", ".join(parts)


def _execute_tool_call(config: Config, iteration: int, request) -> str:
    """Run one parsed tool call and return the <tool_response> string to
    append to the conversation. Never raises — tool/argument errors are
    turned into an error tool_response so the model can self-correct.
    """
    if not request.ok:
        logger.info("[iter %d] tool_call: <malformed> (%s)", iteration, request.error)
        return format_tool_error_response(request.name, request.error)

    func = TOOL_FUNCTIONS.get(request.name)
    if func is None:
        error = f"unknown tool: {request.name!r}"
        logger.info("[iter %d] tool_call: %s(...) -> %s", iteration, request.name, error)
        return format_tool_error_response(request.name, error)

    logger.info(
        "[iter %d] tool_call: %s(%s)",
        iteration,
        request.name,
        _summarize_arguments(request.arguments),
    )

    try:
        result = func(config.workspace_dir, **request.arguments)
    except TypeError as exc:
        result = {"error": f"invalid arguments for {request.name}: {exc}"}
    except Exception as exc:  # a bug in a tool must not crash the harness
        result = {"error": f"unexpected error running {request.name}: {exc}"}

    if isinstance(result, dict) and "error" in result:
        return format_tool_error_response(request.name, result["error"])
    return format_tool_response(request.name, result)


def run(config: Config) -> int:
    if not config.task_prompt or not config.task_prompt.strip():
        print(
            "Error: no task provided. Pass it as a CLI argument "
            "(python -m agent.main \"task text\") or set TASK_PROMPT.",
            file=sys.stderr,
        )
        return 2

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": build_system_prompt()},
        {"role": "user", "content": config.task_prompt},
    ]

    last_reply = ""
    with httpx.Client(timeout=config.request_timeout) as client:
        for iteration in range(1, config.max_iterations + 1):
            try:
                reply_text = call_lmstudio(client, config, messages)
            except LMStudioError as exc:
                print(f"Error communicating with LM Studio: {exc}", file=sys.stderr)
                return 1

            last_reply = reply_text
            messages.append({"role": "assistant", "content": reply_text})

            if not has_tool_calls(reply_text):
                print(reply_text)
                return 0

            tool_requests = parse_tool_calls(reply_text)
            response_blocks = [
                _execute_tool_call(config, iteration, request) for request in tool_requests
            ]
            # Portability note: OpenAI's `tool` role isn't reliably honored
            # by every LM Studio backend/model, so the tool result is sent
            # back as a `user`-role message containing <tool_response> tags
            # instead — this is the documented Hermes-format convention and
            # works across backends without relying on role support.
            messages.append({"role": "user", "content": "\n".join(response_blocks)})

    print(
        f"[iteration limit reached] No final answer was produced within "
        f"MAX_ITERATIONS={config.max_iterations}. Last model output:\n{last_reply}"
    )
    return 1


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    parser = argparse.ArgumentParser(
        prog="agent.main", description="Hermes function-calling agent harness"
    )
    parser.add_argument(
        "task",
        nargs="*",
        help="Task/goal for the agent (overrides TASK_PROMPT env var if given)",
    )
    args = parser.parse_args(argv)
    cli_task = " ".join(args.task).strip() if args.task else None

    config = load_config(cli_task=cli_task)
    _setup_logging()
    return run(config)


if __name__ == "__main__":
    sys.exit(main())
