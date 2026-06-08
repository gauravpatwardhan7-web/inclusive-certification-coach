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
def run_decisions() -> dict:
    from src.orchestrator import decide

    gold = _load("orchestrator_decisions.json")
    cases = []
    passed = 0

    for c in gold["cases"]:
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

        passed += ok
        cases.append({
            "id": c["id"], "pass": ok,
            "checks": [{"name": n, "pass": p, "note": note} for n, p, note in checks],
            "got": detail,
        })

    return {
        "suite": "decisions",
        "metric": "decision_accuracy",
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

    passed = sum(1 for _, p, _ in checks if p)
    return {
        "suite": "groundedness",
        "metric": "citation_fidelity",
        "passed": passed, "total": len(checks),
        "score_pct": round(100 * passed / len(checks)) if checks else 0,
        "cases": [{"name": n, "pass": p, "note": note} for n, p, note in checks],
    }


# --------------------------------------------------------------------------- #
SUITES = {"decisions": run_decisions, "groundedness": run_groundedness}


def main() -> int:
    ap = argparse.ArgumentParser(description="Run evals for the Inclusive Certification Coach.")
    ap.add_argument("--suite", choices=list(SUITES), help="run a single suite (default: all)")
    args = ap.parse_args()

    to_run = [args.suite] if args.suite else list(SUITES)
    results, all_pass = [], True

    for name in to_run:
        print(f"\n=== suite: {name} ===")
        t0 = time.time()
        r = SUITES[name]()
        r["duration_s"] = round(time.time() - t0, 1)
        results.append(r)

        for c in r["cases"]:
            label = c.get("id") or c.get("name")
            mark = "PASS" if c["pass"] else "FAIL"
            print(f"  [{mark}] {label}")
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
