"""Styling and HTML components for the Streamlit interface.

All dataset text is escaped before it is placed in HTML. The HTML strings are
built without leading indentation because Streamlit's Markdown treats indented
lines as code blocks.
"""
from html import escape

import streamlit as st

from utils.validators import CORE_FIELDS, is_empty

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Sora:wght@500;700&family=Source+Sans+3:wght@400;600&display=swap');
:root{--bg:#0B1020;--surface:#121A33;--surface2:#18223F;--line:#263259;--text:#E8ECFA;--muted:#A3AED4;
--purple:#8B5CF6;--blue:#38BDF8;--ok:#34D399;--warn:#FBBF24;--bad:#F87171;}
.stApp{background:radial-gradient(1200px 500px at 85% -10%,rgba(139,92,246,.18),transparent 60%),var(--bg);}
html,body,[class*="css"],.stMarkdown,p,label{font-family:'Source Sans 3','Segoe UI',sans-serif;}
h1,h2,h3,.ui-title{font-family:'Sora','Segoe UI',sans-serif;}
.block-container{max-width:1100px;padding-top:2rem;}
.ui-hero{padding:1.2rem 0 .6rem 0;}
.ui-title{font-size:clamp(2rem,5vw,3.4rem);font-weight:700;letter-spacing:.01em;line-height:1.1;margin:0;
background:linear-gradient(90deg,#C4B5FD,#8B5CF6 45%,#38BDF8);-webkit-background-clip:text;background-clip:text;color:transparent;}
.ui-tagline{font-family:'Sora',sans-serif;font-size:1.35rem;color:var(--text);margin:.6rem 0 .3rem 0;}
.ui-sub{color:var(--muted);max-width:44rem;font-size:1.05rem;line-height:1.55;margin:0 0 1rem 0;}
.ui-steps{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:.8rem;margin:.6rem 0 1rem 0;}
.ui-step{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:.8rem 1rem;color:var(--muted);font-size:.95rem;line-height:1.45;}
.ui-step b{color:var(--text);display:block;margin-bottom:.15rem;}
.ui-chips{display:flex;flex-wrap:wrap;gap:.5rem;margin:.4rem 0 1rem 0;}
.ui-chip{border:1px solid var(--line);background:var(--surface);color:var(--muted);border-radius:999px;padding:.2rem .75rem;font-size:.85rem;}
.ui-card{background:var(--surface);border:1px solid var(--line);border-left:3px solid var(--purple);border-radius:12px;padding:1.1rem 1.25rem;margin:0 0 1rem 0;}
.ui-card h3{margin:0 0 .35rem 0;font-size:1.15rem;color:var(--text);}
.ui-card p{color:var(--text);line-height:1.55;margin:.35rem 0;}
.ui-badges{display:flex;flex-wrap:wrap;gap:.4rem;margin:.2rem 0 .5rem 0;}
.ui-badge{font-size:.8rem;padding:.12rem .6rem;border-radius:999px;border:1px solid var(--line);color:var(--muted);background:var(--surface2);}
.ui-badge.ok{color:var(--ok);border-color:rgba(52,211,153,.45);}
.ui-badge.warn{color:var(--warn);border-color:rgba(251,191,36,.45);}
.ui-badge.bad{color:var(--bad);border-color:rgba(248,113,113,.45);}
.ui-badge.blue{color:var(--blue);border-color:rgba(56,189,248,.45);}
.ui-badge.purple{color:#C4B5FD;border-color:rgba(139,92,246,.55);}
.ui-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:.6rem 1.2rem;margin:.6rem 0;}
.ui-field span{display:block;font-size:.8rem;color:var(--muted);margin-bottom:.1rem;}
.ui-field div{color:var(--text);font-size:.95rem;line-height:1.4;}
.ui-na{color:var(--muted)!important;font-style:italic;}
.ui-card a,.ui-table a{color:var(--blue);}
.ui-note{background:var(--surface2);border:1px dashed var(--line);border-radius:10px;padding:.6rem .8rem;color:var(--muted);font-size:.92rem;margin:.5rem 0;}
.ui-note b{color:var(--text);}
.ui-list{margin:.2rem 0 .2rem 1.1rem;padding:0;color:var(--text);font-size:.93rem;line-height:1.5;}
.ui-table-wrap{overflow-x:auto;}
.ui-table{border-collapse:collapse;width:100%;min-width:560px;}
.ui-table th,.ui-table td{border:1px solid var(--line);padding:.6rem .75rem;vertical-align:top;text-align:left;font-size:.93rem;color:var(--text);}
.ui-table th{background:var(--surface2);}
.ui-table td:first-child{background:var(--surface);color:var(--muted);white-space:nowrap;}
.ui-bar{height:6px;background:var(--line);border-radius:4px;overflow:hidden;margin:.3rem 0 .5rem 0;}
.ui-bar>div{height:100%;background:linear-gradient(90deg,var(--purple),var(--blue));}
button:focus-visible,a:focus-visible,[role="tab"]:focus-visible{outline:2px solid var(--blue)!important;outline-offset:2px;}
@media (prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important;}}
</style>
"""

STATUS_TONE = {"verified": ("Verified", "ok"), "partially_verified": ("Partly verified", "warn"),
               "unverified": ("Unverified", "bad")}
NA_TEXT = "Not recorded in our dataset"


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def badge(text: str, tone: str = "") -> str:
    return f'<span class="ui-badge {tone}">{escape(str(text))}</span>'


def status_badge(status: str) -> str:
    label, tone = STATUS_TONE.get(status, ("Unknown", "bad"))
    return badge(label, tone)


def _value_html(value, unavailable: str = NA_TEXT) -> str:
    if is_empty(value):
        return f'<span class="ui-na">{escape(unavailable)}</span>'
    if isinstance(value, (list, tuple)):
        return escape(", ".join(str(v) for v in value))
    return escape(str(value))


def _field(label: str, value, unavailable: str = NA_TEXT) -> str:
    inner = _value_html(value, unavailable)
    return f'<div class="ui-field"><span>{escape(label)}</span><div>{inner}</div></div>'


def _bullets(items) -> str:
    return '<ul class="ui-list">' + "".join(f"<li>{escape(str(i))}</li>" for i in items) + "</ul>"


def render_hero(records: list) -> None:
    total = len(records)
    verified = sum(1 for r in records if r.get("verification_status") == "verified")
    partial = sum(1 for r in records if r.get("verification_status") == "partially_verified")
    st.markdown(
        '<div class="ui-hero"><h1 class="ui-title">THE UNSEEN INDIA</h1>'
        '<div class="ui-tagline">Discover opportunities hiding in plain sight.</div>'
        '<p class="ui-sub">Find relevant scholarships, skill programmes, public services, and learning '
        'opportunities you may never have thought to search for.</p>'
        '<div class="ui-chips">'
        f'<span class="ui-chip">{total} records in the dataset</span>'
        f'<span class="ui-chip">{verified} fully verified</span>'
        f'<span class="ui-chip">{partial} partly verified</span>'
        '<span class="ui-chip">Searches this dataset only, not the live web</span></div>'
        '<div class="ui-steps">'
        '<div class="ui-step"><b>1. Describe yourself</b>Say who you are and what you want in your own words.</div>'
        '<div class="ui-step"><b>2. We match against real records</b>Transparent rules rank records and show why each one matched.</div>'
        '<div class="ui-step"><b>3. See what is still unknown</b>Every result lists missing details and links to its official source.</div>'
        '</div></div>', unsafe_allow_html=True)


def notice(title: str, text: str = "") -> str:
    body = f"<b>{escape(title)}</b>" + (f" {escape(text)}" if text else "")
    return f'<div class="ui-note">{body}</div>'


def opportunity_card(record: dict, reasons=None, missing_fields=None, strength: str = "",
                     score=None, show_gaps: bool = True) -> str:
    """HTML for one opportunity (used by Radar, Connections and Assistant)."""
    badges = [badge(record.get("category", ""), "purple"),
              badge("Portal reference" if record.get("record_type") == "portal_reference" else "Programme", "blue"),
              status_badge(record.get("verification_status", "unverified"))]
    if strength:
        badges.append(badge(strength, "ok" if strength.startswith("Strong") else "warn"))
    parts = [f'<div class="ui-card"><h3>{escape(record["name"])}</h3>',
             f'<div class="ui-badges">{"".join(badges)}</div>']
    if score is not None:
        parts.append(f'<div class="ui-bar"><div style="width:{min(100, int(score * 10))}%"></div></div>')
    parts.append(f'<p>{escape(record["description"])}</p><div class="ui-grid">')
    parts += [
        _field("Who it may suit", record.get("target_audience")),
        _field("Eligibility", record.get("eligibility")),
        _field("Location", record.get("state_or_location")),
        _field("Benefits", record.get("benefits")),
        _field("Deadline", record.get("deadline")),
        _field("Required documents", record.get("required_documents")),
    ]
    last = record.get("last_verified") or "Not verified yet"
    url = escape(record["official_source_url"], quote=True)
    parts.append(_field("Last verified", last))
    parts.append('<div class="ui-field"><span>Official source</span><div>'
                 f'{escape(record["source_name"])}: <a href="{url}" target="_blank" rel="noopener noreferrer">open source</a>'
                 '</div></div></div>')
    if record.get("verification_note"):
        parts.append(f'<div class="ui-note"><b>Verification note:</b> {escape(record["verification_note"])}</div>')
    if reasons:
        parts.append("<p><b>Why it matched</b></p>" + _bullets(reasons))
    if show_gaps:
        gaps = [CORE_FIELDS[f] + ": not recorded" for f in (missing_fields or [])]
        gaps += list(record.get("missing_information") or [])
        if gaps:
            parts.append("<p><b>Still missing or unconfirmed</b></p>" + _bullets(gaps))
    parts.append("</div>")
    return "".join(parts)


def compare_table(records: list) -> str:
    """Side-by-side comparison; unavailable details are marked clearly."""
    rows = [("Category", "category"), ("Type", "record_type"), ("Who it may suit", "target_audience"),
            ("Eligibility", "eligibility"), ("Location", "state_or_location"), ("Benefits", "benefits"),
            ("Deadline", "deadline"), ("Required documents", "required_documents"),
            ("Verification status", "verification_status"), ("Last verified", "last_verified")]
    head = "<tr><th></th>" + "".join(f"<th>{escape(r['name'])}</th>" for r in records) + "</tr>"
    body = ""
    for label, key in rows:
        cells = ""
        for rec in records:
            value = rec.get(key)
            if key == "verification_status":
                value = STATUS_TONE.get(value, ("Unknown", ""))[0]
            if key == "record_type":
                value = "Portal reference" if value == "portal_reference" else "Programme"
            cells += f"<td>{_value_html(value, 'Not available')}</td>"
        body += f"<tr><td>{escape(label)}</td>{cells}</tr>"
    links = "".join(
        f'<td><a href="{escape(r["official_source_url"], quote=True)}" target="_blank" rel="noopener noreferrer">'
        f'{escape(r["source_name"])}</a></td>' for r in records)
    body += f"<tr><td>Official source</td>{links}</tr>"
    return f'<div class="ui-table-wrap"><table class="ui-table">{head}{body}</table></div>'
