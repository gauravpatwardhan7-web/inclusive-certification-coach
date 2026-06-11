"""
Design system for the Inclusive Certification Coach UI.

Style: Swiss/minimal enterprise (clean surfaces, generous whitespace, subtle
200ms transitions). Typography: Lexend for headings - a typeface designed for
reading proficiency, on-brand for an accessibility-first product - and
Source Sans 3 for body. Tokens are semantic CSS variables; status is never
conveyed by colour alone (every status pairs an icon + label); focus rings are
visible; prefers-reduced-motion is respected.

Everything here is presentation only: small HTML component builders that the
app composes. No agent logic.
"""

import html as _html

# --------------------------------------------------------------------------- #
# Inline SVG icons (Lucide-style paths) - no emoji-as-icon in components.
# --------------------------------------------------------------------------- #
_ICON_PATHS = {
    "check": '<path d="M20 6 9 17l-5-5"/>',
    "repeat": '<path d="m17 2 4 4-4 4"/><path d="M3 11v-1a4 4 0 0 1 4-4h14"/>'
              '<path d="m7 22-4-4 4-4"/><path d="M21 13v1a4 4 0 0 1-4 4H3"/>',
    "user": '<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
    "calendar": '<rect width="18" height="18" x="3" y="4" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/>',
    "brain": '<path d="M12 5a3 3 0 1 0-5.997.125 4 4 0 0 0-2.526 5.77 4 4 0 0 0 .556 6.588A4 4 0 1 0 12 18Z"/>'
             '<path d="M12 5a3 3 0 1 1 5.997.125 4 4 0 0 1 2.526 5.77 4 4 0 0 1-.556 6.588A4 4 0 1 1 12 18Z"/>',
    "book": '<path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1 0-5H20"/>',
    "alert": '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/>'
             '<path d="M12 9v4M12 17h.01"/>',
    "shield": '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/>',
    "clock": '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
    "mic": '<path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/>'
           '<path d="M19 10v2a7 7 0 0 1-14 0v-2M12 19v3"/>',
    "trend": '<path d="M16 7h6v6"/><path d="m22 7-8.5 8.5-5-5L2 17"/>',
    "lock": '<rect width="18" height="11" x="3" y="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
    "send": '<path d="m22 2-7 20-4-9-9-4Z"/><path d="M22 2 11 13"/>',
    "target": '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>',
    "zap": '<path d="M4 14a1 1 0 0 1-.78-1.63l9.9-10.2a.5.5 0 0 1 .86.46l-1.92 6.02A1 1 0 0 0 13 10h7a1 1 0 0 1 .78 1.63l-9.9 10.2a.5.5 0 0 1-.86-.46l1.92-6.02A1 1 0 0 0 11 14z"/>',
}


def icon(name: str, size: int = 16, color: str = "currentColor") -> str:
    return (f'<svg aria-hidden="true" width="{size}" height="{size}" viewBox="0 0 24 24" '
            f'fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" '
            f'stroke-linejoin="round" style="vertical-align:-2px">{_ICON_PATHS[name]}</svg>')


def esc(s) -> str:
    return _html.escape(str(s))


# --------------------------------------------------------------------------- #
# Global stylesheet
# --------------------------------------------------------------------------- #
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Lexend:wght@400;500;600;700&family=Source+Sans+3:wght@400;500;600;700&display=swap');

:root {
  --bg: #F7F9FC;          --surface: #FFFFFF;
  --ink: #0F172A;         --ink-2: #44546A;       --ink-3: #5B6B82;
  --border: #E2E8F0;      --border-2: #CBD5E1;
  --primary: #2563EB;     --primary-deep: #1D4ED8; --primary-soft: #EFF4FF;
  --success: #047857;     --success-soft: #ECFDF5; --success-line: #A7F3D0;
  --warn: #B45309;        --warn-soft: #FFFBEB;    --warn-line: #FDE68A;
  --danger: #B91C1C;      --danger-soft: #FEF2F2;  --danger-line: #FECACA;
  --violet: #6D28D9;      --violet-soft: #F5F3FF;
  --teal: #0F766E;        --teal-soft: #F0FDFA;
  --radius: 12px;
  --shadow: 0 1px 2px rgba(15,23,42,.05), 0 4px 14px rgba(15,23,42,.05);
  --font-head: 'Lexend', 'Segoe UI', sans-serif;
  --font-body: 'Source Sans 3', 'Segoe UI', sans-serif;
}

html, body, [data-testid="stAppViewContainer"] * { font-family: var(--font-body); }
h1, h2, h3, h4, .icc-head { font-family: var(--font-head) !important; letter-spacing: -0.01em; }

[data-testid="stAppViewContainer"] { background: var(--bg); }
.block-container { padding-top: 1.2rem; max-width: 1240px; }

/* ---- buttons: 44px targets, visible focus, calm motion ---- */
.stButton > button {
  min-height: 44px; border-radius: 10px; font-weight: 600;
  font-family: var(--font-head); border: 1px solid var(--border-2);
  transition: transform .15s ease, box-shadow .2s ease, background .2s ease;
  cursor: pointer;
}
.stButton > button:hover { transform: translateY(-1px); box-shadow: var(--shadow); }
.stButton > button:active { transform: translateY(0); }
.stButton > button:focus-visible {
  outline: 3px solid rgba(37,99,235,.45); outline-offset: 2px;
}
.stButton > button[kind="primary"] { background: var(--primary); border-color: var(--primary); }
.stButton > button[kind="primary"]:hover { background: var(--primary-deep); }

/* ---- inputs ---- */
[data-testid="stTextInput"] input, [data-testid="stTextArea"] textarea,
[data-testid="stSelectbox"] > div > div {
  border-radius: 10px !important;
}
[data-testid="stTextArea"] textarea:focus, [data-testid="stTextInput"] input:focus {
  border-color: var(--primary) !important; box-shadow: 0 0 0 3px rgba(37,99,235,.18) !important;
}

/* ---- expanders as quiet cards ---- */
[data-testid="stExpander"] {
  border: 1px solid var(--border); border-radius: var(--radius);
  background: var(--surface); box-shadow: none;
}

/* ---- generic card ---- */
.icc-card {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius); box-shadow: var(--shadow);
  padding: 16px 18px; margin: 8px 0;
}
.icc-soft { box-shadow: none; }

/* ---- hero ---- */
.icc-hero {
  border-radius: 16px; padding: 26px 28px 22px;
  background: linear-gradient(120deg, #1E3A8A 0%, #2563EB 55%, #3B82F6 100%);
  color: #fff; margin-bottom: 14px;
}
.icc-hero h1 { color:#fff; font-size: 1.7rem; margin: 0 0 6px; font-weight: 700; }
.icc-hero p { color: #DBEAFE; margin: 0 0 12px; font-size: 1.02rem; max-width: 62ch; }
.icc-chip {
  display: inline-flex; align-items: center; gap: 6px;
  background: rgba(255,255,255,.14); border: 1px solid rgba(255,255,255,.28);
  color: #fff; border-radius: 999px; padding: 4px 12px;
  font-size: .8rem; font-weight: 600; margin: 0 6px 6px 0; font-family: var(--font-head);
}

/* ---- section headers ---- */
.icc-section { display: flex; align-items: baseline; gap: 10px; margin: 26px 0 4px; }
.icc-step {
  font-family: var(--font-head); font-weight: 700; font-size: .8rem; color: var(--primary-deep);
  background: var(--primary-soft); border: 1px solid #C7D8FE;
  border-radius: 8px; padding: 2px 9px; white-space: nowrap;
}
.icc-section h3 { margin: 0; font-size: 1.18rem; color: var(--ink); }
.icc-sub { color: var(--ink-3); font-size: .92rem; margin: 2px 0 10px; max-width: 75ch; }

/* ---- badges & status ---- */
.icc-badge {
  display: inline-flex; align-items: center; gap: 6px; border-radius: 999px;
  padding: 3px 11px; font-size: .8rem; font-weight: 600; font-family: var(--font-head);
  border: 1px solid var(--border-2); color: var(--ink-2); background: var(--surface);
}
.icc-badge.ok    { color: var(--success); background: var(--success-soft); border-color: var(--success-line); }
.icc-badge.warn  { color: var(--warn);    background: var(--warn-soft);    border-color: var(--warn-line); }
.icc-badge.bad   { color: var(--danger);  background: var(--danger-soft);  border-color: var(--danger-line); }
.icc-badge.info  { color: var(--primary-deep); background: var(--primary-soft); border-color: #C7D8FE; }

.icc-banner { border-radius: var(--radius); padding: 16px 18px; margin: 10px 0; border: 1px solid; }
.icc-banner .t { font-family: var(--font-head); font-weight: 700; font-size: 1.05rem; margin-bottom: 4px; display:flex; align-items:center; gap:8px; }
.icc-banner.ok   { background: var(--success-soft); border-color: var(--success-line); color: var(--success); }
.icc-banner.warn { background: var(--warn-soft);    border-color: var(--warn-line);    color: var(--warn); }
.icc-banner.bad  { background: var(--danger-soft);  border-color: var(--danger-line);  color: var(--danger); }
.icc-banner.info { background: var(--primary-soft); border-color: #C7D8FE;             color: var(--primary-deep); }
.icc-banner .b { color: var(--ink); font-weight: 400; }

/* ---- metric tiles ---- */
.icc-tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 10px; margin: 8px 0; }
.icc-tile { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 12px 14px; }
.icc-tile .v { font-family: var(--font-head); font-weight: 700; font-size: 1.35rem; color: var(--ink); font-variant-numeric: tabular-nums; }
.icc-tile .l { font-size: .8rem; color: var(--ink-3); font-weight: 600; }

/* ---- module / session cards ---- */
.icc-mod { display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; }
.icc-mod .name { font-family: var(--font-head); font-weight: 600; color: var(--ink); }
.icc-mod .note { color: var(--ink-2); font-size: .92rem; margin-top: 4px; }
.icc-src {
  font-size: .72rem; font-weight: 600; color: var(--ink-3);
  background: var(--bg); border: 1px solid var(--border); border-radius: 6px; padding: 2px 7px;
  font-variant-numeric: tabular-nums;
}
.icc-hours {
  font-family: var(--font-head); font-weight: 700; color: var(--primary-deep);
  background: var(--primary-soft); border: 1px solid #C7D8FE; border-radius: 8px;
  padding: 4px 10px; white-space: nowrap; font-variant-numeric: tabular-nums;
}

/* ---- week grid (calendar) ---- */
.icc-week { display: grid; grid-template-columns: repeat(5, 1fr); gap: 8px; margin: 10px 0; }
.icc-day { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 10px; min-height: 120px; }
.icc-day .d { font-family: var(--font-head); font-weight: 700; font-size: .82rem; color: var(--ink-2); margin-bottom: 8px; }
.icc-ev { border-radius: 7px; padding: 4px 8px; font-size: .74rem; margin: 4px 0; line-height: 1.35; }
.icc-ev.meet  { background: #EEF1F6; color: var(--ink-3); border: 1px dashed var(--border-2); }
.icc-ev.study { background: var(--primary-soft); color: var(--primary-deep); border: 1px solid #C7D8FE; font-weight: 600; }
.icc-ev .tm { font-variant-numeric: tabular-nums; font-weight: 600; display: block; }

/* ---- memory decay bars ---- */
.icc-mem { margin: 10px 0; }
.icc-mem .row1 { display: flex; justify-content: space-between; font-size: .9rem; margin-bottom: 5px; }
.icc-mem .skill { font-weight: 600; color: var(--ink); font-family: var(--font-head); font-size: .88rem; }
.icc-mem .meta { color: var(--ink-3); font-size: .8rem; font-variant-numeric: tabular-nums; }
.icc-track { position: relative; height: 12px; border-radius: 999px; background: #EAEFF6; border: 1px solid var(--border); overflow: hidden; }
.icc-fill { position: absolute; inset: 0 auto 0 0; border-radius: 999px; transition: width .5s ease; }
.icc-ghost { position: absolute; top: -3px; bottom: -3px; width: 2px; background: var(--border-2); }

/* ---- timeline (reasoning trace) ---- */
.icc-tl { position: relative; margin: 6px 0 0 6px; padding-left: 22px; border-left: 2px solid var(--border); }
.icc-tl-item { position: relative; margin: 0 0 16px; }
.icc-dot {
  position: absolute; left: -31px; top: 2px; width: 16px; height: 16px;
  border-radius: 50%; border: 3px solid var(--surface); box-shadow: 0 0 0 1.5px var(--border-2);
}
.icc-agent { font-family: var(--font-head); font-weight: 700; font-size: .86rem; }
.icc-did { color: var(--ink-2); font-size: .9rem; margin: 2px 0 4px; line-height: 1.5; }
.icc-tl details { margin: 4px 0 0; }
.icc-tl summary {
  cursor: pointer; font-size: .8rem; font-weight: 600; color: var(--primary-deep);
  list-style: none; display: inline-flex; align-items: center; gap: 5px;
  border: 1px solid var(--border); border-radius: 8px; padding: 3px 10px; background: var(--surface);
  transition: background .2s ease;
}
.icc-tl summary:hover { background: var(--primary-soft); }
.icc-tl summary:focus-visible { outline: 3px solid rgba(37,99,235,.45); outline-offset: 2px; }
.icc-tl .pane { border: 1px solid var(--border); border-radius: 10px; background: var(--bg); padding: 10px 12px; margin-top: 6px; font-size: .84rem; color: var(--ink-2); }
.icc-tl .pane ul { margin: 4px 0; padding-left: 18px; }
.icc-score { color: var(--ink-3); font-size: .76rem; font-variant-numeric: tabular-nums; }

/* ---- ledger (advocacy) ---- */
.icc-ledger { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.icc-ledger ul { margin: 6px 0 0; padding-left: 18px; color: var(--ink-2); font-size: .9rem; }
.icc-ledger .h { font-family: var(--font-head); font-weight: 700; font-size: .85rem; }

/* attempts chips */
.icc-attempts { display: flex; gap: 6px; flex-wrap: wrap; margin: 6px 0 10px; }

/* hide Streamlit chrome for a user-facing app */
#MainMenu, header [data-testid="stToolbar"], footer { visibility: hidden; }
[data-testid="stDecoration"] { display: none; }
[data-testid="stHeader"] { background: transparent; }

/* sidebar as a calm panel */
[data-testid="stSidebar"] { background: #FFFFFF; border-right: 1px solid var(--border); }
[data-testid="stSidebar"] .block-container { padding-top: 1rem; }
.icc-brand { font-family: var(--font-head); font-weight: 700; font-size: 1.15rem; color: var(--ink); display:flex; align-items:center; gap:8px; }
.icc-brand-sub { color: var(--ink-3); font-size: .82rem; margin: 2px 0 8px; }

/* tabs */
[data-baseweb="tab-list"] { gap: 4px; border-bottom: 1px solid var(--border); }
[data-baseweb="tab"] { font-family: var(--font-head); font-weight: 600; border-radius: 9px 9px 0 0; }
[data-baseweb="tab"][aria-selected="true"] { color: var(--primary-deep); }

/* audio player (rendered inside an iframe, styles inlined there too) */
.icc-help { color: var(--ink-3); font-size: .86rem; }
</style>
"""


# --------------------------------------------------------------------------- #
# Component builders (return HTML strings)
# --------------------------------------------------------------------------- #
def hero(chips: list[tuple[str, str]]) -> str:
    chip_html = "".join(f'<span class="icc-chip">{icon(i, 13)} {esc(t)}</span>'
                        for i, t in chips)
    return f"""
    <div class="icc-hero">
      <h1>Inclusive Certification Coach</h1>
      <p>An accessibility-first, multi-agent coach that builds your path, negotiates
      with your real calendar, checks what you actually understand, and remembers
      what you're starting to forget. Grounded in Microsoft Foundry IQ - all data synthetic.</p>
      <div>{chip_html}</div>
    </div>"""


def section(step: str, title: str, sub: str = "") -> str:
    sub_html = f'<p class="icc-sub">{sub}</p>' if sub else ""
    return (f'<div class="icc-section"><span class="icc-step">{esc(step)}</span>'
            f'<h3>{esc(title)}</h3></div>{sub_html}')


def banner(kind: str, icon_name: str, title: str, body: str) -> str:
    return (f'<div class="icc-banner {kind}"><div class="t">{icon(icon_name)} '
            f'{esc(title)}</div><div class="b">{body}</div></div>')


def tiles(items: list[tuple[str, str]]) -> str:
    cells = "".join(f'<div class="icc-tile"><div class="v">{esc(v)}</div>'
                    f'<div class="l">{esc(l)}</div></div>' for v, l in items)
    return f'<div class="icc-tiles">{cells}</div>'


def module_card(skill: str, hours, note: str, source: str) -> str:
    return f"""
    <div class="icc-card icc-soft"><div class="icc-mod">
      <div><div class="name">{esc(skill)}</div>
        <div class="note">{esc(note)}</div>
        <div style="margin-top:7px"><span class="icc-src">{icon('book', 11)} {esc(source)}</span></div>
      </div>
      <div class="icc-hours">{esc(hours)}h</div>
    </div></div>"""


def session_row(day, skill: str, minutes, blocks: str, note: str) -> str:
    return f"""
    <div class="icc-card icc-soft" style="padding:11px 14px"><div class="icc-mod">
      <div><span class="icc-badge info">{icon('clock', 12)} Day {esc(day)}</span>
        <span class="name" style="margin-left:8px">{esc(skill)}</span>
        <div class="note">{esc(blocks)} · {esc(note)}</div></div>
      <div class="icc-hours" style="font-size:.92rem">{esc(minutes)} min</div>
    </div></div>"""


def week_grid(calendar: dict, blocks: list[dict]) -> str:
    by_day: dict[str, list] = {}
    for b in blocks:
        by_day.setdefault(b["date"], []).append(b)
    cols = []
    for day in calendar["days"]:
        evs = sorted(
            [{"s": e["start"], "e": e["end"], "label": e["subject"], "kind": "meet"}
             for e in day["events"]] +
            [{"s": b["start"], "e": b["end"], "label": b["skill_area"], "kind": "study"}
             for b in by_day.get(day["date"], [])],
            key=lambda x: x["s"])
        rows = "".join(
            f'<div class="icc-ev {e["kind"]}"><span class="tm">{e["s"]}–{e["e"]}</span>'
            f'{esc(e["label"][:42])}</div>' for e in evs)
        cols.append(f'<div class="icc-day"><div class="d">{esc(day["weekday"][:3])} '
                    f'{esc(day["date"][5:])}</div>{rows}</div>')
    legend = (f'<span class="icc-badge">{icon("user", 12)} meeting</span> '
              f'<span class="icc-badge info">{icon("book", 12)} booked study block</span>')
    return f'{legend}<div class="icc-week">{"".join(cols)}</div>'


def memory_bar(row: dict) -> str:
    decayed, raw = row["decayed_mastery"], row["raw_mastery"]
    color = ("var(--success)" if decayed >= 60 else
             "var(--warn)" if decayed >= 35 else "var(--danger)")
    due = (f' <span class="icc-badge warn">{icon("alert", 11)} refresher due</span>'
           if row["due_refresher"] else "")
    return f"""
    <div class="icc-mem">
      <div class="row1"><span class="skill">{esc(row['skill_area'])}{due}</span>
        <span class="meta">retains {decayed}% of {raw}% · {row['days_since_review']}d ago ·
        half-life {round(row['half_life_days'])}d</span></div>
      <div class="icc-track" role="img"
           aria-label="{esc(row['skill_area'])}: retains {decayed} percent of {raw} percent">
        <div class="icc-fill" style="width:{max(2, min(100, decayed))}%; background:{color}"></div>
        <div class="icc-ghost" style="left:{max(2, min(100, raw))}%"></div>
      </div>
    </div>"""


_AGENT_STYLE = {
    "Learning Path Curator":    ("book",     "var(--primary)"),
    "Study Plan Generator":     ("clock",    "var(--teal)"),
    "Calendar Negotiator":      ("calendar", "#4338CA"),
    "Assessment Agent":         ("target",   "var(--warn)"),
    "Teach-back Assessor":      ("mic",      "var(--violet)"),
    "Orchestrator (reasoning)": ("brain",    "var(--ink)"),
    "Accessibility Narrator":   ("zap",      "#0E7490"),
    "Manager Insights":         ("trend",    "var(--success)"),
    "Advocate":                 ("shield",   "var(--success)"),
    "Memory Tracker":           ("repeat",   "#0E7490"),
}


def trace_timeline(steps: list[dict]) -> str:
    items = []
    for i, step in enumerate(steps, 1):
        icon_name, color = _AGENT_STYLE.get(step["agent"], ("zap", "var(--ink-3)"))
        extras = []
        if step.get("retrieved"):
            rows = "".join(
                f'<li><span class="icc-src">{esc(c["source_id"])}</span> '
                f'<span class="icc-score">score {esc(c["score"])}</span><br>'
                f'{esc(c["snippet"][:140])}…</li>' for c in step["retrieved"])
            extras.append(f'<details><summary>{icon("book", 12)} retrieved '
                          f'{len(step["retrieved"])} chunks</summary>'
                          f'<div class="pane"><ul>{rows}</ul></div></details>')
        d = step.get("decision_detail")
        if d and (d.get("signals_considered") or d.get("alternatives_rejected")
                  or d.get("guardrail_notes")):
            parts = []
            if d.get("signals_considered"):
                parts.append("<strong>Signals weighed</strong><ul>" + "".join(
                    f"<li>{esc(s)}</li>" for s in d["signals_considered"]) + "</ul>")
            if d.get("alternatives_rejected"):
                parts.append("<strong>Alternatives rejected</strong><ul>" + "".join(
                    f"<li>{esc(a)}</li>" for a in d["alternatives_rejected"]) + "</ul>")
            if d.get("guardrail_notes"):
                parts.append("<strong>Guardrails applied</strong><ul>" + "".join(
                    f"<li>{esc(g)}</li>" for g in d["guardrail_notes"]) + "</ul>")
            extras.append(f'<details><summary>{icon("brain", 12)} reasoning detail'
                          f'</summary><div class="pane">{"".join(parts)}</div></details>')
        items.append(f"""
        <div class="icc-tl-item">
          <span class="icc-dot" style="background:{color}"></span>
          <div class="icc-agent" style="color:{color}">{i}. {icon(icon_name, 13)} {esc(step["agent"])}</div>
          <div class="icc-did">{esc(step["did"])}</div>
          {"".join(extras)}
        </div>""")
    return f'<div class="icc-tl">{"".join(items)}</div>'


def attempts_chips(history: list[dict]) -> str:
    chips = []
    for h in history:
        pct = h.get("score_pct", 0)
        kind = "ok" if pct >= 75 else "warn" if pct >= 50 else "bad"
        chips.append(f'<span class="icc-badge {kind}">{icon("target", 11)} '
                     f'attempt {h.get("attempt")}: {pct}%</span>')
    return f'<div class="icc-attempts">{"".join(chips)}</div>'


def ledger(shared: list[str], withheld: list[str]) -> str:
    s = "".join(f"<li>{esc(x)}</li>" for x in shared) or "<li>—</li>"
    w = "".join(f"<li>{esc(x)}</li>" for x in withheld) or "<li>—</li>"
    return f"""
    <div class="icc-ledger">
      <div class="icc-card icc-soft"><span class="h" style="color:var(--primary-deep)">
        {icon('send', 13)} This note shares</span><ul>{s}</ul></div>
      <div class="icc-card icc-soft"><span class="h" style="color:var(--success)">
        {icon('lock', 13)} Kept private</span><ul>{w}</ul></div>
    </div>"""


def concept_ledger(covered: list[str], missing: list[str]) -> str:
    c = "".join(f"<li>{esc(x)}</li>" for x in covered) or "<li>—</li>"
    m = "".join(f"<li>{esc(x)}</li>" for x in missing) or "<li>—</li>"
    return f"""
    <div class="icc-ledger">
      <div class="icc-card icc-soft"><span class="h" style="color:var(--success)">
        {icon('check', 13)} You explained</span><ul>{c}</ul></div>
      <div class="icc-card icc-soft"><span class="h" style="color:var(--warn)">
        {icon('target', 13)} Still to cover</span><ul>{m}</ul></div>
    </div>"""


def learner_card(lid: str, status: str, rationale: str, action: str) -> str:
    kind = {"ready": "ok", "on_track": "info",
            "at_risk": "warn", "needs_support": "bad"}.get(status, "")
    icon_name = {"ready": "check", "on_track": "trend",
                 "at_risk": "alert", "needs_support": "user"}.get(status, "user")
    return f"""
    <div class="icc-card icc-soft" style="padding:12px 14px">
      <span class="icc-badge {kind}">{icon(icon_name, 12)} {esc(status.replace('_', ' '))}</span>
      <span class="icc-agent" style="margin-left:8px">{esc(lid)}</span>
      <div class="icc-did" style="margin-top:5px">{esc(rationale)}</div>
      <div class="icc-sub" style="margin:2px 0 0">Action: {esc(action)}</div>
    </div>"""
