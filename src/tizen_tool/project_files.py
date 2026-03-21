from __future__ import annotations

import shutil
from pathlib import Path

from defusedxml import ElementTree as ET
from pathspec import PathSpec

from .errors import ToolError


def validate_profiles(profiles_dir: Path, profile: str) -> None:
    profiles_xml = profiles_dir / "profiles.xml"
    if not profiles_xml.is_file():
        raise ToolError(f"profiles.xml is not found: {profiles_xml}")
    try:
        root = ET.parse(profiles_xml).getroot()
    except ET.ParseError as exc:
        raise ToolError(f"Failed to parse profiles.xml: {exc}") from exc

    for element in root.iter():
        if element.attrib.get("name") == profile:
            return

    raise ToolError(f"Profile {profile!r} is not present in {profiles_xml}")


def load_ignore_spec(ignore_file: Path | None) -> PathSpec | None:
    if ignore_file is None:
        return None
    lines = ignore_file.read_text(encoding="utf-8").splitlines()
    return PathSpec.from_lines("gitwildmatch", lines)


def copy_project_tree(src_dir: Path, dst_dir: Path, buildignore_file: Path | None) -> None:
    spec = load_ignore_spec(buildignore_file)

    def ignore(directory: str, names: list[str]) -> set[str]:
        if spec is None:
            return set()

        directory_path = Path(directory)
        relative_dir = directory_path.relative_to(src_dir)
        ignored: set[str] = set()

        for name in names:
            relative_path = (relative_dir / name).as_posix()
            if relative_path == ".":
                relative_path = name

            full_path = directory_path / name
            candidate = f"{relative_path}/" if full_path.is_dir() else relative_path
            if spec.match_file(candidate):
                ignored.add(name)

        return ignored

    shutil.copytree(src_dir, dst_dir, symlinks=True, dirs_exist_ok=True, ignore=ignore)

    if buildignore_file is not None:
        try:
            relative_ignore_path = buildignore_file.resolve().relative_to(src_dir.resolve())
        except ValueError:
            return

        copied_ignore_file = dst_dir / relative_ignore_path
        if copied_ignore_file.exists():
            copied_ignore_file.unlink()
