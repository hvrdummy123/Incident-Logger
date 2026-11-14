"""Dataset path sandbox — every file lives under data/<workspace_id>/."""

from __future__ import annotations

from pathlib import Path


class PathEscapeError(ValueError):
    """Raised when a path would leave the workspace sandbox."""


def workspace_root(data_dir: Path, workspace_id: str) -> Path:
    if not workspace_id or "/" in workspace_id or "\\" in workspace_id or ".." in workspace_id:
        raise PathEscapeError("invalid workspace_id")
    root = (data_dir / workspace_id).resolve()
    data = data_dir.resolve()
    if not root.is_relative_to(data) or root == data:
        raise PathEscapeError("workspace root escapes data dir")
    return root


def resolve_in_workspace(data_dir: Path, workspace_id: str, *parts: str) -> Path:
    """Resolve a path under the workspace; reject .. and absolute escapes."""
    root = workspace_root(data_dir, workspace_id)
    candidate = root.joinpath(*parts).resolve()
    if not candidate.is_relative_to(root):
        raise PathEscapeError(f"path escapes workspace sandbox: {parts!r}")
    return candidate


def assert_under_workspace(data_dir: Path, workspace_id: str, path: Path) -> Path:
    root = workspace_root(data_dir, workspace_id)
    resolved = path.resolve()
    if not resolved.is_relative_to(root):
        raise PathEscapeError("path is outside workspace sandbox")
    return resolved
