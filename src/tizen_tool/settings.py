from __future__ import annotations

import ipaddress
from pathlib import Path
from typing import Any, TypeVar

from pydantic import (
    AliasChoices,
    DirectoryPath,
    Field,
    FilePath,
    ValidationError,
    computed_field,
    field_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

from .errors import ToolError
from .paths import env_file_path, working_directory

DEFAULT_TV_PORT = 26101
MAX_PORT = 65535
SHA256_HEX_LENGTH = 64
SettingsT = TypeVar("SettingsT", bound="CommonSettings")


def resolve_working_path(value: Any) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = working_directory() / path
    return path.resolve()


def resolve_cli_path(path: Path | None) -> Path | None:
    if path is None:
        return None
    return path.expanduser().resolve()


def normalize_tv_serial(raw_value: str) -> str:
    value = raw_value.strip()
    if not value:
        raise ValueError("must not be empty")

    def validate_port(port: str) -> str:
        if not port.isdigit():
            raise ValueError("must use a numeric port")
        if not 1 <= int(port) <= MAX_PORT:
            raise ValueError("must use a port in the range 1-65535")
        return port

    if value.startswith("["):
        if "]" not in value:
            raise ValueError("uses bracketed IPv6 syntax but is missing a closing bracket")
        host, remainder = value[1:].split("]", 1)
        try:
            ipaddress.IPv6Address(host)
        except ValueError as exc:
            raise ValueError(f"contains an invalid IPv6 address: {host}") from exc

        if remainder == "":
            return f"[{host}]:{DEFAULT_TV_PORT}"
        if not remainder.startswith(":"):
            raise ValueError("must use [IPv6]:port when specifying a port for IPv6")
        validate_port(remainder[1:])
        return value

    if value.count(":") > 1:
        try:
            ipaddress.IPv6Address(value)
        except ValueError as exc:
            raise ValueError("must be host, host:port, IPv4, or [IPv6]:port") from exc
        return f"[{value}]:{DEFAULT_TV_PORT}"

    if ":" not in value:
        return f"{value}:{DEFAULT_TV_PORT}"

    host, port = value.rsplit(":", 1)
    if not host:
        raise ValueError("must use host:port when specifying a port")
    validate_port(port)
    return value


def normalize_package_file_path(value: Any) -> Path:
    return resolve_working_path(value)


def validate_wgt_path(path: Path) -> Path:
    if path.suffix.lower() != ".wgt":
        raise ValueError("must point to a .wgt file")
    return path


class CommonSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(env_file_path()),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    tizen_version: str = Field(validation_alias="TIZEN_VERSION")
    required_packages: list[str] = Field(validation_alias="REQUIRED_PACKAGES")
    tizen_installer_sha256: str | None = Field(
        default=None, validation_alias="TIZEN_INSTALLER_SHA256"
    )
    profiles_dir: DirectoryPath | None = Field(default=None, validation_alias="PROFILES_DIR")
    profile: str | None = Field(default=None, validation_alias="PROFILE")
    tv_ip: str | None = Field(default=None, validation_alias="TV_IP")

    @computed_field
    @property
    def image_tag(self) -> str:
        return f"tizen-studio:{self.tizen_version}"

    @field_validator("required_packages")
    @classmethod
    def validate_required_packages(cls, value: list[str]) -> list[str]:
        packages: list[str] = []
        seen: set[str] = set()
        for package in value:
            normalized = package.strip()
            if not normalized or normalized in seen:
                continue
            packages.append(normalized)
            seen.add(normalized)
        if not packages:
            raise ValueError("must list at least one package")
        return packages

    @field_validator("tizen_installer_sha256")
    @classmethod
    def validate_installer_sha256(cls, value: str | None) -> str | None:
        if value in (None, ""):
            return None
        normalized = value.strip().lower()
        if len(normalized) != SHA256_HEX_LENGTH or any(
            ch not in "0123456789abcdef" for ch in normalized
        ):
            raise ValueError("must be a 64-character hexadecimal SHA-256 digest")
        return normalized

    @field_validator("profiles_dir", mode="before")
    @classmethod
    def normalize_profiles_dir(cls, value: Any) -> Path | None:
        if value in (None, ""):
            return None
        return resolve_working_path(value)


class BuildSettings(CommonSettings):
    src_dir: DirectoryPath = Field(validation_alias=AliasChoices("BUILD_SRC_DIR", "SRC_DIR"))
    buildignore_file: FilePath | None = Field(
        default=None, validation_alias=AliasChoices("BUILDIGNORE_FILE", "BUILD_IGNORE_FILE")
    )
    rebuild: bool = Field(default=False, validation_alias=AliasChoices("BUILD_REBUILD", "REBUILD"))
    profiles_dir: DirectoryPath = Field(validation_alias="PROFILES_DIR")
    profile: str = Field(validation_alias="PROFILE")

    @field_validator("src_dir", mode="before")
    @classmethod
    def normalize_src_dir(cls, value: Any) -> Path:
        return resolve_working_path(value)

    @field_validator("buildignore_file", mode="before")
    @classmethod
    def normalize_buildignore_file(cls, value: Any) -> Path | None:
        if value in (None, ""):
            return None
        return resolve_working_path(value)


class InstallSettings(CommonSettings):
    package_file: FilePath = Field(
        validation_alias=AliasChoices("INSTALL_PACKAGE_FILE", "PACKAGE_FILE")
    )
    rebuild: bool = Field(
        default=False, validation_alias=AliasChoices("INSTALL_REBUILD", "REBUILD")
    )
    tv_ip: str = Field(validation_alias="TV_IP")

    @field_validator("package_file", mode="before")
    @classmethod
    def normalize_package_file(cls, value: Any) -> Path:
        return normalize_package_file_path(value)

    @field_validator("package_file")
    @classmethod
    def validate_package_file(cls, value: Path) -> Path:
        return validate_wgt_path(value)

    @field_validator("tv_ip")
    @classmethod
    def normalize_tv_ip(cls, value: str) -> str:
        return normalize_tv_serial(value)


class ResignSettings(CommonSettings):
    package_file: FilePath = Field(
        validation_alias=AliasChoices("RESIGN_PACKAGE_FILE", "PACKAGE_FILE")
    )
    rebuild: bool = Field(default=False, validation_alias=AliasChoices("RESIGN_REBUILD", "REBUILD"))
    profiles_dir: DirectoryPath = Field(validation_alias="PROFILES_DIR")
    profile: str = Field(validation_alias="PROFILE")

    @field_validator("package_file", mode="before")
    @classmethod
    def normalize_package_file(cls, value: Any) -> Path:
        return normalize_package_file_path(value)

    @field_validator("package_file")
    @classmethod
    def validate_package_file(cls, value: Path) -> Path:
        return validate_wgt_path(value)


def format_validation_error(exc: ValidationError) -> str:
    messages: list[str] = []
    for error in exc.errors(include_url=False):
        location = ".".join(str(part) for part in error.get("loc", ()))
        message = error.get("msg", "invalid value")
        messages.append(f"{location}: {message}" if location else message)
    return "Invalid configuration:\n- " + "\n- ".join(messages)


def load_settings(settings_type: type[SettingsT], **overrides: Any) -> SettingsT:
    normalized_overrides = {key: value for key, value in overrides.items() if value is not None}

    try:
        return settings_type(**normalized_overrides)
    except ValidationError as exc:
        raise ToolError(format_validation_error(exc)) from exc
