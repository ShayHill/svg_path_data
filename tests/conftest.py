"""See full diffs in pytest.

:author: Shay Hill
:created: 2025-07-02
"""

from __future__ import annotations

from typing import Any


def pytest_assertrepr_compare(
    config: Any, op: str, left: str, right: str
) -> list[str] | None:
    """See full error diffs"""
    del config
    if op in ("==", "!="):
        return [f"{left} {op} {right}"]
    return None
