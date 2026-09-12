"""Füzyon: tek karar mercii, mutlak limitler her zaman üstte kalır."""
from __future__ import annotations

SEVERITY_ORDER = ["NORMAL", "WATCH", "ALARM", "CRITICAL", "EMERGENCY"]


def max_severity(*severities: str) -> str:
    return max(severities, key=SEVERITY_ORDER.index)
