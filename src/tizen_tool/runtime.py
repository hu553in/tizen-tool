from __future__ import annotations

import ipaddress
import os
import shutil
import subprocess  # nosec B404
from collections.abc import Sequence
from pathlib import Path

import ifaddr

from .errors import ToolError


def log_step(message: str) -> None:
    print(f"==> {message}", flush=True)


def log_success(message: str) -> None:
    print(f"OK: {message}", flush=True)


def run(
    args: Sequence[str],
    *,
    cwd: Path | None = None,
    check: bool = True,
    capture_output: bool = False,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # nosec B603
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


def get_lan_ips() -> list[tuple[str, list[str]]]:
    lan_ips_by_interface: list[tuple[str, list[str]]] = []

    for adapter in ifaddr.get_adapters():
        lan_ips: set[str] = set()
        for address in adapter.ips:
            if isinstance(address.ip, tuple):
                continue

            candidate_ip = ipaddress.ip_address(address.ip)
            if candidate_ip.is_loopback or not candidate_ip.is_private:
                continue

            lan_ips.add(str(candidate_ip))

        if lan_ips:
            lan_ips_by_interface.append((str(adapter.nice_name), sorted(lan_ips)))

    if not lan_ips_by_interface:
        raise ToolError("No private LAN IPv4 addresses were found on any network interface")

    return lan_ips_by_interface
