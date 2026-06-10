"""
Evaluation harness for the Inclusive Certification Coach.

Two suites, each scored against a gold set in evals/gold/:

  decisions     - Orchestrator reasoning: for each gold case, assert the
                  decision (advance | loop | escalate) and the focus_next
                  shape. Needs the reasoning model only (no retrieval),
                  so it runs even after the Azure AI Search resource is torn
                  down. This is the core "Reasoning" eval.

  groundedness  - Citation fidelity: the Curator and Assessment agents must
                  only emit skill areas and study-hour figures that exist in
                  the knowledge base, and every grounded item must carry a
                  non-empty source_id. Needs the full pipeline incl. Foundry
                  IQ retrieval (Azure AI Search).

Usage:
  python -m evals.run_evals                  # run all suites
  python -m evals.run_evals --suite decisions
  python -m evals.run_evals --suite groundedness

Results (pass/fail per case + aggregate metrics) are written to
evals/results/latest.json.
"""

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
GOLD_DIR = EVAL_DIR / "gold"
RESULTS_DIR = EVAL_DIR / "results"


def _load(name: str) -> dict:
    return json.loads((GOLD_DIR / name).read_text())


# --------------------------------------------------------------------------- #
# Suite 1: orchestrator decisions
# --------------------------------------------------------------------------- #
def _run_decision_case(decide, c: dict) -> tuple[bool, list, dict]:
    """One execution of one gold case. Returns (ok, checks, detail)."""
    checks = []
    try:
        out = decide(c["assessment_result"], c["history"], c["accessibility_profile"])
        action = out.get("action")
        focus = out.get("focus_next", [])
        exp = c["expect"]

        checks.append(("action", action == exp["action"],
                       f"expected {exp['action']}, got {action}"))
        if exp.get("focus_next_empty"):
            checks.append(("focus_next_empty", len(focus) == 0,
                           f"expected empty focus_next, got {focus}"))
        if exp.get("focus_next_nonempty"):
            checks.append(("focus_next_nonempty", len(focus) > 0,
                           "expected non-empty focus_next, got []"))
        ok = all(p for _, p, _ in checks)
        detail = {"action": action, "reason": out.get("reason", "")}
    except Exception as e:  # noqa: BLE001 - eval should never crash the suite
        ok = False
        checks.append(("ran", False, f"raised {type(e).__name__}: {e}"))
        detail = {}
    return ok, checks, detail


def run_decisions(repeat: int = 1) -> dict:
    """
    Orchestrator decision accuracy. With repeat > 1, every gold case runs
    repeat times and only passes if ALL runs pass - LLM decisions are
    stochastic, so the pass RATE is the honest reliability metric.
    """
    from src.orchestrator import decide

    gold = _load("orchestrator_decisions.json")
    cases = []
    passed = 0

    for c in gold["cases"]:
        runs_ok = 0
        checks, detail = [], {}
        for _ in range(repeat):
            ok, checks, detail = _run_decision_case(decide, c)
            runs_ok += ok
        case_pass = runs_ok == repeat

        passed += case_pass
        entry = {
            "id": c["id"], "pass": case_pass,
            "checks": [{"name": n, "pass": p, "note": note} for n, p, note in checks],
            "got": detail,
        }
        if repeat > 1:
            entry["pass_rate"] = f"{runs_ok}/{repeat}"
        cases.append(entry)

    return {
        "suite": "decisions",
        "metric": "decision_accuracy",
        "repeat": repeat,
        "passed": passed, "total": len(gold["cases"]),
        "score_pct": round(100 * passed / len(gold["cases"])),
        "cases": cases,
    }


# --------------------------------------------------------------------------- #
# Suite 2: groundedness / citation fidelity
# --------------------------------------------------------------------------- #
def _norm(s: str) -> str:
    return "".join(ch.lower() for ch in s if ch.isalnum() or ch == " ").strip()


def _skill_grounded(emitted: str, kb_skills: list[dict]) -> bool:
    """A skill is grounded if it shares a meaningful key phrase with a KB skill."""
    e = _norm(emitted)
    for k in kb_skills:
        n = _norm(k["name"])
        # match on the leading content word group, e.g. "develop for azure storage"
        head = " ".join(n.split()[:3])
        if head and head in e or e in n or n in e:
            return True
    return False


def run_groundedness() -> dict:
    from src.agents.curator import curate
    from src.agents.assessor import generate_assessment
    from src.agents.study_planner import generate_study_plan

    facts = _load("kb_facts.json")
    valid_hours = set(facts["valid_recommended_hours"])
    cert, role = facts["certification"], facts["role"]
    checks = []

    # --- Curator: every module's hours + skill must be grounded; source_id present
    try:
        path = curate(cert, role, "Has ADHD; struggles to focus in long sessions.")
        mods = path.get("modules", [])
        bad_hours = [m for m in mods if m.get("recommended_hours") not in valid_hours]
        bad_skill = [m for m in mods if not _skill_grounded(m.get("skill_area", ""), facts["skill_areas"])]
        no_cite = [m for m in mods if not str(m.get("source_id", "")).strip()
                   or m.get("source_id") == "unknown-source"]
        checks.append(("curator_has_modules", len(mods) > 0, f"{len(mods)} modules"))
        checks.append(("curator_hours_grounded", not bad_hours,
                       f"{len(bad_hours)} modules with hallucinated hours"))
        checks.append(("curator_skills_grounded", not bad_skill,
                       f"{len(bad_skill)} modules with ungrounded skill areas"))
        checks.append(("curator_all_cited", not no_cite,
                       f"{len(no_cite)} modules missing a source_id"))
    except Exception as e:  # noqa: BLE001
        checks.append(("curator_ran", False, f"raised {type(e).__name__}: {e}"))

    # --- Study Plan Generator: sessions stay grounded, cited, within daily load
    try:
        sp_profile = "Has ADHD; struggles to focus in long study sessions."
        plan = generate_study_plan(path, sp_profile)
        sess = plan.get("sessions", [])
        s_bad_skill = [s for s in sess if not _skill_grounded(s.get("skill_area", ""), facts["skill_areas"])]
        s_no_cite = [s for s in sess if not str(s.get("source_id", "")).strip()
                     or s.get("source_id") == "unknown-source"]
        daily_max = plan.get("daily_max_minutes", 0)
        by_day: dict = {}
        for s in sess:
            by_day[s.get("day")] = by_day.get(s.get("day"), 0) + int(s.get("minutes", 0))
        over_load = [d for d, m in by_day.items() if daily_max and m > daily_max]
        checks.append(("planner_has_sessions", len(sess) > 0, f"{len(sess)} sessions"))
        checks.append(("planner_skills_grounded", not s_bad_skill,
                       f"{len(s_bad_skill)} sessions with ungrounded skill areas"))
        checks.append(("planner_all_cited", not s_no_cite,
                       f"{len(s_no_cite)} sessions missing a source_id"))
        checks.append(("planner_respects_daily_load", not over_load,
                       f"{len(over_load)} days exceed the stated daily max"))
    except Exception as e:  # noqa: BLE001
        checks.append(("planner_ran", False, f"raised {type(e).__name__}: {e}"))

    # --- Assessor: every question must carry a source_id and a known skill area
    try:
        a = generate_assessment(cert, role, num_questions=3)
        qs = a.get("questions", [])
        q_no_cite = [q for q in qs if not str(q.get("source_id", "")).strip()
                     or q.get("source_id") == "unknown-source"]
        q_bad_skill = [q for q in qs if not _skill_grounded(q.get("skill_area", ""), facts["skill_areas"])]
        checks.append(("assessor_has_questions", len(qs) > 0, f"{len(qs)} questions"))
        checks.append(("assessor_all_cited", not q_no_cite,
                       f"{len(q_no_cite)} questions missing a source_id"))
        checks.append(("assessor_skills_grounded", not q_bad_skill,
                       f"{len(q_bad_skill)} questions with ungrounded skill areas"))
    except Exception as e:  # noqa: BLE001
        checks.append(("assessor_ran", False, f"raised {type(e).__name__}: {e}"))

    # --- Negative test: a certification absent from the KB must be REFUSED,
    # not hallucinated. This is the strongest groundedness check there is.
    try:
        ghost = curate("DP-900", "Data Analyst")
        ghost_mods = ghost.get("modules", [])
        checks.append(("curator_refuses_unknown_cert", not ghost_mods,
                       f"expected empty modules for a cert not in the KB, "
                       f"got {len(ghost_mods)} modules"))
        checks.append(("curator_explains_refusal",
                       bool(str(ghost.get("note", "")).strip()),
                       "expected a non-empty 'note' explaining the refusal"))
    except Exception as e:  # noqa: BLE001
        checks.append(("negative_case_ran", False, f"raised {type(e).__name__}: {e}"))

    passed = sum(1 for _, p, _ in checks if p)
    return {
        "suite": "groundedness",
        "metric": "citation_fidelity",
        "passed": passed, "total": len(checks),
        "score_pct": round(100 * passed / len(checks)) if checks else 0,
        "cases": [{"name": n, "pass": p, "note": note} for n, p, note in checks],
    }


# --------------------------------------------------------------------------- #
# Suite 3: manager insights (team readiness)
# --------------------------------------------------------------------------- #
def run_manager() -> dict:
    from src.agents.manager_insights import team_insights, load_team

    team = load_team()
    threshold = team["readiness_threshold_pct"]
    records = {l["learner_id"]: l for l in team["learners"]}
    valid_status = {"ready", "on_track", "at_risk", "needs_support"}
    # Ground truth: a learner is "ready" iff their latest score meets the threshold.
    truly_ready = {lid for lid, r in records.items() if r["latest_score_pct"] >= threshold}
    expected_pct = round(100 * len(truly_ready) / len(records))
    checks = []

    try:
        out = team_insights(team)
        learners = {l["learner_id"]: l for l in out.get("learners", [])}

        checks.append(("all_learners_covered", set(learners) == set(records),
                       f"covered {sorted(learners)} vs {sorted(records)}"))
        bad_status = [lid for lid, l in learners.items() if l.get("status") not in valid_status]
        checks.append(("valid_statuses", not bad_status, f"invalid: {bad_status}"))
        # The agent must mark exactly the at/above-threshold learners as "ready".
        agent_ready = {lid for lid, l in learners.items() if l.get("status") == "ready"}
        checks.append(("ready_set_correct", agent_ready == truly_ready,
                       f"expected ready={sorted(truly_ready)}, got {sorted(agent_ready)}"))
        checks.append(("team_pct_correct", out.get("team_readiness_pct") == expected_pct,
                       f"expected {expected_pct}%, got {out.get('team_readiness_pct')}"))
        # The 3+ stalled-attempt learner must be flagged for human support.
        l3 = learners.get("L-1003", {})
        checks.append(("stalled_learner_supported", l3.get("status") == "needs_support",
                       f"L-1003 status={l3.get('status')}"))
    except Exception as e:  # noqa: BLE001
        checks.append(("ran", False, f"raised {type(e).__name__}: {e}"))

    passed = sum(1 for _, p, _ in checks if p)
    return {
        "suite": "manager",
        "metric": "team_rollup_accuracy",
        "passed": passed, "total": len(checks),
        "score_pct": round(100 * passed / len(checks)) if checks else 0,
        "cases": [{"name": n, "pass": p, "note": note} for n, p, note in checks],
    }


# --------------------------------------------------------------------------- #
# Suite 4: accessibility narrator (spoken output is screen-reader friendly)
# --------------------------------------------------------------------------- #
_SAMPLE_PATH = {
    "certification": "AZ-204", "role": "Cloud Engineer",
    "modules": [
        {"skill_area": "Develop for Azure storage (Blob, Cosmos DB)",
         "recommended_hours": 5, "accommodation_note": "Plain-language summary first.",
         "source_id": "KB-AZ204-001"},
        {"skill_area": "Implement Azure security (auth, Key Vault)",
         "recommended_hours": 5, "accommodation_note": "Short blocks with breaks.",
         "source_id": "KB-AZ204-001"},
    ],
    "total_hours": 10, "note": "",
}


def run_accessibility() -> dict:
    from src.accessibility import to_spoken

    checks = []
    try:
        spoken = to_spoken("learning_path", _SAMPLE_PATH, "Low vision; uses a screen reader.")
        # Screen-reader-friendly = no markup the synthesizer would read out as junk.
        markup = [ch for ch in "|#*`_" if ch in spoken]
        checks.append(("non_empty", len(spoken) > 40, f"{len(spoken)} chars"))
        checks.append(("no_markdown", not markup, f"found markup chars: {markup}"))
        checks.append(("no_percent_symbol", "%" not in spoken, "raw '%' present"))
        checks.append(("no_link_syntax", "](" not in spoken, "markdown link syntax present"))
        # The cert code should be spoken, not printed as "AZ-204".
        checks.append(("abbreviation_spelled_out", "AZ-204" not in spoken,
                       "literal 'AZ-204' should be spelled out for speech"))
    except Exception as e:  # noqa: BLE001
        checks.append(("ran", False, f"raised {type(e).__name__}: {e}"))

    passed = sum(1 for _, p, _ in checks if p)
    return {
        "suite": "accessibility",
        "metric": "spoken_output_quality",
        "passed": passed, "total": len(checks),
        "score_pct": round(100 * passed / len(checks)) if checks else 0,
        "cases": [{"name": n, "pass": p, "note": note} for n, p, note in checks],
    }


# --------------------------------------------------------------------------- #
# Suite 5: calendar negotiation (blocks fit real gaps; infeasible weeks push back)
# --------------------------------------------------------------------------- #
def _hhmm_overlaps(a_start, a_end, b_start, b_end) -> bool:
    """Zero-padded HH:MM strings compare correctly lexicographically."""
    return a_start < b_end and b_start < a_end


def run_calendar() -> dict:
    from src.agents.calendar_negotiator import negotiate, load_calendar

    fixture = _load("calendar_fixture.json")
    plan, profile = fixture["study_plan"], fixture["accessibility_profile"]
    checks = []

    # --- Light week: everything must fit, and fit CORRECTLY.
    try:
        cal = load_calendar("calendar_light_week.json")
        events = {d["date"]: d["events"] for d in cal["days"]}
        wh = cal["work_hours"]
        out = negotiate(plan, cal, profile)
        blocks = out["scheduled_blocks"]

        overlaps = [b for b in blocks for ev in events.get(b["date"], [])
                    if _hhmm_overlaps(b["start"], b["end"], ev["start"], ev["end"])]
        outside = [b for b in blocks
                   if b["start"] < wh["start"] or b["end"] > wh["end"]]
        per_day: dict = {}
        for b in blocks:
            per_day[b["date"]] = per_day.get(b["date"], 0) + b["minutes"]
        cap = out["policy"]["max_daily_minutes"]
        over_cap = [d for d, m in per_day.items() if m > cap]
        no_cite = [b for b in blocks if not str(b.get("source_id", "")).strip()]

        checks.append(("light_feasible", out["feasible"],
                       f"feasible={out['feasible']}, unplaced={out['unplaced']}"))
        checks.append(("light_all_minutes_booked",
                       out["stats"]["scheduled_minutes"] == out["stats"]["required_minutes_this_week"],
                       f"booked {out['stats']['scheduled_minutes']} of "
                       f"{out['stats']['required_minutes_this_week']}"))
        checks.append(("light_no_meeting_overlap", not overlaps,
                       f"{len(overlaps)} blocks overlap meetings"))
        checks.append(("light_within_work_hours", not outside,
                       f"{len(outside)} blocks outside work hours"))
        checks.append(("light_daily_cap_respected", not over_cap,
                       f"days over the {cap}-min policy cap: {over_cap}"))
        checks.append(("light_blocks_cited", not no_cite,
                       f"{len(no_cite)} blocks missing a source_id"))
    except Exception as e:  # noqa: BLE001
        checks.append(("light_ran", False, f"raised {type(e).__name__}: {e}"))

    # --- Packed week: the agent must NOT pretend - it must push back.
    try:
        out = negotiate(plan, load_calendar("calendar_packed_week.json"), profile)
        stats, neg = out["stats"], out["negotiation"]
        checks.append(("packed_infeasible", not out["feasible"],
                       f"feasible={out['feasible']}"))
        checks.append(("packed_shortfall_detected",
                       stats["available_minutes_this_week"] < stats["required_minutes_this_week"],
                       f"available={stats['available_minutes_this_week']}, "
                       f"required={stats['required_minutes_this_week']}"))
        checks.append(("packed_manager_message", bool(str(neg.get("message_to_manager", "")).strip()),
                       "expected a non-empty evidence-based message to the manager"))
        checks.append(("packed_offers_options", len(neg.get("options", [])) >= 2,
                       f"{len(neg.get('options', []))} trade-off options offered"))
    except Exception as e:  # noqa: BLE001
        checks.append(("packed_ran", False, f"raised {type(e).__name__}: {e}"))

    passed = sum(1 for _, p, _ in checks if p)
    return {
        "suite": "calendar",
        "metric": "negotiation_correctness",
        "passed": passed, "total": len(checks),
        "score_pct": round(100 * passed / len(checks)) if checks else 0,
        "cases": [{"name": n, "pass": p, "note": note} for n, p, note in checks],
    }


# --------------------------------------------------------------------------- #
# Suite 6: teach-back grading (understanding, gaps, misconceptions, probing)
# --------------------------------------------------------------------------- #
def run_teachback() -> dict:
    from src.agents.teachback import evaluate_teachback

    gold = _load("teachback_cases.json")
    cert, skill = gold["certification"], gold["skill_area"]
    checks = []
    scores: dict[str, int] = {}

    for c in gold["cases"]:
        cid, exp = c["id"], c["expect"]
        try:
            ev = evaluate_teachback(cert, skill, c["explanation"])
            pct = int(ev.get("understanding_pct", -1))
            scores[cid] = pct
            if "min_understanding_pct" in exp:
                checks.append((f"{cid}_understanding", pct >= exp["min_understanding_pct"],
                               f"expected >= {exp['min_understanding_pct']}, got {pct}"))
            if "max_understanding_pct" in exp:
                checks.append((f"{cid}_low_score", pct <= exp["max_understanding_pct"],
                               f"expected <= {exp['max_understanding_pct']}, got {pct}"))
            if exp.get("no_misconception"):
                checks.append((f"{cid}_no_misconception",
                               not str(ev.get("misconception", "")).strip(),
                               f"unexpected misconception: {ev.get('misconception')!r}"))
            if exp.get("concepts_missing_nonempty"):
                checks.append((f"{cid}_names_the_gap",
                               len(ev.get("concepts_missing", [])) > 0,
                               "expected non-empty concepts_missing"))
            if exp.get("misconception_nonempty"):
                checks.append((f"{cid}_misconception_flagged",
                               bool(str(ev.get("misconception", "")).strip()),
                               "expected the misconception to be flagged"))
            checks.append((f"{cid}_one_follow_up",
                           bool(str(ev.get("follow_up_question", "")).strip()),
                           "expected a follow-up question"))
            checks.append((f"{cid}_cited",
                           bool(str(ev.get("source_id", "")).strip()),
                           "expected a KB source_id on the grade"))
        except Exception as e:  # noqa: BLE001
            checks.append((f"{cid}_ran", False, f"raised {type(e).__name__}: {e}"))

    # Relative check: complete must outscore incomplete - robust to grader strictness.
    if "T1-complete-explanation" in scores and "T2-incomplete-explanation" in scores:
        checks.append(("complete_outscores_incomplete",
                       scores["T1-complete-explanation"] > scores["T2-incomplete-explanation"],
                       f"T1={scores['T1-complete-explanation']} vs "
                       f"T2={scores['T2-incomplete-explanation']}"))

    passed = sum(1 for _, p, _ in checks if p)
    return {
        "suite": "teachback",
        "metric": "grading_quality",
        "passed": passed, "total": len(checks),
        "score_pct": round(100 * passed / len(checks)) if checks else 0,
        "cases": [{"name": n, "pass": p, "note": note} for n, p, note in checks],
    }


# --------------------------------------------------------------------------- #
# Suite 7: memory decay model (pure code - no LLM, no Search)
# --------------------------------------------------------------------------- #
def run_mastery() -> dict:
    from src import mastery

    checks = []
    d = mastery.decayed_mastery

    e1 = {"mastery": 80, "last_reviewed": "2026-01-01", "reviews": 1}
    checks.append(("halves_after_one_half_life",
                   round(d(e1, "2026-01-08")) == 40,
                   f"80 after 7d (HL 7d) -> {d(e1, '2026-01-08'):.1f}, expected 40"))

    e3 = {"mastery": 80, "last_reviewed": "2026-01-01", "reviews": 3}
    checks.append(("spacing_slows_decay",
                   d(e3, "2026-01-08") > d(e1, "2026-01-08"),
                   f"3 reviews retains {d(e3, '2026-01-08'):.1f} vs "
                   f"1 review {d(e1, '2026-01-08'):.1f} after 7d"))

    checks.append(("no_decay_same_day", d(e1, "2026-01-01") == 80.0,
                   f"got {d(e1, '2026-01-01')}"))

    store: dict = {}
    first = mastery.record_review(store, "L", "Skill A", 70, "2026-01-01")
    checks.append(("first_review_weighted", first["mastery"] == 49,
                   f"0.3*0 + 0.7*70 -> {first['mastery']}, expected 49"))
    second = mastery.record_review(store, "L", "Skill A", 100, "2026-01-02")
    checks.append(("reviews_increment", second["reviews"] == 2,
                   f"got {second['reviews']}"))
    checks.append(("mastery_clamped", 0 <= second["mastery"] <= 100,
                   f"got {second['mastery']}"))

    store2 = {"L": {
        "Learned then forgot": {"mastery": 80, "last_reviewed": "2026-01-01", "reviews": 1},
        "Never mastered":      {"mastery": 45, "last_reviewed": "2026-01-01", "reviews": 1},
        "Fresh and strong":    {"mastery": 90, "last_reviewed": "2026-01-29", "reviews": 3},
    }}
    due = mastery.due_refreshers(store2, "L", "2026-01-31")
    checks.append(("due_flags_learned_then_forgot", "Learned then forgot" in due,
                   f"due={due}"))
    checks.append(("due_skips_never_mastered", "Never mastered" not in due,
                   f"due={due} - studying anew is the remediation loop's job"))
    checks.append(("due_skips_fresh_skills", "Fresh and strong" not in due,
                   f"due={due}"))

    passed = sum(1 for _, p, _ in checks if p)
    return {
        "suite": "mastery",
        "metric": "decay_model_correctness",
        "passed": passed, "total": len(checks),
        "score_pct": round(100 * passed / len(checks)) if checks else 0,
        "cases": [{"name": n, "pass": p, "note": note} for n, p, note in checks],
    }


# --------------------------------------------------------------------------- #
SUITES = {
    "decisions": run_decisions,
    "groundedness": run_groundedness,
    "manager": run_manager,
    "accessibility": run_accessibility,
    "calendar": run_calendar,
    "teachback": run_teachback,
    "mastery": run_mastery,
}


def main() -> int:
    ap = argparse.ArgumentParser(description="Run evals for the Inclusive Certification Coach.")
    ap.add_argument("--suite", choices=list(SUITES), help="run a single suite (default: all)")
    ap.add_argument("--repeat", type=int, default=1, metavar="N",
                    help="decisions suite: run each gold case N times; a case "
                         "passes only if ALL runs pass (reliability under "
                         "LLM nondeterminism)")
    args = ap.parse_args()

    to_run = [args.suite] if args.suite else list(SUITES)
    results, all_pass = [], True

    for name in to_run:
        print(f"\n=== suite: {name} ===")
        t0 = time.time()
        r = SUITES[name](repeat=args.repeat) if name == "decisions" else SUITES[name]()
        r["duration_s"] = round(time.time() - t0, 1)
        results.append(r)

        for c in r["cases"]:
            label = c.get("id") or c.get("name")
            mark = "PASS" if c["pass"] else "FAIL"
            rate = f"  ({c['pass_rate']} runs)" if c.get("pass_rate") else ""
            print(f"  [{mark}] {label}{rate}")
            if not c["pass"]:
                subs = c.get("checks", [c])
                for s in subs:
                    if not s["pass"]:
                        print(f"         - {s['name']}: {s['note']}")
        print(f"  -> {r['metric']}: {r['passed']}/{r['total']} ({r['score_pct']}%)")
        all_pass = all_pass and r["passed"] == r["total"]

    RESULTS_DIR.mkdir(exist_ok=True)
    payload = {"run_at": datetime.now(timezone.utc).isoformat(), "suites": results}
    (RESULTS_DIR / "latest.json").write_text(json.dumps(payload, indent=2))
    print(f"\nWrote {RESULTS_DIR / 'latest.json'}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
