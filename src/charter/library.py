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
    for path in sorted(directory.glob("*.yaml")):
        try:
            raw = yaml.safe_load(path.read_text()) or {}
            obj = model(**raw)
        except (ValidationError, TypeError, yaml.YAMLError) as exc:
            raise LibraryError(f"{path.name}: {exc}") from exc
        out[obj.id] = obj
    if not out:
        raise LibraryError(f"no definitions found in {directory}")
    return out


def load_roles(root: Path | None = None) -> dict[str, RoleDef]:
    return _load_dir((root or DEFINITIONS_ROOT) / "roles", RoleDef)


def load_methodologies(root: Path | None = None) -> dict[str, MethodologyDef]:
    return _load_dir((root or DEFINITIONS_ROOT) / "methodologies", MethodologyDef)
