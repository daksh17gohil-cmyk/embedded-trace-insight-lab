
"""
Analysis layer for Embedded Trace Insight Lab.
Detects common embedded system anomalies from parsed Event streams.
"""

from dataclasses import dataclass, field
from typing import List
from datetime import timedelta

# Assuming Event is importable from your parsing layer
from src.parsing.event import Event


@dataclass(slots=True, frozen=True)
class DetectedIssue:
    """Represents a discrete anomaly found in the trace."""
    issue_type: str
    severity: str
    description: str
    related_events: List[Event] = field(default_factory=list)


class AnomalyDetector:
    """Scans a sequence of Events to find patterns indicating bugs."""

    def __init__(
        self, 
        time_gap_threshold_sec: float = 5.0,
        reset_window_sec: float = 10.0,
        reset_count_threshold: int = 3
    ):
        self.time_gap_threshold = timedelta(seconds=time_gap_threshold_sec)
        self.reset_window = timedelta(seconds=reset_window_sec)
        self.reset_threshold = reset_count_threshold

    def detect(self, events: List[Event]) -> List[DetectedIssue]:
        """Runs all detection rules against the provided events."""
        if not events:
            return []

        issues: List[DetectedIssue] = []
        
        # O(N) single-pass checks and time gaps
        issues.extend(self._detect_single_event_anomalies(events))
        issues.extend(self._detect_time_gaps(events))
        
        # O(N) sliding window checks
        issues.extend(self._detect_reset_loops(events))
        
        return issues

    def _detect_single_event_anomalies(self, events: List[Event]) -> List[DetectedIssue]:
        """Checks for independent event flags like NAKs or Watchdogs."""
        issues = []
        for event in events:
            msg = event.message.lower()
            src = event.source.lower()

            # 1. Watchdog Triggers
            if "watchdog" in msg or "wdt" in src:
                issues.append(DetectedIssue(
                    issue_type="WATCHDOG_TRIGGER",
                    severity="CRITICAL",
                    description="Hardware watchdog timer triggered a reset.",
                    related_events=[event]
                ))

            # 2. Communication Errors
            if "nak" in msg or "nack" in msg or "timeout" in msg:
                issues.append(DetectedIssue(
                    issue_type="COMM_ERROR",
                    severity="ERROR",
                    description=f"Peripheral communication failure detected in {event.source}.",
                    related_events=[event]
                ))
        return issues

    def _detect_time_gaps(self, events: List[Event]) -> List[DetectedIssue]:
        """Detects unexpectedly large intervals between log lines."""
        issues = []
        valid_events = [e for e in events if e.timestamp is not None]

        for i in range(1, len(valid_events)):
            prev_event = valid_events[i - 1]
            curr_event = valid_events[i]
            
            delta = curr_event.timestamp - prev_event.timestamp
            if delta > self.time_gap_threshold:
                issues.append(DetectedIssue(
                    issue_type="TIME_GAP",
                    severity="WARNING",
                    description=f"Large logging gap of {delta.total_seconds():.1f} seconds detected.",
                    related_events=[prev_event, curr_event]
                ))
        return issues

    def _detect_reset_loops(self, events: List[Event]) -> List[DetectedIssue]:
        """Detects rapid, repeated reboot patterns."""
        issues = []
        # Filter down to just boot/reset events with timestamps
        reset_events = [
            e for e in events 
            if e.timestamp is not None and ("boot" in e.message.lower() or "reset" in e.message.lower())
        ]

        if len(reset_events) < self.reset_threshold:
            return issues

        # Sliding window
        for i in range(len(reset_events) - self.reset_threshold + 1):
            window = reset_events[i : i + self.reset_threshold]
            duration = window[-1].timestamp - window[0].timestamp
            
            if duration <= self.reset_window:
                issues.append(DetectedIssue(
                    issue_type="RESET_LOOP",
                    severity="CRITICAL",
                    description=f"System reset {self.reset_threshold} times within {duration.total_seconds():.1f} seconds.",
                    related_events=window
                ))
                # Skip ahead to avoid duplicating the same loop issue
                break 

        return issues