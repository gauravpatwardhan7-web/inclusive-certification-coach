"""
Inclusive Certification Coach - demo UI.

The core idea of this UI: make the AGENT REASONING VISIBLE. The right-hand
panel is a live timeline of each agent's step - what it retrieved (chunks +
relevance scores), what it cited, and how the orchestrator weighed the
evidence - across every loop iteration.

Presentation is delegated to app/theme.py (Swiss/minimal design system,
Lexend + Source Sans 3, semantic tokens, visible focus, reduced-motion
support). All agent logic is unchanged.
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
from src.agents.advocate import draft_advocacy
from src.accessibility import to_spoken
from src.orchestrator import decide
from src import mastery
from app import theme

st.set_page_config(page_title="Inclusive Certification Coach",
                   page_icon="🎓", layout="wide")

st.markdown(theme.CSS, unsafe_allow_html=True)


def H(html_str: str):
    st.markdown(html_str, unsafe_allow_html=True)


def read_aloud(text: str, key: str):
    """Client-side text-to-speech via the browser Web Speech API (no quota)."""
    if not text:
        return
    safe = _json.dumps(text)
    components.html(
        f"""
        <div style="font-family: 'Source Sans 3', sans-serif;">
          <button onclick="speak_{key}()" aria-label="Read this aloud"
            style="min-height:40px;padding:6px 16px;margin-right:6px;border:1px solid #CBD5E1;
                   border-radius:10px;cursor:pointer;font-weight:600;background:#fff;">
            ▶ Read aloud</button>
          <button onclick="window.speechSynthesis.cancel()" aria-label="Stop reading"
            style="min-height:40px;padding:6px 16px;border:1px solid #CBD5E1;border-radius:10px;
                   cursor:pointer;font-weight:600;background:#fff;">■ Stop</button>
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
        height=54,
    )


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
ss.setdefault("advocacy", None)     # drafted advocacy note awaiting approval
ss.setdefault("advocacy_sent", False)

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
        H(theme.banner("warn", "alert", "Nothing to build from",
                       "The knowledge base has no content for this certification: "
                       + theme.esc(ss.path.get("note") or "no further detail given.")))
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


# ---- hero ----
H(theme.hero([
    ("brain", "8 reasoning agents"),
    ("book", "Grounded via Foundry IQ — every claim cited"),
    ("shield", "Consent enforced in code"),
    ("check", "72/72 eval checks green"),
]))

left, right = st.columns([3, 2], gap="large")

# ================= LEFT: the learner flow =================
with left:
    H(theme.section("Step 1", "Your goal",
                    "Tell the coach what you're working toward and how you work best."))
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
        "Voice / screen-reader mode",
        value=False,
        help="Generates a screen-reader-first spoken script for each result and "
             "lets you play it aloud (browser text-to-speech, no audio model).",
    )

    if st.button("Build my learning path", type="primary", use_container_width=True):
        ss.trace = []
        ss.history = []          # a fresh goal starts a fresh attempt history
        ss.focus_areas = None
        build_round(cert, role, profile, voice_mode, focus_areas=None)

    if ss.path and ss.path.get("modules"):
        H(theme.section("Step 2", "Your accessibility-aware learning path",
                        ("Remediation path — focused on: " + ", ".join(ss.focus_areas))
                        if ss.focus_areas else
                        "Every module is grounded in the knowledge base and cites its source."))
        for m in ss.path["modules"]:
            H(theme.module_card(m.get("skill_area", "?"),
                                m.get("recommended_hours", "?"),
                                m.get("accommodation_note", "—"),
                                m.get("source_id", "—")))
        if ss.spoken_path:
            with st.expander("Spoken version (screen-reader friendly)"):
                st.write(ss.spoken_path)
                read_aloud(ss.spoken_path, "path")

    if ss.study_plan:
        sp = ss.study_plan
        H(theme.section("Step 3", "Your accommodation-aware study schedule"))
        H(theme.tiles([
            (str(sp.get("total_days", "?")), "days"),
            (f"≤ {sp.get('daily_max_minutes', '?')}", "min / day"),
            (str(sp.get("block_minutes", "?")), "min blocks"),
            (str(len(sp.get("sessions", []))), "sessions"),
        ]))
        for s in sp.get("sessions", [])[:8]:
            H(theme.session_row(s.get("day", "?"), s.get("skill_area", "?"),
                                s.get("minutes", "?"), s.get("blocks", ""),
                                s.get("accommodation_note", "")))
        if len(sp.get("sessions", [])) > 8:
            st.caption(f"… and {len(sp['sessions']) - 8} more sessions.")
        if sp.get("checkpoints"):
            H(theme.banner("info", "target", "Checkpoints",
                           " · ".join(theme.esc(c) for c in sp["checkpoints"])))

        H(theme.section("Step 3b", "Make it real: negotiate with your calendar",
                        "A plan that ignores your meetings is a plan you won't follow. "
                        "The negotiator books blocks into actual gaps — or pushes back "
                        "with evidence when the week doesn't have the time."))
        week_choice = st.radio(
            "Your work calendar this week (synthetic)",
            ["Light week — a few meetings", "Packed week — back-to-back"],
            horizontal=True,
        )
        if st.button("Negotiate study time with my calendar", use_container_width=True):
            cal_file = ("calendar_light_week.json" if week_choice.startswith("Light")
                        else "calendar_packed_week.json")
            with st.spinner("Calendar Negotiator finding real gaps and booking blocks..."):
                ss.negotiation = negotiate(sp, load_calendar(cal_file), profile)
                ss.negotiation["_calendar_file"] = cal_file
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
            H(theme.tiles([
                (f"{stats['required_minutes_this_week']}", "min the plan needs"),
                (f"{stats['available_minutes_this_week']}", "min calendar has"),
                (f"{stats['scheduled_minutes']}", "min booked"),
                (f"~{stats['est_weeks_to_complete_plan']} wk", "projected to finish"),
            ]))
            st.write(neg["negotiation"].get("summary", ""))
            if neg["scheduled_blocks"]:
                H(theme.week_grid(load_calendar(neg.get("_calendar_file",
                                                        "calendar_light_week.json")),
                                  neg["scheduled_blocks"]))
            if not neg["feasible"]:
                H(theme.banner("bad", "alert", "This week can't hold the plan",
                               f"Projected ~{stats['est_weeks_to_complete_plan']} weeks at "
                               f"your calendar's pace. Evidence, not excuses — here's a "
                               f"draft for your manager:"))
                H(f'<div class="icc-card">{theme.esc(neg["negotiation"].get("message_to_manager", ""))}</div>')
                if neg["negotiation"].get("options"):
                    H(theme.banner("info", "repeat", "Your options",
                                   "<br>".join("• " + theme.esc(o)
                                               for o in neg["negotiation"]["options"])))

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
        H(theme.section("Step 4", f"Readiness check — attempt {attempt_no}",
                        "Show what you know, the way that suits you."))
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
            if st.button("Submit answers", type="primary"):
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
            if st.button("Evaluate my explanation", type="primary") and tb_text.strip():
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
                H(theme.ledger(
                    [f"✓ {c}" for c in ev.get("concepts_covered", [])],
                    [f"… {c}" for c in ev.get("concepts_missing", [])],
                ).replace("This note shares", "You covered")
                 .replace("Kept private", "Still missing"))
                if ev.get("misconception"):
                    H(theme.banner("warn", "alert", "One thing to un-learn",
                                   theme.esc(ev["misconception"])))
                H(theme.banner("info", "brain", "Follow-up question",
                               theme.esc(ev.get("follow_up_question", ""))))
                tb_answer = st.text_area("Your answer", key=f"tbf-{attempt_no}", height=90)
                if st.button("Submit follow-up answer", type="primary") and tb_answer.strip():
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
                H(theme.tiles([(f"{ss.tb_final.get('understanding_pct', 0)}%",
                                "understanding")]))

    if ss.decision:
        H(theme.section("Step 5", "Recommendation"))
        if ss.history:
            H(theme.attempts_chips(ss.history))
        action = ss.decision.get("action")
        if action == "advance":
            H(theme.banner("ok", "check", "Advance — you're ready",
                           theme.esc(ss.decision.get("message_to_learner", ""))))
        elif action == "loop":
            focus = ss.decision.get("focus_next", [])
            body = theme.esc(ss.decision.get("message_to_learner", ""))
            if focus:
                body += ("<br><strong>Focus next on:</strong> "
                         + theme.esc(", ".join(focus)))
            H(theme.banner("warn", "repeat", "Keep going — loop back to weak areas", body))
            # THE LOOP, MADE REAL: one click re-curates only the weak areas,
            # re-plans lighter, and generates a focused retake.
            if st.button(
                f"Start focused remediation (attempt {len(ss.history) + 1})",
                type="primary", use_container_width=True,
            ):
                ss.focus_areas = ss.decision.get("focus_next") or None
                build_round(cert, role, profile, voice_mode,
                            focus_areas=ss.focus_areas)
                st.rerun()
        else:
            scores = " → ".join(f"{h.get('score_pct')}%" for h in ss.history)
            H(theme.banner("bad", "user", "Escalating to a human coach",
                           theme.esc(ss.decision.get("message_to_learner", ""))
                           + f"<br><span class='icc-sub'>Attempt history that triggered "
                             f"the handoff: {scores}</span>"))
        if ss.spoken_rec:
            with st.expander("Spoken version (screen-reader friendly)"):
                st.write(ss.spoken_rec)
                read_aloud(ss.spoken_rec, "rec")

    st.divider()
    H(theme.section("Privacy", "Advocacy — you control the aperture",
                    "Your accessibility profile is private by default; redaction is "
                    "enforced in code before any manager-facing agent runs. When you "
                    "want something from your manager, the Advocate drafts an "
                    "evidence-based note on your behalf. Nothing is sent without "
                    "your approval."))
    share_ctx = st.toggle(
        "Share my accessibility profile with my manager",
        value=False,
        help="Off: the note and the manager rollup are framed purely on workload "
             "and evidence. On: your context is shared briefly, as a support "
             "need, never as a deficit.",
    )
    remedy = st.selectbox(
        "What do you want to ask for?",
        ["two recurring 30-minute protected study blocks per week",
         "two more weeks before the certification target date",
         "a lighter daily study load while keeping the same goal"],
    )
    if st.button("Draft a note to my manager", use_container_width=True):
        evidence = {}
        if ss.history:
            evidence["score_history"] = [h.get("score_pct") for h in ss.history]
            evidence["latest_score_pct"] = ss.history[-1].get("score_pct")
            evidence["attempts"] = len(ss.history)
        if ss.result:
            evidence["weak_areas"] = ss.result.get("weak_areas", [])
        if ss.negotiation:
            evidence["plan_required_minutes"] = \
                ss.negotiation["stats"]["required_minutes_this_week"]
            evidence["calendar_available_minutes"] = \
                ss.negotiation["stats"]["available_minutes_this_week"]
        if not evidence:
            evidence["note"] = "no assessment yet; ask is based on workload alone"
        with st.spinner("Advocate drafting (and leak-checking) your note..."):
            ss.advocacy = draft_advocacy(evidence, remedy, profile, share_ctx)
            ss.advocacy_sent = False
            log("Advocate",
                f"Drafted a manager note asking for: {remedy}. "
                f"Accessibility context {'shared with consent' if share_ctx else 'withheld'}; "
                f"leak check {'flagged and corrected' if ss.advocacy.get('guardrail_notes') else 'clean'}.",
                decision_detail={
                    "signals_considered":
                        [f"shared: {s}" for s in ss.advocacy.get("what_was_shared", [])] +
                        [f"withheld: {w}" for w in ss.advocacy.get("what_was_withheld", [])],
                    "guardrail_notes": ss.advocacy.get("guardrail_notes", []),
                })
    if ss.advocacy:
        H(f'<div class="icc-card">{theme.esc(ss.advocacy.get("note_to_manager", ""))}</div>')
        H(theme.ledger(ss.advocacy.get("what_was_shared", []),
                       ss.advocacy.get("what_was_withheld", [])))
        if not ss.advocacy_sent:
            if st.button("Approve and send", type="primary"):
                ss.advocacy_sent = True
                log("Advocate", "Learner approved the note. Sent to manager "
                                "(demo: marked as sent, nothing leaves the app).")
                st.rerun()
        else:
            H(theme.banner("ok", "send", "Approved and sent",
                           "Demo: nothing actually leaves the app."))

    st.divider()
    H(theme.section("Memory", "Your memory, tracked honestly",
                    "A skill passed three weeks ago is not a skill known today. "
                    "Mastery decays with a half-life that doubles every review (the "
                    "spacing effect) — refreshers land just before you'd forget. The "
                    "grey tick marks where you last peaked."))
    mem_rows = mastery.snapshot(mastery.load_store(), LEARNER_ID, date.today())
    if not mem_rows:
        H(theme.banner("info", "brain", "Nothing tracked yet",
                       "Complete an assessment and your per-skill memory will appear here."))
    due_now = []
    for r in mem_rows:
        if r["due_refresher"]:
            due_now.append(r["skill_area"])
        H(theme.memory_bar(r))
    if due_now:
        H(theme.banner("warn", "repeat", "Due for a refresher",
                       theme.esc(" · ".join(due_now))))
        if st.button("Build a refresher path for the fading skills",
                     use_container_width=True):
            ss.focus_areas = due_now
            log("Memory Tracker",
                f"Decayed mastery below retention on {len(due_now)} previously "
                f"learned skill(s): {due_now}. Requesting a focused refresher path.")
            build_round(cert, role, profile, voice_mode, focus_areas=due_now)
            st.rerun()

    st.divider()
    H(theme.section("Manager", "Team readiness",
                    "Manager Insights reasons over a synthetic team (TEAM-A). Consent "
                    "is enforced in code: profiles of learners who haven't opted in "
                    "are redacted before the model sees the records."))
    if st.button("Run team readiness rollup", use_container_width=True):
        with st.spinner("Manager Insights reasoning over the team..."):
            ss.insights = team_insights(load_team())
            log("Manager Insights",
                f"Rolled up TEAM-A: {ss.insights.get('team_readiness_pct')}% ready.")
    if ss.insights:
        ins = ss.insights
        ready_n = sum(1 for l in ins.get("learners", []) if l.get("status") == "ready")
        H(theme.tiles([
            (f"{ins.get('team_readiness_pct', '?')}%", "team readiness"),
            (f"{ready_n}/{len(ins.get('learners', []))}", "learners ready"),
        ]))
        st.write(ins.get("summary", ""))
        for lr in ins.get("learners", []):
            H(theme.learner_card(lr.get("learner_id", "?"), lr.get("status", "?"),
                                 lr.get("rationale", ""),
                                 lr.get("recommended_action", "")))
        if ins.get("team_actions"):
            H(theme.banner("info", "trend", "Team actions",
                           "<br>".join("• " + theme.esc(a)
                                       for a in ins["team_actions"])))

# ================= RIGHT: the reasoning trace =================
with right:
    H(theme.section("Trace", "Agent reasoning, live",
                    "What each agent did, what it retrieved, and how the "
                    "orchestrator weighed the evidence — across every loop iteration."))
    if ss.history:
        H(theme.attempts_chips(ss.history))
    if not ss.trace:
        H(theme.banner("info", "brain", "Nothing yet",
                       "Build a learning path to watch the agents reason step by step."))
    else:
        H(theme.trace_timeline(ss.trace))
