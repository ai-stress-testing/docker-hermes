"""The three sandboxed file tools plus the path-safety boundary they share.

This module is the actual security boundary described in the spec: every
tool call the model makes is treated as adversarial input (prompt injection,
path traversal, symlink tricks) and must be contained to `WORKSPACE_DIR`.

Path-safety strategy (see `resolve_safe_path`):
  1. Fast rejection of absolute paths and literal ".." path components,
     before doing any filesystem work.
  2. The actual defense: resolve the candidate path with `Path.resolve()`
     (which follows symlinks) and require the result to be equal to, or a
     proper descendant of, the resolved workspace root. This is what catches
     a symlink created *inside* the workspace by an earlier tool call that
     points back out to the host filesystem — string-prefix checks alone
     (e.g. `str(candidate).startswith(str(workspace_root))`) are not safe,
     since "/workspace-evil" startswith "/workspace" but is not inside it;
     we use `Path.relative_to` on resolved paths instead, which respects the
     path-separator boundary.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


class PathSafetyError(Exception):
    """Raised when a tool-supplied path escapes (or attempts to escape) the
    workspace sandbox. Callers must catch this and turn it into a tool-level
    error result rather than letting it propagate as a crash.
    """


def resolve_safe_path(workspace_dir: str, user_path: str) -> Path:
    """Resolve `user_path` (as supplied by the model) against `workspace_dir`
    and return the resolved, guaranteed-in-bounds absolute Path.

    Raises PathSafetyError on anything that would escape the workspace.
    """
    if not isinstance(user_path, str) or user_path.strip() == "":
        raise PathSafetyError(f"path must be a non-empty string, got: {user_path!r}")

    # --- Fast rejection pass (cheap, before touching the filesystem) ---
    if os.path.isabs(user_path):
        raise PathSafetyError(f"absolute paths are not allowed: {user_path!r}")

    # Split on both separators so this also catches Windows-style traversal
    # if a model ever emits backslashes.
    normalized_parts = user_path.replace("\\", "/").split("/")
    if ".." in normalized_parts:
        raise PathSafetyError(f"path traversal ('..') is not allowed: {user_path!r}")

    # --- Real defense: resolve symlinks and check containment ---
    workspace_root = Path(workspace_dir).resolve()
    candidate = (workspace_root / user_path).resolve()

    if candidate != workspace_root and workspace_root not in candidate.parents:
        raise PathSafetyError(
            f"path resolves outside the workspace sandbox: {user_path!r} -> {candidate}"
        )

    return candidate


def write_file(workspace_dir: str, path: str, content: str) -> dict[str, Any]:
    """Create or overwrite a file inside the workspace, creating parent
    directories inside the workspace as needed.
    """
    try:
        if not isinstance(content, str):
            return {"error": f"content must be a string, got: {type(content).__name__}"}
        target = resolve_safe_path(workspace_dir, path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return {"success": True, "path": str(target.relative_to(Path(workspace_dir).resolve()))}
    except PathSafetyError as exc:
        return {"error": str(exc)}
    except OSError as exc:
        return {"error": f"failed to write file: {exc}"}


def read_file(workspace_dir: str, path: str) -> dict[str, Any]:
    """Return the contents of a file inside the workspace."""
    try:
        target = resolve_safe_path(workspace_dir, path)
        if not target.exists():
            return {"error": f"file not found: {path!r}"}
        if not target.is_file():
            return {"error": f"not a regular file: {path!r}"}
        return {"success": True, "content": target.read_text(encoding="utf-8")}
    except PathSafetyError as exc:
        return {"error": str(exc)}
    except OSError as exc:
        return {"error": f"failed to read file: {exc}"}


def list_files(workspace_dir: str, path: str = ".") -> dict[str, Any]:
    """List files/directories at `path` within the workspace."""
    try:
        target = resolve_safe_path(workspace_dir, path)
        if not target.exists():
            return {"error": f"path not found: {path!r}"}
        if not target.is_dir():
            return {"error": f"not a directory: {path!r}"}
        entries = sorted(
            f"{child.name}/" if child.is_dir() else child.name
            for child in target.iterdir()
        )
        return {"success": True, "entries": entries}
    except PathSafetyError as exc:
        return {"error": str(exc)}
    except OSError as exc:
        return {"error": f"failed to list directory: {exc}"}


# Dispatch table used by the agentic loop to call tools by name.
TOOL_FUNCTIONS = {
    "write_file": write_file,
    "read_file": read_file,
    "list_files": list_files,
}
