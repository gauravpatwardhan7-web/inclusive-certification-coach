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
from datetime import date

import streamlit as st
import streamlit.components.v1 as components
from src.agents.curator import curate
from src.agents.study_planner import generate_study_plan
from src.agents.assessor import generate_assessment, score_assessment
from src.agents.manager_insights import team_insights, load_team
from src.agents.calendar_negotiator import negotiate, load_calendar
from src.agents.teachback import evaluate_teachback, to_assessment_result
from src.accessibility import to_spoken
from src.orchestrator import decide
from src import mastery


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
ss.setdefault("negotiation", None)  # calendar negotiation result
ss.setdefault("tb_eval", None)      # teach-back round-1 evaluation
ss.setdefault("tb_final", None)     # teach-back final evaluation

LEARNER_ID = "demo-learner"


def record_mastery(per_skill: list[dict] | None = None,
                   skill: str | None = None, score_pct: int | None = None):
    """Fold assessment outcomes into the persistent memory-decay store."""
    store = mastery.load_store()
    today = date.today()
    if per_skill:
        for entry in per_skill:
            pct = 100 if entry.get("result") == "correct" else 20
            mastery.record_review(store, LEARNER_ID, entry.get("skill_area", "?"),
                                  pct, today)
    if skill and score_pct is not None:
        mastery.record_review(store, LEARNER_ID, skill, score_pct, today)
    mastery.save_store(store)


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
    ss.negotiation = None
    ss.tb_eval = None
    ss.tb_final = None


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

        st.subheader("3b · Make it real: negotiate with your calendar")
        st.caption("A plan that ignores your meetings is a plan you won't follow. "
                   "The Calendar Negotiator books study blocks into actual gaps — "
                   "or pushes back with evidence when the week doesn't have the time.")
        week_choice = st.selectbox(
            "Your work calendar this week (synthetic)",
            ["Light week (a few meetings)", "Packed week (back-to-back)"],
        )
        if st.button("📅 Negotiate study time with my calendar"):
            cal_file = ("calendar_light_week.json" if week_choice.startswith("Light")
                        else "calendar_packed_week.json")
            with st.spinner("Calendar Negotiator finding real gaps and booking blocks..."):
                ss.negotiation = negotiate(sp, load_calendar(cal_file), profile)
                neg = ss.negotiation
                stats = neg["stats"]
                log("Calendar Negotiator",
                    f"Week needs {stats['required_minutes_this_week']} min; calendar has "
                    f"{stats['available_minutes_this_week']} usable min between meetings. "
                    f"Booked {stats['scheduled_minutes']} min -> "
                    f"{'feasible' if neg['feasible'] else 'INFEASIBLE: pushed back with options'}.",
                    decision_detail={
                        "signals_considered": neg["policy"].get("rationale", []),
                        "guardrail_notes": neg.get("guardrail_notes", []),
                    })
        if ss.negotiation:
            neg = ss.negotiation
            stats = neg["stats"]
            c1, c2, c3 = st.columns(3)
            c1.metric("Plan needs (this week)", f"{stats['required_minutes_this_week']} min")
            c2.metric("Calendar has", f"{stats['available_minutes_this_week']} min")
            c3.metric("Booked", f"{stats['scheduled_minutes']} min")
            st.write(neg["negotiation"].get("summary", ""))
            if neg["scheduled_blocks"]:
                with st.expander(f"📅 {len(neg['scheduled_blocks'])} booked study blocks"):
                    last_day = None
                    for b in neg["scheduled_blocks"]:
                        if b["date"] != last_day:
                            st.markdown(f"**{b['weekday']} {b['date']}**")
                            last_day = b["date"]
                        st.markdown(f"- {b['start']}–{b['end']} · {b['skill_area']} "
                                    f"({b['minutes']} min) — `{b['source_id']}`")
            if not neg["feasible"]:
                st.error(f"⚖️ This week can't hold the plan — projected "
                         f"{stats['est_weeks_to_complete_plan']} weeks at your calendar's pace.")
                st.markdown("**Draft message to your manager (evidence, not excuses):**")
                st.info(neg["negotiation"].get("message_to_manager", ""))
                if neg["negotiation"].get("options"):
                    st.markdown("**Your options:**")
                    for o in neg["negotiation"]["options"]:
                        st.markdown(f"- {o}")

    def finish_attempt(result: dict, attempt_no: int):
        """Shared tail of both assessment modes: history -> decide -> narrate."""
        ss.result = result
        # The history GROWS across retakes - this is what lets the
        # orchestrator see trends and escalate after stalled attempts.
        ss.history = ss.history + [
            {"attempt": attempt_no, "score_pct": result.get("score_pct")}
        ]
        ss.decision = decide(result, ss.history, profile)
        log("Orchestrator (reasoning)",
            f"Decision after attempt {attempt_no}: {ss.decision['action'].upper()} "
            f"— {ss.decision.get('reason', '')}",
            decision_detail=ss.decision)
        if voice_mode:
            ss.spoken_rec = to_spoken("recommendation", ss.decision, profile)
            log("Accessibility Narrator",
                "Rendered the recommendation as a spoken script.")

    if ss.path and ss.path.get("modules"):
        attempt_no = len(ss.history) + 1
        st.subheader(f"4 · Readiness check — attempt {attempt_no}")
        mode = st.radio(
            "How do you want to show what you know?",
            ["Quick check (multiple choice)",
             "Teach it back (explain in your own words)"],
            horizontal=True,
            help="Teach-back grades your understanding, not your option-picking — "
                 "and works typed or dictated, with no answer grid to scan.",
        )

        if mode.startswith("Quick") and ss.assessment and ss.assessment.get("questions"):
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
                    result = score_assessment(ss.assessment["questions"], picked)
                    log("Assessment Agent",
                        f"Scored attempt {attempt_no}: {result.get('score_pct')}% "
                        f"(ready={result.get('ready')}); "
                        f"weak areas: {result.get('weak_areas') or 'none'}.")
                    record_mastery(per_skill=result.get("per_skill"))
                    finish_attempt(result, attempt_no)

        elif mode.startswith("Teach"):
            skill_options = [m.get("skill_area", "?") for m in ss.path["modules"]]
            tb_skill = st.selectbox("Pick a skill area to explain", skill_options)
            tb_text = st.text_area(
                "Explain it like you're telling a colleague (typed or dictated)",
                key=f"tb-{attempt_no}", height=140,
                placeholder="In your own words: what is it, why does it matter, "
                            "how would you actually use it?",
            )
            if st.button("Evaluate my explanation") and tb_text.strip():
                with st.spinner("Teach-back Assessor grading against the knowledge base..."):
                    ss.tb_eval = evaluate_teachback(cert, tb_skill, tb_text, profile)
                    ss.tb_final = None
                    ev = ss.tb_eval
                    log("Teach-back Assessor",
                        f"Graded explanation of '{tb_skill}': {ev.get('understanding_pct')}% "
                        f"understanding; missing: {ev.get('concepts_missing') or 'nothing'}; "
                        f"probing with one follow-up.",
                        retrieved=ev.get("_retrieval"))

            if ss.tb_eval and not ss.tb_final:
                ev = ss.tb_eval
                st.write(ev.get("feedback", ""))
                cov, mis = st.columns(2)
                with cov:
                    st.markdown("**You covered:**")
                    for c in ev.get("concepts_covered", []) or ["—"]:
                        st.markdown(f"- ✅ {c}")
                with mis:
                    st.markdown("**Still missing:**")
                    for c in ev.get("concepts_missing", []) or ["—"]:
                        st.markdown(f"- ⬜ {c}")
                if ev.get("misconception"):
                    st.warning(f"⚠️ One thing to un-learn: {ev['misconception']}")
                st.markdown(f"**Follow-up question:** {ev.get('follow_up_question', '')}")
                tb_answer = st.text_area("Your answer", key=f"tbf-{attempt_no}", height=90)
                if st.button("Submit follow-up answer") and tb_answer.strip():
                    with st.spinner("Folding your answer into the final grade..."):
                        ss.tb_final = evaluate_teachback(
                            cert, tb_skill, tb_text, profile,
                            follow_up_question=ev.get("follow_up_question", ""),
                            follow_up_answer=tb_answer,
                        )
                        fin = ss.tb_final
                        log("Teach-back Assessor",
                            f"Final grade after follow-up: {fin.get('understanding_pct')}% "
                            f"understanding of '{tb_skill}'.")
                        result = to_assessment_result(fin)
                        record_mastery(skill=tb_skill,
                                       score_pct=int(fin.get("understanding_pct", 0)))
                        finish_attempt(result, attempt_no)

            if ss.tb_final:
                st.write(ss.tb_final.get("feedback", ""))
                st.metric("Understanding", f"{ss.tb_final.get('understanding_pct', 0)}%")

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
    st.subheader("🧠 Your memory, tracked honestly")
    st.caption("A skill passed three weeks ago is not a skill known today. Mastery "
               "decays with a half-life that doubles every review (the spacing "
               "effect) — refreshers land just before you'd forget.")
    mem_rows = mastery.snapshot(mastery.load_store(), LEARNER_ID, date.today())
    if not mem_rows:
        st.info("Complete an assessment and your per-skill memory will be tracked here.")
    due_now = []
    for r in mem_rows:
        icon = "🔔" if r["due_refresher"] else "🟢"
        if r["due_refresher"]:
            due_now.append(r["skill_area"])
        st.progress(min(100, max(0, r["decayed_mastery"])) / 100,
                    text=f"{icon} {r['skill_area']} — retained {r['decayed_mastery']}% "
                         f"(was {r['raw_mastery']}%, reviewed {r['days_since_review']}d ago, "
                         f"half-life {round(r['half_life_days'])}d)")
    if due_now:
        st.warning("Due for a refresher: " + " · ".join(due_now))
        if st.button("🔔 Build a refresher path for the fading skills"):
            ss.focus_areas = due_now
            log("Memory Tracker",
                f"Decayed mastery below retention on {len(due_now)} previously "
                f"learned skill(s): {due_now}. Requesting a focused refresher path.")
            build_round(cert, role, profile, voice_mode, focus_areas=due_now)
            st.rerun()

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
            with st.expander("🧩 Reasoning detail"):
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
