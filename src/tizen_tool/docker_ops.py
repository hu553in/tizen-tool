from __future__ import annotations

import json
import shutil
import tempfile
from collections.abc import Iterable, Sequence
from pathlib import Path

from .bundled_resources import build_context_fingerprint, materialize_build_context
from .errors import ToolError
from .paths import temp_root
from .project_files import copy_project_tree, validate_profiles
from .runtime import log_step, log_success, require_command, run
from .settings import BuildSettings, CommonSettings, InstallSettings, ResignSettings

IMAGE_LABEL_PREFIX = "com.github.hu553in.tizen.tool"
IMAGE_LABEL_VERSION = f"{IMAGE_LABEL_PREFIX}.version"
IMAGE_LABEL_REQUIRED_PACKAGES = f"{IMAGE_LABEL_PREFIX}.required-packages"
IMAGE_LABEL_BUILD_CONTEXT = f"{IMAGE_LABEL_PREFIX}.build-context-fingerprint"


def expected_image_labels(settings: CommonSettings) -> dict[str, str]:
    required_packages_json = json.dumps(settings.required_packages, separators=(",", ":"))
    return {
        IMAGE_LABEL_REQUIRED_PACKAGES: required_packages_json,
        IMAGE_LABEL_BUILD_CONTEXT: build_context_fingerprint(),
        IMAGE_LABEL_VERSION: settings.tizen_version,
    }


def inspect_image_labels(image_tag: str) -> dict[str, str] | None:
    result = run(
        ["docker", "image", "inspect", image_tag, "--format", "{{json .Config.Labels}}"],
        capture_output=True,
        check=False,
    )

    if result.returncode != 0:
        return None

    raw = result.stdout.strip()
    if not raw or raw == "null":
        return {}

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ToolError(f"Failed to parse Docker image labels for {image_tag}: {exc}") from exc

    if not isinstance(parsed, dict):
        return {}

    return {
        key: value
        for key, value in parsed.items()
        if isinstance(key, str) and isinstance(value, str)
    }


def should_rebuild_image(settings: CommonSettings, *, force_rebuild: bool) -> bool:
    if force_rebuild:
        return True

    labels = inspect_image_labels(settings.image_tag)
    if labels is None:
        return True

    expected_labels = expected_image_labels(settings)
    return any(labels.get(key) != value for key, value in expected_labels.items())


def ensure_image(settings: CommonSettings, *, force_rebuild: bool) -> None:
    require_command("docker")

    if not should_rebuild_image(settings, force_rebuild=force_rebuild):
        log_success(f"Using existing Docker image: {settings.image_tag}")
        return

    log_step(f"Building Docker image: {settings.image_tag}")
    context_fingerprint = build_context_fingerprint()
    build_temp_root = temp_root()
    build_temp_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="docker-build-", dir=build_temp_root) as raw_build_dir:
        build_dir = Path(raw_build_dir)
        materialize_build_context(build_dir)
        required_packages_json = json.dumps(settings.required_packages, separators=(",", ":"))

        run(
            [
                "docker",
                "build",
                "--progress=plain",
                "-t",
                settings.image_tag,
                "--platform",
                "linux/amd64",
                "--build-arg",
                f"TIZEN_VERSION={settings.tizen_version}",
                "--build-arg",
                f"REQUIRED_PACKAGES_JSON={required_packages_json}",
                "--build-arg",
                f"TIZEN_INSTALLER_SHA256={settings.tizen_installer_sha256 or ''}",
                "--build-arg",
                f"BUILD_CONTEXT_FINGERPRINT={context_fingerprint}",
                str(build_dir),
            ]
        )
    log_success(f"Docker image is ready: {settings.image_tag}")


def docker_run_tizen(
    image_tag: str,
    *,
    docker_args: Sequence[str],
    inner_script: str,
    script_args: Iterable[str] = (),
) -> None:
    run(
        [
            "docker",
            "run",
            "--rm",
            "--platform",
            "linux/amd64",
            *docker_args,
            image_tag,
            "bash",
            "-euo",
            "pipefail",
            "-c",
            inner_script,
            "bash",
            *script_args,
        ]
    )


def find_exactly_one_wgt(build_dir: Path) -> Path:
    wgt_files = sorted(build_dir.glob("*.wgt"))
    if len(wgt_files) != 1:
        raise ToolError(f"Expected exactly one .wgt file in {build_dir}, found: {len(wgt_files)}")
    return wgt_files[0]


def execute_build(settings: BuildSettings) -> None:
    log_step(f"Validating signing profile: {settings.profile}")
    validate_profiles(settings.profiles_dir, settings.profile)
    ensure_image(settings, force_rebuild=settings.rebuild)

    build_temp_root = temp_root()
    build_temp_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="tizen-build-", dir=build_temp_root) as temp_dir_raw:
        temp_dir = Path(temp_dir_raw)
        package_temp_dir = temp_dir / "package"
        log_step(f"Copying project files into temporary build directory: {settings.src_dir}")
        copy_project_tree(settings.src_dir, package_temp_dir, settings.buildignore_file)

        inner_script = """
trap 'cat /home/tizen/tizen-studio-data/cli/logs/cli.log 2>/dev/null || true' ERR
profile="$1"

tizen cli-config profiles.path=/profiles/profiles.xml
tizen build-web -- /package -out /package/build
tizen package --type wgt --sign "$profile" -- /package/build
""".strip()

        log_step("Running Tizen web build and packaging")
        docker_run_tizen(
            settings.image_tag,
            docker_args=[
                "-v",
                f"{package_temp_dir}:/package",
                "-v",
                f"{settings.profiles_dir}:/profiles:ro",
            ],
            inner_script=inner_script,
            script_args=[settings.profile],
        )

        built_wgt = find_exactly_one_wgt(package_temp_dir / "build")
        dist_dir = settings.src_dir / "dist"
        dist_dir.mkdir(parents=True, exist_ok=True)
        output_path = dist_dir / built_wgt.name
        shutil.copy2(built_wgt, output_path)
        log_success(f"Built package: {output_path}")


def execute_install(settings: InstallSettings) -> None:
    ensure_image(settings, force_rebuild=settings.rebuild)

    package_dir = settings.package_file.parent
    package_name = settings.package_file.name

    inner_script = """
trap 'cat /home/tizen/tizen-studio-data/cli/logs/cli.log 2>/dev/null || true' ERR
package_name="$1"
tv_serial="$2"

cleanup() {
  sdb disconnect "$tv_serial" >/dev/null 2>&1 || true
}
trap cleanup EXIT

if ! sdb devices | awk 'NR > 1 {print $1}' | grep -Fx -- "$tv_serial" >/dev/null 2>&1; then
  sdb connect "$tv_serial"
fi

tizen install --name "$package_name" --serial "$tv_serial"
""".strip()

    log_step(f"Installing package on TV {settings.tv_ip}: {settings.package_file}")
    docker_run_tizen(
        settings.image_tag,
        docker_args=["-v", f"{package_dir}:{package_dir}:ro", "-w", str(package_dir)],
        inner_script=inner_script,
        script_args=[package_name, settings.tv_ip],
    )
    log_success(f"Installed package on {settings.tv_ip}: {settings.package_file}")


def execute_resign(settings: ResignSettings) -> None:
    log_step(f"Validating signing profile: {settings.profile}")
    validate_profiles(settings.profiles_dir, settings.profile)
    ensure_image(settings, force_rebuild=settings.rebuild)

    package_dir = settings.package_file.parent
    resigned_dir = package_dir / "resigned"

    inner_script = """
trap 'cat /home/tizen/tizen-studio-data/cli/logs/cli.log 2>/dev/null || true' ERR
profile="$1"
package_file="$2"
resigned_dir="$3"

tizen cli-config profiles.path=/profiles/profiles.xml
mkdir -p "$resigned_dir"
tizen package --type wgt --sign "$profile" -o "$resigned_dir" -- "$package_file"
""".strip()

    log_step(f"Re-signing package: {settings.package_file}")
    docker_run_tizen(
        settings.image_tag,
        docker_args=[
            "-v",
            f"{settings.profiles_dir}:/profiles:ro",
            "-v",
            f"{package_dir}:{package_dir}",
            "-w",
            str(package_dir),
        ],
        inner_script=inner_script,
        script_args=[settings.profile, str(settings.package_file), str(resigned_dir)],
    )

    resigned_file = resigned_dir / settings.package_file.name
    log_success(f"Re-signed package: {resigned_file}")
