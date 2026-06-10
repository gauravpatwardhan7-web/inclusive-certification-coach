"""
Per-skill memory decay and spaced refreshers.

A skill passed three weeks ago is not a skill known today. This module tracks
each skill's mastery as a DECAYING quantity, so the coach can reason
longitudinally: schedule a five-minute refresher just before the learner
would have forgotten, instead of re-teaching after they already have.

Model (deliberately simple, fully deterministic, spaced-repetition-inspired):
- Each review of a skill records a raw mastery score (0-100) and a timestamp.
- Mastery decays exponentially with a HALF-LIFE that DOUBLES with every
  review: 7 days after one review, 14 after two, 28 after three... - the
  spacing effect: the more times you've revisited something, the slower
  you forget it.
- A skill is DUE for a refresher when it was genuinely learned once
  (raw mastery >= the learned threshold) but its decayed value has dropped
  below the retention threshold: learned-then-forgetting, the exact moment a
  short review is cheap and effective. A skill never mastered is not "due" -
  it needs study, not a refresher, and that is the remediation loop's job.

No LLM anywhere in this file: memory arithmetic is precision work, so it is
code; deciding what to DO about a decayed skill stays with the agents.
"""

import json
from datetime import date, datetime
from pathlib import Path

STORE_PATH = Path(__file__).resolve().parents[1] / "data" / "state" / "mastery_demo.json"

BASE_HALF_LIFE_DAYS = 7.0
LEARNED_THRESHOLD = 60      # raw mastery at/above this means "was learned"
RETENTION_THRESHOLD = 60    # decayed mastery below this means "fading"


def load_store(path: Path = STORE_PATH) -> dict:
    if Path(path).exists():
        return json.loads(Path(path).read_text())
    return {}


def save_store(store: dict, path: Path = STORE_PATH) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(store, indent=2))


def _as_date(d) -> date:
    if isinstance(d, date):
        return d
    return datetime.strptime(str(d), "%Y-%m-%d").date()


def half_life_days(reviews: int) -> float:
    """Half-life doubles with each review: 7, 14, 28, 56... days."""
    return BASE_HALF_LIFE_DAYS * (2 ** max(0, reviews - 1))


def decayed_mastery(entry: dict, today: date | str) -> float:
    """Exponential decay of raw mastery since the last review."""
    days = ( _as_date(today) - _as_date(entry["last_reviewed"]) ).days
    if days <= 0:
        return float(entry["mastery"])
    hl = half_life_days(int(entry.get("reviews", 1)))
    return float(entry["mastery"]) * 0.5 ** (days / hl)


def record_review(store: dict, learner_id: str, skill_area: str,
                  score_pct: int, when: date | str) -> dict:
    """
    Fold a new review result into a skill's mastery.

    New raw mastery blends what was retained (the decayed value today) with
    today's evidence, weighted toward the fresh result. Clamped to [0, 100].
    """
    learner = store.setdefault(learner_id, {})
    when = _as_date(when)
    prior = learner.get(skill_area)
    retained = decayed_mastery(prior, when) if prior else 0.0
    reviews = int(prior.get("reviews", 0)) + 1 if prior else 1
    new_raw = round(min(100.0, max(0.0, 0.3 * retained + 0.7 * score_pct)))
    learner[skill_area] = {
        "mastery": new_raw,
        "last_reviewed": when.isoformat(),
        "reviews": reviews,
    }
    return learner[skill_area]


def snapshot(store: dict, learner_id: str, today: date | str) -> list[dict]:
    """Current memory state per skill: raw, decayed, age, and due flag."""
    today = _as_date(today)
    rows = []
    for skill, entry in store.get(learner_id, {}).items():
        decayed = decayed_mastery(entry, today)
        rows.append({
            "skill_area": skill,
            "raw_mastery": int(entry["mastery"]),
            "decayed_mastery": round(decayed),
            "days_since_review": (today - _as_date(entry["last_reviewed"])).days,
            "reviews": int(entry.get("reviews", 1)),
            "half_life_days": half_life_days(int(entry.get("reviews", 1))),
            "due_refresher": (entry["mastery"] >= LEARNED_THRESHOLD
                              and decayed < RETENTION_THRESHOLD),
        })
    rows.sort(key=lambda r: r["decayed_mastery"])
    return rows


def due_refreshers(store: dict, learner_id: str, today: date | str) -> list[str]:
    """Skill areas that were learned once but have decayed below retention."""
    return [r["skill_area"] for r in snapshot(store, learner_id, today)
            if r["due_refresher"]]


if __name__ == "__main__":
    today = date.today()
    store = load_store()
    for row in snapshot(store, "demo-learner", today):
        flag = "  <- REFRESHER DUE" if row["due_refresher"] else ""
        print(f"{row['skill_area'][:50]:52} raw {row['raw_mastery']:3} -> "
              f"now {row['decayed_mastery']:3} "
              f"({row['days_since_review']}d ago, {row['reviews']} reviews){flag}")
