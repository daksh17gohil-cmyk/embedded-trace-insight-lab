"""
Log/trace parser supporting regex-based line logs and CSV logs.
Implements a Strategy/Factory pattern for unbounded extensibility.
"""

from __future__ import annotations

import csv
import datetime
import logging
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterator, List, Optional, Pattern, Union

from .event import Event

logger = logging.getLogger(__name__)

DEFAULT_LINE_PATTERN: Pattern[str] = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z?)\s+"
    r"(?P<level>\w+)\s+"
    r"(?P<source>\S+?):\s+"
    r"(?P<message>.+)$"
)

DEFAULT_CSV_COLUMNS = ["timestamp", "level", "source", "message"]


def _parse_timestamp(ts_str: str, filename: str, line_no: int) -> Optional[datetime.datetime]:
    """Helper function to parse timestamps and retain UTC timezone awareness."""
    if not ts_str:
        return None
    try:
        normalized = ts_str.replace('Z', '+00:00')
        dt = datetime.datetime.fromisoformat(normalized)
        # Keep UTC timezone awareness instead of stripping it
        if dt.tzinfo is not None:
            dt = dt.astimezone(datetime.timezone.utc)
        return dt
    except ValueError:
        try:
            import pandas as pd
            ts = pd.Timestamp(ts_str).to_pydatetime()
            if ts.tzinfo is not None:
                ts = ts.astimezone(datetime.timezone.utc)
            return ts
        except Exception:
            logger.warning("Invalid timestamp in %s at line %d: %s", filename, line_no, ts_str)
            return None


class BaseParser(ABC):
    """Abstract base class establishing the contract for all parsers."""
    
    @abstractmethod
    def parse(self, file_path: Union[str, Path]) -> Iterator[Event]:
        """Yields parsed Events lazily from a given file."""
        pass


class RegexLogParser(BaseParser):
    def __init__(self, line_pattern: Optional[Pattern[str]] = None) -> None:
        self.line_pattern = line_pattern or DEFAULT_LINE_PATTERN

    def parse(self, file_path: Union[str, Path]) -> Iterator[Event]:
        path = Path(file_path)
        with open(path, encoding="utf-8") as f:
            for line_no, raw_line in enumerate(f, start=1):
                line = raw_line.strip()
                if not line:
                    continue

                m = self.line_pattern.match(line)
                if not m:
                    # Guarantee: Zero Silent Data Loss. Yield UNKNOWN event.
                    yield Event(
                        level="UNKNOWN",
                        message="Failed to parse line via regex.",
                        raw=raw_line.rstrip('\n'), 
                        line_number=line_no
                    )
                    continue

                data = m.groupdict()
                ts = _parse_timestamp(data.get("timestamp", ""), path.name, line_no)
                
                # Dynamically pack any regex groups not explicitly defined in Event into 'extra'
                extra_fields = {k: v for k, v in data.items() if k not in Event.__annotations__ and v}

                yield Event(
                    timestamp=ts,
                    level=data.get("level", ""),
                    source=data.get("source", ""),
                    message=data.get("message", ""),
                    raw=raw_line.rstrip('\n'),
                    line_number=line_no,
                    extra=extra_fields
                )


class CsvLogParser(BaseParser):
    def __init__(self, csv_columns: Optional[List[str]] = None) -> None:
        self.csv_columns = csv_columns or DEFAULT_CSV_COLUMNS

    def parse(self, file_path: Union[str, Path]) -> Iterator[Event]:
        path = Path(file_path)
        with open(path, encoding="utf-8") as f:
            header_line = f.readline()
            if not header_line:
                return
            
            headers = next(csv.reader([header_line]))

            for line_no, raw_line in enumerate(f, start=2):
                if not raw_line.strip():
                    continue
                    
                try:
                    # Parse row natively to respect complex quoting/escaping
                    row_vals = next(csv.reader([raw_line]))
                    row = dict(zip(headers, row_vals))
                except StopIteration:
                    yield Event(
                        level="UNKNOWN",
                        message="Malformed CSV row.",
                        raw=raw_line.rstrip('\n'),
                        line_number=line_no
                    )
                    continue

                ts = _parse_timestamp(row.get("timestamp", ""), path.name, line_no)
                
                # Push non-standard CSV columns into 'extra'
                extra_fields = {k: v for k, v in row.items() if k not in self.csv_columns and v}

                yield Event(
                    timestamp=ts,
                    level=row.get("level", ""),
                    source=row.get("source", ""),
                    message=row.get("message", ""),
                    raw=raw_line.rstrip('\n'), # 100% accurate raw string
                    line_number=line_no,
                    extra=extra_fields
                )


class ParserFactory:
    """Dispatches the correct parser based on file type."""
    
    _parsers = {
        ".csv": CsvLogParser(),
        ".log": RegexLogParser(),
        ".txt": RegexLogParser(),
    }

    @classmethod
    def get_parser(cls, file_path: Union[str, Path]) -> BaseParser:
        path = Path(file_path)
        # Default to RegexLogParser if the extension is unregistered
        return cls._parsers.get(path.suffix.lower(), RegexLogParser())


def parse_file(file_path: Union[str, Path]) -> Iterator[Event]:
    """Convenience entry point for the downstream analysis engine."""
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"No such file: {path}")
        
    parser = ParserFactory.get_parser(path)
    return parser.parse(path)