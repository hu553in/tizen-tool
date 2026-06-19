from __future__ import annotations

import hashlib
import json
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse

from .errors import ToolError
from .runtime import ensure_ignored_directory, log_step, log_success

DOWNLOAD_ATTEMPTS = 3
DOWNLOAD_RETRY_DELAY_SECONDS = 1
DOWNLOAD_SOCKET_TIMEOUT_SECONDS = 30
DOWNLOAD_PROGRESS_CHUNK_BYTES = 5 * 1024 * 1024
INSTALLER_METADATA_FILE = "installer.json"


@dataclass(frozen=True)
class InstallerCandidate:
    name: str
    url: str


@dataclass(frozen=True)
class CachedInstaller:
    installer_path: Path
    sha256: str


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


def load_cached_installer(version_cache_dir: Path) -> CachedInstaller | None:
    metadata_path = version_cache_dir / INSTALLER_METADATA_FILE
    cached_installer: CachedInstaller | None = None
    if metadata_path.is_file():
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

        if isinstance(metadata, dict):
            installer_name = metadata.get("name")
            expected_sha256 = metadata.get("sha256")
            if isinstance(installer_name, str) and isinstance(expected_sha256, str):
                installer_path = version_cache_dir / installer_name
                if installer_path.is_file():
                    try:
                        actual_sha256 = sha256_file(installer_path)
                    except OSError:
                        return None

                    if actual_sha256 == expected_sha256:
                        cached_installer = CachedInstaller(
                            installer_path=installer_path, sha256=actual_sha256
                        )

    return cached_installer


def download_file(url: str, destination: Path) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ToolError(f"Installer URL must use https: {url}")

    last_error: OSError | HTTPError | URLError | None = None
    for attempt in range(1, DOWNLOAD_ATTEMPTS + 1):
        try:
            log_step(f"Downloading Tizen installer (attempt {attempt}/{DOWNLOAD_ATTEMPTS}): {url}")
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
                        log_step(
                            f"Downloaded installer payload: {bytes_written // (1024 * 1024)} MiB"
                        )
                        next_progress_threshold += DOWNLOAD_PROGRESS_CHUNK_BYTES
            log_success(
                f"Finished downloading installer payload: {bytes_written // (1024 * 1024)} MiB"
            )
            return
        except (HTTPError, OSError, URLError) as exc:
            last_error = exc
            log_step(f"Download attempt failed: {exc}")
            if attempt == DOWNLOAD_ATTEMPTS:
                break
            time.sleep(DOWNLOAD_RETRY_DELAY_SECONDS)

    raise ToolError(f"Failed to download installer from {url}: {last_error}")


def write_metadata(version_cache_dir: Path, *, candidate: InstallerCandidate, sha256: str) -> None:
    metadata = {"name": candidate.name, "url": candidate.url, "sha256": sha256}
    metadata_path = version_cache_dir / INSTALLER_METADATA_FILE
    temp_metadata_path = version_cache_dir / f"{INSTALLER_METADATA_FILE}.tmp"
    try:
        temp_metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
        temp_metadata_path.replace(metadata_path)
    except OSError as exc:
        raise ToolError(
            f"Failed to write installer cache metadata in {version_cache_dir}: {exc}"
        ) from exc


def prune_cache_directory(version_cache_dir: Path, *, preserve: set[str]) -> None:
    for child in version_cache_dir.iterdir():
        if child.name in preserve:
            continue
        if child.is_file():
            try:
                child.unlink()
            except OSError as exc:
                raise ToolError(
                    f"Failed to clean installer cache in {version_cache_dir}: {exc}"
                ) from exc


def download_installer_candidate(
    candidate: InstallerCandidate, version_cache_dir: Path
) -> CachedInstaller:
    temp_path = version_cache_dir / f"{candidate.name}.tmp"
    installer_path = version_cache_dir / candidate.name

    if temp_path.exists():
        temp_path.unlink()

    try:
        log_step(f"Trying Tizen installer candidate: {candidate.url}")
        download_file(candidate.url, temp_path)
        sha256 = sha256_file(temp_path)
        if installer_path.exists():
            installer_path.unlink()
        temp_path.replace(installer_path)
        write_metadata(version_cache_dir, candidate=candidate, sha256=sha256)
        prune_cache_directory(
            version_cache_dir, preserve={installer_path.name, INSTALLER_METADATA_FILE}
        )
        log_success(f"Cached Tizen installer: {installer_path}")
        return CachedInstaller(installer_path=installer_path, sha256=sha256)
    except OSError as exc:
        raise ToolError(f"Failed to update installer cache in {version_cache_dir}: {exc}") from exc
    finally:
        if temp_path.exists():
            temp_path.unlink()


def ensure_cached_installer(tizen_version: str, cache_root: Path) -> CachedInstaller:
    version_cache_dir = cache_root / tizen_version
    ensure_ignored_directory(cache_root)
    ensure_ignored_directory(version_cache_dir)

    cached_installer = load_cached_installer(version_cache_dir)
    if cached_installer is not None:
        log_success(f"Using cached Tizen installer: {cached_installer.installer_path}")
        return cached_installer

    log_step(f"Resolving Tizen installer for version {tizen_version}")
    candidate_errors: list[str] = []
    for candidate in installer_candidates(tizen_version):
        try:
            return download_installer_candidate(candidate, version_cache_dir)
        except ToolError as exc:
            candidate_errors.append(f"{candidate.url}: {exc}")
            log_step(f"Installer candidate failed: {exc}")

    joined_errors = "\n- ".join(candidate_errors)
    raise ToolError(
        f"Failed to download Tizen Studio with all known installer variants:\n- {joined_errors}"
    )
