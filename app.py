"""Streamlit UI for the Epic note-fetcher + LLM-as-jury POC.

Run:  streamlit run app.py
Jury mode follows the environment (JURY_MODE=stub default, or live + keys).

V1 sections:
  - Summary Explorer (this file, built out): browse ingested summaries (cases),
    see the jury verdict + disagreement, view reference notes, and create a new
    summary from note IDs and/or pasted note text.
  - Jury Config, Live Judge: placeholders (roadmap 3b / 3c).
"""

import re
import streamlit as st

import service

st.set_page_config(page_title="Jury Explorer", layout="wide")


# ------------------------------------------------------------- helpers
def _score_color(score, scale_max=5):
    if score is None:
        return "#9e9e9e"
    frac = score / scale_max
    if frac >= 0.8:
        return "#2e7d32"  # green
    if frac >= 0.5:
        return "#f9a825"  # amber
    return "#c62828"      # red


_AGREEMENT_BADGE = {"unanimous": "✅ unanimous", "minor": "🟡 minor split", "split": "🔴 split"}


def _badge(text, color):
    return (f"<span style='background:{color};color:white;padding:2px 8px;"
            f"border-radius:10px;font-size:0.85em;'>{text}</span>")


def _split_ids(raw):
    return [t for t in re.split(r"[\s,]+", raw or "") if t.strip()]


def _split_pasted(raw):
    chunks = re.split(r"(?m)^\s*---\s*$", raw or "")
    return [c.strip() for c in chunks if c.strip()]


# ------------------------------------------------------------- header
def render_header():
    info = service.panel_info()
    live = info["mode"] == "live"
    dot = "🟢 live" if live else "🟡 stub"
    members = ", ".join(info["members"]) if live else "offline stub panel"
    st.markdown(f"### ⚖️ Jury Explorer &nbsp;&nbsp; <small>{dot} · {members}</small>",
                unsafe_allow_html=True)
    if not live:
        st.caption("Stub mode: scores are deterministic placeholders. Set "
                   "JURY_MODE=live (+ API keys) for real judgments.")


# --------------------------------------------------------- new summary
def render_new_summary():
    with st.expander("➕ New summary", expanded=False):
        st.caption("Create a case from a summary plus reference notes — by Epic "
                   "note ID, pasted note text, or a mix.")
        with st.form("new_summary", clear_on_submit=False):
            case_id = st.text_input("Case ID", placeholder="(auto-generated if blank)")
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
                    summary_text=summary,
                    case_id=case_id,
                    note_ids=_split_ids(note_ids),
                    pasted_notes=[{"text": t} for t in _split_pasted(pasted)],
                )
                st.session_state.selected_case = case["case_id"]
                st.success(f"Created case '{case['case_id']}'.")
                st.rerun()
            except Exception as exc:
                st.error(f"Could not create case: {exc}")


# --------------------------------------------------------- verdict view
def render_verdict(case):
    verdict = service.load_verdict(case["case_id"])
    run = st.button("▶︎ Run jury" if not verdict else "↻ Re-run jury", key="run_jury")
    if run:
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
    st.markdown(f"**Overall:** "
                + _badge(f"{overall} / 5", _score_color(overall)), unsafe_allow_html=True)
    if verdict.get("split_dimensions"):
        st.caption(f"⚠ jurors split on: {', '.join(verdict['split_dimensions'])}")

    for d in verdict["dimensions"]:
        mean = d.get("mean_score")
        cols = st.columns([3, 2, 3])
        cols[0].markdown(f"**{d['dimension']}**  \n<small>{d.get('description','')}</small>",
                         unsafe_allow_html=True)
        cols[1].markdown(_badge(f"{mean} / {d.get('scale','1-5')}", _score_color(mean)),
                         unsafe_allow_html=True)
        agree = d.get("agreement")
        cols[2].markdown(f"{_AGREEMENT_BADGE.get(agree, agree or '')} "
                         f"<small>(spread {d.get('score_spread')})</small>",
                         unsafe_allow_html=True)
        with st.expander(f"jurors & rationale — {d['dimension']}"):
            for jv in d.get("verdicts", []):
                if jv.get("error"):
                    st.markdown(f"- **{jv.get('member')}**: ⚠️ error — {jv['error']}")
                    continue
                st.markdown(f"- **{jv.get('member')}** — score **{jv.get('score')}**")
                st.markdown(f"  <small>{jv.get('rationale','')}</small>", unsafe_allow_html=True)
            issues = d.get("issues", [])
            if issues:
                st.markdown("**flagged issues**")
                for it in issues:
                    st.markdown(f"- <small>[{it.get('member')}] {it.get('issue')}</small>",
                                unsafe_allow_html=True)


# ----------------------------------------------------- reference notes
def render_reference_notes(case):
    notes, missing = service.case_notes(case)
    by_id = {n["document_reference_id"]: n for n in notes}
    st.markdown(f"#### Reference notes ({len(case.get('source_note_ids', []))})")
    for nid in case.get("source_note_ids", []):
        note = by_id.get(nid)
        if not note:
            st.markdown(f"- `{nid}` — *not fetched yet (needs Epic creds; run the jury to fetch)*")
            continue
        md = note.get("metadata", {})
        manual = note.get("resolved_via") == "manual"
        label = f"{'📝 ' if manual else ''}{nid} · {md.get('type') or '—'} · {md.get('date') or '—'}"
        with st.expander(label):
            st.text(note.get("combined_text") or "(empty)")
            if not manual and note.get("raw_document_reference"):
                with st.expander("raw FHIR DocumentReference"):
                    st.json(note["raw_document_reference"])


# -------------------------------------------------------- explorer page
def render_explorer():
    render_new_summary()
    cases_list = service.list_cases()
    if not cases_list:
        st.info("No summaries yet. Use **➕ New summary** to create one.")
        return

    ids = [c["case_id"] for c in cases_list]
    if st.session_state.get("selected_case") not in ids:
        st.session_state.selected_case = ids[0]

    left, right = st.columns([1, 2])
    with left:
        st.markdown("#### Ingested summaries")
        def _fmt(cid):
            c = next((x for x in cases_list if x["case_id"] == cid), None)
            score = c["overall"] if (c and c["judged"]) else "—"
            return f"{cid}   ·   {score}"
        st.session_state.selected_case = st.radio(
            "cases", ids, format_func=_fmt,
            index=ids.index(st.session_state.selected_case), label_visibility="collapsed",
        )

    with right:
        meta = next(x for x in cases_list if x["case_id"] == st.session_state.selected_case)
        case = service.load_case(meta["path"])
        summary = case.get("summary", {}) or {}
        st.markdown(f"#### {case['case_id']} "
                    f"<small>· source: {summary.get('source','—')}</small>", unsafe_allow_html=True)
        st.markdown("**Summary**")
        st.markdown(f"> {summary.get('text','')}")
        st.divider()
        render_verdict(case)
        st.divider()
        render_reference_notes(case)


# --------------------------------------------------------------- main
def main():
    render_header()
    section = st.sidebar.radio(
        "Section", ["Summary Explorer", "Jury Config (soon)", "Live Judge (soon)"]
    )
    st.sidebar.caption("Roadmap V1 — 3a built; 3b/3c next.")
    if section == "Summary Explorer":
        render_explorer()
    else:
        st.info(f"**{section}** — coming next in the roadmap.")


if __name__ == "__main__":
    main()
