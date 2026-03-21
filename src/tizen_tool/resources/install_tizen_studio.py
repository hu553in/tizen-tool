#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

DOWNLOAD_ATTEMPTS = 3
DOWNLOAD_RETRY_DELAY_SECONDS = 1


@dataclass(frozen=True)
class InstallerCandidate:
    name: str
    url: str


def getenv_required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"{name} is required")
    return value


def run(args: list[str]) -> None:
    subprocess.run(args, check=True)


def download_file(url: str, destination: Path) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise SystemExit(f"Installer URL must use https: {url}")

    last_error: Exception | None = None
    for attempt in range(1, DOWNLOAD_ATTEMPTS + 1):
        try:
            with (
                urllib.request.urlopen(url, timeout=30) as response,  # nosec B310
                destination.open("wb") as output,
            ):
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    output.write(chunk)
            return
        except Exception as exc:
            last_error = exc
            if attempt == DOWNLOAD_ATTEMPTS:
                break
            time.sleep(DOWNLOAD_RETRY_DELAY_SECONDS)

    raise SystemExit(f"Failed to download installer from {url}: {last_error}")


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as file_obj:
        for chunk in iter(lambda: file_obj.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def installer_candidates(tizen_version: str) -> list[InstallerCandidate]:
    return [
        InstallerCandidate(
            name=f"web-cli_Tizen_SDK_{tizen_version}_ubuntu-64.bin",
            url=(
                "https://download.tizen.org/sdk/Installer/"
                f"tizen-sdk_{tizen_version}/"
                f"web-cli_Tizen_SDK_{tizen_version}_ubuntu-64.bin"
            ),
        ),
        InstallerCandidate(
            name=f"web-cli_Tizen_Studio_{tizen_version}_ubuntu-64.bin",
            url=(
                "https://download.tizen.org/sdk/Installer/"
                f"tizen-studio_{tizen_version}/"
                f"web-cli_Tizen_Studio_{tizen_version}_ubuntu-64.bin"
            ),
        ),
    ]


def main() -> int:
    tizen_version = getenv_required("TIZEN_VERSION")
    expected_sha256 = getenv_required("TIZEN_INSTALLER_SHA256").lower()
    raw_packages = getenv_required("REQUIRED_PACKAGES_JSON")

    try:
        packages = json.loads(raw_packages)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"REQUIRED_PACKAGES_JSON must be valid JSON: {exc}") from exc
    if not isinstance(packages, list) or not all(
        isinstance(item, str) and item.strip() for item in packages
    ):
        raise SystemExit("REQUIRED_PACKAGES_JSON must be a JSON array of non-empty strings")

    installer_dir = Path("/home/tizen/installer")
    installer_dir.mkdir(parents=True, exist_ok=True)
    package_manager = Path("/home/tizen/tizen-studio/package-manager/package-manager-cli.bin")
    candidate_errors: list[str] = []

    for candidate in installer_candidates(tizen_version):
        installer_path = installer_dir / candidate.name
        temp_path = installer_dir / f"{candidate.name}.tmp"

        if temp_path.exists():
            temp_path.unlink()

        try:
            print(f"Trying Tizen installer: {candidate.url}")
            download_file(candidate.url, temp_path)
            actual_sha256 = sha256_file(temp_path)
            if actual_sha256 != expected_sha256:
                raise RuntimeError(
                    f"Installer checksum mismatch: expected {expected_sha256}, got {actual_sha256}"
                )

            temp_path.replace(installer_path)
            installer_path.chmod(installer_path.stat().st_mode | stat.S_IXUSR)

            run(
                [
                    str(installer_path),
                    "--accept-license",
                    "Y",
                    "--no-java-check",
                    "/home/tizen/tizen-studio",
                ]
            )

            for package in packages:
                print(f"Installing Tizen package: {package}")
                run([str(package_manager), "install", package])

            return 0
        except Exception as exc:
            candidate_errors.append(f"{candidate.url}: {exc}")
        finally:
            if temp_path.exists():
                temp_path.unlink()

    joined_errors = "\n- ".join(candidate_errors)
    raise SystemExit(
        f"Failed to install Tizen Studio with all known installer variants:\n- {joined_errors}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
