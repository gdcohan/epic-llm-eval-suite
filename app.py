"""Streamlit UI for the Epic note-fetcher + LLM-as-jury POC.

Run:  streamlit run app.py
Jury mode follows the environment (JURY_MODE=stub default, or live + keys).

Sections (top tabs): Summary Explorer (built), Jury Config / Live Judge (next).
The service layer (service.py) holds all logic, so the UI stays swappable.
"""

import re
import html
import uuid
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

import service
import config

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


def _harm_badge(f):
    """Severity-colored harm badge (always includes the severity word) for a finding."""
    sev = (f.get("harm_severity") or "").strip().lower()
    if not sev:
        return ""
    color = {"severe": "#c62828", "moderate": "#f9a825", "low": "#6c757d"}.get(sev, "#6c757d")
    cat = f.get("harm_category")
    label = sev + (f" · {cat}" if cat else "")
    return " " + _badge(label, color)


def _issue_findings(dimension):
    return [f for f in dimension.get("findings", []) if f.get("type") == "issue"]


# ------------------------------------------------------------- overview
_SEV_DOT = {"severe": "🔴", "moderate": "🟠", "low": "⚪"}
_SEV_RANK = {"severe": 0, "moderate": 1, "low": 2}


def _harm_drilldown(hm, cats):
    """Clickable chips for each non-zero harm cell → an inline list of those issue
    findings (case + quotes + harm badge), each with an ↪ jump into the Explorer
    with the cited note expanded + highlighted. The matrix counts cases per cell;
    this list is per finding, so counts can differ (stated honestly in the header)."""
    cells = [(cat, sev, hm[cat][sev]) for cat in cats for sev in ("severe", "moderate", "low")
             if hm.get(cat, {}).get(sev)]
    if not cells:
        return
    cells.sort(key=lambda x: (_SEV_RANK[x[1]], cats.index(x[0])))
    st.caption("Drill into a harm cell:")
    ncol = 4
    for i in range(0, len(cells), ncol):
        cols = st.columns(ncol)
        for j, (cat, sev, cnt) in enumerate(cells[i:i + ncol]):
            if cols[j].button(f"{_SEV_DOT[sev]} {cat} · {sev} ({cnt})",
                              key=f"harmchip_{sev}_{cat}", width="stretch"):
                st.session_state.harm_drill = [cat, sev]
                st.rerun()

    drill = st.session_state.get("harm_drill")
    if not drill:
        return
    cat, sev = drill
    if not hm.get(cat, {}).get(sev):  # cell vanished (data changed) — drop the stale drill
        st.session_state.pop("harm_drill", None)
        return
    findings = service.findings_by_harm(cat, sev)
    ncases = len({f["case_id"] for f in findings})
    head, clear = st.columns([5, 1])
    head.markdown(f"{_SEV_DOT[sev]} **{sev} · {cat}** — "
                  f"{len(findings)} issue(s) across {ncases} case(s)")
    if clear.button("× close", key="harm_drill_close"):
        st.session_state.pop("harm_drill", None)
        st.rerun()
    for idx, f in enumerate(findings):
        c0, c1 = st.columns([9, 1])
        with c0:
            line = (f"<small><b>{html.escape(f['case_id'])}</b> · {f.get('dimension', '')}"
                    f"{_harm_badge(f)}<br>⚠ {html.escape(f.get('explanation') or '')}")
            if f.get("summary_quote"):
                line += f"<br>· summary: “<i>{html.escape(f['summary_quote'])}</i>”"
            if f.get("note_quote"):
                line += (f"<br>· note <code>{html.escape(str(f.get('note_id')))}</code>: "
                         f"“<i>{html.escape(f['note_quote'])}</i>”")
            line += f" <span style='color:#888'>[{html.escape(str(f.get('member')))}]</span></small>"
            st.markdown(line, unsafe_allow_html=True)
        with c1:
            st.button("↪", key=f"harmopen_{idx}", help="open in Explorer",
                      on_click=_open_finding_in_explorer,
                      args=(f["case_id"], f.get("note_id"), f.get("note_quote")))


def render_overview():
    s = service.overview_stats()
    k = s["kpis"]
    cols = st.columns(6)
    cols[0].metric("Cases", k["cases"])
    cols[1].metric("Judged", k["judged"])
    cols[2].metric("Avg overall", "—" if k["avg_overall"] is None else k["avg_overall"])
    with cols[3]:
        st.metric("With issues", k["with_issues"])
        if st.button("show these »", key="filter_issues", disabled=not k["with_issues"]):
            st.session_state.issues_only = True
            st.session_state.pop("severe_only", None)
            st.session_state.scroll_to_scorecard = True
            st.rerun()
    with cols[4]:
        st.metric("⚠ Severe", k.get("severe_cases", 0))
        if st.button("show these »", key="filter_severe", disabled=not k.get("severe_cases")):
            st.session_state.severe_only = True
            st.session_state.pop("issues_only", None)
            st.session_state.scroll_to_scorecard = True
            st.rerun()
    cols[5].metric("Juror splits", k["splits"])

    if k["judged"] == 0:
        st.info("No judged cases yet — judge some in the Summary Explorer.")
        return

    c1, c2 = st.columns(2)
    with c1:
        st.caption("Avg score by dimension")
        if s["avg_by_dim"]:
            st.bar_chart(pd.DataFrame({"avg score": s["avg_by_dim"]}))
    with c2:
        st.caption("Issues by dimension")
        if s["issues_by_dim"]:
            st.bar_chart(pd.DataFrame({"issues": s["issues_by_dim"]}))

    st.caption("Harm matrix — # cases with ≥1 issue by category × severity")
    hm = s.get("harm_matrix") or {}
    if not hm:
        st.caption("No harm-tagged findings yet (harm appears on live jury runs).")
    else:
        sev_cols = ["low", "moderate", "severe"]
        cats = ([c for c in service.HARM_CATEGORIES if c in hm]
                + [c for c in hm if c not in service.HARM_CATEGORIES])
        hrows = [{"category": cat, **{sv: hm.get(cat, {}).get(sv, 0) for sv in sev_cols}} for cat in cats]
        hstyler = pd.DataFrame(hrows)[["category"] + sev_cols].style
        for sv, color in [("low", "#6c757d"), ("moderate", "#f9a825"), ("severe", "#c62828")]:
            hstyler = hstyler.map(
                lambda v, c=color: f"background-color:{c}; color:white"
                if isinstance(v, (int, float)) and v > 0 else "", subset=[sv])
        st.dataframe(hstyler, hide_index=True, width="stretch")
        _harm_drilldown(hm, cats)

    dims = s["dims"]
    col_order = ["case", "overall"] + dims + ["issues", "max_harm", "adjudicated", "agreement"]
    df = pd.DataFrame(s["rows"])
    for col in col_order:
        if col not in df.columns:
            df[col] = None
    df = df[col_order]
    df["max_harm"] = df["max_harm"].fillna("").replace("", "—")

    # One-shot: after a "show these »" click the scorecard is below the fold, so
    # scroll it into view. Injected here (just above the table) so the component's
    # own iframe is the scroll target — no dependence on Streamlit element ids.
    if st.session_state.pop("scroll_to_scorecard", False):
        components.html(
            "<script>const f = window.frameElement;"
            "if (f) f.scrollIntoView({behavior: 'smooth', block: 'start'});</script>",
            height=0,
        )

    issues_only = st.session_state.get("issues_only", False)
    severe_only = st.session_state.get("severe_only", False)
    if severe_only:
        df_display = df[df["max_harm"] == "severe"]
        head, clear = st.columns([4, 1])
        head.caption(f"Case scorecard — only the {len(df_display)} case(s) with a severe issue")
        if clear.button("× show all"):
            st.session_state.pop("severe_only", None)
            st.rerun()
    elif issues_only:
        df_display = df[pd.to_numeric(df["issues"], errors="coerce").fillna(0) > 0]
        head, clear = st.columns([4, 1])
        head.caption(f"Case scorecard — only the {len(df_display)} case(s) with issues")
        if clear.button("× show all"):
            st.session_state.pop("issues_only", None)
            st.rerun()
    else:
        df_display = df
        st.caption("Case scorecard (lower = redder; sort any column; click a row to open it)")

    score_cols = ["overall"] + dims

    def _style(val):
        if not isinstance(val, (int, float)) or pd.isna(val):
            return ""
        return f"background-color: {_score_color(val)}; color: white"

    def _harm_style(val):
        c = {"severe": "#c62828", "moderate": "#f9a825", "low": "#6c757d"}.get(val)
        return f"background-color: {c}; color: white" if c else ""

    styler = df_display.style
    styler = styler.map(_style, subset=score_cols) if hasattr(styler, "map") \
        else styler.applymap(_style, subset=score_cols)
    if hasattr(styler, "map"):
        styler = styler.map(_harm_style, subset=["max_harm"])
    styler = styler.format(precision=2)

    event = st.dataframe(styler, hide_index=True, width="stretch",
                         on_select="rerun", selection_mode="single-row", key="scorecard")
    sel_rows = []
    try:
        sel_rows = list(event.selection.rows)
    except Exception:
        try:
            sel_rows = list(event["selection"]["rows"])
        except Exception:
            sel_rows = []
    if sel_rows:
        st.session_state.selected_case = df_display.iloc[sel_rows[0]]["case"]
        st.session_state.nav = "Summary Explorer"
        st.session_state.pop("scorecard", None)  # clear selection so we don't bounce back
        st.rerun()


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


def _open_finding_in_explorer(case_id, note_id, quote):
    """Jump from an Overview drill-down to the case in the Explorer, with the
    cited note expanded + highlighted (reuses the focus-note plumbing)."""
    st.session_state.selected_case = case_id
    st.session_state.nav = "Summary Explorer"
    if note_id and quote:
        st.session_state.focus_note_id = note_id
        st.session_state.focus_quote = quote
    st.session_state.pop("scorecard", None)  # avoid a stale scorecard selection bouncing us


def _toggle_finding_label(case_id, key, label, meta):
    cur = (service.get_adjudication(case_id) or {}).get("finding_labels", {}).get(key, {}).get("label")
    service.set_finding_label(case_id, key, None if cur == label else label, meta)


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

    adj = service.get_adjudication(case["case_id"]) or {}
    adj_dims = adj.get("dimensions", {})
    adj_rationales = adj.get("rationales", {})
    finding_labels = adj.get("finding_labels", {})
    adjudicator = st.text_input("Adjudicator", value=adj.get("adjudicator", ""),
                                key=f"adjudicator_{case['case_id']}",
                                placeholder="your name (for the overrides below)")

    for d in verdict["dimensions"]:
        score_badge = _badge(f"{d.get('mean_score')} / {d.get('scale')}", _score_color(d.get("mean_score")))
        agree_badge = _AGREEMENT_BADGE.get(d.get("agreement"), "")
        st.markdown(
            f"**{d['dimension']}** &nbsp; {score_badge} &nbsp; {agree_badge} "
            f"<small>(spread {d.get('score_spread')})</small>",
            unsafe_allow_html=True,
        )
        if d["dimension"] in adj_dims:
            st.markdown(_badge(f"✎ adjudicated {adj_dims[d['dimension']]}", "#1565c0")
                        + f" <small>(jury {d.get('mean_score')})</small>", unsafe_allow_html=True)
            if adj_rationales.get(d["dimension"]):
                st.caption(f"✎ {adj_rationales[d['dimension']]}")
        # Each juror: score + one-line synopsis, with that juror's own issues
        # nested directly beneath it (rather than all jurors then all issues).
        issues = _issue_findings(d)
        issues_by_member = {}
        for f in issues:
            issues_by_member.setdefault(f.get("member"), []).append(f)
        if issues:
            st.markdown("<small>**issues** — mark each ✓ valid / ✗ false alarm</small>",
                        unsafe_allow_html=True)

        def _render_finding(f, idx):
            fkey = service.finding_key(d["dimension"], f.get("member"),
                                       f.get("summary_quote"), f.get("note_quote"))
            cur_label = (finding_labels.get(fkey) or {}).get("label")
            tag = {"valid": " <b>✓</b>", "false_alarm": " <b>✗</b>"}.get(cur_label, "")
            cols = st.columns([7, 3])
            with cols[0]:
                line = f"<small>&emsp;⚠ {html.escape(f.get('explanation',''))}{tag}{_harm_badge(f)}"
                if f.get("summary_quote"):
                    line += f"<br>&emsp;· summary: “<i>{html.escape(f['summary_quote'])}</i>”"
                if f.get("note_quote"):
                    line += (f"<br>&emsp;· note <code>{html.escape(str(f.get('note_id')))}</code>: "
                             f"“<i>{html.escape(f['note_quote'])}</i>”")
                line += "</small>"
                st.markdown(line, unsafe_allow_html=True)
            with cols[1]:
                meta = {"dimension": d["dimension"], "member": f.get("member"),
                        "summary_quote": f.get("summary_quote"),
                        "note_quote": f.get("note_quote"), "note_id": f.get("note_id")}
                bc = st.columns(3)
                if f.get("note_id") and f.get("note_quote"):
                    bc[0].button("↪", key=f"src_{d['dimension']}_{idx}", help="show source note",
                                 on_click=_focus_note, args=(f["note_id"], f["note_quote"]))
                bc[1].button("✓", key=f"val_{d['dimension']}_{idx}", help="valid issue",
                             on_click=_toggle_finding_label,
                             args=(case["case_id"], fkey, "valid", meta))
                bc[2].button("✗", key=f"fa_{d['dimension']}_{idx}", help="false alarm",
                             on_click=_toggle_finding_label,
                             args=(case["case_id"], fkey, "false_alarm", meta))

        fi = 0
        seen_members = set()
        for v in d.get("verdicts", []):
            member = v.get("member")
            seen_members.add(member)
            if v.get("error"):
                st.markdown(f"- <small>**{member}**: ⚠️ {v['error']}</small>", unsafe_allow_html=True)
            else:
                st.markdown(f"- <small>**{member}** ({v.get('score')}): {v.get('synopsis','')}</small>",
                            unsafe_allow_html=True)
            for f in issues_by_member.get(member, []):
                _render_finding(f, fi)
                fi += 1
        # Defensive: surface any findings whose member had no verdict line.
        for member, fs in issues_by_member.items():
            if member in seen_members:
                continue
            st.markdown(f"- <small>**{member}**</small>", unsafe_allow_html=True)
            for f in fs:
                _render_finding(f, fi)
                fi += 1

        # Per-dimension human adjudication (override just this dimension).
        with st.expander(f"✎ adjudicate · {d['dimension']}"):
            with st.form(f"adj_{case['case_id']}_{d['dimension']}"):
                opts = ["— (use jury)", 1, 2, 3, 4, 5]
                cur = adj_dims.get(d["dimension"])
                idx = opts.index(cur) if cur in opts else 0
                choice = st.selectbox(f"final score (jury {d.get('mean_score')})", opts, index=idx,
                                      key=f"adjsel_{case['case_id']}_{d['dimension']}")
                rationale = st.text_input("rationale", value=adj_rationales.get(d["dimension"], ""),
                                          key=f"adjrat_{case['case_id']}_{d['dimension']}")
                if st.form_submit_button("Save"):
                    score = None if choice == "— (use jury)" else int(choice)
                    service.set_dimension_adjudication(
                        case["case_id"], d["dimension"], score, rationale, adjudicator)
                    st.success("Saved.")
                    st.rerun()


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
def _seed(items):
    out = []
    for it in items:
        it = dict(it)
        it["_id"] = uuid.uuid4().hex[:8]
        out.append(it)
    return out


def _render_dimensions():
    st.subheader("Dimensions")
    st.caption("Each dimension is one juror prompt. Toggle, edit, add, or remove — applies to the next run.")
    if "dim_edit" not in st.session_state:
        st.session_state.dim_edit = _seed(config.all_dimension_configs())
    for dim in st.session_state.dim_edit:
        _id = dim["_id"]
        suffix = "" if dim.get("enabled", True) else "  ·  (disabled)"
        with st.expander(f"{dim.get('name') or 'new dimension'}{suffix}", expanded=not dim.get("name")):
            dim["enabled"] = st.checkbox("enabled", value=dim.get("enabled", True), key=f"en_{_id}")
            dim["name"] = st.text_input("name", value=dim.get("name", ""), key=f"nm_{_id}")
            dim["description"] = st.text_input("description", value=dim.get("description", ""), key=f"ds_{_id}")
            dim["scale"] = st.text_input("scale", value=dim.get("scale", "1-5"), key=f"sc_{_id}")
            dim["prompt"] = st.text_area("prompt", value=dim.get("prompt", ""), height=200, key=f"pr_{_id}")
            if st.button("remove", key=f"rm_{_id}"):
                st.session_state.dim_edit = [x for x in st.session_state.dim_edit if x["_id"] != _id]
                st.rerun()
    a, b, c = st.columns(3)
    if a.button("➕ add dimension"):
        st.session_state.dim_edit.append({"_id": uuid.uuid4().hex[:8], "name": "", "description": "",
                                          "prompt": "", "scale": "1-5", "enabled": True})
        st.rerun()
    if b.button("💾 save dimensions"):
        config.save_dimensions([{k: v for k, v in d.items() if k != "_id"} for d in st.session_state.dim_edit])
        st.success(f"Saved — {len(config.active_dimensions())} active dimension(s).")
    if c.button("↺ reset dimensions"):
        config.reset_dimensions()
        st.session_state.pop("dim_edit", None)
        st.rerun()


def _render_personas():
    st.subheader("Personas")
    st.caption("Reviewer styles. The live jury = models × personas (one juror per pairing).")
    if "persona_edit" not in st.session_state:
        st.session_state.persona_edit = _seed(config.all_personas())
    for p in st.session_state.persona_edit:
        _id = p["_id"]
        with st.expander(f"{p.get('name') or 'new persona'}  ·  temp {p.get('temperature', 0.2)}",
                         expanded=not p.get("name")):
            p["name"] = st.text_input("name", value=p.get("name", ""), key=f"pn_{_id}")
            p["temperature"] = st.number_input("temperature", value=float(p.get("temperature", 0.2)),
                                               min_value=0.0, max_value=2.0, step=0.1, key=f"pt_{_id}")
            p["text"] = st.text_area("persona text (prepended to the prompt)",
                                     value=p.get("text", ""), height=80, key=f"px_{_id}")
            if st.button("remove", key=f"pr_{_id}"):
                st.session_state.persona_edit = [x for x in st.session_state.persona_edit if x["_id"] != _id]
                st.rerun()
    a, b, c = st.columns(3)
    if a.button("➕ add persona"):
        st.session_state.persona_edit.append({"_id": uuid.uuid4().hex[:8], "name": "", "temperature": 0.2, "text": ""})
        st.rerun()
    if b.button("💾 save personas"):
        config.save_personas([{k: v for k, v in p.items() if k != "_id"} for p in st.session_state.persona_edit])
        st.success("Saved personas.")
    if c.button("↺ reset personas"):
        config.reset_personas()
        st.session_state.pop("persona_edit", None)
        st.rerun()


def _render_models():
    st.subheader("Models")
    st.caption("One `provider:model` per line (providers: anthropic, openai, gemini). Live mode only.")
    txt = st.text_area("models", value="\n".join(f"{m['provider']}:{m['model']}" for m in config.all_models()),
                       height=90, label_visibility="collapsed")
    a, b = st.columns(2)
    if a.button("💾 save models"):
        models = []
        for line in txt.splitlines():
            parts = [x.strip() for x in line.split(":")]
            if parts and parts[0]:
                models.append({"provider": parts[0], "model": parts[1] if len(parts) > 1 else ""})
        config.save_models(models)
        st.success("Saved models.")
    if b.button("↺ reset models"):
        config.reset_models()
        st.rerun()


def _render_shared_text(title, caption, getter, saver, resetter, height):
    st.subheader(title)
    if caption:
        st.caption(caption)
    txt = st.text_area(title, value=getter(), height=height, label_visibility="collapsed")
    a, b = st.columns(2)
    if a.button(f"💾 save", key=f"save_{title}"):
        saver(txt)
        st.success("Saved.")
    if b.button("↺ reset", key=f"reset_{title}"):
        resetter()
        st.rerun()


def _render_panel_preview():
    st.subheader("Panel preview")
    panel = config.active_panel()
    n_dims = len(config.active_dimensions())
    info = service.panel_info()
    dot = "🟢 live" if info["mode"] == "live" else "🟡 stub"
    st.caption(f"{dot} · {len(panel)} juror(s): {', '.join(m.name for m in panel)}")
    st.caption(f"Calls per case ≈ jurors × dimensions = {len(panel)} × {n_dims} = **{len(panel) * n_dims}**")


def _render_show_prompt():
    st.subheader("Show the prompt")
    st.caption("Reflects the SAVED config (save your edits above to preview them).")
    dims = config.active_dimensions()
    personas = config.all_personas()
    if not dims:
        st.caption("Add a dimension with a prompt to preview it.")
        return
    dpick = st.selectbox("dimension", [d.name for d in dims])
    ppick = st.selectbox("persona", ["(none)"] + [p.get("name") or "unnamed" for p in personas])
    d = next(x for x in dims if x.name == dpick)
    persona_text = ""
    if ppick != "(none)":
        pp = next((p for p in personas if (p.get("name") or "unnamed") == ppick), None)
        persona_text = pp.get("text", "") if pp else ""
    contract = config.active_output_contract().replace("{scale}", str(d.scale))
    system = "\n\n".join(filter(None, [d.prompt, persona_text, config.active_source_guidance(), contract]))
    st.caption("Exactly what this juror gets as the system prompt (notes + summary are the user message):")
    st.code(system)


def render_jury_config():
    _render_dimensions()
    st.divider()
    _render_personas()
    st.divider()
    _render_models()
    st.divider()
    _render_shared_text(
        "Reconciliation guidance (shared)",
        "How jurors should reconcile notes that conflict (temporal, status/certainty, "
        "authority, specificity, repeated measures, clear error) before scoring.",
        config.active_source_guidance, config.save_source_guidance, config.reset_source_guidance, 260)
    st.divider()
    _render_shared_text(
        "Output contract (shared)",
        "⚠️ Load-bearing: the app parses `score` / `synopsis` / `findings` and uses the verbatim quotes "
        "for source-links. Keep those keys or scores/links break. Use `{scale}` as the score-range placeholder.",
        config.active_output_contract, config.save_output_contract, config.reset_output_contract, 220)
    st.divider()
    _render_panel_preview()
    st.divider()
    _render_show_prompt()


def _lj_focus(note_id, quote):
    st.session_state.lj_focus_id = note_id
    st.session_state.lj_focus_quote = quote


def _render_verdict_block(verdict, src_key, focus_cb):
    """Compact verdict: per-dimension scores + disagreement + source-linked issues.
    `focus_cb(note_id, quote)` is wired to each issue's source button."""
    overall = verdict.get("overall_score")
    st.markdown("**Verdict** &nbsp; overall " + _badge(f"{overall} / 5", _score_color(overall)),
                unsafe_allow_html=True)
    if verdict.get("split_dimensions"):
        st.caption(f"⚠ jurors split on: {', '.join(verdict['split_dimensions'])}")
    for d in verdict["dimensions"]:
        score_badge = _badge(f"{d.get('mean_score')} / {d.get('scale')}", _score_color(d.get("mean_score")))
        agree_badge = _AGREEMENT_BADGE.get(d.get("agreement"), "")
        st.markdown(f"**{d['dimension']}** &nbsp; {score_badge} &nbsp; {agree_badge} "
                    f"<small>(spread {d.get('score_spread')})</small>", unsafe_allow_html=True)
        for v in d.get("verdicts", []):
            if v.get("error"):
                st.markdown(f"- <small>**{v.get('member')}**: ⚠️ {v['error']}</small>", unsafe_allow_html=True)
            else:
                syn = v.get("synopsis") or ""
                st.markdown(f"- <small>**{v.get('member')}** ({v.get('score')}): {syn}</small>",
                            unsafe_allow_html=True)
        for i, f in enumerate(_issue_findings(d)):
            cols = st.columns([8, 2])
            with cols[0]:
                line = f"<small>⚠ {html.escape(f.get('explanation', ''))}{_harm_badge(f)}"
                if f.get("summary_quote"):
                    line += f"<br>· summary: “<i>{html.escape(f['summary_quote'])}</i>”"
                if f.get("note_quote"):
                    line += (f"<br>· note <code>{html.escape(str(f.get('note_id')))}</code>: "
                             f"“<i>{html.escape(f['note_quote'])}</i>”")
                line += "</small>"
                st.markdown(line, unsafe_allow_html=True)
            with cols[1]:
                if f.get("note_id") and f.get("note_quote"):
                    st.button("↪ source", key=f"{src_key}_{d['dimension']}_{i}",
                              on_click=focus_cb, args=(f["note_id"], f["note_quote"]))


def render_live_judge():
    st.caption("Scratchpad — paste or fetch notes, type a summary, and judge it live. "
               "Edit the summary and re-judge to watch the scores move. Nothing is saved "
               "unless you Save as case.")
    left, right = st.columns(2)

    # Right column first so the notes inputs commit before Judge reads them, and so
    # a source-click (left) can focus/highlight a note here on the same rerun.
    with right:
        with st.container(height=760):
            st.markdown("#### Reference notes")
            st.text_area("Paste note text (separate multiple notes with a line of ---)",
                         height=180, key="lj_pasted")
            st.text_area("…or fetch by Epic note ID (space / comma / newline separated)",
                         height=70, key="lj_ids")
            st.caption("Pasted text works offline; fetched IDs need JURY_MODE=live + Epic creds.")
            notes = st.session_state.get("live_notes") or []
            if notes:
                st.markdown("**Resolved notes**")
            focus_id = st.session_state.get("lj_focus_id")
            focus_quote = st.session_state.get("lj_focus_quote")
            for n in notes:
                nid = n["document_reference_id"]
                focused = nid == focus_id
                with st.expander(f"{nid} · {n['metadata'].get('type') or '—'}", expanded=focused):
                    st.markdown(_highlight(n.get("combined_text") or "(empty)",
                                           [focus_quote] if focused else []), unsafe_allow_html=True)

    with left:
        with st.container(height=760):
            st.markdown("#### Summary")
            summary = st.text_area("Candidate summary", height=200, key="lj_summary",
                                   placeholder="Paste or type the summary to judge…")
            b1, b2 = st.columns([1, 1])
            if b1.button("⚖️ Judge", key="lj_judge"):
                try:
                    verdict, judged_notes, missing = service.judge_adhoc(
                        summary,
                        _split_ids(st.session_state.get("lj_ids", "")),
                        [{"text": t} for t in _split_pasted(st.session_state.get("lj_pasted", ""))],
                    )
                    st.session_state.live_verdict = verdict
                    st.session_state.live_notes = judged_notes
                    st.session_state.pop("lj_focus_id", None)
                    if missing:
                        st.warning(f"Could not fetch: {', '.join(missing)}")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))
            with b2.popover("💾 Save as case"):
                cid = st.text_input("case id", key="lj_save_id", placeholder="(auto if blank)")
                if st.button("save", key="lj_save_btn"):
                    try:
                        case = service.create_case(
                            summary_text=st.session_state.get("lj_summary", ""),
                            case_id=cid,
                            note_ids=_split_ids(st.session_state.get("lj_ids", "")),
                            pasted_notes=[{"text": t} for t in _split_pasted(st.session_state.get("lj_pasted", ""))],
                        )
                        st.success(f"Saved case '{case['case_id']}' — see Summary Explorer.")
                    except Exception as exc:
                        st.error(str(exc))

            verdict = st.session_state.get("live_verdict")
            if verdict:
                st.divider()
                _render_verdict_block(verdict, "ljsrc", _lj_focus)
            else:
                st.info("Enter a summary and notes, then **Judge**.")


def render_calibrate():
    st.subheader("Finding-level calibration (precision)")
    st.caption("Precision = of the jury's flagged findings you reviewed, how many were valid. "
               "Label findings in the Summary Explorer (✓ valid / ✗ false alarm). Recall "
               "(issues the jury missed) is a planned next step.")
    s = service.precision_stats()
    if not s["labeled_cases"]:
        st.info("No labeled findings yet. In the Summary Explorer, run the jury on a case "
                "and mark each issue ✓ valid / ✗ false alarm.")
        return

    cols = st.columns(3)
    cols[0].metric("Labeled cases", s["labeled_cases"])
    cols[1].metric("Labeled findings", s["total_labeled"])
    cols[2].metric("Overall precision", "—" if s["overall_precision"] is None else s["overall_precision"])

    rows = [{"dimension": d, **v} for d, v in s["per_dimension"].items()]
    if rows:
        df = pd.DataFrame(rows)[["dimension", "labeled", "validated", "false_alarms", "precision"]]
        st.dataframe(df, hide_index=True, width="stretch")

    if s["false_alarms"]:
        st.markdown("**False alarms** (jury flagged, you rejected) — the tuning signal")
        for fa in s["false_alarms"]:
            st.markdown(
                f"- <small>`{fa['case']}` · **{fa['dimension']}** — "
                f"summary: “{html.escape(fa.get('summary_quote') or '—')}” · "
                f"note: “{html.escape(fa.get('note_quote') or '—')}”</small>",
                unsafe_allow_html=True)


def main():
    render_header()
    NAV = ["Overview", "Summary Explorer", "Jury Config", "Live Judge", "Calibrate"]
    if st.session_state.get("nav") not in NAV:
        st.session_state.nav = "Overview"
    # Server-side section selector (not st.tabs) so we can switch programmatically
    # — e.g. clicking a row in the Overview scorecard jumps to the Explorer.
    choice = st.radio("section", NAV, index=NAV.index(st.session_state.nav),
                      horizontal=True, label_visibility="collapsed")
    st.session_state.nav = choice
    st.divider()
    if choice == "Overview":
        render_overview()
    elif choice == "Summary Explorer":
        render_explorer()
    elif choice == "Jury Config":
        render_jury_config()
    elif choice == "Live Judge":
        render_live_judge()
    else:
        render_calibrate()


if __name__ == "__main__":
    main()
