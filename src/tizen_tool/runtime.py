from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path

from .errors import ToolError


def run(
    args: Sequence[str],
    *,
    cwd: Path | None = None,
    check: bool = True,
    capture_output: bool = False,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(args),
        cwd=str(cwd) if cwd is not None else None,
        check=check,
        text=True,
        capture_output=capture_output,
        env=os.environ.copy(),
    )


def require_command(name: str) -> None:
    if shutil.which(name) is None:
        raise ToolError(f"Required command is not installed or not in PATH: {name}")


def require_file(path: Path, description: str = "File") -> None:
    if not path.is_file():
        raise ToolError(f"{description} is not found: {path}")
