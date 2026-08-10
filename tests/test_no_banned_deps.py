"""Banned-dependency guard.

CLAUDE.md rule 6 and ``docs/04_SPEC_PYTHON_CLI.md`` section 2: no ``pandas_ta``,
no TA-Lib. Their EMA/RSI seeding differs from Pine's and will silently break
parity -- silently being the operative word, which is why this is a test rather
than a code-review convention.
"""

from __future__ import annotations

import importlib.util
import tomllib
from pathlib import Path

import pytest

BANNED = ["pandas_ta", "talib", "TA-Lib", "pandas-ta"]


@pytest.mark.parametrize("module", ["pandas_ta", "talib"])
def test_banned_module_not_importable(module: str):
    assert importlib.util.find_spec(module) is None, (
        f"{module} is installed. CLAUDE.md rule 6 bans it: its EMA/RSI seeding "
        "differs from Pine's and will silently break parity."
    )


def test_banned_packages_not_declared():
    raw = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    declared = list(raw["project"]["dependencies"])
    for group in raw.get("dependency-groups", {}).values():
        declared.extend(group)

    lowered = [d.lower() for d in declared]
    for banned in BANNED:
        assert not any(banned.lower() in d for d in lowered), (
            f"{banned} is declared in pyproject.toml but banned by CLAUDE.md rule 6."
        )


def test_core_does_not_import_a_ta_library():
    """Primitives are implemented in-repo so they can be made bit-comparable to Pine."""
    for path in Path("azimuth").rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        for banned in ("import pandas_ta", "import talib", "from talib", "from pandas_ta"):
            assert banned not in source, f"{path} imports a banned TA library ({banned})"
