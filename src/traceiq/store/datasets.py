"""Content-addressed dataset directories under the workspace sandbox."""

from __future__ import annotations

import contextlib
import hashlib
import json
from pathlib import Path
from typing import Any

from traceiq.tenancy.paths import resolve_in_workspace, workspace_root


def content_hash_files(paths: list[Path]) -> str:
    h = hashlib.sha256()
    for p in sorted(paths, key=lambda x: str(x)):
        h.update(p.name.encode())
        with p.open("rb") as f:
            while True:
                chunk = f.read(1024 * 1024)
                if not chunk:
                    break
                h.update(chunk)
    return h.hexdigest()


def dataset_dir(data_dir: Path, workspace_id: str, dataset_id: str) -> Path:
    d = resolve_in_workspace(data_dir, workspace_id, "datasets", dataset_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def write_manifest(ds_dir: Path, manifest: dict[str, Any]) -> None:
    path = ds_dir / "manifest.json"
    path.write_text(json.dumps(manifest, sort_keys=True, indent=2), encoding="utf-8")
    with contextlib.suppress(OSError):
        path.chmod(0o444)


def list_workspace_datasets(data_dir: Path, workspace_id: str) -> list[Path]:
    root = workspace_root(data_dir, workspace_id) / "datasets"
    if not root.exists():
        return []
    return [p for p in root.iterdir() if p.is_dir()]
