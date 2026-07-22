"""Unit tests for log parsing with synthetic inputs."""

import datetime
import logging
import tempfile
from pathlib import Path

import pytest

from src.parsing.event import Event
from src.parsing.log_parser import LogParser


@pytest.fixture
def parser() -> LogParser:
    """Return a default LogParser instance."""
    return LogParser()


# ----- line‑based parsing -----
def test_parse_valid_lines(parser: LogParser) -> None:
    content = (
        "2025-01-15T14:32:01.123Z ERROR UART: buffer overflow\n"
        "2025-01-15T14:32:02.456Z INFO  TIMER: tick\n"
        "2025-01-15T14:32:03.789Z WARN  ADC: voltage low\n"
    )
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".log", delete=False, encoding="utf-8"
    ) as f:
        f.write(content)
        tmp_path = f.name

    events = parser.parse_file(tmp_path)
    assert len(events) == 3

    e1 = events[0]
    assert e1.level == "ERROR"
    assert e1.source == "UART"
    assert e1.message == "buffer overflow"
    assert e1.timestamp == datetime.datetime(2025, 1, 15, 14, 32, 1, 123000)

    e3 = events[2]
    assert e3.source == "ADC"

    Path(tmp_path).unlink(missing_ok=True)


def test_skip_malformed_lines(parser: LogParser, caplog) -> None:
    content = (
        "2025-01-15T14:32:01.123Z ERROR UART: ok\n"
        "this line is garbage\n"
        "2025-01-15T14:32:03.789Z WARN  ADC: ok\n"
    )
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".log", delete=False, encoding="utf-8"
    ) as f:
        f.write(content)
        tmp_path = f.name

    with caplog.at_level(logging.WARNING):
        events = parser.parse_file(tmp_path)

    assert len(events) == 2
    assert any("Skipping malformed line" in rec.message for rec in caplog.records)
    Path(tmp_path).unlink(missing_ok=True)


def test_missing_timestamp_is_none(parser: LogParser) -> None:
    """Line with a broken timestamp should still yield an Event but with timestamp=None."""
    invalid_date_line = "2025-13-01T14:32:01.123Z ERROR UART: msg"
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".log", delete=False, encoding="utf-8"
    ) as f:
        f.write(invalid_date_line)
        tmp_path = f.name

    events = parser.parse_file(tmp_path)
    assert len(events) == 1
    assert events[0].timestamp is None
    assert events[0].level == "ERROR"
    Path(tmp_path).unlink(missing_ok=True)


# ----- CSV parsing -----
def test_parse_valid_csv(parser: LogParser) -> None:
    content = (
        "timestamp,level,source,message\n"
        "2025-01-15T14:32:01.123Z,ERROR,UART,buffer overflow\n"
        "2025-01-15T14:32:02.456Z,INFO,TIMER,tick\n"
    )
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".csv", delete=False, encoding="utf-8"
    ) as f:
        f.write(content)
        tmp_path = f.name

    events = parser.parse_file(tmp_path)
    assert len(events) == 2
    e1 = events[0]
    assert e1.level == "ERROR"
    assert e1.source == "UART"
    assert e1.timestamp == datetime.datetime(2025, 1, 15, 14, 32, 1, 123000)
    Path(tmp_path).unlink(missing_ok=True)


def test_csv_missing_column(parser: LogParser, caplog) -> None:
    content = (
        "timestamp,level,message\n"
        "2025-01-15T14:32:01.123Z,ERROR,missing source col\n"
    )
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".csv", delete=False, encoding="utf-8"
    ) as f:
        f.write(content)
        tmp_path = f.name

    with caplog.at_level(logging.WARNING):
        events = parser.parse_file(tmp_path)

    # Source column missing -> filled with ""
    assert len(events) == 1
    assert events[0].source == ""

    # Check that a warning about the missing column was logged
    # (look for the column name rather than a fixed phrase)
    assert any("source" in rec.message for rec in caplog.records)
    Path(tmp_path).unlink(missing_ok=True)