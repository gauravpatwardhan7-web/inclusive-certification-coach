"""
Inclusive Certification Coach - demo UI.

The core idea of this UI: make the AGENT REASONING VISIBLE. As the learner moves
through the flow, the right-hand panel shows each agent's step, what it retrieved
and cited, and the orchestrator's advance/loop decision with its reasoning.
"""

import sys
from pathlib import Path

# Make `src` importable when run via `streamlit run app/streamlit_app.py`.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st
from src.agents.curator import curate
from src.agents.assessor import generate_assessment, score_assessment
from src.orchestrator import decide

st.set_page_config(page_title="Inclusive Certification Coach", page_icon="🎓", layout="wide")

# ---- session state ----
ss = st.session_state
ss.setdefault("trace", [])
ss.setdefault("path", None)
ss.setdefault("assessment", None)
ss.setdefault("result", None)
ss.setdefault("decision", None)


def log(agent: str, did: str):
    ss.trace.append({"agent": agent, "did": did})


# ---- header ----
st.title("🎓 Inclusive Certification Coach")
st.caption(
    "An accessibility-first, multi-agent certification coach. "
    "Grounded in Microsoft Foundry IQ. All data synthetic."
)

left, right = st.columns([3, 2])

# ================= LEFT: the learner flow =================
with left:
    st.subheader("1 · Your goal")
    cert = st.selectbox("Target certification", ["AZ-204"])
    role = st.text_input("Your role", "Cloud Engineer")
    profile = st.text_area(
        "Accessibility profile (optional)",
        "Has ADHD; struggles to focus in long study sessions.",
        help="Used to adapt pacing, formats, and study blocks.",
    )

    if st.button("Build my learning path", type="primary"):
        ss.trace = []
        with st.spinner("Curator retrieving grounded content..."):
            ss.path = curate(cert, role, profile)
            log("Learning Path Curator",
                f"Retrieved grounded content from Foundry IQ and built a "
                f"{ss.path['total_hours']}h path ({len(ss.path['modules'])} modules), each cited.")
            ss.assessment = generate_assessment(cert, role, num_questions=3)
            log("Assessment Agent",
                f"Generated {len(ss.assessment['questions'])} grounded, cited questions.")
        ss.result = None
        ss.decision = None

    if ss.path:
        st.subheader("2 · Your accessibility-aware learning path")
        for m in ss.path["modules"]:
            with st.expander(f"{m['skill_area']} · {m['recommended_hours']}h"):
                st.write(f"**Accommodation:** {m['accommodation_note']}")
                st.caption(f"Source: {m['source_id']}")

    if ss.assessment:
        st.subheader("3 · Quick readiness check")
        answers = {}
        for q in ss.assessment["questions"]:
            answers[q["id"]] = st.radio(
                q["question"], q["options"], key=q["id"], index=None
            )
        if st.button("Submit answers"):
            # Map selected option text back to its letter (A/B/C/D).
            picked = {}
            for q in ss.assessment["questions"]:
                sel = answers[q["id"]]
                picked[q["id"]] = sel.split(")")[0].strip() if sel else "X"
            with st.spinner("Assessment scoring + Orchestrator reasoning..."):
                ss.result = score_assessment(ss.assessment["questions"], picked)
                log("Assessment Agent",
                    f"Scored {ss.result['score_pct']}% (ready={ss.result['ready']}); "
                    f"weak areas: {ss.result['weak_areas'] or 'none'}.")
                ss.decision = decide(ss.result, [{"attempt": 1, "score_pct": ss.result["score_pct"]}], profile)
                log("Orchestrator (reasoning)",
                    f"Decision: {ss.decision['action'].upper()} — {ss.decision['reason']}")

    if ss.decision:
        st.subheader("4 · Recommendation")
        action = ss.decision["action"]
        if action == "advance":
            st.success(f"✅ Advance. {ss.decision['message_to_learner']}")
        elif action == "loop":
            st.warning(f"🔁 Keep going. {ss.decision['message_to_learner']}")
            if ss.decision.get("focus_next"):
                st.write("**Focus next on:** " + ", ".join(ss.decision["focus_next"]))
        else:
            st.info(f"🧑‍🏫 Escalating to a human coach. {ss.decision['message_to_learner']}")

# ================= RIGHT: the reasoning trace =================
with right:
    st.subheader("🧠 Agent reasoning trace")
    st.caption("What each agent did, in order. This is the multi-step reasoning.")
    if not ss.trace:
        st.info("Run a learning path to see the agents reason step by step.")
    for i, step in enumerate(ss.trace, 1):
        st.markdown(f"**{i}. {step['agent']}**")
        st.write(step["did"])
        st.divider()
