"""Data model for a single parsed event from an embedded trace log."""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass(slots=True, frozen=True)
class Event:
    """Represents one event extracted from a trace or log file.

    Attributes:
        timestamp: The time of the event. Remains None if unparsable.
        level: Severity or event type (e.g. 'INFO', 'ERROR', 'ISR').
        source: Subsystem or module that generated the event.
        message: The main payload of the event.
        raw: The original unparsed line (for debugging and exact reconstruction).
        line_number: The line number in the source file.
        category: Optional high-level grouping (e.g., 'Network', 'Kernel').
        error_code: Optional extracted error code (e.g., '0xDEADBEEF').
        extra: Any additional fields not captured by the standard attributes.
    """

    timestamp: Optional[datetime.datetime] = None
    level: str = ""
    source: str = ""
    message: str = ""
    raw: str = ""
    line_number: int = 0
    category: str = ""
    error_code: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        ts = self.timestamp.isoformat() if self.timestamp else "NoTimestamp"
        err = f" [{self.error_code}]" if self.error_code else ""
        return f"[{ts}] {self.level:8s} {self.source}{err} (Line {self.line_number}): {self.message}"