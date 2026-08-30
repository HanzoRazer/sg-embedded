"""Architectural guard: the kernel is native and standard-library only.

Two properties are asserted over the production source under ``acquisition/``:

* it has zero runtime dependency on the TTP Analyzer implementation;
* it carries none of that project's domain vocabulary.

The guard is deliberately narrow. Ordinary engineering words -- frequency,
measurement, noise, evidence -- are not forbidden and must never become so.
What is forbidden is importing that project or reproducing its domain
identifiers. Documentation may discuss the relationship historically; this
scans production Python only.
"""

import ast
import pathlib

import pytest

PRODUCTION_ROOT = pathlib.Path(__file__).resolve().parents[2] / "acquisition"

PRODUCTION_FILES = sorted(PRODUCTION_ROOT.glob("*.py"))

ALLOWED_TOP_LEVEL_IMPORTS = frozenset(
    {
        "collections",
        "dataclasses",
        "enum",
        "json",
        "math",
        "typing",
    }
)
"""Standard-library modules the SGAQ kernel is permitted to import.

The kernel has no third-party runtime dependency of any kind. Anything not in
this set is a deliberate decision, so it should have to be added here first.
"""

FORBIDDEN_IMPORT_SEGMENTS = frozenset({"ttp", "ttp_analyzer", "ttpanalyzer"})
"""Module path segments that would indicate a TTP runtime dependency.

Matched per dotted segment, never as a substring: ``http`` contains the
letters ``ttp`` and is not a violation of anything.
"""

FORBIDDEN_DOMAIN_IDENTIFIERS = (
    "SpecimenSpec",
    "SweepSpec",
    "ModulusBudget",
    "modulus_budget",
    "physical_repeatability_hz",
)
"""Domain identifiers belonging to another project's problem space.

Specific names, not word stems. SGAQ terminates in audio acquisition
qualification; specimen, sweep and modulus semantics belong to a different
system and must not reappear here under any spelling.
"""


def _module_names(tree: ast.AST) -> list[str]:
    """Every absolute module path imported by ``tree``.

    Relative imports are internal to the package and are skipped.
    """
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif (
            isinstance(node, ast.ImportFrom)
            and node.level == 0
            and node.module is not None
        ):
            names.append(node.module)
    return names


def test_production_source_is_present() -> None:
    """Guard against the guard silently passing over an empty directory."""
    assert PRODUCTION_ROOT.is_dir()
    assert PRODUCTION_FILES, f"no production modules found under {PRODUCTION_ROOT}"
    assert {path.name for path in PRODUCTION_FILES} >= {
        "__init__.py",
        "models.py",
        "noise.py",
        "provenance.py",
    }


@pytest.mark.parametrize("path", PRODUCTION_FILES, ids=lambda p: p.name)
def test_no_ttp_runtime_dependency(path: pathlib.Path) -> None:
    """No production module imports the TTP Analyzer implementation."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for module in _module_names(tree):
        segments = set(module.lower().split("."))
        offending = segments & FORBIDDEN_IMPORT_SEGMENTS
        assert not offending, f"{path.name} imports {module!r} ({sorted(offending)})"


@pytest.mark.parametrize("path", PRODUCTION_FILES, ids=lambda p: p.name)
def test_kernel_imports_only_the_standard_library(path: pathlib.Path) -> None:
    """No third-party runtime dependency, TTP or otherwise.

    The qualification mathematics must stay portable and deterministic enough
    to run on the instrument, which means the standard library only.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for module in _module_names(tree):
        top_level = module.split(".")[0]
        assert top_level in ALLOWED_TOP_LEVEL_IMPORTS, (
            f"{path.name} imports {module!r}, which is outside the permitted "
            f"standard-library set {sorted(ALLOWED_TOP_LEVEL_IMPORTS)}"
        )


@pytest.mark.parametrize("path", PRODUCTION_FILES, ids=lambda p: p.name)
def test_no_foreign_domain_identifiers(path: pathlib.Path) -> None:
    """No specimen, sweep, or modulus semantics in production source."""
    source = path.read_text(encoding="utf-8")
    for identifier in FORBIDDEN_DOMAIN_IDENTIFIERS:
        assert identifier not in source, (
            f"{path.name} contains the foreign domain identifier {identifier!r}"
        )


def test_the_guard_does_not_forbid_ordinary_engineering_language() -> None:
    """The guard must stay narrow enough to be worth keeping.

    A check that failed on words like "frequency" or "measurement" would be
    deleted within a week, and the real protection would go with it. These
    words appear throughout the kernel and must remain entirely legal.
    """
    corpus = "\n".join(
        path.read_text(encoding="utf-8") for path in PRODUCTION_FILES
    )
    for ordinary in ("frequency", "measurement", "noise", "evidence", "jitter"):
        assert ordinary in corpus

    for identifier in FORBIDDEN_DOMAIN_IDENTIFIERS:
        assert identifier not in corpus

    assert "http" not in FORBIDDEN_IMPORT_SEGMENTS
