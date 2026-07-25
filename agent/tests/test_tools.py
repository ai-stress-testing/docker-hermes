import os

import pytest

from agent.tools import PathSafetyError, list_files, read_file, resolve_safe_path, write_file


@pytest.fixture
def workspace(tmp_path):
    ws = tmp_path / "workspace"
    ws.mkdir()
    return ws


# --- Happy path -------------------------------------------------------


def test_write_then_read_file(workspace):
    result = write_file(str(workspace), "notes.txt", "hello world")
    assert result == {"success": True, "path": "notes.txt"}

    result = read_file(str(workspace), "notes.txt")
    assert result == {"success": True, "content": "hello world"}


def test_write_creates_parent_dirs_inside_workspace(workspace):
    result = write_file(str(workspace), "sub/dir/file.txt", "x")
    assert result["success"] is True
    assert (workspace / "sub" / "dir" / "file.txt").read_text() == "x"


def test_list_files(workspace):
    (workspace / "a.txt").write_text("1")
    (workspace / "sub").mkdir()
    result = list_files(str(workspace), ".")
    assert result["success"] is True
    assert "a.txt" in result["entries"]
    assert "sub/" in result["entries"]


def test_read_missing_file_returns_error_not_exception(workspace):
    result = read_file(str(workspace), "does-not-exist.txt")
    assert "error" in result


# --- Adversarial path-safety cases -------------------------------------


def test_rejects_dotdot_traversal(workspace):
    result = read_file(str(workspace), "../../etc/passwd")
    assert "error" in result
    assert not (workspace.parent.parent / "etc" / "passwd").exists()


def test_rejects_absolute_path(workspace):
    result = read_file(str(workspace), "/etc/passwd")
    assert "error" in result


def test_rejects_dotdot_embedded_mid_path(workspace):
    # "subdir/../../escape" - passes a naive "startswith workspace" string
    # check after joining, but must still be rejected.
    result = write_file(str(workspace), "subdir/../../escape", "pwned")
    assert "error" in result
    assert not (workspace.parent / "escape").exists()


def test_rejects_symlink_escape_created_inside_workspace(workspace, tmp_path):
    # A prior tool call could plant a symlink inside the workspace that
    # points outside of it; resolve_safe_path must still catch this even
    # though the *symlink itself* has a workspace-internal path.
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    secret = outside_dir / "secret.txt"
    secret.write_text("top secret")

    escape_link = workspace / "escape_link"
    escape_link.symlink_to(outside_dir)

    result = read_file(str(workspace), "escape_link/secret.txt")
    assert "error" in result

    result = write_file(str(workspace), "escape_link/pwned.txt", "pwned")
    assert "error" in result
    assert not (outside_dir / "pwned.txt").exists()


def test_rejects_sibling_directory_with_shared_prefix(tmp_path):
    # Classic bypass check: "/workspace-evil".startswith("/workspace") is
    # True as a string, but must NOT be treated as inside the workspace.
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    evil_root = tmp_path / "workspace-evil"
    evil_root.mkdir()
    (evil_root / "secret.txt").write_text("nope")

    with pytest.raises(PathSafetyError):
        resolve_safe_path(str(workspace_root), "../workspace-evil/secret.txt")


def test_rejects_non_string_path(workspace):
    result = read_file(str(workspace), 123)  # type: ignore[arg-type]
    assert "error" in result


def test_accepts_and_confines_relative_subdir_paths(workspace):
    result = write_file(str(workspace), "./a/b/c.txt", "ok")
    assert result["success"] is True
    resolved = resolve_safe_path(str(workspace), "a/b/c.txt")
    assert resolved == (workspace / "a" / "b" / "c.txt").resolve()
