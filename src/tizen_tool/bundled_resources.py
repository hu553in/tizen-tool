from __future__ import annotations

import hashlib
from importlib.resources import files
from pathlib import Path

RESOURCE_PACKAGE = "tizen_tool.resources"


def resource_bytes(relative_path: str) -> bytes:
    return files(RESOURCE_PACKAGE).joinpath(relative_path).read_bytes()


def build_context_fingerprint() -> str:
    hasher = hashlib.sha256()
    for relative_path in ("Dockerfile", "install_tizen_studio.py"):
        content = resource_bytes(relative_path)
        hasher.update(relative_path.encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(content)
        hasher.update(b"\0")
    return hasher.hexdigest()


def materialize_build_context(target_dir: Path) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "Dockerfile").write_bytes(resource_bytes("Dockerfile"))
    (target_dir / "install_tizen_studio.py").write_bytes(resource_bytes("install_tizen_studio.py"))
