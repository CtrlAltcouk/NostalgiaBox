"""Maintainable dependency-boundary checks for the completed Phase 2 architecture."""

import ast
import importlib
import pkgutil
import re
from pathlib import Path

import nostalgiabox

_PACKAGE_ROOT = Path(__file__).parents[2] / "src" / "nostalgiabox"


def test_domain_has_no_infrastructure_or_filesystem_dependency() -> None:
    imports = _imports_under(_PACKAGE_ROOT / "domain")

    _assert_no_prefix(
        imports,
        "fastapi",
        "sqlalchemy",
        "alembic",
        "pathlib",
        "os",
        "nostalgiabox.application",
        "nostalgiabox.persistence",
        "nostalgiabox.playback",
        "nostalgiabox.input",
        "nostalgiabox.api",
    )
    assert "media path" not in _source_under(_PACKAGE_ROOT / "domain").lower()


def test_application_has_no_framework_orm_or_physical_protocol_details() -> None:
    imports = _imports_under(_PACKAGE_ROOT / "application")
    source = _source_under(_PACKAGE_ROOT / "application")

    _assert_no_prefix(imports, "fastapi", "sqlalchemy", "alembic", "evdev")
    for marker in ('"loadfile"', '"get_property"', "EV_KEY", "KEY_PLAYPAUSE", "/dev/input"):
        assert marker not in source


def test_persistence_playback_input_and_api_dependencies_remain_directed() -> None:
    persistence_imports = _imports_under(_PACKAGE_ROOT / "persistence")
    playback_imports = _imports_under(_PACKAGE_ROOT / "playback")
    input_imports = _imports_under(_PACKAGE_ROOT / "input")
    api_source = _source_under(_PACKAGE_ROOT / "api" / "routes")

    _assert_no_prefix(
        persistence_imports,
        "nostalgiabox.playback",
        "nostalgiabox.input",
        "nostalgiabox.api",
    )
    _assert_no_prefix(
        playback_imports,
        "sqlalchemy",
        "alembic",
        "nostalgiabox.persistence",
        "nostalgiabox.domain.timeline",
        "nostalgiabox.application.runtime",
    )
    _assert_no_prefix(input_imports, "sqlalchemy", "alembic", "nostalgiabox.persistence")
    assert "nostalgiabox.domain.timeline" not in input_imports
    for marker in ("resolve_active_entry", "loadfile", "get_property", "sqlalchemy", "evdev"):
        assert marker not in api_source.lower()


def test_raw_reference_key_binding_exists_only_in_input_profile() -> None:
    occurrences: list[Path] = []
    for path in _PACKAGE_ROOT.rglob("*.py"):
        if re.search(r"\b164\b", path.read_text(encoding="utf-8")):
            occurrences.append(path.relative_to(_PACKAGE_ROOT))

    assert occurrences == [Path("input/profile.py")]


def test_every_backend_module_imports_without_a_cycle_or_optional_evdev() -> None:
    module_names = [
        module.name
        for module in pkgutil.walk_packages(
            nostalgiabox.__path__,
            prefix=f"{nostalgiabox.__name__}.",
        )
    ]

    for module_name in module_names:
        importlib.import_module(module_name)


def _imports_under(root: Path) -> set[str]:
    imports: set[str] = set()
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                imports.add(node.module)
    return imports


def _source_under(root: Path) -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in sorted(root.rglob("*.py")))


def _assert_no_prefix(imports: set[str], *forbidden: str) -> None:
    violations = {
        imported
        for imported in imports
        if any(imported == prefix or imported.startswith(f"{prefix}.") for prefix in forbidden)
    }
    assert violations == set()
