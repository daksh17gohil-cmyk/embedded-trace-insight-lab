import streamlit as st
from typing import List, Optional
from dataclasses import asdict
import datetime
from pathlib import Path

# ---- CORRECTED IMPORTS ----
from src.parsing.log_parser import parse_file
from src.analysis.detector import AnomalyDetector
from src.ai_explanation.explainer import TraceExplainer, TraceExplanation
from src.parsing.event import Event

# ---- Data Model for Orchestration ----
class AnalysisResult:
    def __init__(self, success: bool, error_message: Optional[str] = None,
                 events: Optional[List[Event]] = None,
                 issues: Optional[List] = None,
                 explanation: Optional[TraceExplanation] = None,
                 raw_log_text: Optional[str] = None):
        self.success = success
        self.error_message = error_message
        self.events = events or []
        self.issues = issues or []
        self.explanation = explanation
        self.raw_log_text = raw_log_text

# ---- Orchestrator ----
def run_analysis(log_text: str, mode: str) -> AnalysisResult:
    """Orchestrate parsing, anomaly detection, and explanation generation."""
    if not log_text or not log_text.strip():
        return AnalysisResult(
            success=False,
            error_message="Log text is empty. Please provide valid log data."
        )

    try:
        # 1. Parse (Save text to a temp file since our parser expects a file path)
        temp_file = Path("data/temp_streamlit.log")
        temp_file.parent.mkdir(exist_ok=True)
        temp_file.write_text(log_text, encoding="utf-8")
        
        events = list(parse_file(temp_file))
        
        if not events:
            return AnalysisResult(
                success=False,
                error_message="No events could be parsed from the log. Check the format."
            )

        # 2. Detect anomalies
        detector = AnomalyDetector()
        issues = detector.detect(events)

        # 3. Explain
        explainer = TraceExplainer()
        explanation = explainer.generate_explanation(events, issues, mode=mode)

        return AnalysisResult(
            success=True,
            events=events,
            issues=issues,
            explanation=explanation,
            raw_log_text=log_text
        )

    except Exception as e:
        return AnalysisResult(
            success=False,
            error_message=f"An unexpected error occurred: {str(e)}"
        )

# ---- Markdown Export ----
def explanation_to_markdown(result: AnalysisResult) -> str:
    """Convert an AnalysisResult into a Markdown formatted report."""
    lines = []
    lines.append("# Embedded Trace Insight Lab – Analysis Report")
    lines.append(f"*Generated on {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n")

    if not result.success:
        lines.append("## Error")
        lines.append(result.error_message)
        return "\n".join(lines)

    expl = result.explanation
    lines.append("## Incident Summary")
    lines.append(expl.summary + "\n")

    if result.issues:
        lines.append("## Detected Issues")
        for idx, issue in enumerate(result.issues, 1):
            issue_type = getattr(issue, 'issue_type', 'Unknown')
            desc = getattr(issue, 'description', '')
            lines.append(f"{idx}. **{issue_type}** – {desc}")

    lines.append("\n## Detailed Explanations")
    for issue_type, text in expl.explanations.items():
        lines.append(f"### {issue_type}")
        lines.append(text + "\n")

    lines.append("## Suggested Checks")
    for idx, check in enumerate(expl.suggested_checks, 1):
        lines.append(f"{idx}. {check}")

    return "\n".join(lines)

# ---- Streamlit UI ----
def main():
    st.set_page_config(page_title="Embedded Trace Insight Lab", layout="wide")
    st.title("🔍 Embedded Trace Insight Lab")
    st.markdown("Upload or paste a log file to detect anomalies and get AI‑powered explanations.")

    # Initialize session state for log input so the "Load sample log" button works
    if "log_input" not in st.session_state:
        st.session_state.log_input = ""

    # Sidebar – mode selection
    mode = st.sidebar.radio(
        "Explanation Mode",
        options=["analysis", "educational"],
        index=0,
        help="'Analysis' gives actionable checks; 'Educational' provides learning-oriented insights."
    )

    # Main input area
    col1, col2 = st.columns([2, 1])
    with col1:
        uploaded_file = st.file_uploader("Upload a log file", type=["log", "txt", "csv"])
        if uploaded_file is not None:
            st.session_state.log_input = uploaded_file.read().decode("utf-8")
            
        log_text = st.text_area("File content (editable) or paste your log here", 
                                value=st.session_state.log_input, 
                                height=200)

    with col2:
        st.markdown("### Quick sample")
        if st.button("Load sample log (synthetic)"):
            # Load from a predefined string or file
            sample_data = (
                "2026-07-22T10:00:00.000Z INFO kernel: System boot complete\n"
                "2026-07-22T10:00:01.123Z WARN power: Low voltage detected (3.2V)\n"
                "2026-07-22T10:00:02.456Z ERROR i2c_bus: Rx NAK from sensor 0x42\n"
                "2026-07-22T10:00:10.000Z INFO kernel: System boot complete\n"
                "2026-07-22T10:00:15.000Z INFO kernel: System boot complete\n"
                "2026-07-22T10:00:18.000Z INFO kernel: System boot complete\n"
            )
            st.session_state.log_input = sample_data
            st.rerun()

    # Run button
    if st.button("🚀 Run Analysis"):
        if not log_text.strip():
            st.error("Please provide a log file or paste log text.")
        else:
            with st.spinner("Analysing..."):
                result = run_analysis(log_text, mode)

            if not result.success:
                st.error(f"Analysis failed: {result.error_message}")
            else:
                # ---- Display Results ----
                st.success("Analysis completed successfully!")
                expl = result.explanation

                # Summary
                st.subheader("📋 Incident Summary")
                st.write(expl.summary)

                # Issues table
                if result.issues:
                    st.subheader("🔎 Detected Issues")
                    issue_data = []
                    for issue in result.issues:
                        issue_type = getattr(issue, 'issue_type', 'Unknown')
                        desc = getattr(issue, 'description', '')
                        issue_data.append({"Type": issue_type, "Description": desc})
                    st.table(issue_data)

                # Detailed explanations (expandable)
                if expl.explanations:
                    st.subheader("📖 Detailed Explanations")
                    for issue_type, text in expl.explanations.items():
                        with st.expander(f"Explanation for {issue_type}"):
                            st.write(text)

                # Suggested checks
                if expl.suggested_checks:
                    st.subheader("✅ Suggested Checks")
                    for idx, check in enumerate(expl.suggested_checks, 1):
                        st.markdown(f"{idx}. {check}")

                # Download report
                markdown_report = explanation_to_markdown(result)
                st.download_button(
                    label="📥 Download Report (Markdown)",
                    data=markdown_report,
                    file_name=f"trace_analysis_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
                    mime="text/markdown"
                )

if __name__ == "__main__":
    main()