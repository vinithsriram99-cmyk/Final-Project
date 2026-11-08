"""Streamlit dashboard.   Run:  python3 -m streamlit run app.py"""
import json
import os
from pathlib import Path

import pandas as pd
import streamlit as st

from analyzer import analyze
from config import DEFAULT_MODELS
from ingest import IngestError, from_pdf_bytes, from_text, from_url
from llm import GeminiClient, LLMError
from report_pdf import build_pdf
from viz import dependency_dot, sector_scores_figure, timeline_figure

st.set_page_config(page_title="PPIIA - Public Policy Insight & Impact Analyzer", page_icon="🏛️", layout="wide")
SAMPLE_DIR = Path(__file__).parent / "sample_bills"
EFFECT_ICON = {"Benefit": "✅ Benefit", "Restriction": "⛔ Restriction", "Mixed": "⚖️ Mixed"}


def secret_key() -> str:
    try:
        return st.secrets.get("GEMINI_API_KEY", "") or os.getenv("GEMINI_API_KEY", "")
    except Exception:  # no secrets file locally
        return os.getenv("GEMINI_API_KEY", "")


# ------------------------------------------------------------------ sidebar
st.sidebar.header("⚙️ Settings")
api_key = st.sidebar.text_input("Gemini API key", value=secret_key(), type="password",
                                help="Free key: aistudio.google.com/apikey. It is only used for this session.")
models = st.session_state.get("models", DEFAULT_MODELS)
model = st.sidebar.selectbox("Gemini model", models)
if st.sidebar.button("List models my key can use") and api_key:
    try:
        st.session_state["models"] = GeminiClient(api_key).list_models() or DEFAULT_MODELS
        st.rerun()
    except LLMError as exc:
        st.sidebar.error(str(exc))
offline = st.sidebar.checkbox("Offline mode (no Gemini, extractive only)", value=not api_key)
st.sidebar.caption("Free-tier note: each bill uses ONE Gemini request.")

st.title("🏛️ Public Policy Insight & Impact Analyzer")
st.caption("Simplifying Government Bills for Every Citizen - upload a bill, get a plain-language analysis.")

# ------------------------------------------------------------------ input
source = st.radio("Bill source", ["Upload PDF", "Paste URL", "Paste text", "Sample bill"], horizontal=True)
raw, name = None, "input"
if source == "Upload PDF":
    up = st.file_uploader("Bill PDF", type=["pdf"])
    if up is not None:
        raw_bytes, name = up.read(), up.name
elif source == "Paste URL":
    url = st.text_input("Bill URL (PDF or HTML page, e.g. from sansad.in)")
elif source == "Paste text":
    pasted = st.text_area("Bill text", height=200)
else:
    samples = sorted(p.name for p in SAMPLE_DIR.glob("*.txt"))
    if not samples:
        st.warning("No sample bills found. Put .txt bills in the sample_bills folder, or use another source.")
    pick = st.selectbox("Fictional sample bills (for testing)", samples or ["(none)"])

if st.button("Analyze bill", type="primary"):
    try:
        with st.spinner("Reading the document..."):
            if source == "Upload PDF":
                if up is None:
                    raise IngestError("Please choose a PDF first.")
                raw = from_pdf_bytes(raw_bytes)
            elif source == "Paste URL":
                raw, name = from_url(url), url
            elif source == "Paste text":
                raw = from_text(pasted)
            else:
                if pick == "(none)":
                    raise IngestError("There are no sample bills to analyze.")
                raw, name = from_text((SAMPLE_DIR / pick).read_text()), pick
        client = None if (offline or not api_key) else GeminiClient(api_key, model)
        with st.spinner("Analyzing..." + (" (Gemini)" if client else " (offline)")):
            st.session_state["result"] = analyze(raw, client, name)
    except (IngestError, LLMError) as exc:
        st.error(str(exc))

r = st.session_state.get("result")
if not r:
    st.info("Choose a bill source above and click **Analyze bill**. No API key? Offline mode still gives a basic extractive view.")
    st.stop()

meta = r["meta"]
if meta["warning"]:
    st.warning(meta["warning"])
c1, c2, c3, c4 = st.columns(4)
c1.metric("Mode", meta["mode"] + (f" ({meta['model']})" if meta["model"] else ""))
c2.metric("Words analysed", f"{meta['words']:,}")
c3.metric("Processing time", f"{meta['processing_seconds']} s")
c4.metric("Top sector", r["detected_sectors"][0]["sector"])
st.subheader(r["title"])
st.write(f"**Ministry:** {r['ministry']}")

t_sum, t_json, t_ind, t_time, t_graph, t_imp, t_risk, t_dl = st.tabs(
    ["📝 AI Summary", "🧾 Structured JSON", "🏭 Industry impact", "🕰️ Timeline", "🕸️ Dependency graph",
     "🔮 Impact forecast", "⚠️ Risks & controversy", "⬇️ Download"])

with t_sum:
    st.markdown("#### What does this bill mean for a normal person?")
    st.write(f"**Objective:** {r['objective']}")
    for line in r["summary_lines"]:
        st.markdown(f"- {line}")
    if r["key_provisions"]:
        with st.expander("Key provisions", expanded=True):
            for p in r["key_provisions"]:
                st.markdown(f"- {p}")
    pos, neg = st.columns(2)
    pos.markdown("##### 👍 Positives")
    for x in r["positives"]:
        pos.markdown(f"- {x}")
    neg.markdown("##### 👎 Negatives")
    for x in r["negatives"]:
        neg.markdown(f"- {x}")
    if not (r["positives"] or r["negatives"]):
        st.caption("Positives/negatives need the Gemini analysis.")

with t_json:
    st.json({k: r[k] for k in ["title", "ministry", "objective", "key_provisions", "related_acts", "stakeholders",
                               "affected_industries", "risks_and_unintended_consequences"]})
    with st.expander("Full result"):
        st.json(r)

with t_ind:
    left, right = st.columns(2)
    with left:
        st.markdown("##### Sector detection (rule-based classifier)")
        fig = sector_scores_figure(r["sector_scores"])
        if fig:
            st.pyplot(fig)
        st.write("Detected:", ", ".join(f"**{s['sector']}** ({s['share']:.0%})" for s in r["detected_sectors"]))
    with right:
        st.markdown("##### Who benefits, who faces restrictions (Gemini)")
        ind = [i for i in r["affected_industries"] if isinstance(i, dict)]
        if ind:
            st.dataframe(pd.DataFrame([{"Sector": i.get("sector"), "Effect": EFFECT_ICON.get(i.get("effect"), i.get("effect")),
                                        "Why": i.get("reason")} for i in ind]))
        else:
            st.caption("Needs the Gemini analysis.")
        if r["new_business_opportunities"]:
            st.markdown("**New business opportunities**")
            for x in r["new_business_opportunities"]:
                st.markdown(f"- {x}")
    st.markdown("##### Stakeholders")
    for k, v in r["stakeholders"].items():
        if v:
            st.markdown(f"**{k.replace('_', ' ').title()}:** " + "; ".join(map(str, v)))

with t_time:
    rows = r["chronology"]
    if rows:
        fig = timeline_figure(rows, r["title"])
        if fig:
            st.pyplot(fig)
        table = pd.DataFrame(rows)[["year", "event", "type", "context"]]
        table["year"] = pd.to_numeric(table["year"]).astype("Int64")
        st.dataframe(table)
    else:
        st.info("No earlier acts, amendments or committee reviews were detected in the text.")
    if r["related_acts"]:
        st.markdown("##### Related acts (Gemini)")
        st.dataframe(pd.DataFrame([a if isinstance(a, dict) else {"name": a} for a in r["related_acts"]]))

with t_graph:
    st.markdown("##### How this bill connects to earlier laws, amendments and committees")
    if r["chronology"]:
        dot = dependency_dot(r["chronology"], r["title"])
        st.graphviz_chart(dot)
        with st.expander("Graph source (DOT)"):
            st.code(dot)
    else:
        st.info("No related acts or committees were detected, so there is nothing to connect.")

with t_imp:
    cols = st.columns(3)
    for col, (label, key) in zip(cols, [("Short term (0-1 yr)", "short_term"), ("Medium term (1-5 yrs)", "medium_term"),
                                        ("Long term (>5 yrs)", "long_term")]):
        col.markdown(f"##### {label}")
        for x in r["impact"][key]:
            col.markdown(f"- {x}")
    if r["risks_and_unintended_consequences"]:
        st.markdown("##### Risks & unintended consequences")
        for x in r["risks_and_unintended_consequences"]:
            st.markdown(f"- {x}")

with t_risk:
    st.markdown("##### Clause-level risk flags (rule-based, from the bill text)")
    for x in r["rule_based_risks"]:
        icon = {"High": "🔴", "Medium": "🟠", "Low": "🟡"}[x["severity"]]
        with st.expander(f"{icon} {x['category']} - {x['severity']} ({x['mentions']} mentions)"):
            for ex in x["examples"]:
                st.markdown(f"> {ex}")
    if not r["rule_based_risks"]:
        st.success("No risk patterns detected.")
    for label, key in [("Controversial areas", "controversial_areas"), ("Possible public backlash", "possible_public_backlash"),
                       ("Implementation challenges", "implementation_challenges")]:
        if r[key]:
            st.markdown(f"##### {label} (Gemini)")
            for x in r[key]:
                st.markdown(f"- {x}")

with t_dl:
    st.download_button("⬇️ Download JSON", json.dumps(r, indent=2, default=str), "bill_analysis.json", "application/json")
    try:
        st.download_button("⬇️ Download PDF summary", build_pdf(r), "bill_summary.pdf", "application/pdf")
    except Exception as exc:
        st.error(f"Could not build the PDF: {exc}")
st.caption("AI-generated for general understanding - not legal advice. Check the official bill text.")
