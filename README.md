# Tizen tool

[![CI](https://github.com/hu553in/tizen-tool/actions/workflows/ci.yml/badge.svg)](https://github.com/hu553in/tizen-tool/actions/workflows/ci.yml)

- [License](./LICENSE)
- [How to contribute](./CONTRIBUTING.md)
- [Code of conduct](./CODE_OF_CONDUCT.md)

`tizen-tool` is a small CLI for building, re-signing, and installing Tizen web packages
through a Dockerized Tizen Studio environment.

It provides:

- a reproducible Tizen Studio setup inside Docker
- `build`, `resign`, and `install` commands
- strict configuration loading from CLI arguments and `.env`
- installer checksum verification
- Docker image reuse keyed by the tool version, required packages, and bundled Docker resources

The project is intentionally small. It is designed to remain predictable, easy to audit,
and simple to run from a single working directory.

---

## What it does

- Builds a `.wgt` package from a Tizen web app directory
- Re-signs an existing `.wgt` package with a configured profile
- Installs a `.wgt` package on a TV over `sdb`
- Builds and reuses a local Docker image with Tizen Studio and the required Tizen packages

Typical workflow:

1. Configure `.env`
2. Build or re-sign a package
3. Install it on a TV

---

## Requirements

- Python 3.10 or newer
- Docker with Linux image support
- [uv](https://docs.astral.sh/uv/)
- a valid Tizen signing profile directory containing `profiles.xml`

The default local development version is Python 3.14, as defined in
[`.python-version`](./.python-version). CI also runs on Python 3.14.

---

## Installation

### Install as a tool

```bash
uv tool install tizen-tool
```

You can also use `pipx`:

```bash
pipx install tizen-tool
```

### Local development

```bash
make install_deps
```

---

## Configuration

The tool reads `.env` from the current working directory. CLI arguments override `.env` values.

| Name                                                               | Required         | Description                                                                                          |
| ------------------------------------------------------------------ | ---------------- | ---------------------------------------------------------------------------------------------------- |
| `TIZEN_VERSION`                                                    | Yes              | Tizen Studio version used to resolve the installer URL.                                              |
| `REQUIRED_PACKAGES`                                                | Yes              | JSON array of Tizen package IDs installed into the Docker image.                                     |
| `TIZEN_INSTALLER_SHA256`                                           | Yes              | Expected SHA-256 checksum for the installer binary.                                                  |
| `PROFILES_DIR`                                                     | Build / resign   | Directory containing `profiles.xml`. Relative paths are resolved from the current working directory. |
| `PROFILE`                                                          | Build / resign   | Signing profile name from `profiles.xml`.                                                            |
| `TV_IP`                                                            | Install          | TV address or serial. Accepted forms: `host`, `host:port`, `IPv4`, or `[IPv6]:port`.                 |
| `BUILD_SRC_DIR` or `SRC_DIR`                                       | Build fallback   | Source directory for the app when not passed on the CLI.                                             |
| `BUILDIGNORE_FILE` or `BUILD_IGNORE_FILE`                          | Build fallback   | Optional gitignore-style exclude file for the build copy step.                                       |
| `BUILD_REBUILD`, `INSTALL_REBUILD`, `RESIGN_REBUILD`, or `REBUILD` | No               | Forces Docker image rebuilding for the corresponding command.                                        |
| `INSTALL_PACKAGE_FILE` or `PACKAGE_FILE`                           | Install fallback | `.wgt` package path used when not passed on the CLI.                                                 |
| `RESIGN_PACKAGE_FILE` or `PACKAGE_FILE`                            | Resign fallback  | `.wgt` package path used when not passed on the CLI.                                                 |

See [`.env.example`](./.env.example) for a complete example.

---

## Commands

Build a package:

```bash
tizen-tool build /path/to/app
```

Build with explicit package overrides:

```bash
tizen-tool build /path/to/app \
  --required-package TV-Samsung_Public_6.0 \
  --required-package TV-Samsung_Wearable_6.0
```

Re-sign a package:

```bash
tizen-tool resign /path/to/app.wgt
```

Install a package on the configured TV:

```bash
tizen-tool install /path/to/app.wgt
```

Override the TV target from the CLI:

```bash
tizen-tool install /path/to/app.wgt --tv-ip 192.168.1.100
```

Force rebuilding the Docker image:

```bash
tizen-tool build /path/to/app --rebuild
```

You can also run the package directly from a checkout:

```bash
uv run tizen-tool --help
```

---

## Outputs and runtime behavior

- `build` copies the app into a temporary directory, runs `tizen build-web`,
  and writes the final `.wgt` to `dist/` inside the source directory
- `resign` writes the new package to `resigned/` next to the source package
- `install` mounts the package directory read-only and installs by package name over `sdb`
- temporary files are stored under `.tizen-tool/tmp/` in the current working directory
- the Docker image is reused unless its identifying labels no longer match the requested configuration

During image build, the installer helper tries both known Tizen installer URL patterns
and stops at the first successful match.

---

## Development

Useful commands:

```bash
make install_deps
make lint
make check_types
make check
make check_deps_updates
make check_deps_vuln
make build
```

The development toolchain uses:

- `ruff`
- `ty`
- `prek`
- `pysentry-rs`
- `bandit`

Run the full local check suite:

```bash
make check
```

---

## Release

Create a release from the `main` branch with a clean working tree:

```bash
make release V=0.1.0
```

The `release` target:

- installs dependencies
- runs the local checks
- builds distributions
- updates the version if `V` differs from the current project version
- commits and pushes the version bump when needed
- creates and pushes the annotated tag `v<V>`

GitHub Actions publishes tagged releases to PyPI from
[`.github/workflows/ci.yml`](./.github/workflows/ci.yml).
