"""
Embedded Trace Insight Lab – Streamlit UI entry point.

Upload a firmware log (.log/.txt/.csv), detect anomalies, and get
AI-generated explanations in either "analysis" or "educational" mode.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import streamlit as st

from src.parsing.log_parser import parse_file
from src.analysis.detector import AnomalyDetector
from src.ai_explanation.explainer import TraceExplainer

st.set_page_config(page_title="Embedded Trace Insight Lab", layout="wide")

st.title("Embedded Trace Insight Lab")
st.markdown(
    "Upload a firmware log or trace file (`.log`, `.txt`, `.csv`) and get "
    "AI-assisted anomaly detection with plain-English explanations."
)

mode = st.radio(
    "Explanation mode",
    options=["analysis", "educational"],
    horizontal=True,
    help="Analysis: technical/actionable checks. Educational: beginner-friendly explanations.",
)

uploaded_file = st.file_uploader(
    "Upload a log file", type=["log", "txt", "csv"]
)

st.divider()

if uploaded_file is not None:
    suffix = Path(uploaded_file.name).suffix or ".log"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded_file.getvalue())
        tmp_path = tmp.name

    if st.button("Run Analysis", type="primary"):
        try:
            events = list(parse_file(tmp_path))
        except Exception as e:
            st.error(f"Failed to parse the file: {e}")
            events = []

        if not events:
            st.warning("No events could be parsed from this file.")
        else:
            st.success(f"Parsed {len(events)} events from `{uploaded_file.name}`.")

            detector = AnomalyDetector()
            issues = detector.detect(events)

            explainer = TraceExplainer()
            explanation = explainer.generate_explanation(events, issues, mode=mode)

            st.subheader("Summary")
            st.write(explanation.summary)

            st.subheader(f"Detected Issues ({len(issues)})")
            if issues:
                issue_rows = [
                    {
                        "Type": issue.issue_type,
                        "Severity": issue.severity,
                        "Description": issue.description,
                        "Related Events": len(issue.related_events),
                    }
                    for issue in issues
                ]
                st.dataframe(issue_rows, use_container_width=True)
            else:
                st.info("No anomalies detected.")

            if explanation.explanations:
                st.subheader("Detailed Explanations")
                for issue_type, text in explanation.explanations.items():
                    with st.expander(issue_type):
                        st.write(text)

            st.subheader("Suggested Checks")
            for check in explanation.suggested_checks:
                st.markdown(f"- {check}")

            with st.expander("Raw parsed events (debug view)"):
                st.dataframe(
                    [
                        {
                            "Line": e.line_number,
                            "Timestamp": str(e.timestamp),
                            "Level": e.level,
                            "Source": e.source,
                            "Message": e.message,
                        }
                        for e in events
                    ],
                    use_container_width=True,
                )
else:
    st.info("Upload a log file above to get started.")