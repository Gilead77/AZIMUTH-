"""Pine-exact indicator primitives.

Implemented in Task 2 (``docs/10_ROADMAP.md`` M1). See ``docs/06_PARITY_TESTS.md``
section 3 for the specific ways naive pandas implementations diverge from Pine --
every one of them gets a named regression test.

``pandas_ta`` and TA-Lib are BANNED (CLAUDE.md rule 6): their EMA/RSI seeding
differs from Pine's and will silently break parity.
"""

from __future__ import annotations
