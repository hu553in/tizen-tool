from pathlib import Path

ENV_FILE_NAME = ".env"
CACHE_ROOT_NAME = ".tizen-tool"


def working_directory() -> Path:
    return Path.cwd().resolve()


def home_directory() -> Path:
    return Path.home().resolve()


def env_file_path() -> Path:
    return working_directory() / ENV_FILE_NAME


def cache_root() -> Path:
    return home_directory() / CACHE_ROOT_NAME


def temp_root(cache_dir: Path) -> Path:
    return cache_dir / "tmp"


def installer_cache_root(cache_dir: Path) -> Path:
    return cache_dir / "installers"
