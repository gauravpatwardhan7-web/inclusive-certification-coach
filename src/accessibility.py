"""
Accessibility Narrator.

Turns any agent's structured output into a screen-reader-first, voice-ready
SPOKEN SCRIPT: linear plain text, no tables or markdown, abbreviations spelled
out, symbols read as words. The script adapts to the learner's accessibility
profile (screen-reader user, voice-only, focus-support).

This is a text rendering layer on top of the existing agents - it never changes
their JSON contracts. The actual speech is produced client-side by the browser's
Web Speech API (no audio model, no Azure quota), so the text-only model
constraint is respected end to end.
"""

import json
import re
from src.foundry_client import chat

SYSTEM_PROMPT = """You are the Accessibility Narrator for an inclusive learning \
coach. You convert structured data into a short spoken script for a learner who
is using a screen reader or listening hands-free.

Rules for the script:
- Plain text only. No markdown, no tables, no bullet symbols, no emoji, no
  headings, no asterisks, no pipes.
- Read symbols and abbreviations as words: "75%" -> "seventy five percent";
  "AZ-204" -> "A Z two oh four"; "hrs"/"h" -> "hours".
- Short, calm sentences. Warm, encouraging, second person ("you").
- Linear narration the learner can follow by ear: say the most important thing
  first, then the details in order.
- Adapt to the accessibility profile if given (e.g. mention that materials are
  text-only and screen-reader friendly for a low-vision learner; keep it brief
  and chunked for a focus-support learner).
- Do not invent facts beyond what is in the data.

Output ONLY the spoken script as plain text. No preamble, no quotes, no JSON."""

# What each payload kind is, to steer the narration.
_KIND_HINT = {
    "learning_path": "a learning path: skill areas, hours per area, and total hours",
    "study_plan": "a study schedule: days, skill areas, block sizes, and checkpoints",
    "assessment_result": "an assessment result: score, whether ready, and weak areas",
    "recommendation": "the coach's recommendation: advance, keep going, or get human help",
    "team_insights": "a manager's team-readiness rollup",
}

_MARKDOWN = re.compile(r"[|#*`>_]|\[[^\]]*\]\([^)]*\)")


def _strip_markdown(text: str) -> str:
    """Deterministic guard: remove any stray markdown the model leaves in."""
    return _MARKDOWN.sub("", text).strip()


def to_spoken(kind: str, payload: dict, profile: str = "none") -> str:
    """Return a screen-reader/voice-friendly spoken script for an agent payload."""
    hint = _KIND_HINT.get(kind, "structured learning data")
    user_msg = (
        f"DATA KIND: {hint}\n"
        f"ACCESSIBILITY PROFILE: {profile}\n\n"
        f"DATA (JSON):\n{json.dumps(payload, indent=2)}\n\n"
        f"Write the spoken script now."
    )
    raw = chat([
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ])
    return _strip_markdown(raw)


if __name__ == "__main__":
    from src.agents.curator import curate
    path = curate("AZ-204", "Cloud Engineer", "Low vision; uses a screen reader.")
    print(to_spoken("learning_path", path, "Low vision; uses a screen reader."))
