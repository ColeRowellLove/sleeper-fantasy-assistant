"""Packages depend in one direction: features never import each other (see CLAUDE.md)."""

import ast
from pathlib import Path

ROOT = Path(__file__).parent.parent / "src" / "sleeper_assistant"
FEATURES = {"views", "alerts", "sync"}
SHARED = {"utils", "core", "constants", "db"}
# what each layer may import (besides itself); entry points (api, worker, boot, sample_league) may
# import anything
ALLOWED = {
    "utils": {"utils", "constants", "db"},
    "core": {"core", "utils", "constants", "db"},
    **{feature: {feature} | SHARED for feature in FEATURES},
}


def _imports(path: Path) -> set[str]:
    """The top-level sleeper_assistant packages or modules a file imports."""
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.ImportFrom) and node.module:
            parts = node.module.split(".")
            if parts[0] == "sleeper_assistant" and len(parts) > 1:
                found.add(parts[1])
            elif node.module == "sleeper_assistant":
                found.update(a.name for a in node.names)
    return found


def test_each_layer_only_imports_the_layers_it_may() -> None:
    problems = []
    for path in sorted(ROOT.rglob("*.py")):
        package = path.relative_to(ROOT).parts[0]
        if package not in ALLOWED:
            continue
        extra = _imports(path) - ALLOWED[package] - {"__version__"}
        if extra:
            problems.append(f"{path.relative_to(ROOT)} imports {sorted(extra)}")
    assert not problems, "\n".join(problems)
