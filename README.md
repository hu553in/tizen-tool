# Tizen tool

[![CI](https://github.com/hu553in/tizen-tool/actions/workflows/ci.yml/badge.svg)](https://github.com/hu553in/tizen-tool/actions/workflows/ci.yml)

CLI for building, re-signing, and installing Tizen web packages through Dockerized Tizen Studio.

## What it does

- Builds `.wgt` packages from Tizen web app directories
- Re-signs existing `.wgt` packages with a configured signing profile
- Installs `.wgt` packages on a TV over `sdb`
- Builds and reuses a local Docker image with Tizen Studio and required packages
- Loads settings from CLI arguments, environment variables, and `.env`
- Caches Tizen Studio installers by version

## Requirements

- Python 3.10+
- Docker with Linux image support
- `uv`
- Tizen signing profile directory with `profiles.xml`
- Tizen Studio version 3.7 or newer configured through `TIZEN_VERSION`

Local development uses Python 3.14 from `.python-version`.

## Setup

Install as a `uv` tool:

```bash
uv tool install git+https://github.com/hu553in/tizen-tool.git
```

Or run without installing:

```bash
uvx --from git+https://github.com/hu553in/tizen-tool.git tizen-tool --help
```

## Configuration

The tool reads `.env` from the current working directory. Precedence:

1. CLI arguments
2. Environment variables
3. `.env`

| Name                                                               | Required         | Description                                        |
| ------------------------------------------------------------------ | ---------------- | -------------------------------------------------- |
| `TIZEN_VERSION`                                                    | Yes              | Tizen Studio version used to resolve the installer |
| `REQUIRED_PACKAGES`                                                | Yes              | JSON array of Tizen package IDs                    |
| `CACHE_DIR`                                                        | No               | Cache directory, default `~/.tizen-tool`           |
| `PROFILES_DIR`                                                     | Build or resign  | Directory containing `profiles.xml`                |
| `PROFILE`                                                          | Build or resign  | Signing profile name                               |
| `TV_IP`                                                            | Install          | TV host, `host:port`, IPv4, or `[IPv6]:port`       |
| `BUILD_SRC_DIR` or `SRC_DIR`                                       | Build fallback   | Source directory when not passed on the CLI        |
| `BUILDIGNORE_FILE` or `BUILD_IGNORE_FILE`                          | Build fallback   | Optional gitignore-style build exclude file        |
| `INSTALL_PACKAGE_FILE` or `PACKAGE_FILE`                           | Install fallback | `.wgt` package path when not passed on the CLI     |
| `RESIGN_PACKAGE_FILE` or `PACKAGE_FILE`                            | Resign fallback  | `.wgt` package path when not passed on the CLI     |
| `BUILD_REBUILD`, `INSTALL_REBUILD`, `RESIGN_REBUILD`, or `REBUILD` | No               | Force Docker image rebuild for the command         |

See `.env.example` for a common example.

## Usage

```bash
tizen-tool build /path/to/app
tizen-tool resign /path/to/app.wgt
tizen-tool install /path/to/app.wgt
tizen-tool get-lan-ips
```

Useful options:

```bash
tizen-tool build /path/to/app --required-package TV-Samsung_Public_6.0
tizen-tool build /path/to/app --rebuild
tizen-tool install /path/to/app.wgt --tv-ip 192.168.1.100
```

Run from a checkout:

```bash
uv run tizen-tool --help
```

## Runtime behavior

- `build` copies the app to a temp directory, runs `tizen build-web`, and writes `.wgt` to `dist/`
  inside the source directory
- `resign` writes the new package to `resigned/` next to the source package
- `install` mounts the package directory read-only and installs by package name over `sdb`
- Installers are cached under `<CACHE_DIR>/installers/`
- Temporary files are stored under `<CACHE_DIR>/tmp/`
- Docker images are reused while their identifying labels match the requested configuration

## Development

```bash
make install-deps
make check
make build
```

Focused checks:

```bash
make lint
make check-types
```
