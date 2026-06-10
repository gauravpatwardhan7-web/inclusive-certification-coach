"""
Inclusive Certification Coach - demo UI.

The core idea of this UI: make the AGENT REASONING VISIBLE. As the learner moves
through the flow, the right-hand panel shows each agent's step, what it
retrieved (chunks + relevance scores), what it cited, and the orchestrator's
advance/loop/escalate decision with the signals it weighed.

The loop is REAL here: attempt history persists across retakes, a "loop"
decision triggers focused remediation (weak areas only), and three stalled
attempts escalate to a human coach.
"""

import sys
from pathlib import Path

# Make `src` importable when run via `streamlit run app/streamlit_app.py`.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import json as _json
import streamlit as st
import streamlit.components.v1 as components
from src.agents.curator import curate
from src.agents.study_planner import generate_study_plan
from src.agents.assessor import generate_assessment, score_assessment
from src.agents.manager_insights import team_insights, load_team
from src.accessibility import to_spoken
from src.orchestrator import decide


def read_aloud(text: str, key: str):
    """Client-side text-to-speech via the browser Web Speech API (no quota)."""
    if not text:
        return
    safe = _json.dumps(text)
    components.html(
        f"""
        <div style="font-family: sans-serif;">
          <button onclick="speak_{key}()"
            style="padding:6px 12px;margin-right:6px;border:1px solid #ccc;
                   border-radius:6px;cursor:pointer;">🔊 Read aloud</button>
          <button onclick="window.speechSynthesis.cancel()"
            style="padding:6px 12px;border:1px solid #ccc;border-radius:6px;
                   cursor:pointer;">⏹ Stop</button>
        </div>
        <script>
          function speak_{key}() {{
            window.speechSynthesis.cancel();
            const u = new SpeechSynthesisUtterance({safe});
            u.rate = 0.95;
            window.speechSynthesis.speak(u);
          }}
        </script>
        """,
        height=48,
    )

st.set_page_config(page_title="Inclusive Certification Coach", page_icon="🎓", layout="wide")

# ---- session state ----
ss = st.session_state
ss.setdefault("trace", [])
ss.setdefault("path", None)
ss.setdefault("study_plan", None)
ss.setdefault("assessment", None)
ss.setdefault("result", None)
ss.setdefault("decision", None)
ss.setdefault("insights", None)
ss.setdefault("spoken_path", "")
ss.setdefault("spoken_rec", "")
ss.setdefault("history", [])        # attempt history - persists across retakes
ss.setdefault("focus_areas", None)  # set when the orchestrator loops


def log(agent: str, did: str, retrieved: list | None = None,
        decision_detail: dict | None = None):
    step = {"agent": agent, "did": did}
    if retrieved:
        step["retrieved"] = retrieved
    if decision_detail:
        step["decision_detail"] = decision_detail
    ss.trace.append(step)


def build_round(cert: str, role: str, profile: str, voice_mode: bool,
                focus_areas: list[str] | None):
    """One curate -> plan -> assess round (full path, or focused remediation)."""
    tag = f" (remediation: {', '.join(focus_areas)})" if focus_areas else ""
    with st.spinner("Curator retrieving grounded content..."):
        ss.path = curate(cert, role, profile, focus_areas=focus_areas)
        mods = ss.path.get("modules", [])
        log("Learning Path Curator",
            f"Retrieved grounded content from Foundry IQ and built a "
            f"{ss.path.get('total_hours', 0)}h path ({len(mods)} modules), each cited{tag}.",
            retrieved=ss.path.get("_retrieval"))
    if not mods:
        st.warning("The knowledge base has no content for this certification: "
                   + (ss.path.get("note") or "no further detail given."))
        ss.study_plan = None
        ss.assessment = None
        return
    with st.spinner("Study Plan Generator scheduling, accommodation-aware..."):
        ss.study_plan = generate_study_plan(ss.path, profile,
                                            remediation=focus_areas is not None)
        log("Study Plan Generator",
            f"Scheduled the path into {len(ss.study_plan.get('sessions', []))} sessions over "
            f"{ss.study_plan.get('total_days', '?')} days "
            f"({ss.study_plan.get('block_minutes', '?')}-min blocks).",
            retrieved=ss.study_plan.get("_retrieval"))
    with st.spinner("Assessment Agent generating grounded questions..."):
        ss.assessment = generate_assessment(cert, role, num_questions=3,
                                            focus_areas=focus_areas)
        log("Assessment Agent",
            f"Generated {len(ss.assessment.get('questions', []))} grounded, cited questions{tag}.",
            retrieved=ss.assessment.get("_retrieval"))
    ss.spoken_path = ""
    if voice_mode:
        with st.spinner("Accessibility Narrator preparing a spoken version..."):
            ss.spoken_path = to_spoken("learning_path", ss.path, profile)
            log("Accessibility Narrator",
                "Rendered the learning path as a screen-reader-first spoken script.")
    ss.result = None
    ss.decision = None
    ss.spoken_rec = ""


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
    cert = st.selectbox(
        "Target certification", ["AZ-204", "AZ-900"],
        help="AZ-900 requires data/knowledge_base/az900_fundamentals_guide.md "
             "to be indexed in your Azure AI Search resource. If it isn't, the "
             "Curator will (correctly) refuse rather than invent a path.",
    )
    role = st.text_input("Your role", "Cloud Engineer")
    profile = st.text_area(
        "Accessibility profile (optional)",
        "Has ADHD; struggles to focus in long study sessions.",
        help="Used to adapt pacing, formats, and study blocks.",
    )
    voice_mode = st.toggle(
        "🔊 Voice / screen-reader mode",
        value=False,
        help="Generates a screen-reader-first spoken script for each result and "
             "lets you play it aloud (browser text-to-speech, no audio model).",
    )

    if st.button("Build my learning path", type="primary"):
        ss.trace = []
        ss.history = []          # a fresh goal starts a fresh attempt history
        ss.focus_areas = None
        build_round(cert, role, profile, voice_mode, focus_areas=None)

    if ss.path and ss.path.get("modules"):
        focus_note = (f" · focused on: {', '.join(ss.focus_areas)}"
                      if ss.focus_areas else "")
        st.subheader("2 · Your accessibility-aware learning path")
        if focus_note:
            st.caption(f"Remediation path{focus_note}")
        for m in ss.path["modules"]:
            with st.expander(f"{m.get('skill_area', '?')} · {m.get('recommended_hours', '?')}h"):
                st.write(f"**Accommodation:** {m.get('accommodation_note', '—')}")
                st.caption(f"Source: {m.get('source_id', '—')}")
        if ss.spoken_path:
            with st.expander("🔊 Spoken version (screen-reader friendly)"):
                st.write(ss.spoken_path)
                read_aloud(ss.spoken_path, "path")

    if ss.study_plan:
        sp = ss.study_plan
        st.subheader("3 · Your accommodation-aware study schedule")
        st.caption(
            f"{sp.get('total_days', '?')} days · up to {sp.get('daily_max_minutes', '?')} min/day · "
            f"{sp.get('block_minutes', '?')}-min blocks"
        )
        for s in sp.get("sessions", [])[:8]:
            st.markdown(
                f"**Day {s.get('day', '?')} · {s.get('skill_area', '?')}** — "
                f"{s.get('minutes', '?')} min ({s.get('blocks', '?')})  \n"
                f"_{s.get('accommodation_note', '')}_"
            )
        if len(sp.get("sessions", [])) > 8:
            st.caption(f"... and {len(sp['sessions']) - 8} more sessions.")
        if sp.get("checkpoints"):
            st.write("**Checkpoints:** " + " · ".join(sp["checkpoints"]))

    if ss.assessment and ss.assessment.get("questions"):
        attempt_no = len(ss.history) + 1
        st.subheader(f"4 · Quick readiness check — attempt {attempt_no}")
        answers = {}
        for q in ss.assessment["questions"]:
            answers[q["id"]] = st.radio(
                q.get("question", q["id"]), q.get("options", []),
                key=f"{q['id']}-a{attempt_no}", index=None,
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
                    f"Scored attempt {attempt_no}: {ss.result.get('score_pct')}% "
                    f"(ready={ss.result.get('ready')}); "
                    f"weak areas: {ss.result.get('weak_areas') or 'none'}.")
                # The history GROWS across retakes - this is what lets the
                # orchestrator see trends and escalate after stalled attempts.
                ss.history = ss.history + [
                    {"attempt": attempt_no, "score_pct": ss.result.get("score_pct")}
                ]
                ss.decision = decide(ss.result, ss.history, profile)
                log("Orchestrator (reasoning)",
                    f"Decision after attempt {attempt_no}: {ss.decision['action'].upper()} "
                    f"— {ss.decision.get('reason', '')}",
                    decision_detail=ss.decision)
                if voice_mode:
                    ss.spoken_rec = to_spoken("recommendation", ss.decision, profile)
                    log("Accessibility Narrator",
                        "Rendered the recommendation as a spoken script.")

    if ss.decision:
        st.subheader("5 · Recommendation")
        action = ss.decision.get("action")
        if action == "advance":
            st.success(f"✅ Advance. {ss.decision.get('message_to_learner', '')}")
        elif action == "loop":
            st.warning(f"🔁 Keep going. {ss.decision.get('message_to_learner', '')}")
            if ss.decision.get("focus_next"):
                st.write("**Focus next on:** " + ", ".join(ss.decision["focus_next"]))
            # THE LOOP, MADE REAL: one click re-curates only the weak areas,
            # re-plans lighter, and generates a focused retake.
            if st.button(
                f"🔁 Start focused remediation (attempt {len(ss.history) + 1})",
                type="primary",
            ):
                ss.focus_areas = ss.decision.get("focus_next") or None
                build_round(cert, role, profile, voice_mode,
                            focus_areas=ss.focus_areas)
                st.rerun()
        else:
            st.info(f"🧑‍🏫 Escalating to a human coach. {ss.decision.get('message_to_learner', '')}")
            scores = " → ".join(str(h.get("score_pct")) for h in ss.history)
            st.caption(f"Attempt history that triggered the handoff: {scores}")
        if ss.spoken_rec:
            with st.expander("🔊 Spoken version (screen-reader friendly)"):
                st.write(ss.spoken_rec)
                read_aloud(ss.spoken_rec, "rec")

    st.divider()
    st.subheader("👥 Manager view · team readiness")
    st.caption("Agent 5 — Manager Insights. Reasons over a synthetic team's progress (TEAM-A).")
    if st.button("Run team readiness rollup"):
        with st.spinner("Manager Insights reasoning over the team..."):
            ss.insights = team_insights(load_team())
            log("Manager Insights",
                f"Rolled up TEAM-A: {ss.insights.get('team_readiness_pct')}% ready.")
    if ss.insights:
        ins = ss.insights
        st.metric("Team readiness", f"{ins.get('team_readiness_pct', '?')}%")
        st.write(ins.get("summary", ""))
        status_icon = {"ready": "✅", "on_track": "📈", "at_risk": "⚠️", "needs_support": "🧑‍🏫"}
        for lr in ins.get("learners", []):
            st.markdown(
                f"{status_icon.get(lr.get('status'), '•')} **{lr.get('learner_id', '?')}** "
                f"({lr.get('status', '?')}) — {lr.get('rationale', '')}  \n"
                f"_Action: {lr.get('recommended_action', '')}_"
            )
        if ins.get("team_actions"):
            st.write("**Team actions:** " + " · ".join(ins["team_actions"]))

# ================= RIGHT: the reasoning trace =================
with right:
    st.subheader("🧠 Agent reasoning trace")
    st.caption("What each agent did, what it retrieved, and how the orchestrator "
               "weighed the evidence — across every loop iteration.")
    if ss.history:
        st.caption("Attempts so far: " +
                   " → ".join(f"{h.get('score_pct')}%" for h in ss.history))
    if not ss.trace:
        st.info("Run a learning path to see the agents reason step by step.")
    for i, step in enumerate(ss.trace, 1):
        st.markdown(f"**{i}. {step['agent']}**")
        st.write(step["did"])
        if step.get("retrieved"):
            with st.expander(f"📚 Retrieved {len(step['retrieved'])} chunks (Foundry IQ)"):
                for c in step["retrieved"]:
                    st.caption(f"`{c['source_id']}` · relevance {c['score']}")
                    st.write(c["snippet"] + ("…" if len(c["snippet"]) >= 160 else ""))
        d = step.get("decision_detail")
        if d:
            with st.expander("🧩 How the orchestrator decided"):
                if d.get("signals_considered"):
                    st.markdown("**Signals weighed:**")
                    for s in d["signals_considered"]:
                        st.markdown(f"- {s}")
                if d.get("alternatives_rejected"):
                    st.markdown("**Alternatives rejected:**")
                    for a in d["alternatives_rejected"]:
                        st.markdown(f"- {a}")
                if d.get("guardrail_notes"):
                    st.markdown("**Deterministic guardrails applied:**")
                    for g in d["guardrail_notes"]:
                        st.markdown(f"- ⚙️ {g}")
        st.divider()
