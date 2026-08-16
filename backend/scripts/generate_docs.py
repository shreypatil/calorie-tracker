"""Derive the in-app documentation from the things it documents.

    python -m scripts.generate_docs            # regenerate
    python -m scripts.generate_docs --check     # fail if the committed output is stale

Documentation that is a *copy* of a source of truth rots, and rotted documentation is worse than
none because it is believed. So every page here has exactly one authoritative source and is derived
from it: requirements from `requirements.md`, the test inventory from pytest itself, dependency
versions from the manifests that install them, the feature guide from `docs/features.md`.

The part that makes this worth doing is `_verify_features`. Deriving the feature guide from a
markdown file would still let it claim things that stopped being true — so every endpoint it names
is checked against the app's actual OpenAPI paths, and every source file it points at is checked to
exist. A broken reference fails the build instead of being published.

Output lands in `frontend/src/docs/generated/` and is committed, so a fresh clone shows complete
docs without running anything.
"""

import ast
import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

BACKEND = Path(__file__).resolve().parent.parent
ROOT = BACKEND.parent
OUT = ROOT / "frontend" / "src" / "docs" / "generated"

# ---------------------------------------------------------------------------
# Requirements — from requirements.md
# ---------------------------------------------------------------------------

_REQUIREMENT = re.compile(r"^### (FR|NFR)-(\d+)\s+—\s+(.+)$", re.M)


def build_requirements() -> dict[str, Any]:
    """Parse the FR/NFR sections, their prose, and their acceptance criteria."""
    text = (ROOT / "requirements.md").read_text(encoding="utf-8")
    matches = list(_REQUIREMENT.finditer(text))

    items = []
    for index, match in enumerate(matches):
        kind, number, title = match.groups()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[match.end() : end]

        # Everything before "**Acceptance criteria**" is the description; the bullet list after it
        # is the criteria. Sections without criteria (the NFRs) simply get an empty list.
        head, _, tail = body.partition("**Acceptance criteria**")
        description = " ".join(line.strip() for line in head.strip().splitlines() if line.strip())
        criteria = [
            re.sub(r"\s+", " ", line.lstrip("- ").strip())
            for line in tail.splitlines()
            if line.strip().startswith("- ")
        ]

        items.append(
            {
                "id": f"{kind}-{number}",
                "kind": "functional" if kind == "FR" else "non-functional",
                "title": title.strip(),
                "description": _clip(description),
                "criteria": criteria,
            }
        )

    if not items:
        raise SystemExit("requirements.md: no FR/NFR headings matched — has the format changed?")
    return {"items": items}


def _clip(text: str, limit: int = 600) -> str:
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + "…"


# ---------------------------------------------------------------------------
# Tests — from pytest and the test sources themselves
# ---------------------------------------------------------------------------


def build_tests() -> dict[str, Any]:
    """Inventory every test, with its docstring, grouped by file.

    Classified by fixture: a test that takes `client` drives the API over HTTP and is functional;
    one that does not exercises a unit directly. That is a real distinction in this suite rather
    than a label applied by hand.
    """
    # Two numbers, deliberately. The AST gives one entry per `def test_*`, which is what a reader
    # wants to browse; pytest expands `@parametrize` into a case per argument set, which is the
    # number `make test` prints. Reporting only the first would quietly disagree with the suite.
    collected = _collected_counts()
    files = []
    total = 0

    for path in sorted((BACKEND / "tests").glob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        module_doc = ast.get_docstring(tree) or ""

        cases = []
        for node in tree.body:
            if not isinstance(node, ast.FunctionDef) or not node.name.startswith("test_"):
                continue
            args = {argument.arg for argument in node.args.args}
            cases.append(
                {
                    "name": node.name,
                    "kind": "functional" if "client" in args else "unit",
                    "description": _first_sentence(ast.get_docstring(node) or ""),
                }
            )

        total += len(cases)
        files.append(
            {
                "file": f"backend/tests/{path.name}",
                "purpose": _first_sentence(module_doc),
                "count": len(cases),
                "collected": collected.get(f"tests/{path.name}", len(cases)),
                "cases": cases,
            }
        )

    return {
        "total": total,
        "collected": sum(collected.values()) or total,
        "files": files,
        "frontend": [
            {
                "file": "frontend/scripts/screenshots.mjs",
                "kind": "browser",
                "description": (
                    "Drives a real browser through every screen, exercises the photo scan, the "
                    "nutrition estimate and a chat turn, and fails on any console error."
                ),
            },
            {
                "file": "frontend/scripts/validate-palette.mjs",
                "kind": "check",
                "description": (
                    "Simulates protanopia, deuteranopia and tritanopia and fails if any chart "
                    "series pair falls below the CIEDE2000 separation threshold."
                ),
            },
            {
                "file": "frontend (tsc + oxlint + build)",
                "kind": "check",
                "description": "Type check, lint and production build, run by `make test`.",
            },
        ],
        # Deliberately empty: these are records of testing actually performed, and inventing them
        # would defeat the purpose. Fill in as manual verification is done.
        "manual": [],
        "manual_columns": ["area", "scenario", "environment", "expected", "observed", "date"],
    }


def _collected_counts() -> dict[str, int]:
    """Per-file counts straight from pytest, so the totals match what `make test` reports."""
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider"],
        cwd=BACKEND,
        capture_output=True,
        text=True,
    )
    counts: dict[str, int] = {}
    for line in result.stdout.splitlines():
        name, separator, count = line.partition(": ")
        if separator and name.startswith("tests/") and count.strip().isdigit():
            counts[name] = int(count)
    return counts


def _first_sentence(text: str) -> str:
    collapsed = " ".join(text.split())
    if not collapsed:
        return ""
    head, separator, _ = collapsed.partition(". ")
    return _clip(head + ("." if separator else ""), 240)


# ---------------------------------------------------------------------------
# Architecture — real versions, from the manifests that install them
# ---------------------------------------------------------------------------

LAYERS = [
    ("backend/app/core", "Config, security, dependencies, errors, pagination, logging."),
    ("backend/app/db", "Engine and session, declarative base, ORM models."),
    ("backend/app/schemas", "Pydantic request and response models — the validation boundary."),
    ("backend/app/services", "All business logic. Every function takes the owning user_id."),
    ("backend/app/services/reports", "The composable aggregation layer every report is built on."),
    ("backend/app/services/chat", "Tool registry, argument dispatch, the bounded agent loop."),
    ("backend/app/services/photo", "Image normalisation, vision extraction, verification."),
    ("backend/app/services/imports", "PDF extraction, mapping, preview, commit and undo."),
    ("backend/app/ai", "Provider Protocol, deterministic stub, one OpenAI-compatible adapter."),
    ("backend/app/api/v1/routers", "HTTP layer only — parse, authorize, delegate."),
    ("frontend/src/lib", "API client, session, query hooks, formatting."),
    ("frontend/src/components", "UI primitives and charts."),
    ("frontend/src/pages", "One file per screen."),
]

INVARIANTS = [
    (
        "Routers are thin; services hold the logic",
        "Routes parse, authorize and delegate. This is what lets a chat tool call the same "
        "create_entry the REST API calls instead of growing a second implementation of the app.",
    ),
    (
        "Services always take the owning user_id",
        "There is deliberately no get_entry(session, id). Isolation survives someone adding a "
        "route without thinking about it. Another user's record returns 404, not 403.",
    ),
    (
        "Goals are versioned, never mutated across time",
        "The goal in force on a date is the latest version at or before it. Without this, "
        "changing a target silently rewrites what every past day was measured against.",
    ),
    (
        "food_entries is a fact table; aggregation never touches JSON",
        "Anything that might be aggregated gets a typed column. micros_extra is display-only.",
    ),
    (
        "A new report is a new caller, not new SQL",
        "METRICS and DIMENSIONS registries plus one aggregate(). Names resolve through the "
        "registries, so user input never reaches the query text — that is the injection defence.",
    ),
    (
        "All dialect-specific SQL lives in one helper",
        "Exactly one construct differs between SQLite and PostgreSQL, which is what keeps the "
        "Postgres move a configuration change.",
    ),
]


def build_architecture() -> dict[str, Any]:
    backend_manifest = tomllib.loads((BACKEND / "pyproject.toml").read_text(encoding="utf-8"))
    project = backend_manifest["project"]

    backend_deps = [_split_requirement(item) for item in project.get("dependencies", [])]
    for extra, items in project.get("optional-dependencies", {}).items():
        backend_deps += [{**_split_requirement(item), "extra": extra} for item in items]

    package = json.loads((ROOT / "frontend" / "package.json").read_text(encoding="utf-8"))
    frontend_deps = [
        {"name": name, "version": version}
        for name, version in sorted(package.get("dependencies", {}).items())
    ]

    return {
        "python": project.get("requires-python", ""),
        "backend_dependencies": backend_deps,
        "frontend_dependencies": frontend_deps,
        "layers": [{"path": path, "purpose": purpose} for path, purpose in LAYERS],
        "invariants": [{"title": title, "detail": detail} for title, detail in INVARIANTS],
    }


def _split_requirement(requirement: str) -> dict[str, str]:
    match = re.match(r"^([A-Za-z0-9._-]+(?:\[[^\]]+\])?)\s*(.*)$", requirement.strip())
    if not match:
        return {"name": requirement, "version": ""}
    return {"name": match.group(1), "version": match.group(2).strip()}


# ---------------------------------------------------------------------------
# Features — parsed from docs/features.md, then checked against reality
# ---------------------------------------------------------------------------

# Tuples, not sets: set iteration order varies between processes under hash randomisation, which
# made the generated JSON differ run to run and `--check` report staleness against its own output.
_REPEATABLE = ("endpoint", "source", "control")
_SINGLE = ("screen", "summary", "use", "internal", "safeguard")


def build_features(paths: set[str]) -> dict[str, Any]:
    text = (ROOT / "docs" / "features.md").read_text(encoding="utf-8")
    # Fenced blocks first: the file documents its own format with a fenced example containing a
    # `## Feature name` line, which would otherwise parse as a feature — and did, on the first run.
    text = re.sub(r"^```.*?^```", "", text, flags=re.M | re.S)
    # The header before the first `## ` is the file's own instructions, not a feature.
    sections = re.split(r"^## ", text, flags=re.M)[1:]

    features = []
    for section in sections:
        lines = section.strip().splitlines()
        feature: dict[str, Any] = {"name": lines[0].strip()}
        feature.update({key: [] for key in _REPEATABLE})

        for line in lines[1:]:
            key, separator, value = line.partition(":")
            key = key.strip().lower()
            if not separator:
                continue
            if key in _REPEATABLE:
                feature[key].append(value.strip())
            elif key in _SINGLE:
                feature[key] = value.strip()

        features.append(feature)

    _verify_features(features, paths)
    return {"features": features}


def _verify_features(features: list[dict], paths: set[str]) -> None:
    """Fail the build when the guide describes something that no longer exists.

    This is the whole reason the docs are generated rather than written. Without it the feature
    guide would keep confidently naming an endpoint that was renamed six months ago.
    """
    problems: list[str] = []

    for feature in features:
        for reference in feature["endpoint"]:
            method, _, path = reference.partition(" ")
            if (path.strip(), method.strip().lower()) not in paths:
                problems.append(f"{feature['name']}: no such endpoint — {reference}")
        for source in feature["source"]:
            if not (ROOT / source).exists():
                problems.append(f"{feature['name']}: no such file — {source}")
        for required in ("screen", "summary", "use", "internal"):
            if not feature.get(required):
                problems.append(f"{feature['name']}: missing `{required}:`")

    if problems:
        raise SystemExit("docs/features.md does not match the code:\n  " + "\n  ".join(problems))


def openapi_paths() -> tuple[set[tuple[str, str]], dict]:
    """Every (path, method) the app actually serves, straight from the app object."""
    from fastapi.testclient import TestClient

    from app.core.config import get_settings
    from app.main import create_app

    with TestClient(create_app(get_settings())) as client:
        spec = client.get("/openapi.json").json()

    return {
        (path, method) for path, operations in spec["paths"].items() for method in operations
    }, spec


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    check = "--check" in sys.argv
    paths, spec = openapi_paths()

    documents = {
        "requirements.json": build_requirements(),
        "tests.json": build_tests(),
        "architecture.json": build_architecture(),
        "features.json": build_features(paths),
        "meta.json": {
            "generated_by": "backend/scripts/generate_docs.py",
            "endpoint_count": sum(len(ops) for ops in spec["paths"].values()),
            "api_version": spec["info"]["version"],
        },
    }

    OUT.mkdir(parents=True, exist_ok=True)
    stale = []
    for name, payload in documents.items():
        rendered = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
        target = OUT / name
        if check:
            if not target.exists() or target.read_text(encoding="utf-8") != rendered:
                stale.append(name)
        else:
            target.write_text(rendered, encoding="utf-8")

    if check and stale:
        raise SystemExit(f"docs are stale, run `make docs`: {', '.join(stale)}")

    verb = "checked" if check else "wrote"
    print(f"{verb} {len(documents)} documents in {OUT.relative_to(ROOT)}")
    print(
        f"  {len(documents['requirements.json']['items'])} requirements, "
        f"{documents['tests.json']['total']} tests, "
        f"{len(documents['features.json']['features'])} features, "
        f"{documents['meta.json']['endpoint_count']} endpoints verified"
    )


if __name__ == "__main__":
    main()
