"""
Embedded Trace Insight Lab – Streamlit UI entry point.

Upload a firmware log (.log/.txt/.csv), detect anomalies, and get
AI-generated explanations in either "analysis" or "educational" mode.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import streamlit as st

# Ensure repo root is importable when Streamlit Cloud runs app/main.py
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.analysis.detector import AnomalyDetector
from src.ai_explanation.explainer import TraceExplainer
from src.parsing.log_parser import parse_file

st.set_page_config(page_title="Embedded Trace Insight Lab", layout="wide")


def save_uploaded_file(uploaded_file) -> str:
    suffix = Path(uploaded_file.name).suffix or ".log"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded_file.getvalue())
        return tmp.name


def main() -> None:
    st.title("Embedded Trace Insight Lab")
    st.markdown(
        "Upload a firmware log or trace file (`.log`, `.txt`, `.csv`) and get "
        "AI-assisted anomaly detection with plain-English explanations."
    )

    mode = st.radio(
        "Explanation mode",
        options=["analysis", "educational"],
        horizontal=True,
        help="Analysis gives technical checks. Educational gives beginner-friendly explanations.",
    )

    uploaded_file = st.file_uploader(
        "Upload a log file",
        type=["log", "txt", "csv"],
    )

    st.divider()

    if uploaded_file is None:
        st.info("Upload a log file above to get started.")
        return

    if st.button("Run Analysis", type="primary"):
        tmp_path = None
        try:
            tmp_path = save_uploaded_file(uploaded_file)
            events = list(parse_file(tmp_path))

            if not events:
                st.warning("No events could be parsed from this file.")
                return

            detector = AnomalyDetector()
            issues = detector.detect(events)

            explainer = TraceExplainer()
            explanation = explainer.generate_explanation(events, issues, mode=mode)

            st.success(f"Parsed {len(events)} events from `{uploaded_file.name}`.")

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

            with st.expander("Raw Parsed Events"):
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

        except Exception as e:
            st.error(f"Analysis failed: {e}")
        finally:
            if tmp_path:
                try:
                    Path(tmp_path).unlink(missing_ok=True)
                except Exception:
                    pass


if __name__ == "__main__":
    main()