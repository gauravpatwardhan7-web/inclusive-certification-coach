"""
Agent 2 - Study Plan Generator.

Takes the Curator's grounded learning path plus the learner's accessibility
profile and turns it into a concrete, accommodation-aware study SCHEDULE:
which skill area to study on which day, in what size blocks, with checkpoints.

It does not invent study guidance - the pacing rules (session length, break
cadence, weekly checkpoints, readiness target) are grounded in the knowledge
base's "Recommended study pattern" section via Foundry IQ retrieval.
"""

import json
from src.foundry_client import chat_json
from src.retrieval import retrieve_with_context

SYSTEM_PROMPT = """You are the Study Plan Generator in an accessibility-first \
enterprise certification system.

You are given a learning path (skill areas + recommended hours, each cited) and
the learner's accessibility profile. Produce a day-by-day study schedule.

Hard rules:
- Schedule ALL skill areas from the learning path. Do not add or drop skills.
- Use the pacing guidance in the KNOWLEDGE BASE (session length, break cadence,
  weekly checkpoints, readiness target). Do not invent pacing rules.
- Adapt to the accessibility profile: if the learner reports attention/focus
  difficulty, break study into the shorter blocks the KB recommends and keep
  daily load light; if low-vision/screen-reader, note text-only/plain-language
  delivery. If profile is "none", use standard pacing.
- If the path is a REMEDIATION path (a note will say so), keep the schedule
  short and the daily load lighter - the learner is revisiting weak areas.
- Carry each skill's "source_id" through to its scheduled sessions.

Output ONLY valid JSON:
{
  "certification": "<id>",
  "total_days": <int>,
  "daily_max_minutes": <int>,
  "block_minutes": <int>,
  "sessions": [
    {
      "day": <int>,
      "skill_area": "<from the learning path>",
      "minutes": <int>,
      "blocks": "<e.g. '2 x 25 min with a 5 min break'>",
      "accommodation_note": "<accessibility-aware guidance for this session>",
      "source_id": "<carried from the learning path / KB>"
    }
  ],
  "checkpoints": ["<e.g. 'Weekly practice assessment at end of week 1'>"],
  "note": "<any caveat, else empty string>"
}
No preamble. JSON only."""


def generate_study_plan(learning_path: dict, accessibility_profile: str = "none",
                        remediation: bool = False) -> dict:
    """Turn a grounded learning path into an accommodation-aware schedule."""
    # Ground the pacing rules (session length, breaks, checkpoints) in the KB.
    pacing, chunks = retrieve_with_context(
        "recommended study pattern session length breaks weekly checkpoints "
        "readiness target accessibility shorter blocks focus"
    )
    # Don't leak trace metadata into the prompt.
    path_for_prompt = {k: v for k, v in learning_path.items() if not k.startswith("_")}
    remediation_note = (
        "NOTE: this is a REMEDIATION path - the learner failed these areas and "
        "is revisiting them. Keep it short and supportive.\n\n" if remediation else ""
    )
    user_msg = (
        f"KNOWLEDGE BASE (pacing guidance):\n{pacing}\n\n"
        f"{remediation_note}"
        f"LEARNING PATH:\n{json.dumps(path_for_prompt, indent=2)}\n\n"
        f"ACCESSIBILITY PROFILE: {accessibility_profile}\n\n"
        f"Produce the accommodation-aware study schedule JSON now."
    )
    plan = chat_json([
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ])
    plan["_retrieval"] = [
        {"source_id": c["source_id"], "score": c["score"],
         "snippet": c["text"][:160]}
        for c in chunks
    ]
    return plan


if __name__ == "__main__":
    from src.agents.curator import curate
    path = curate("AZ-204", "Cloud Engineer",
                  "Has ADHD; struggles to focus in long study sessions.")
    plan = generate_study_plan(path, "Has ADHD; struggles to focus in long study sessions.")
    print(json.dumps(plan, indent=2))
