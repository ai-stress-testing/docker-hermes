"""Environment-variable configuration for the Hermes tool-calling harness.

Everything here is read lazily via `os.environ.get` with sane defaults so the
harness can be reconfigured purely through the environment (no code changes,
no config files) — this matches the "one-shot `docker compose run agent`"
deployment model described in the interface contract.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


def _get_float(name: str, default: float) -> float:
    """Parse a float env var, tolerating int-looking strings ("60" as well
    as "60.0"). Falls back to the default on anything unparsable rather than
    raising, so a typo'd env var degrades gracefully instead of crashing the
    container at startup.
    """
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _get_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class Config:
    lmstudio_url: str
    model_name: str
    workspace_dir: str
    max_iterations: int
    request_timeout: float
    task_prompt: str


def load_config(cli_task: str | None = None) -> Config:
    """Build the runtime config from the environment, with an optional CLI
    task string that takes precedence over `TASK_PROMPT` when both are set.
    """
    task_prompt = cli_task if cli_task else os.environ.get("TASK_PROMPT", "")
    return Config(
        lmstudio_url=os.environ.get(
            "LMSTUDIO_URL", "http://host.docker.internal:1234/v1"
        ),
        model_name=os.environ.get("MODEL_NAME", "local-model"),
        workspace_dir=os.environ.get("WORKSPACE_DIR", "/workspace"),
        max_iterations=_get_int("MAX_ITERATIONS", 10),
        request_timeout=_get_float("REQUEST_TIMEOUT", 60.0),
        task_prompt=task_prompt,
    )
