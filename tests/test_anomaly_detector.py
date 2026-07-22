"""Tests for the AnomalyDetector rules."""

import datetime
from src.parsing.event import Event
from src.analysis.detector import AnomalyDetector, DetectedIssue


def create_event(mins: int, secs: int, source: str, message: str) -> Event:
    """Helper to generate mock events with sequential timestamps."""
    return Event(
        timestamp=datetime.datetime(2026, 7, 22, 10, mins, secs, tzinfo=datetime.timezone.utc),
        level="INFO",
        source=source,
        message=message,
        line_number=1
    )


def test_watchdog_trigger():
    detector = AnomalyDetector()
    events = [
        create_event(0, 1, "kernel", "System normal"),
        create_event(0, 2, "WDT", "Watchdog bark"),
        create_event(0, 3, "kernel", "System reset by watchdog")
    ]
    
    issues = detector.detect(events)
    
    wdt_issues = [i for i in issues if i.issue_type == "WATCHDOG_TRIGGER"]
    assert len(wdt_issues) == 2
    assert wdt_issues[0].severity == "CRITICAL"
    assert "WDT" in wdt_issues[0].related_events[0].source


def test_comm_error_nak():
    detector = AnomalyDetector()
    events = [
        create_event(0, 1, "i2c_bus", "Sending payload"),
        create_event(0, 2, "i2c_bus", "Rx NAK from sensor 0x42"),
    ]
    
    issues = detector.detect(events)
    
    comm_issues = [i for i in issues if i.issue_type == "COMM_ERROR"]
    assert len(comm_issues) == 1
    assert "NAK" in comm_issues[0].related_events[0].message

def test_time_gaps():
    detector = AnomalyDetector(time_gap_threshold_sec=5.0)
    events = [
        create_event(0, 0, "app", "Start sequence"),
        # 2-second gap (Normal)
        create_event(0, 2, "app", "Step 1"),
        # 10-second gap (Anomaly)
        create_event(0, 12, "app", "Step 2"),
    ]
    
    issues = detector.detect(events)
    
    gap_issues = [i for i in issues if i.issue_type == "TIME_GAP"]
    assert len(gap_issues) == 1
    assert gap_issues[0].severity == "WARNING"
    assert len(gap_issues[0].related_events) == 2


def test_reset_loop():
    # Require 3 resets within 10 seconds to trigger
    detector = AnomalyDetector(reset_window_sec=10.0, reset_count_threshold=3)
    events = [
        create_event(0, 0, "kernel", "System boot"),
        create_event(0, 2, "kernel", "Init crash... reset"),
        create_event(0, 4, "kernel", "System boot"),
        create_event(0, 6, "kernel", "Init crash... reset"),
        create_event(0, 8, "kernel", "System boot"),
    ]
    
    issues = detector.detect(events)
    
    loop_issues = [i for i in issues if i.issue_type == "RESET_LOOP"]
    assert len(loop_issues) == 1
    assert loop_issues[0].severity == "CRITICAL"
    # Should flag the exact events causing the loop
    assert len(loop_issues[0].related_events) == 3