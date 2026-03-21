from __future__ import annotations

import subprocess  # nosec B404
import sys
from pathlib import Path
from shlex import join as shell_join
from typing import Annotated

import click
import typer

from .docker_ops import execute_build, execute_install, execute_resign
from .errors import ToolError
from .runtime import get_lan_ips
from .settings import (
    BuildSettings,
    InstallSettings,
    ResignSettings,
    load_settings,
    resolve_cli_path,
)

app = typer.Typer(
    name="tizen-tool",
    help=(
        "Build, re-sign, and install Tizen web packages "
        "through a Dockerized Tizen Studio environment."
    ),
    no_args_is_help=True,
    pretty_exceptions_show_locals=False,
)

BuildSrcDirArgument = Annotated[
    Path | None,
    typer.Argument(
        help=(
            "Source directory containing the Tizen web app. Falls back to BUILD_SRC_DIR or SRC_DIR."
        )
    ),
]
BuildIgnoreFileArgument = Annotated[
    Path | None,
    typer.Argument(
        help=(
            "Optional gitignore-style exclude file. "
            "Falls back to BUILDIGNORE_FILE or BUILD_IGNORE_FILE."
        )
    ),
]
InstallPackageFileArgument = Annotated[
    Path | None,
    typer.Argument(
        help="Path to the .wgt package. Falls back to INSTALL_PACKAGE_FILE or PACKAGE_FILE."
    ),
]
ResignPackageFileArgument = Annotated[
    Path | None,
    typer.Argument(
        help="Path to the .wgt package. Falls back to RESIGN_PACKAGE_FILE or PACKAGE_FILE."
    ),
]
BuildRebuildOption = Annotated[
    bool | None,
    typer.Option(
        "--rebuild/--no-rebuild",
        help="Override rebuild behavior. Falls back to BUILD_REBUILD or REBUILD.",
    ),
]
InstallRebuildOption = Annotated[
    bool | None,
    typer.Option(
        "--rebuild/--no-rebuild",
        help="Override rebuild behavior. Falls back to INSTALL_REBUILD or REBUILD.",
    ),
]
ResignRebuildOption = Annotated[
    bool | None,
    typer.Option(
        "--rebuild/--no-rebuild",
        help="Override rebuild behavior. Falls back to RESIGN_REBUILD or REBUILD.",
    ),
]
TizenVersionOption = Annotated[
    str | None,
    typer.Option("--tizen-version", help="Tizen Studio version. Falls back to TIZEN_VERSION."),
]
InstallerSha256Option = Annotated[
    str | None,
    typer.Option(
        "--tizen-installer-sha256",
        help=(
            "Optional installer SHA-256 digest used for verification. "
            "Falls back to TIZEN_INSTALLER_SHA256."
        ),
    ),
]
RequiredPackageOption = Annotated[
    list[str] | None,
    typer.Option(
        "--required-package",
        help="Required Tizen package. Repeat the option to override REQUIRED_PACKAGES from env.",
    ),
]
ProfilesDirOption = Annotated[
    Path | None,
    typer.Option(
        "--profiles-dir", help="Directory containing profiles.xml. Falls back to PROFILES_DIR."
    ),
]
ProfileOption = Annotated[
    str | None, typer.Option("--profile", help="Signing profile name. Falls back to PROFILE.")
]
TvIpOption = Annotated[
    str | None, typer.Option("--tv-ip", help="TV address or serial. Falls back to TV_IP.")
]


def eprint(message: str) -> None:
    print(message, file=sys.stderr)


@app.command("get-lan-ips", help="Print private LAN IPv4 addresses grouped by interface.")
def get_lan_ips_command() -> None:
    for interface_name, ips in get_lan_ips():
        print(f"{interface_name}: {', '.join(ips)}")


@app.command("build", help="Build a .wgt package from a Tizen web app directory.")
def build_command(  # noqa: PLR0913
    src_dir: BuildSrcDirArgument = None,
    buildignore_file: BuildIgnoreFileArgument = None,
    rebuild: BuildRebuildOption = None,
    tizen_version: TizenVersionOption = None,
    tizen_installer_sha256: InstallerSha256Option = None,
    required_package: RequiredPackageOption = None,
    profiles_dir: ProfilesDirOption = None,
    profile: ProfileOption = None,
) -> None:
    settings = load_settings(
        BuildSettings,
        src_dir=resolve_cli_path(src_dir),
        buildignore_file=resolve_cli_path(buildignore_file),
        rebuild=rebuild,
        tizen_version=tizen_version,
        tizen_installer_sha256=tizen_installer_sha256,
        required_packages=required_package,
        profiles_dir=resolve_cli_path(profiles_dir),
        profile=profile,
    )
    execute_build(settings)


@app.command("install", help="Install a .wgt package on a TV over sdb.")
def install_command(  # noqa: PLR0913
    package_file: InstallPackageFileArgument = None,
    rebuild: InstallRebuildOption = None,
    tizen_version: TizenVersionOption = None,
    tizen_installer_sha256: InstallerSha256Option = None,
    tv_ip: TvIpOption = None,
    required_package: RequiredPackageOption = None,
) -> None:
    settings = load_settings(
        InstallSettings,
        package_file=resolve_cli_path(package_file),
        rebuild=rebuild,
        tizen_version=tizen_version,
        tizen_installer_sha256=tizen_installer_sha256,
        tv_ip=tv_ip,
        required_packages=required_package,
    )
    execute_install(settings)


@app.command("resign", help="Re-sign an existing .wgt package.")
def resign_command(  # noqa: PLR0913
    package_file: ResignPackageFileArgument = None,
    rebuild: ResignRebuildOption = None,
    tizen_version: TizenVersionOption = None,
    tizen_installer_sha256: InstallerSha256Option = None,
    required_package: RequiredPackageOption = None,
    profiles_dir: ProfilesDirOption = None,
    profile: ProfileOption = None,
) -> None:
    settings = load_settings(
        ResignSettings,
        package_file=resolve_cli_path(package_file),
        rebuild=rebuild,
        tizen_version=tizen_version,
        tizen_installer_sha256=tizen_installer_sha256,
        required_packages=required_package,
        profiles_dir=resolve_cli_path(profiles_dir),
        profile=profile,
    )
    execute_resign(settings)


def format_called_process_error(exc: subprocess.CalledProcessError) -> str:
    command = shell_join(str(part) for part in exc.cmd)
    return f"Command failed with exit code {exc.returncode}: {command}"


def main() -> int:
    exit_code = 0
    try:
        app(standalone_mode=False)
    except ToolError as exc:
        eprint(str(exc))
        exit_code = 1
    except subprocess.CalledProcessError as exc:
        eprint(format_called_process_error(exc))
        exit_code = exc.returncode or 1
    except OSError as exc:
        eprint(f"Failed to run external command: {exc}")
        exit_code = 1
    except click.ClickException as exc:
        exc.show()
        exit_code = exc.exit_code
    except typer.Exit as exc:
        exit_code = exc.exit_code
    except KeyboardInterrupt:
        eprint("Interrupted")
        exit_code = 130
    return exit_code
