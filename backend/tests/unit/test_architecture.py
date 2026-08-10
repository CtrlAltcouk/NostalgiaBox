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


def test_task31_catalogue_foundation_has_no_scanner_or_probe_dependencies() -> None:
    catalogue_files = [
        _PACKAGE_ROOT / "domain" / "catalogue.py",
        _PACKAGE_ROOT / "application" / "catalogue.py",
        _PACKAGE_ROOT / "persistence" / "catalogue_mappers.py",
        _PACKAGE_ROOT / "persistence" / "catalogue_repositories.py",
    ]
    source = "\n".join(path.read_text(encoding="utf-8") for path in catalogue_files)
    imports = set().union(*(_imports_under(path.parent) for path in catalogue_files[:2]))

    _assert_no_prefix(imports, "subprocess", "fastapi", "sqlalchemy", "alembic", "pydantic")
    for marker in ("ffprobe", "fingerprint", "directory scan", "os.walk", "rglob("):
        assert marker not in source.lower()


def test_task32_source_lifecycle_keeps_filesystem_and_policy_boundaries_directed() -> None:
    application_source = (_PACKAGE_ROOT / "application" / "sources.py").read_text(encoding="utf-8")
    persistence_source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            _PACKAGE_ROOT / "persistence" / "catalogue_repositories.py",
            _PACKAGE_ROOT / "persistence" / "source_uow.py",
        )
    )
    local_adapter = (_PACKAGE_ROOT / "source" / "local.py").read_text(encoding="utf-8")

    for marker in ("pathlib", "os.scandir", "os.stat", "sqlalchemy", "fastapi", "ffprobe"):
        assert marker not in application_source.lower()
    for marker in ("pathlib", "is_relative_to", "os.scandir", "approved_roots"):
        assert marker not in persistence_source
    for marker in ("os.walk", "rglob(", "ffprobe", "subprocess", "sqlalchemy", "fastapi"):
        assert marker not in local_adapter.lower()
    assert "os.scandir" in local_adapter


def test_phase2_timeline_and_runtime_do_not_depend_on_catalogue_infrastructure() -> None:
    phase2_files = [
        _PACKAGE_ROOT / "domain" / "timeline.py",
        _PACKAGE_ROOT / "application" / "runtime.py",
    ]

    for path in phase2_files:
        assert "nostalgiabox.domain.catalogue" not in path.read_text(encoding="utf-8")
        assert "nostalgiabox.persistence.catalogue" not in path.read_text(encoding="utf-8")


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
