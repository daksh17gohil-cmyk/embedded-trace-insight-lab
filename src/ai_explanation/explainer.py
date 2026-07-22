"""
AI explanation module for Embedded Trace Insight Lab.

Provides a mock explanation generator that translates detected issues
into human-readable summaries, detailed explanations, and actionable checks.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional


@dataclass
class TraceExplanation:
    """
    Structured explanation for a set of detected issues in a trace.

    Attributes:
        summary: A concise high‑level description of the overall situation.
        explanations: A mapping from each issue type to a detailed explanatory
            text that describes the root cause and impact.
        suggested_checks: A list of actionable steps (3‑5) to diagnose or
            resolve the issues, tailored to the requested mode.
    """
    summary: str
    explanations: Dict[str, str] = field(default_factory=dict)
    suggested_checks: List[str] = field(default_factory=list)


class TraceExplainer:
    """
    Mock explainer that generates explanations without calling an external LLM.

    The output is deterministic and based on the ``issue_type`` of each
    ``DetectedIssue`` and the requested ``mode`` (``"analysis"`` or
    ``"educational"``).

    Supported issue types:
        - RESET_LOOP
        - COMM_ERROR
        - WATCHDOG_TRIGGER
        - TIME_GAP
    """

    # Templates for each known issue type.
    # Each entry provides:
    #   summary_suffix: phrase appended to the main summary.
    #   explanation_template: detailed explanation (may use placeholders).
    #   analysis_checks: list of technical/actionable checks.
    #   educational_checks: list of explanatory/learning checks.
    _TEMPLATES = {
        "RESET_LOOP": {
            "summary_suffix": "repeated system resets detected.",
            "explanation_template": (
                "The device is stuck in a reset loop, likely caused by a hardware fault, "
                "power supply instability, or a software crash during early boot. "
                "Each reset prevents the system from reaching a stable operational state."
            ),
            "analysis_checks": [
                "Inspect the last events before each reset for common crash patterns.",
                "Check the power supply voltage logs for dips or spikes.",
                "Verify that the bootloader and firmware versions are compatible.",
                "Enable persistent crash logging to capture the reset cause.",
            ],
            "educational_checks": [
                "A reset loop means the device restarts over and over without completing startup.",
                "Common causes include failing hardware, corrupted firmware, or a critical software bug.",
                "Look at the timing between resets – they may be periodic (e.g., every 2 seconds) or erratic.",
                "Try disconnecting peripherals to see if the loop stops – that points to a peripheral fault.",
            ],
        },
        "COMM_ERROR": {
            "summary_suffix": "communication errors with external devices.",
            "explanation_template": (
                "The system is experiencing intermittent or persistent failures when communicating "
                "with one or more peripherals or the network. This can be due to baud rate mismatch, "
                "noise on the bus, or a faulty connection."
            ),
            "analysis_checks": [
                "Verify the physical connections (cables, connectors) for damage.",
                "Check the baud rate and protocol settings against the peripheral datasheet.",
                "Use an oscilloscope or logic analyzer to inspect signal integrity.",
                "Review the error counter registers in the UART/SPI/I²C driver.",
            ],
            "educational_checks": [
                "Communication errors happen when the sender and receiver do not understand each other.",
                "Common causes: wrong speed settings, electrical noise, or loose wiring.",
                "The error messages often include a code that tells you if it's a timeout, parity error, or framing error.",
                "Try simplifying the system (e.g., loopback test) to isolate the problem.",
            ],
        },
        "WATCHDOG_TRIGGER": {
            "summary_suffix": "watchdog timer triggered.",
            "explanation_template": (
                "The watchdog timer expired and reset the system because the main loop did not "
                "service the watchdog within the expected time window. This indicates a hang "
                "or a long‑running task that blocked the scheduler."
            ),
            "analysis_checks": [
                "Identify the last task or interrupt that ran before the reset.",
                "Check for unbounded loops or blocking I/O calls in the application code.",
                "Increase the watchdog timeout temporarily to see if the issue becomes less frequent.",
                "Add debug instrumentation to log task scheduling times.",
            ],
            "educational_checks": [
                "A watchdog is a safety timer that resets the system if the software stops responding.",
                "When it triggers, it means the system was unresponsive for longer than the timeout.",
                "This often happens because of infinite loops, deadlocks, or heavy interrupt loads.",
                "To fix it, make sure the watchdog is 'fed' regularly in the main loop or a high‑priority task.",
            ],
        },
        "TIME_GAP": {
            "summary_suffix": "unexpected time gaps in the trace.",
            "explanation_template": (
                "There are significant time gaps (larger than expected) between consecutive "
                "events in the trace. This may indicate data loss, buffer overruns, or the "
                "system entering a low‑power state without proper timestamping."
            ),
            "analysis_checks": [
                "Compare the timestamps with a known accurate time source (e.g., GPS or NTP).",
                "Check if the logging buffer is being overwritten – increase buffer size if possible.",
                "Examine the system's clock source (crystal, PLL) for stability.",
                "Look for patterns: gaps may coincide with interrupts or power mode transitions.",
            ],
            "educational_checks": [
                "Time gaps mean that the log does not show what happened during those periods.",
                "Possible reasons: the system was too busy to log events, the buffer filled up and dropped data, or the clock stopped.",
                "If the gaps are regular, they might be caused by a periodic activity like a sleep/wake cycle.",
                "To close the gaps, you might need to use a higher‑priority logging task or a dedicated hardware timestamping unit.",
            ],
        },
    }

    # Default fallback for unknown issue types.
    _DEFAULT = {
        "summary_suffix": "one or more issues of unknown type.",
        "explanation_template": "An issue was detected but its specific type is not recognized. "
                                "Please refer to the raw events for more details.",
        "analysis_checks": [
            "Review the raw log lines around the detected issue.",
            "Check if the issue matches any known pattern from the device manual.",
            "Enable verbose logging to capture additional context.",
        ],
        "educational_checks": [
            "Sometimes the system encounters a problem that doesn't fit a known category.",
            "Start by reading the event messages carefully – they often contain hints.",
            "Compare with a healthy trace to see what is different.",
        ],
    }

    def __init__(self) -> None:
        """Initialise the explainer (no external dependencies)."""
        pass

    def generate_explanation(
        self,
        events: List["Event"],          # noqa: F821 (forward reference)
        issues: List["DetectedIssue"],  # noqa: F821
        mode: str = "analysis"
    ) -> TraceExplanation:
        """
        Generate a structured explanation for the given events and issues.

        Args:
            events: List of Event objects (used for context, but currently ignored
                in the mock implementation).
            issues: List of DetectedIssue objects; each must have an `issue_type`
                attribute (string) and optionally other fields.
            mode: Either "analysis" (technical, actionable) or "educational"
                (explanatory, learning‑oriented).

        Returns:
            A TraceExplanation dataclass with summary, explanations per issue,
            and suggested checks.

        Raises:
            ValueError: if mode is not "analysis" or "educational".
        """
        if mode not in ("analysis", "educational"):
            raise ValueError("mode must be either 'analysis' or 'educational'")

        if not issues:
            # Handle the edge case of no issues.
            return TraceExplanation(
                summary="No issues detected in the trace.",
                explanations={},
                suggested_checks=["Ensure the system is running as expected."],
            )

        # Build explanations and collect summary parts.
        explanations: Dict[str, str] = {}
        summary_parts: List[str] = []
        all_checks: List[str] = []

        for issue in issues:
            issue_type = getattr(issue, "issue_type", "UNKNOWN")
            template = self._TEMPLATES.get(issue_type, self._DEFAULT)

            # Add a brief summary phrase.
            summary_parts.append(template["summary_suffix"])

            # Generate the detailed explanation.
            # We could also incorporate data from the issue object (e.g., event count)
            # to make it more dynamic. For simplicity, we use the fixed template.
            explanations[issue_type] = template["explanation_template"]

            # Add checks based on mode.
            if mode == "analysis":
                checks = template["analysis_checks"]
            else:  # educational
                checks = template["educational_checks"]
            all_checks.extend(checks)

        # Build a coherent summary sentence.
        if summary_parts:
            # Capitalise first letter and join with commas.
            summary = "The trace shows " + ", ".join(summary_parts)
        else:
            summary = "No issues were identified."

        # Deduplicate and limit checks to 3‑5, preserving order of appearance.
        seen = set()
        unique_checks = []
        for check in all_checks:
            if check not in seen:
                seen.add(check)
                unique_checks.append(check)
        # Truncate to 5 if more, but keep at least 3.
        if len(unique_checks) > 5:
            unique_checks = unique_checks[:5]
        # If fewer than 3, pad with a general suggestion (should not happen with our templates).
        if len(unique_checks) < 3:
            unique_checks.append("Consult the device documentation for more details.")
            if len(unique_checks) < 3:
                unique_checks.append("Consider enabling higher‑level logging.")

        return TraceExplanation(
            summary=summary,
            explanations=explanations,
            suggested_checks=unique_checks,
        )