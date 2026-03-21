from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Annotated

import click
import typer

from .docker_ops import execute_build, execute_install, execute_resign
from .errors import ToolError
from .settings import (
    BuildSettings,
    InstallSettings,
    ResignSettings,
    load_settings,
    resolve_cli_path,
)

app = typer.Typer(
    name="tizen-tool",
    help="Build, re-sign, and install Tizen packages through Dockerized Tizen Studio.",
    no_args_is_help=True,
    pretty_exceptions_show_locals=False,
)

REQUIRED_PACKAGE_HELP = (
    "Required Tizen package. Repeat the option to override REQUIRED_PACKAGES from env."
)


def eprint(message: str) -> None:
    print(message, file=sys.stderr)


@app.command("build")
def build_command(
    src_dir: Annotated[
        Path | None,
        typer.Argument(
            help=(
                "Source directory containing the Tizen web app. "
                "Falls back to BUILD_SRC_DIR or SRC_DIR."
            )
        ),
    ] = None,
    buildignore_file: Annotated[
        Path | None,
        typer.Argument(
            help=(
                "Optional gitignore-style exclude file. "
                "Falls back to BUILDIGNORE_FILE or BUILD_IGNORE_FILE."
            )
        ),
    ] = None,
    rebuild: Annotated[
        bool | None,
        typer.Option(
            "--rebuild/--no-rebuild",
            help="Override rebuild behavior. Falls back to BUILD_REBUILD or REBUILD.",
        ),
    ] = None,
    required_package: Annotated[
        list[str] | None, typer.Option("--required-package", help=REQUIRED_PACKAGE_HELP)
    ] = None,
) -> None:
    settings = load_settings(
        BuildSettings,
        src_dir=resolve_cli_path(src_dir),
        buildignore_file=resolve_cli_path(buildignore_file),
        rebuild=rebuild,
        required_packages=required_package,
    )
    execute_build(settings)


@app.command("install")
def install_command(
    package_file: Annotated[
        Path | None,
        typer.Argument(
            help="Path to the .wgt package. Falls back to INSTALL_PACKAGE_FILE or PACKAGE_FILE."
        ),
    ] = None,
    rebuild: Annotated[
        bool | None,
        typer.Option(
            "--rebuild/--no-rebuild",
            help="Override rebuild behavior. Falls back to INSTALL_REBUILD or REBUILD.",
        ),
    ] = None,
    tv_ip: Annotated[
        str | None, typer.Option("--tv-ip", help="TV address or serial. Falls back to TV_IP.")
    ] = None,
    required_package: Annotated[
        list[str] | None, typer.Option("--required-package", help=REQUIRED_PACKAGE_HELP)
    ] = None,
) -> None:
    settings = load_settings(
        InstallSettings,
        package_file=resolve_cli_path(package_file),
        rebuild=rebuild,
        tv_ip=tv_ip,
        required_packages=required_package,
    )
    execute_install(settings)


@app.command("resign")
def resign_command(
    package_file: Annotated[
        Path | None,
        typer.Argument(
            help="Path to the .wgt package. Falls back to RESIGN_PACKAGE_FILE or PACKAGE_FILE."
        ),
    ] = None,
    rebuild: Annotated[
        bool | None,
        typer.Option(
            "--rebuild/--no-rebuild",
            help="Override rebuild behavior. Falls back to RESIGN_REBUILD or REBUILD.",
        ),
    ] = None,
    required_package: Annotated[
        list[str] | None, typer.Option("--required-package", help=REQUIRED_PACKAGE_HELP)
    ] = None,
) -> None:
    settings = load_settings(
        ResignSettings,
        package_file=resolve_cli_path(package_file),
        rebuild=rebuild,
        required_packages=required_package,
    )
    execute_resign(settings)


def format_called_process_error(exc: subprocess.CalledProcessError) -> str:
    command = " ".join(str(part) for part in exc.cmd)
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
