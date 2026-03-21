#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess  # nosec B404
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse

DOWNLOAD_ATTEMPTS = 3
DOWNLOAD_RETRY_DELAY_SECONDS = 1
DOWNLOAD_SOCKET_TIMEOUT_SECONDS = 30
DOWNLOAD_PROGRESS_CHUNK_BYTES = 50 * 1024 * 1024
SHA256_HEX_LENGTH = 64


@dataclass(frozen=True)
class InstallerCandidate:
    name: str
    url: str


class InstallerCandidateError(RuntimeError):
    """Raised when a specific installer candidate cannot be used."""


def log(message: str) -> None:
    print(f"==> {message}", flush=True)


def log_success(message: str) -> None:
    print(f"OK: {message}", flush=True)


def getenv_required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"{name} is required")
    return value


def getenv_optional(name: str) -> str | None:
    value = os.environ.get(name, "").strip()
    return value or None


def run(args: list[str]) -> None:
    subprocess.run(args, check=True)  # nosec B603


def download_file(url: str, destination: Path) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise InstallerCandidateError(f"Installer URL must use https: {url}")

    last_error: OSError | HTTPError | URLError | RuntimeError | None = None
    for attempt in range(1, DOWNLOAD_ATTEMPTS + 1):
        try:
            log(f"Downloading installer (attempt {attempt}/{DOWNLOAD_ATTEMPTS}): {url}")
            bytes_written = 0
            next_progress_threshold = DOWNLOAD_PROGRESS_CHUNK_BYTES
            with (
                urllib.request.urlopen(  # nosec B310
                    url, timeout=DOWNLOAD_SOCKET_TIMEOUT_SECONDS
                ) as response,
                destination.open("wb") as output,
            ):
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    output.write(chunk)
                    bytes_written += len(chunk)
                    if bytes_written >= next_progress_threshold:
                        log(f"Downloaded installer payload: {bytes_written // (1024 * 1024)} MiB")
                        next_progress_threshold += DOWNLOAD_PROGRESS_CHUNK_BYTES
            log_success(
                f"Finished downloading installer payload: {bytes_written // (1024 * 1024)} MiB"
            )
            return
        except (HTTPError, OSError, URLError) as exc:
            last_error = exc
            log(f"Download attempt failed: {exc}")
            if attempt == DOWNLOAD_ATTEMPTS:
                break
            time.sleep(DOWNLOAD_RETRY_DELAY_SECONDS)

    raise InstallerCandidateError(f"Failed to download installer from {url}: {last_error}")


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as file_obj:
        for chunk in iter(lambda: file_obj.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def normalize_expected_sha256(raw_value: str | None) -> str | None:
    if raw_value is None:
        return None

    normalized = raw_value.strip().lower()
    if len(normalized) != SHA256_HEX_LENGTH or any(
        character not in "0123456789abcdef" for character in normalized
    ):
        raise SystemExit("TIZEN_INSTALLER_SHA256 must be a 64-character hexadecimal SHA-256 digest")
    return normalized


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


def verify_installer_checksum(installer_path: Path, expected_sha256: str | None) -> None:
    if expected_sha256 is None:
        log("Skipping installer checksum verification")
        return

    log("Verifying installer checksum")
    actual_sha256 = sha256_file(installer_path)
    if actual_sha256 != expected_sha256:
        raise InstallerCandidateError(
            f"Installer checksum mismatch: expected {expected_sha256}, got {actual_sha256}"
        )
    log_success("Installer checksum verification passed")


def install_tizen_studio(
    candidate: InstallerCandidate, installer_dir: Path, expected_sha256: str | None
) -> Path:
    installer_path = installer_dir / candidate.name
    temp_path = installer_dir / f"{candidate.name}.tmp"

    if temp_path.exists():
        temp_path.unlink()

    try:
        log(f"Trying Tizen installer candidate: {candidate.url}")
        download_file(candidate.url, temp_path)
        verify_installer_checksum(temp_path, expected_sha256)

        temp_path.replace(installer_path)
        installer_path.chmod(installer_path.stat().st_mode | stat.S_IXUSR)
        log(f"Running installer: {installer_path.name}")
        run(
            [
                str(installer_path),
                "--accept-license",
                "Y",
                "--no-java-check",
                "/home/tizen/tizen-studio",
            ]
        )
        log_success("Tizen Studio installation completed")
        return Path("/home/tizen/tizen-studio/package-manager/package-manager-cli.bin")
    except subprocess.CalledProcessError as exc:
        raise InstallerCandidateError(
            f"Installer process exited with code {exc.returncode}"
        ) from exc
    finally:
        if temp_path.exists():
            temp_path.unlink()


def install_required_packages(package_manager: Path, packages: list[str]) -> None:
    for package in packages:
        log(f"Installing Tizen package: {package}")
        try:
            run([str(package_manager), "install", package])
        except subprocess.CalledProcessError as exc:
            raise SystemExit(
                f"Failed to install Tizen package {package!r}: "
                f"package manager exited with code {exc.returncode}"
            ) from exc
        log_success(f"Installed Tizen package: {package}")


def main() -> int:
    tizen_version = getenv_required("TIZEN_VERSION")
    expected_sha256 = normalize_expected_sha256(getenv_optional("TIZEN_INSTALLER_SHA256"))
    raw_packages = getenv_required("REQUIRED_PACKAGES_JSON")

    try:
        packages = json.loads(raw_packages)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"REQUIRED_PACKAGES_JSON must be valid JSON: {exc}") from exc
    if not isinstance(packages, list) or not all(
        isinstance(item, str) and item.strip() for item in packages
    ):
        raise SystemExit("REQUIRED_PACKAGES_JSON must be a JSON array of non-empty strings")

    log(f"Preparing Tizen Studio installer for version {tizen_version}")
    installer_dir = Path("/home/tizen/installer")
    installer_dir.mkdir(parents=True, exist_ok=True)
    candidate_errors: list[str] = []
    package_manager: Path | None = None

    for candidate in installer_candidates(tizen_version):
        try:
            package_manager = install_tizen_studio(candidate, installer_dir, expected_sha256)
            break
        except InstallerCandidateError as exc:
            candidate_errors.append(f"{candidate.url}: {exc}")
            log(f"Installer candidate failed: {exc}")

    if package_manager is None:
        joined_errors = "\n- ".join(candidate_errors)
        raise SystemExit(
            f"Failed to install Tizen Studio with all known installer variants:\n- {joined_errors}"
        )

    install_required_packages(package_manager, packages)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
