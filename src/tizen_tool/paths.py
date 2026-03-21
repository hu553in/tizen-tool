from pathlib import Path

ENV_FILE_NAME = ".env"
CACHE_ROOT_NAME = ".tizen-tool"


def working_directory() -> Path:
    return Path.cwd().resolve()


def env_file_path() -> Path:
    return working_directory() / ENV_FILE_NAME


def cache_root() -> Path:
    return working_directory() / CACHE_ROOT_NAME


def temp_root() -> Path:
    return cache_root() / "tmp"
