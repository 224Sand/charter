"""Loads kernel definitions from YAML.

Kept out of charter.kernel deliberately: the kernel is pure and does no I/O,
so all filesystem access for definitions is concentrated here.
"""
from pathlib import Path

import yaml
from pydantic import ValidationError

from charter.kernel.models import MethodologyDef, RoleDef

DEFINITIONS_ROOT = Path(__file__).parent / "kernel" / "definitions"


class LibraryError(Exception):
    """A definition file is missing or malformed."""


def _load_dir(directory: Path, model):
    if not directory.is_dir():
        raise LibraryError(f"definitions directory not found: {directory}")
    out = {}
    seen: dict[str, str] = {}
    files = sorted(
        [*directory.glob("*.yaml"), *directory.glob("*.yml")],
        key=lambda p: p.name,
    )
    for path in files:
        try:
            raw = yaml.safe_load(path.read_text()) or {}
            obj = model(**raw)
        except (ValidationError, TypeError, yaml.YAMLError, OSError,
                UnicodeDecodeError) as exc:
            raise LibraryError(f"{path.name}: {exc}") from exc
        # Two files claiming one id is a config error, not a merge. Silently
        # letting the later filename win makes the roster depend on sort order.
        if obj.id in seen:
            raise LibraryError(
                f"{path.name}: duplicate id {obj.id!r}, already defined in "
                f"{seen[obj.id]}")
        seen[obj.id] = path.name
        out[obj.id] = obj
    if not out:
        raise LibraryError(f"no definitions found in {directory}")
    return out


def load_roles(root: Path | None = None) -> dict[str, RoleDef]:
    return _load_dir((root or DEFINITIONS_ROOT) / "roles", RoleDef)


def load_methodologies(root: Path | None = None) -> dict[str, MethodologyDef]:
    return _load_dir((root or DEFINITIONS_ROOT) / "methodologies", MethodologyDef)
