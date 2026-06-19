#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess  # nosec B404
from pathlib import Path

SHA256_HEX_LENGTH = 64
INSTALLER_PATH = Path("/home/tizen/installer.bin")
PACKAGE_MANAGER_PATH = Path("/home/tizen/tizen-studio/package-manager/package-manager-cli.bin")
SHOW_PACKAGES_PATTERN = re.compile(
    r"^\s*(?P<status>[a-z]{1,3})\s+(?P<package>[A-Za-z0-9][A-Za-z0-9._+-]*)\s+"
)
INSTALLED_PACKAGE_STATUSES = {"i", "u"}


def log(message: str) -> None:
    print(f"==> {message}", flush=True)


def log_success(message: str) -> None:
    print(f"OK: {message}", flush=True)


def getenv_required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"{name} is required")
    return value


def run(
    args: list[str], *, check: bool = True, capture_output: bool = False
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, check=check, text=True, capture_output=capture_output)  # nosec B603


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as file_obj:
        for chunk in iter(lambda: file_obj.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def normalize_sha256(raw_value: str) -> str:
    normalized = raw_value.strip().lower()
    if len(normalized) != SHA256_HEX_LENGTH or any(
        character not in "0123456789abcdef" for character in normalized
    ):
        raise SystemExit("TIZEN_INSTALLER_SHA256 must be a 64-character hexadecimal SHA-256 digest")
    return normalized


def normalize_output(stdout: str, stderr: str) -> str:
    return "\n".join(part for part in (stdout.strip(), stderr.strip()) if part).strip()


def format_output(output: str) -> str:
    return output if output else "no diagnostic output"


def parse_show_packages(output: str) -> dict[str, str]:
    packages: dict[str, str] = {}
    for line in output.splitlines():
        match = SHOW_PACKAGES_PATTERN.match(line)
        if match is None:
            continue
        packages[match.group("package")] = match.group("status").lower()
    return packages


def show_packages() -> dict[str, str]:
    result = run(
        [str(PACKAGE_MANAGER_PATH), "show-pkgs", "--tree"], check=False, capture_output=True
    )
    output = normalize_output(result.stdout, result.stderr)

    if result.returncode != 0:
        details = format_output(output)
        raise SystemExit(
            f"Failed to list Tizen packages: 'package-manager-cli show-pkgs --tree' "
            f"exited with code {result.returncode}. Output: {details}"
        )

    packages = parse_show_packages(output)
    if not packages:
        details = format_output(output)
        raise SystemExit(
            f"Failed to parse 'package-manager-cli show-pkgs --tree' output. Output: {details}"
        )
    return packages


def validate_required_package_ids(packages: list[str]) -> None:
    log("Validating required Tizen packages")
    available_packages = show_packages()
    missing_packages = [package for package in packages if package not in available_packages]
    if missing_packages:
        formatted_missing = ", ".join(sorted(missing_packages))
        raise SystemExit(
            f"Unknown Tizen package IDs: {formatted_missing}. "
            "They were not found in 'package-manager-cli show-pkgs --tree' output. "
            "Check the available packages with 'package-manager-cli show-pkgs --tree'."
        )
    log_success("Required Tizen packages are available")


def ensure_package_installed(package: str) -> None:
    packages = show_packages()
    status = packages.get(package)
    if status not in INSTALLED_PACKAGE_STATUSES:
        raise SystemExit(
            f"Failed to install Tizen package {package!r}: 'package-manager-cli' did not mark it "
            f"as installed (status: {status or 'missing'})."
        )


def validate_install_result(package: str, result: subprocess.CompletedProcess[str]) -> None:
    output = normalize_output(result.stdout, result.stderr)

    if result.returncode != 0:
        details = format_output(output)
        raise SystemExit(
            f"Failed to install Tizen package {package!r}: 'package-manager-cli' exited with code "
            f"{result.returncode}. Output: {details}"
        )

    ensure_package_installed(package)


def load_required_packages() -> list[str]:
    raw_packages = getenv_required("REQUIRED_PACKAGES_JSON")

    try:
        packages = json.loads(raw_packages)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"REQUIRED_PACKAGES_JSON must be valid JSON: {exc}") from exc

    if not isinstance(packages, list) or not all(
        isinstance(item, str) and item.strip() for item in packages
    ):
        raise SystemExit("REQUIRED_PACKAGES_JSON must be a JSON array of non-empty strings")

    return packages


def verify_bundled_installer(expected_sha256: str) -> None:
    if not INSTALLER_PATH.is_file():
        raise SystemExit(f"Bundled installer is missing: {INSTALLER_PATH}")

    actual_sha256 = sha256_file(INSTALLER_PATH)
    if actual_sha256 != expected_sha256:
        raise SystemExit(
            f"Bundled installer checksum mismatch: expected {expected_sha256}, got {actual_sha256}"
        )

    log_success("Bundled installer checksum verification passed")


def install_tizen_studio() -> None:
    INSTALLER_PATH.chmod(INSTALLER_PATH.stat().st_mode | stat.S_IXUSR)
    log(f"Running bundled Tizen Studio installer: {INSTALLER_PATH.name}")
    run([str(INSTALLER_PATH), "--accept-license", "Y", "/home/tizen/tizen-studio"])
    log_success("Tizen Studio installation completed")


def install_required_packages(packages: list[str]) -> None:
    validate_required_package_ids(packages)

    for package in packages:
        log(f"Installing Tizen package: {package}")
        result = run(
            [str(PACKAGE_MANAGER_PATH), "install", package, "--accept-license"],
            check=False,
            capture_output=True,
        )
        validate_install_result(package, result)
        log_success(f"Installed Tizen package: {package}")


def main() -> int:
    expected_sha256 = normalize_sha256(getenv_required("TIZEN_INSTALLER_SHA256"))
    packages = load_required_packages()

    verify_bundled_installer(expected_sha256)
    install_tizen_studio()
    install_required_packages(packages)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
