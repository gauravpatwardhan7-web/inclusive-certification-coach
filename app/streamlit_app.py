"""
Inclusive Certification Coach - learner-facing app.

A clean, accessible study companion: tell it your goal and how you work best,
and it builds a cited learning path, fits study blocks into your real calendar,
checks what you actually understand, and tracks what you're starting to forget.

The app has three tabs:
  - Learn        : the learner's own journey (the default, clean experience).
  - Manager view : a team-readiness rollup for a people manager.
  - How it works : the live agent-reasoning trace and the design story.

Presentation is delegated to app/theme.py. Agent logic is unchanged.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import json as _json
import re as _re
import concurrent.futures as _cf

import streamlit as st
import streamlit.components.v1 as components
from src.agents.curator import curate
from src.agents.study_planner import generate_study_plan
from src.agents.assessor import generate_assessment, score_assessment
from src.agents.manager_insights import team_insights, load_team
from src.agents.calendar_negotiator import negotiate, load_calendar, plan_week
from src.agents.teachback import evaluate_teachback, to_assessment_result
from src.agents.advocate import draft_advocacy
from src.accessibility import to_spoken
from src.orchestrator import decide
from app import theme

st.set_page_config(page_title="Certification Coach", page_icon="🎓",
                   layout="wide", initial_sidebar_state="expanded")
st.markdown(theme.CSS, unsafe_allow_html=True)


def H(html_str: str):
    # Streamlit runs a Markdown pass under unsafe_allow_html, so any line that
    # starts with 4+ spaces / '#' / '>' gets mis-parsed as a code block,
    # heading, or blockquote and corrupts the HTML. Collapsing newlines makes
    # each component one HTML block. <br> tags are preserved.
    st.markdown(_re.sub(r"\s*\n\s*", " ", html_str), unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
# Cached agent wrappers - repeats of the same request are instant.
# (Pure-ish: they hit the model, but for a given input the result is stable
# enough for a study plan, and caching makes the demo feel responsive.)
# --------------------------------------------------------------------------- #
@st.cache_data(show_spinner=False)
def cached_curate(cert: str, role: str, profile: str, focus_key: tuple) -> dict:
    return curate(cert, role, profile, focus_areas=list(focus_key) or None)


# --------------------------------------------------------------------------- #
# Read-aloud: a real player (play / pause-resume / stop, voice + speed).
# --------------------------------------------------------------------------- #
def read_aloud_player(text: str, key: str):
    if not text:
        return
    safe = _json.dumps(text)
    components.html(f"""
    <div style="font-family:'Source Sans 3',system-ui,sans-serif;color:#0F172A;">
      <style>
        .pbtn {{ min-height:40px; padding:7px 14px; margin:0 6px 6px 0; border:1px solid #CBD5E1;
                 border-radius:10px; cursor:pointer; font-weight:600; background:#fff; font-size:.9rem; }}
        .pbtn.primary {{ background:#2563EB; border-color:#2563EB; color:#fff; }}
        .pbtn:hover {{ box-shadow:0 2px 8px rgba(15,23,42,.12); }}
        .prow {{ display:flex; align-items:center; flex-wrap:wrap; gap:6px; }}
        .pctl {{ font-size:.84rem; color:#5B6B82; display:flex; align-items:center; gap:6px; }}
        select, input[type=range] {{ font-size:.84rem; }}
        #status_{key} {{ font-size:.8rem; color:#5B6B82; margin-left:4px; }}
      </style>
      <div class="prow">
        <button class="pbtn primary" id="play_{key}">► Listen</button>
        <button class="pbtn" id="pause_{key}">❚❚ Pause</button>
        <button class="pbtn" id="stop_{key}">■ Stop</button>
        <span id="status_{key}"></span>
      </div>
      <div class="prow" style="margin-top:4px">
        <span class="pctl">Voice <select id="voice_{key}"></select></span>
        <span class="pctl">Speed
          <input type="range" id="rate_{key}" min="0.7" max="1.25" step="0.05" value="0.95">
        </span>
      </div>
      <script>
        const text_{key} = {safe};
        const synth = window.speechSynthesis;
        let utt_{key} = null;
        function fillVoices_{key}() {{
          const sel = document.getElementById('voice_{key}');
          if (!sel) return;
          const vs = synth.getVoices().filter(v => v.lang && v.lang.toLowerCase().startsWith('en'));
          if (!vs.length) return;
          const cur = sel.value;
          sel.innerHTML = '';
          vs.forEach(v => {{
            const o = document.createElement('option');
            o.value = v.name;
            o.text = v.name.replace(/Microsoft|Google/g,'').trim() + ' · ' + v.lang;
            sel.appendChild(o);
          }});
          const pref = vs.find(v => /natural|aria|jenny|libby|sonia|samantha|google us/i.test(v.name))
                    || vs.find(v => v.lang.toLowerCase() === 'en-us') || vs[0];
          sel.value = cur || (pref ? pref.name : vs[0].name);
        }}
        fillVoices_{key}();
        if (typeof synth !== 'undefined') synth.onvoiceschanged = fillVoices_{key};
        document.getElementById('play_{key}').onclick = () => {{
          if (synth.paused && synth.speaking) {{ synth.resume(); return; }}
          synth.cancel();
          utt_{key} = new SpeechSynthesisUtterance(text_{key});
          utt_{key}.rate = parseFloat(document.getElementById('rate_{key}').value);
          const name = document.getElementById('voice_{key}').value;
          const v = synth.getVoices().find(x => x.name === name);
          if (v) utt_{key}.voice = v;
          const s = document.getElementById('status_{key}');
          utt_{key}.onstart = () => s.textContent = 'playing…';
          utt_{key}.onend   = () => s.textContent = '';
          utt_{key}.onresume= () => s.textContent = 'playing…';
          synth.speak(utt_{key});
        }};
        document.getElementById('pause_{key}').onclick = () => {{
          const s = document.getElementById('status_{key}');
          if (synth.speaking && !synth.paused) {{ synth.pause(); s.textContent = 'paused'; }}
          else if (synth.paused) {{ synth.resume(); s.textContent = 'playing…'; }}
        }};
        document.getElementById('stop_{key}').onclick = () => {{
          synth.cancel(); document.getElementById('status_{key}').textContent = '';
        }};
      </script>
    </div>
    """, height=116)


# --------------------------------------------------------------------------- #
# Session state
# --------------------------------------------------------------------------- #
ss = st.session_state
for k, v in {
    "trace": [], "path": None, "study_plan": None, "assessment": None,
    "result": None, "decision": None, "insights": None, "spoken_path": "",
    "spoken_rec": "", "history": [], "focus_areas": None, "negotiation": None,
    "tb_eval": None, "tb_final": None, "advocacy": None, "advocacy_sent": False,
}.items():
    ss.setdefault(k, v)

LEARNER_ID = "demo-learner"


def log(agent, did, retrieved=None, decision_detail=None):
    step = {"agent": agent, "did": did}
    if retrieved:
        step["retrieved"] = retrieved
    if decision_detail:
        step["decision_detail"] = decision_detail
    ss.trace.append(step)


def build_round(cert, role, profile, voice_mode, focus_areas):
    """Curate the path, then schedule + write the assessment IN PARALLEL."""
    tag = f" (remediation: {', '.join(focus_areas)})" if focus_areas else ""
    fkey = tuple(focus_areas or [])
    with st.spinner("Building your learning path…"):
        ss.path = cached_curate(cert, role, profile, fkey)
        mods = ss.path.get("modules", [])
        log("Learning Path Curator",
            f"Built a {ss.path.get('total_hours', 0)}h path ({len(mods)} modules), each cited{tag}.",
            retrieved=ss.path.get("_retrieval"))
    if not mods:
        ss.study_plan = None
        ss.assessment = None
        return
    # Study plan and assessment are independent given the path -> run together.
    with st.spinner("Scheduling your week and writing your readiness check…"):
        with _cf.ThreadPoolExecutor(max_workers=2) as ex:
            f_plan = ex.submit(generate_study_plan, ss.path, profile,
                               remediation=focus_areas is not None)
            f_quiz = ex.submit(generate_assessment, cert, role, 3, focus_areas)
            ss.study_plan = f_plan.result()
            ss.assessment = f_quiz.result()
    log("Study Plan Generator",
        f"Scheduled {len(ss.study_plan.get('sessions', []))} sessions over "
        f"{ss.study_plan.get('total_days', '?')} days ({ss.study_plan.get('block_minutes', '?')}-min blocks).",
        retrieved=ss.study_plan.get("_retrieval"))
    log("Assessment Agent",
        f"Wrote {len(ss.assessment.get('questions', []))} grounded, cited questions{tag}.",
        retrieved=ss.assessment.get("_retrieval"))
    ss.spoken_path = ""
    if voice_mode:
        with st.spinner("Preparing the spoken version…"):
            ss.spoken_path = to_spoken("learning_path", ss.path, profile)
            log("Accessibility Narrator", "Rendered the path as a spoken script.")
    ss.result = ss.decision = None
    ss.spoken_rec = ""
    ss.negotiation = ss.tb_eval = ss.tb_final = None


def finish_attempt(result, attempt_no, profile, voice_mode):
    ss.result = result
    ss.history = ss.history + [{"attempt": attempt_no, "score_pct": result.get("score_pct")}]
    ss.decision = decide(result, ss.history, profile)
    log("Orchestrator (reasoning)",
        f"Decision after attempt {attempt_no}: {ss.decision['action'].upper()} — {ss.decision.get('reason', '')}",
        decision_detail=ss.decision)
    if voice_mode:
        ss.spoken_rec = to_spoken("recommendation", ss.decision, profile)
        log("Accessibility Narrator", "Rendered the recommendation as a spoken script.")


# --------------------------------------------------------------------------- #
# Sidebar — the learner's profile and the single primary action.
# --------------------------------------------------------------------------- #
with st.sidebar:
    H('<div class="icc-brand">' + theme.icon("book", 20, "var(--primary)")
      + ' Certification Coach</div>'
      '<div class="icc-brand-sub">Learning that adapts to how you work.</div>')
    st.markdown("**Your goal**")
    cert = st.selectbox("Certification", ["AZ-204", "AZ-900"],
                        help="Pick the certification you're working toward.")
    role = st.text_input("Your role", "Cloud Engineer")
    profile = st.text_area(
        "How you work best (optional)",
        "Has ADHD; struggles to focus in long study sessions.",
        help="We use this to adapt pacing, study-block length, and formats. "
             "It stays private unless you choose to share it.",
    )
    voice_mode = st.toggle("Listen mode (read results aloud)", value=False,
                           help="Adds a spoken version with play/pause for each result.")
    go = st.button("Build my plan", type="primary", use_container_width=True)
    st.caption("All data is synthetic. You're interacting with AI.")

if go:
    ss.trace = []
    ss.history = []
    ss.focus_areas = None
    build_round(cert, role, profile, voice_mode, focus_areas=None)

learn_tab, manager_tab, how_tab = st.tabs(["Learn", "Manager view", "How it works"])

# =========================== LEARN TAB ============================ #
with learn_tab:
    if not ss.path:
        H(theme.banner("info", "book", "Let's get you certified",
                       "Set your goal in the sidebar and choose <b>Build my plan</b>. "
                       "Your coach will map a cited learning path, fit it into your week, "
                       "and check what you actually understand — adapting to how you work."))
    if ss.path and ss.path.get("modules"):
        H(theme.section("1", "Your learning path",
                        ("Focused refresher on: " + ", ".join(ss.focus_areas))
                        if ss.focus_areas else
                        "Built for your goal and grounded in the certification guide."))
        for m in ss.path["modules"]:
            H(theme.module_card(m.get("skill_area", "?"), m.get("recommended_hours", "?"),
                                m.get("accommodation_note", "—"), m.get("source_id", "—")))
        if ss.spoken_path:
            H('<div class="icc-card icc-soft"><div class="icc-agent" style="margin-bottom:6px">'
              + theme.icon("mic", 14, "var(--violet)") + ' Listen to your path</div></div>')
            read_aloud_player(ss.spoken_path, "path")
    elif ss.path and not ss.path.get("modules"):
        H(theme.banner("warn", "alert", "We couldn't build a path for that",
                       theme.esc(ss.path.get("note") or
                                 "The guide doesn't cover this certification yet.")))

    if ss.study_plan:
        sp = ss.study_plan
        H(theme.section("2", "Your study schedule"))
        H(theme.tiles([
            (str(sp.get("total_days", "?")), "days"),
            (f"≤ {sp.get('daily_max_minutes', '?')}", "min / day"),
            (str(sp.get("block_minutes", "?")), "min blocks"),
            (str(len(sp.get("sessions", []))), "sessions"),
        ]))
        for s in sp.get("sessions", [])[:6]:
            H(theme.session_row(s.get("day", "?"), s.get("skill_area", "?"),
                                s.get("minutes", "?"), s.get("blocks", ""),
                                s.get("accommodation_note", "")))
        if len(sp.get("sessions", [])) > 6:
            st.caption(f"…and {len(sp['sessions']) - 6} more sessions.")

        H(theme.section("3", "Fit it into your real week",
                        "A plan that ignores your meetings is a plan you won't follow."))
        week_choice = st.radio("This week's calendar",
                               ["A lighter week", "A packed week"],
                               horizontal=True, label_visibility="collapsed")
        if st.button("Find my study time", use_container_width=True):
            cal_file = ("calendar_light_week.json" if week_choice.startswith("A lighter")
                        else "calendar_packed_week.json")
            with st.spinner("Finding real gaps between your meetings…"):
                ss.negotiation = negotiate(sp, load_calendar(cal_file), profile)
                ss.negotiation["_calendar_file"] = cal_file
                neg, stats = ss.negotiation, ss.negotiation["stats"]
                log("Calendar Negotiator",
                    f"Needs {stats['required_minutes_this_week']} min; calendar has "
                    f"{stats['available_minutes_this_week']} usable. Booked {stats['scheduled_minutes']} min "
                    f"-> {'feasible' if neg['feasible'] else 'pushed back with options'}.",
                    decision_detail={"signals_considered": neg["policy"].get("rationale", []),
                                     "guardrail_notes": neg.get("guardrail_notes", [])})
        if ss.negotiation:
            neg = ss.negotiation
            pol = neg["policy"]
            cal = load_calendar(neg.get("_calendar_file", "calendar_light_week.json"))
            st.caption("Your coach suggested a starting fit — adjust it to taste; "
                       "it re-books instantly.")
            c1, c2, c3 = st.columns(3)
            cap = c1.slider("Max study / day (min)", 25, 120,
                            value=int(pol.get("max_daily_minutes", 50)), step=5)
            block = c2.slider("Block length (min)", 15, 60,
                              value=int(pol.get("block_minutes", 25)), step=5)
            prefer_label = c3.radio("Preferred time",
                                    ["Any time", "Mornings", "Afternoons"], index=0)
            prefer = {"Any time": "any", "Mornings": "mornings",
                      "Afternoons": "afternoons"}[prefer_label]
            # Pure-code re-plan on every change — no model call, instant.
            live = plan_week(ss.study_plan, cal, block,
                             int(pol.get("break_minutes", 5)), cap, prefer)
            stats = live["stats"]
            H(theme.tiles([
                (f"{stats['required_minutes_this_week']}", "min needed"),
                (f"{stats['available_minutes_this_week']}", "free in your week"),
                (f"{stats['scheduled_minutes']}", "min booked"),
                (f"{len(live['scheduled_blocks'])}", "study blocks"),
            ]))
            if live["feasible"]:
                H(theme.banner("ok", "check", "It all fits",
                               f"Booked every one of the {stats['required_minutes_this_week']} "
                               f"minutes you need this week."))
            else:
                short = stats["unplaced_minutes"]
                H(theme.banner("warn", "alert", "Not everything fits this week",
                               f"{short} min couldn't be placed — about "
                               f"{stats['est_weeks_to_complete_plan']} weeks at this pace. "
                               f"Try a higher daily cap, shorter blocks, or a different "
                               f"time of day above."))
            if live["scheduled_blocks"]:
                H(theme.week_grid(cal, live["scheduled_blocks"]))
            # The agent's manager note only makes sense when the calendar itself
            # is overloaded (the initial run found it infeasible). If YOUR control
            # tweaks caused the shortfall, the guidance banner above is the fix.
            if not live["feasible"] and str(neg["negotiation"].get("message_to_manager", "")).strip():
                H(f'<div class="icc-card">{theme.esc(neg["negotiation"]["message_to_manager"])}</div>')
                if neg["negotiation"].get("options"):
                    H(theme.banner("info", "repeat", "Or ask your manager",
                                   "<br>".join("• " + theme.esc(o) for o in neg["negotiation"]["options"])))

    # ---- readiness check: only while there's no standing decision ----
    if ss.path and ss.path.get("modules") and not ss.decision:
        attempt_no = len(ss.history) + 1
        H(theme.section("4", f"Check your readiness — attempt {attempt_no}",
                        "Show what you know, the way that suits you."))
        mode = st.radio("How would you like to be checked?",
                        ["Quick questions", "Explain it in your own words"],
                        horizontal=True)

        if mode.startswith("Quick") and ss.assessment and ss.assessment.get("questions"):
            answers = {}
            for q in ss.assessment["questions"]:
                answers[q["id"]] = st.radio(q.get("question", q["id"]), q.get("options", []),
                                            key=f"{q['id']}-a{attempt_no}", index=None)
            if st.button("Submit answers", type="primary"):
                picked = {}
                for q in ss.assessment["questions"]:
                    sel = answers[q["id"]]
                    picked[q["id"]] = sel.split(")")[0].strip() if sel else "X"
                with st.spinner("Scoring and thinking about your next step…"):
                    result = score_assessment(ss.assessment["questions"], picked)
                    log("Assessment Agent",
                        f"Scored attempt {attempt_no}: {result.get('score_pct')}% "
                        f"(ready={result.get('ready')}); weak: {result.get('weak_areas') or 'none'}.")
                    finish_attempt(result, attempt_no, profile, voice_mode)
                st.rerun()

        elif mode.startswith("Explain"):
            skills = [m.get("skill_area", "?") for m in ss.path["modules"]]
            tb_skill = st.selectbox("Pick a topic to explain", skills)
            tb_text = st.text_area("Explain it like you're telling a colleague",
                                   key=f"tb-{attempt_no}", height=140,
                                   placeholder="What is it, why does it matter, how would you use it?")
            if st.button("Check my explanation", type="primary") and tb_text.strip():
                with st.spinner("Reading your explanation…"):
                    ss.tb_eval = evaluate_teachback(cert, tb_skill, tb_text, profile)
                    ss.tb_final = None
                    ev = ss.tb_eval
                    log("Teach-back Assessor",
                        f"Graded '{tb_skill}': {ev.get('understanding_pct')}% understanding; "
                        f"missing: {ev.get('concepts_missing') or 'nothing'}.",
                        retrieved=ev.get("_retrieval"))
                st.rerun()

            if ss.tb_eval and not ss.tb_final:
                ev = ss.tb_eval
                st.write(ev.get("feedback", ""))
                H(theme.concept_ledger(ev.get("concepts_covered", []), ev.get("concepts_missing", [])))
                if ev.get("misconception"):
                    H(theme.banner("warn", "alert", "One thing to double-check",
                                   theme.esc(ev["misconception"])))
                H(theme.banner("info", "brain", "Quick follow-up",
                               theme.esc(ev.get("follow_up_question", ""))))
                tb_answer = st.text_area("Your answer", key=f"tbf-{attempt_no}", height=90)
                if st.button("Submit", type="primary") and tb_answer.strip():
                    with st.spinner("Finalising your result…"):
                        ss.tb_final = evaluate_teachback(cert, tb_skill, tb_text, profile,
                                                         follow_up_question=ev.get("follow_up_question", ""),
                                                         follow_up_answer=tb_answer)
                        fin = ss.tb_final
                        log("Teach-back Assessor",
                            f"Final grade: {fin.get('understanding_pct')}% on '{tb_skill}'.")
                        finish_attempt(to_assessment_result(fin), attempt_no, profile, voice_mode)
                    st.rerun()

    # ---- recommendation ----
    if ss.decision:
        H(theme.section("5", "Your coach's recommendation"))
        H(theme.attempts_chips(ss.history))
        action = ss.decision.get("action")
        if action == "advance":
            H(theme.banner("ok", "check", "You're ready",
                           theme.esc(ss.decision.get("message_to_learner", ""))))
        elif action == "loop":
            focus = ss.decision.get("focus_next", [])
            body = theme.esc(ss.decision.get("message_to_learner", ""))
            if focus:
                body += "<br><strong>Focus next on:</strong> " + theme.esc(", ".join(focus))
            H(theme.banner("warn", "repeat", "Keep going", body))
            if st.button(f"Start a focused refresher (attempt {len(ss.history) + 1})",
                         type="primary", use_container_width=True):
                ss.focus_areas = ss.decision.get("focus_next") or None
                build_round(cert, role, profile, voice_mode, focus_areas=ss.focus_areas)
                st.rerun()
        else:
            scores = " → ".join(f"{h.get('score_pct')}%" for h in ss.history)
            H(theme.banner("bad", "user", "Let's bring in a human coach",
                           theme.esc(ss.decision.get("message_to_learner", ""))
                           + f"<br><span class='icc-sub'>Attempts: {scores}</span>"))
        if ss.spoken_rec:
            read_aloud_player(ss.spoken_rec, "rec")

    # ---- ask for support (learner-facing advocacy) ----
    if ss.path:
        st.divider()
        H(theme.section("Support", "Need an adjustment?",
                        "Your coach can draft a note to your manager on your behalf. "
                        "Your personal context stays private unless you choose to share it."))
        share_ctx = st.toggle("Share how I work best with my manager", value=False)
        remedy = st.selectbox("What would help?",
                              ["two protected 30-minute study blocks a week",
                               "two more weeks before the target date",
                               "a lighter daily study load, same goal"])
        if st.button("Draft a note for me", use_container_width=True):
            evidence = {}
            if ss.history:
                evidence["score_history"] = [h.get("score_pct") for h in ss.history]
                evidence["attempts"] = len(ss.history)
            if ss.negotiation:
                evidence["plan_required_minutes"] = ss.negotiation["stats"]["required_minutes_this_week"]
                evidence["calendar_available_minutes"] = ss.negotiation["stats"]["available_minutes_this_week"]
            evidence = evidence or {"note": "request based on workload"}
            with st.spinner("Drafting your note…"):
                ss.advocacy = draft_advocacy(evidence, remedy, profile, share_ctx)
                ss.advocacy_sent = False
                log("Advocate",
                    f"Drafted a note asking for: {remedy}. Context "
                    f"{'shared' if share_ctx else 'kept private'}.",
                    decision_detail={"signals_considered":
                        [f"shared: {s}" for s in ss.advocacy.get("what_was_shared", [])]
                        + [f"withheld: {w}" for w in ss.advocacy.get("what_was_withheld", [])],
                        "guardrail_notes": ss.advocacy.get("guardrail_notes", [])})
        if ss.advocacy:
            H(f'<div class="icc-card">{theme.esc(ss.advocacy.get("note_to_manager", ""))}</div>')
            H(theme.ledger(ss.advocacy.get("what_was_shared", []),
                           ss.advocacy.get("what_was_withheld", [])))
            if not ss.advocacy_sent:
                if st.button("Approve & send", type="primary"):
                    ss.advocacy_sent = True
                    st.rerun()
            else:
                H(theme.banner("ok", "send", "Sent", "Demo: nothing actually leaves the app."))

# =========================== MANAGER TAB ============================ #
with manager_tab:
    H(theme.section("Team", "Team readiness",
                    "A supportive rollup for a people manager. Learners' personal "
                    "context is redacted in code unless they've chosen to share it."))
    if st.button("Run team rollup", type="primary"):
        with st.spinner("Reviewing the team…"):
            ss.insights = team_insights(load_team())
            log("Manager Insights", f"Rolled up TEAM-A: {ss.insights.get('team_readiness_pct')}% ready.")
    if ss.insights:
        ins = ss.insights
        ready_n = sum(1 for l in ins.get("learners", []) if l.get("status") == "ready")
        H(theme.tiles([(f"{ins.get('team_readiness_pct', '?')}%", "team readiness"),
                       (f"{ready_n}/{len(ins.get('learners', []))}", "ready")]))
        st.write(ins.get("summary", ""))
        for lr in ins.get("learners", []):
            H(theme.learner_card(lr.get("learner_id", "?"), lr.get("status", "?"),
                                 lr.get("rationale", ""), lr.get("recommended_action", "")))
        if ins.get("team_actions"):
            H(theme.banner("info", "trend", "Suggested team actions",
                           "<br>".join("• " + theme.esc(a) for a in ins["team_actions"])))
    else:
        H('<p class="icc-help">Run the rollup to see each learner\'s status, the team\'s '
          'readiness, and recommended actions.</p>')

# =========================== HOW IT WORKS TAB ============================ #
with how_tab:
    H(theme.section("Inside", "How the coach reasons",
                    "This product is a team of cooperating agents. Everything they do is "
                    "logged here — what each retrieved, what it cited, and how the "
                    "orchestrator weighed the evidence across every loop."))
    H('<div style="margin:2px 0 10px">'
      + "".join(f'<span class="icc-chip" style="background:var(--primary-soft);'
                f'border-color:#C7D8FE;color:var(--primary-deep)">{theme.icon(i,13)} {theme.esc(t)}</span>'
                for i, t in [("brain", "8 reasoning agents"),
                             ("book", "Grounded & cited (Foundry IQ)"),
                             ("shield", "Consent enforced in code"),
                             ("check", "72/72 eval checks")]) + '</div>')
    if ss.history:
        H(theme.attempts_chips(ss.history))
    if not ss.trace:
        H(theme.banner("info", "brain", "Nothing yet",
                       "Build a plan in the Learn tab to watch the agents reason step by step."))
    else:
        H(theme.trace_timeline(ss.trace))
