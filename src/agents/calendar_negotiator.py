"""
Agent 6 - Calendar Negotiator.

The #1 reason corporate study plans die is that the plan lives in a PDF while
the learner's life lives in their calendar. This agent takes the Study Plan
Generator's schedule and the learner's actual work calendar (Microsoft
Graph-shaped; synthetic here) and negotiates real, bookable study blocks:

- finds genuine gaps between meetings inside work hours;
- books study blocks into them, respecting the accommodation policy
  (block size, breaks, daily cap);
- and when the week simply does not have the time, it does NOT pretend -
  it produces an evidence-based pushback: how much time the plan needs,
  how much the calendar actually has, the projected realistic timeline,
  and concrete options to put in front of a manager.

Hybrid design (same philosophy as the rest of the system): the LLM decides
where judgment is needed - the pacing POLICY for this learner and the
NEGOTIATION narrative - while gap-finding and slot allocation are deterministic
code, so a booked block can never overlap a meeting by construction.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path

from src.foundry_client import chat_json

DATA = Path(__file__).resolve().parents[2] / "data" / "synthetic"

MIN_USABLE_GAP_MINUTES = 25   # a gap shorter than this isn't real study time
MIN_CHUNK_MINUTES = 15        # never book a sliver shorter than this

POLICY_PROMPT = """You are the Calendar Negotiator in an accessibility-first \
certification coach. Before booking study blocks into a learner's work
calendar, decide the PACING POLICY for this specific learner.

You are given the study plan's own pacing (block size, daily cap) and the
learner's accessibility profile. Choose:
- "block_minutes": length of one study block. Honour the plan's block size;
  for focus/attention profiles never exceed it.
- "break_minutes": minimum break between two consecutive study blocks.
- "max_daily_minutes": cap on study time per day. Never exceed the plan's
  daily cap; for focus/cognitive-load profiles prefer a lighter cap.
- "rationale": 2-4 short bullets explaining the policy in terms of the
  profile and the plan's pacing rules.

Output ONLY valid JSON:
{
  "block_minutes": <int>,
  "break_minutes": <int>,
  "max_daily_minutes": <int>,
  "rationale": ["<short bullet>"]
}
No preamble. JSON only."""

NEGOTIATION_PROMPT = """You are the Calendar Negotiator in an accessibility-first \
certification coach. The slot allocation has ALREADY been computed in code -
your job is the honest negotiation narrative around it.

You are given the numbers: how many study minutes the plan needs this week,
how many usable minutes the calendar actually has, what got booked, what did
not fit, and the projected number of weeks to finish the whole plan at this
calendar's pace.

Write:
- "summary": 2-3 plain sentences to the LEARNER about what was booked and
  whether the pace is realistic. Encouraging, never guilt-inducing.
- "message_to_manager": ONLY if the week is infeasible - a short, respectful,
  evidence-based note the learner could send their manager: state the numbers
  (needed vs available), the projected timeline, and ask for a concrete
  remedy. Empty string if the week is feasible.
- "options": 2-4 concrete trade-offs, each one sentence, e.g. extend the
  target date to the projected timeline; block protected study time;
  narrow scope to the weakest areas; split sessions across more weeks.
  Empty list if feasible and nothing needs deciding.

Never invent numbers - use only the figures provided.

Output ONLY valid JSON:
{
  "summary": "<2-3 sentences>",
  "message_to_manager": "<empty string if feasible>",
  "options": ["<one-sentence option>"]
}
No preamble. JSON only."""


def load_calendar(name: str = "calendar_light_week.json") -> dict:
    return json.loads((DATA / name).read_text())


def _t(date: str, hhmm: str) -> datetime:
    return datetime.strptime(f"{date} {hhmm}", "%Y-%m-%d %H:%M")


def _fmt(dt: datetime) -> str:
    return dt.strftime("%H:%M")


def find_gaps(calendar: dict, min_minutes: int = MIN_USABLE_GAP_MINUTES) -> list[dict]:
    """
    Deterministically find free slots between meetings inside work hours.

    Returns gaps as {"date", "weekday", "start", "end", "minutes"}, in
    chronological order. Gaps shorter than min_minutes are discarded - a
    12-minute sliver between meetings is not study time.
    """
    gaps = []
    for day in calendar["days"]:
        cursor = _t(day["date"], calendar["work_hours"]["start"])
        day_end = _t(day["date"], calendar["work_hours"]["end"])
        events = sorted(day["events"], key=lambda e: e["start"])
        for ev in events:
            ev_start = _t(day["date"], ev["start"])
            ev_end = _t(day["date"], ev["end"])
            if ev_start > cursor:
                minutes = int((ev_start - cursor).total_seconds() // 60)
                if minutes >= min_minutes:
                    gaps.append({"date": day["date"], "weekday": day["weekday"],
                                 "start": _fmt(cursor), "end": _fmt(ev_start),
                                 "minutes": minutes})
            cursor = max(cursor, ev_end)
        if day_end > cursor:
            minutes = int((day_end - cursor).total_seconds() // 60)
            if minutes >= min_minutes:
                gaps.append({"date": day["date"], "weekday": day["weekday"],
                             "start": _fmt(cursor), "end": _fmt(day_end),
                             "minutes": minutes})
    return gaps


def _allocate(sessions: list[dict], gaps: list[dict], policy: dict) -> tuple[list, list]:
    """
    Greedy, deterministic allocation of study sessions into calendar gaps.

    Each session is split into even chunks no longer than
    policy["block_minutes"] (a 60-min session at 25-min blocks becomes
    3 x 20, never 25+25+10 with a dropped tail - the chunks always sum to the
    session exactly). Chunks go into the earliest gap with room, respecting
    the per-day cap and inserting policy["break_minutes"] between consecutive
    blocks in the same gap. By construction a block can never overlap a
    meeting. Returns (scheduled_blocks, unplaced_sessions).
    """
    block_len = max(int(policy["block_minutes"]), MIN_CHUNK_MINUTES)
    break_len = max(int(policy["break_minutes"]), 0)
    daily_cap = int(policy["max_daily_minutes"])

    # Mutable cursor per gap; minutes booked per day.
    open_gaps = [{**g, "cursor": _t(g["date"], g["start"])} for g in gaps]
    booked_per_day: dict[str, int] = {}
    scheduled, unplaced = [], []

    for s in sessions:
        total = int(s.get("minutes", 0))
        if total <= 0:
            continue
        n_chunks = -(-total // block_len)  # ceil division
        chunks = [total // n_chunks + (1 if i < total % n_chunks else 0)
                  for i in range(n_chunks)]
        minutes_unplaced = 0
        for chunk in chunks:
            placed = False
            for g in open_gaps:
                gap_end = _t(g["date"], g["end"])
                free_here = int((gap_end - g["cursor"]).total_seconds() // 60)
                day_room = daily_cap - booked_per_day.get(g["date"], 0)
                if free_here >= chunk and day_room >= chunk:
                    start = g["cursor"]
                    end = start + timedelta(minutes=chunk)
                    scheduled.append({
                        "date": g["date"], "weekday": g["weekday"],
                        "start": _fmt(start), "end": _fmt(end),
                        "minutes": chunk,
                        "skill_area": s.get("skill_area", "?"),
                        "source_id": s.get("source_id", ""),
                    })
                    g["cursor"] = end + timedelta(minutes=break_len)
                    booked_per_day[g["date"]] = booked_per_day.get(g["date"], 0) + chunk
                    placed = True
                    break
            if not placed:
                minutes_unplaced += chunk
        if minutes_unplaced:
            unplaced.append({"skill_area": s.get("skill_area", "?"),
                             "plan_day": s.get("day"),
                             "minutes_unplaced": minutes_unplaced})
    return scheduled, unplaced


def _order_gaps(gaps: list[dict], prefer: str) -> list[dict]:
    """Order gaps so the learner's time-of-day preference is filled first."""
    if prefer == "mornings":
        return sorted(gaps, key=lambda g: (g["start"] >= "12:00", g["date"], g["start"]))
    if prefer == "afternoons":
        return sorted(gaps, key=lambda g: (g["start"] < "12:00", g["date"], g["start"]))
    return sorted(gaps, key=lambda g: (g["date"], g["start"]))


def plan_week(study_plan: dict, calendar: dict, block_minutes: int,
              break_minutes: int, daily_cap: int, prefer: str = "any") -> dict:
    """
    Pure, deterministic re-planning for the interactive controls - NO model
    call. Given explicit pacing controls and a time-of-day preference, find
    gaps, allocate blocks, and report feasibility. Fast enough to re-run on
    every slider move.
    """
    horizon = len(calendar["days"])
    sessions = [s for s in study_plan.get("sessions", []) if int(s.get("day", 0)) <= horizon]
    required = sum(int(s.get("minutes", 0)) for s in sessions)
    plan_total = sum(int(s.get("minutes", 0)) for s in study_plan.get("sessions", []))
    gaps = _order_gaps(find_gaps(calendar), prefer)
    available = sum(g["minutes"] for g in gaps)
    policy = {"block_minutes": block_minutes, "break_minutes": break_minutes,
              "max_daily_minutes": daily_cap}
    scheduled, unplaced = _allocate(sessions, gaps, policy)
    scheduled_minutes = sum(b["minutes"] for b in scheduled)
    est_weeks = max(1, -(-plan_total // max(scheduled_minutes, 1)))
    return {
        "feasible": not unplaced,
        "scheduled_blocks": scheduled,
        "unplaced": unplaced,
        "policy": policy,
        "stats": {
            "required_minutes_this_week": required,
            "available_minutes_this_week": available,
            "scheduled_minutes": scheduled_minutes,
            "unplaced_minutes": sum(u["minutes_unplaced"] for u in unplaced),
            "plan_total_minutes": plan_total,
            "est_weeks_to_complete_plan": est_weeks,
        },
    }


def negotiate(study_plan: dict, calendar: dict,
              accessibility_profile: str = "none") -> dict:
    """
    Book the plan's first week of sessions into the learner's real calendar,
    or produce an evidence-based pushback when the week cannot hold them.
    """
    sessions = [s for s in study_plan.get("sessions", [])
                if int(s.get("day", 0)) <= len(calendar["days"])]

    # LLM judgment call #1: the pacing policy for THIS learner.
    policy = chat_json([
        {"role": "system", "content": POLICY_PROMPT},
        {"role": "user", "content": (
            f"STUDY PLAN PACING: block_minutes={study_plan.get('block_minutes')}, "
            f"daily_max_minutes={study_plan.get('daily_max_minutes')}\n"
            f"ACCESSIBILITY PROFILE: {accessibility_profile}\n\n"
            "Decide the pacing policy. JSON only."
        )},
    ])
    # Deterministic rails on the policy. The study plan is the accommodation
    # authority on daily load - the policy handles calendar tactics. So the
    # daily cap may never EXCEED the plan's cap, and may never DROP BELOW the
    # plan's own busiest day in this horizon (or the plan could not fit even
    # into an empty calendar, and "infeasible" would be a self-inflicted lie).
    notes = []
    plan_block = int(study_plan.get("block_minutes") or policy["block_minutes"])
    plan_cap = int(study_plan.get("daily_max_minutes") or policy["max_daily_minutes"])
    per_plan_day: dict = {}
    for s in sessions:
        per_plan_day[s.get("day")] = per_plan_day.get(s.get("day"), 0) + int(s.get("minutes", 0))
    plan_daily_need = max(per_plan_day.values(), default=0)
    if int(policy["block_minutes"]) > plan_block:
        policy["block_minutes"] = plan_block
        notes.append("policy block size capped at the plan's accommodation block size")
    if int(policy["max_daily_minutes"]) > plan_cap:
        policy["max_daily_minutes"] = plan_cap
        notes.append("policy daily cap capped at the plan's accommodation daily max")
    if int(policy["max_daily_minutes"]) < plan_daily_need:
        policy["max_daily_minutes"] = plan_daily_need
        notes.append(f"policy daily cap raised to {plan_daily_need} min - the plan "
                     "itself schedules that much per day, and the plan is the "
                     "accommodation authority on daily load")

    # Deterministic allocation via the shared planner (blocks cannot overlap
    # meetings by construction). plan_week is the same code the interactive
    # controls call, so the agent's booking and the learner's tweaks agree.
    result = plan_week(study_plan, calendar, policy["block_minutes"],
                       policy["break_minutes"], policy["max_daily_minutes"])
    scheduled, unplaced = result["scheduled_blocks"], result["unplaced"]
    stats, feasible = result["stats"], result["feasible"]
    required = stats["required_minutes_this_week"]
    available = stats["available_minutes_this_week"]
    est_weeks = stats["est_weeks_to_complete_plan"]

    # LLM judgment call #2: the honest negotiation narrative.
    negotiation = chat_json([
        {"role": "system", "content": NEGOTIATION_PROMPT},
        {"role": "user", "content": (
            f"FEASIBLE THIS WEEK: {feasible}\n"
            f"NUMBERS:\n{json.dumps(stats, indent=2)}\n"
            f"UNPLACED SESSIONS:\n{json.dumps(unplaced, indent=2)}\n"
            f"ACCESSIBILITY PROFILE: {accessibility_profile}\n\n"
            "Write the negotiation JSON now."
        )},
    ])
    # Rail: an infeasible week must surface a manager-ready message + options.
    if not feasible and not str(negotiation.get("message_to_manager", "")).strip():
        negotiation["message_to_manager"] = (
            f"The certification plan needs {required} minutes of study this week, "
            f"but my calendar has only {available} usable minutes between meetings. "
            f"At this pace the plan takes about {est_weeks} weeks. Could we either "
            f"extend the target date or block protected study time?"
        )
        notes.append("model omitted message_to_manager on an infeasible week; "
                     "generated deterministically from the stats")
    if not feasible and len(negotiation.get("options", [])) < 2:
        negotiation["options"] = (negotiation.get("options") or []) + [
            f"Extend the target date to roughly {est_weeks} weeks at the current calendar's pace.",
            "Ask your manager to block recurring protected study time this week.",
        ]
        notes.append("padded trade-off options deterministically on an infeasible week")

    return {
        "feasible": feasible,
        "policy": policy,
        "scheduled_blocks": scheduled,
        "unplaced": unplaced,
        "stats": stats,
        "negotiation": negotiation,
        "guardrail_notes": notes,
    }


if __name__ == "__main__":
    # Demo without retrieval: a fixed mini-plan against both synthetic weeks.
    demo_plan = {
        "block_minutes": 25, "daily_max_minutes": 60,
        "sessions": [
            {"day": d, "skill_area": f"Skill {d}", "minutes": 50,
             "source_id": "KB-AZ204-001"} for d in range(1, 6)
        ],
    }
    for cal_name in ("calendar_light_week.json", "calendar_packed_week.json"):
        out = negotiate(demo_plan, load_calendar(cal_name),
                        "Has ADHD; struggles to focus in long study sessions.")
        print(f"\n=== {cal_name} -> feasible={out['feasible']} ===")
        print(json.dumps(out["stats"], indent=2))
        print(out["negotiation"]["summary"])
        if not out["feasible"]:
            print("PUSHBACK:", out["negotiation"]["message_to_manager"])
