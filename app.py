"""Streamlit UI for the Epic note-fetcher + LLM-as-jury POC.

Run:  streamlit run app.py
Jury mode follows the environment (JURY_MODE=stub default, or live + keys).

Sections (top tabs): Summary Explorer (built), Jury Config / Live Judge (next).
The service layer (service.py) holds all logic, so the UI stays swappable.
"""

import re
import html
import streamlit as st

import service

st.set_page_config(page_title="Jury Explorer", layout="wide")


# ------------------------------------------------------------- helpers
def _score_color(score, scale_max=5):
    if score is None:
        return "#9e9e9e"
    frac = score / scale_max
    if frac >= 0.8:
        return "#2e7d32"
    if frac >= 0.5:
        return "#f9a825"
    return "#c62828"


_AGREEMENT_BADGE = {"unanimous": "✅ unanimous", "minor": "🟡 minor split", "split": "🔴 split"}


def _badge(text, color):
    return (f"<span style='background:{color};color:white;padding:1px 8px;"
            f"border-radius:10px;font-size:0.85em;white-space:nowrap;'>{text}</span>")


def _split_ids(raw):
    return [t for t in re.split(r"[\s,]+", raw or "") if t.strip()]


def _split_pasted(raw):
    return [c.strip() for c in re.split(r"(?m)^\s*---\s*$", raw or "") if c.strip()]


def _highlight(text, quotes, mark_color="#fff3a3"):
    """Escape text and wrap any verbatim quotes in a highlight, preserving layout."""
    esc = html.escape(text or "")
    for q in quotes:
        q = (q or "").strip()
        if not q:
            continue
        qe = html.escape(q)
        if qe in esc:
            esc = esc.replace(qe, f"<mark style='background:{mark_color}'>{qe}</mark>")
    return (f"<div style='white-space:pre-wrap;font-family:ui-monospace,monospace;"
            f"font-size:0.85em;line-height:1.4'>{esc}</div>")


def _issue_findings(dimension):
    return [f for f in dimension.get("findings", []) if f.get("type") == "issue"]


# --------------------------------------------------------------- header
def render_header():
    info = service.panel_info()
    live = info["mode"] == "live"
    dot = "🟢 live" if live else "🟡 stub"
    members = ", ".join(info["members"]) if live else "offline stub panel"
    st.markdown(f"### Jury Explorer &nbsp;&nbsp;<small>{dot} · {members}</small>",
                unsafe_allow_html=True)
    if not live:
        st.caption("Stub mode: deterministic placeholder scores. Set JURY_MODE=live "
                   "(+ API keys) for real judgments.")


# ----------------------------------------------------------- new summary
def render_new_summary():
    with st.expander("➕ New summary", expanded=False):
        # Placeholder for the future FHIR pathway: fetch a summary + its source
        # notes straight from Epic by id. Disabled until provenance is solved.
        st.text_input("Fetch a summary by Epic ID", disabled=True,
                      placeholder="coming soon — pull a GenAI summary and its source notes from Epic",
                      help="Future: resolve a summary and its reference notes via FHIR provenance.")
        st.caption("For now, build a case manually:")
        with st.form("new_summary", clear_on_submit=False):
            case_id = st.text_input("Case name", placeholder="(auto-generated if blank)")
            summary = st.text_area("Summary to evaluate", height=140,
                                   placeholder="Paste the GenAI summary…")
            c1, c2 = st.columns(2)
            with c1:
                note_ids = st.text_area("Reference note IDs", height=120,
                                        placeholder="exArV…  ex.6rD…\n(space / comma / newline separated)")
                st.caption("Fetched + cleaned via FHIR (needs live Epic creds).")
            with c2:
                pasted = st.text_area("…or paste note text", height=120,
                                      placeholder="paste raw note text\n---\nseparate multiple notes with a line of ---")
                st.caption("Escape hatch: no FHIR needed. Split notes with `---`.")
            submitted = st.form_submit_button("Create case")
        if submitted:
            try:
                case = service.create_case(
                    summary_text=summary, case_id=case_id,
                    note_ids=_split_ids(note_ids),
                    pasted_notes=[{"text": t} for t in _split_pasted(pasted)],
                )
                st.session_state.selected_case = case["case_id"]
                st.success(f"Created case '{case['case_id']}'.")
                st.rerun()
            except Exception as exc:
                st.error(f"Could not create case: {exc}")


# ---------------------------------------------------- summary + verdict
def _focus_note(note_id, quote):
    st.session_state.focus_note_id = note_id
    st.session_state.focus_quote = quote


def render_summary_and_verdict(case):
    summary = case.get("summary", {}) or {}
    verdict = service.load_verdict(case["case_id"])

    # Highlight, in the summary, every quote the jury flagged as an issue.
    flagged = []
    if verdict:
        for d in verdict["dimensions"]:
            flagged += [f.get("summary_quote") for f in _issue_findings(d)]

    st.markdown(f"#### {case['case_id']}  <small>· source: {summary.get('source','—')}</small>",
                unsafe_allow_html=True)
    st.markdown("**Summary**")
    st.markdown(_highlight(summary.get("text", ""), flagged), unsafe_allow_html=True)
    st.divider()

    label = "↻ Re-run jury" if verdict else "▶︎ Run jury"
    if st.button(label, key="run_jury"):
        with st.spinner("Polling the jury…"):
            try:
                verdict, missing = service.judge_case(case)
                if missing:
                    st.warning(f"Could not fetch {len(missing)} note(s): {', '.join(missing)}")
            except Exception as exc:
                st.error(f"Judging failed: {exc}")
                return

    if not verdict:
        st.info("Not judged yet — click **Run jury**.")
        return

    overall = verdict.get("overall_score")
    st.markdown("**Judge synopsis** &nbsp; overall " + _badge(f"{overall} / 5", _score_color(overall)),
                unsafe_allow_html=True)

    for d in verdict["dimensions"]:
        score_badge = _badge(f"{d.get('mean_score')} / {d.get('scale')}", _score_color(d.get("mean_score")))
        agree_badge = _AGREEMENT_BADGE.get(d.get("agreement"), "")
        st.markdown(
            f"**{d['dimension']}** &nbsp; {score_badge} &nbsp; {agree_badge} "
            f"<small>(spread {d.get('score_spread')})</small>",
            unsafe_allow_html=True,
        )
        # Structured dispute: each juror's score + one-line synopsis.
        for v in d.get("verdicts", []):
            if v.get("error"):
                st.markdown(f"- <small>**{v.get('member')}**: ⚠️ {v['error']}</small>", unsafe_allow_html=True)
            else:
                st.markdown(f"- <small>**{v.get('member')}** ({v.get('score')}): {v.get('synopsis','')}</small>",
                            unsafe_allow_html=True)
        # Structured findings with source links.
        issues = _issue_findings(d)
        if issues:
            st.markdown("<small>**issues**</small>", unsafe_allow_html=True)
        for i, f in enumerate(issues):
            cols = st.columns([8, 2])
            with cols[0]:
                line = f"<small>⚠ {html.escape(f.get('explanation',''))}"
                if f.get("summary_quote"):
                    line += f"<br>· summary: “<i>{html.escape(f['summary_quote'])}</i>”"
                if f.get("note_quote"):
                    line += (f"<br>· note <code>{html.escape(str(f.get('note_id')))}</code>: "
                             f"“<i>{html.escape(f['note_quote'])}</i>”")
                line += f" <span style='color:#888'>[{f.get('member')}]</span></small>"
                st.markdown(line, unsafe_allow_html=True)
            with cols[1]:
                if f.get("note_id") and f.get("note_quote"):
                    st.button("↪ source", key=f"src_{d['dimension']}_{i}",
                              on_click=_focus_note, args=(f["note_id"], f["note_quote"]))


# ----------------------------------------------------- reference notes
def render_reference_notes(case):
    notes, missing = service.case_notes(case)
    by_id = {n["document_reference_id"]: n for n in notes}
    focus_id = st.session_state.get("focus_note_id")
    focus_quote = st.session_state.get("focus_quote")

    st.markdown(f"#### Reference notes ({len(case.get('source_note_ids', []))})")
    for nid in case.get("source_note_ids", []):
        note = by_id.get(nid)
        if not note:
            st.markdown(f"- `{nid}` — *not fetched yet (needs Epic creds; run the jury to fetch)*")
            continue
        md = note.get("metadata", {})
        manual = note.get("resolved_via") == "manual"
        label = f"{'📝 ' if manual else ''}{nid} · {md.get('type') or '—'} · {md.get('date') or '—'}"
        focused = nid == focus_id
        with st.expander(label, expanded=focused):
            quotes = [focus_quote] if focused else []
            st.markdown(_highlight(note.get("combined_text") or "(empty)", quotes),
                        unsafe_allow_html=True)
            if not manual and note.get("raw_document_reference"):
                if st.checkbox("raw FHIR DocumentReference", key=f"raw_{nid}"):
                    st.json(note["raw_document_reference"])


# -------------------------------------------------------- explorer tab
def _fmt_factory(cases_list):
    def _fmt(cid):
        c = next((x for x in cases_list if x["case_id"] == cid), None)
        score = c["overall"] if (c and c["judged"]) else "—"
        return f"{cid}   ·   {score}"
    return _fmt


def render_explorer():
    cases_list = service.list_cases()
    with st.sidebar:
        st.markdown("#### Ingested summaries")
        if cases_list:
            ids = [c["case_id"] for c in cases_list]
            cur = st.session_state.get("selected_case")
            idx = ids.index(cur) if cur in ids else 0
            sel = st.radio("cases", ids, index=idx, format_func=_fmt_factory(cases_list),
                           label_visibility="collapsed")
            st.session_state.selected_case = sel
        else:
            st.caption("none yet — use ➕ New summary")

    render_new_summary()

    if not cases_list:
        st.info("No summaries yet. Use **➕ New summary** to create one.")
        return

    meta = next(x for x in cases_list if x["case_id"] == st.session_state.selected_case)
    case = service.load_case(meta["path"])
    col1, col2 = st.columns(2)
    with col1:
        with st.container(height=760):
            render_summary_and_verdict(case)
    with col2:
        with st.container(height=760):
            render_reference_notes(case)


# --------------------------------------------------------------- main
def main():
    render_header()
    tab_explorer, tab_config, tab_live = st.tabs(["Summary Explorer", "Jury Config", "Live Judge"])
    with tab_explorer:
        render_explorer()
    with tab_config:
        st.info("**Jury Config** — edit dimensions / prompts / panel. Roadmap 3b.")
    with tab_live:
        st.info("**Live Judge** — ad-hoc summary + notes, break-it-live. Roadmap 3c.")


if __name__ == "__main__":
    main()
