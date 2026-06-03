"""Turn a FHIR DocumentReference into a normalized note record.

Captures more than just the body text: every attachment (inline base64 *and*
url-linked Binary, across formats), linked/embedded content via `relatesTo`
(addenda/appends/replaces -- which matter a lot for clinical notes), and the
metadata you'd want for downstream eval (LOINC type, category, status, authors,
encounter, security labels).
"""

import base64
import re
from datetime import datetime, timezone
from html.parser import HTMLParser

# Content types we can confidently render as text.
_TEXTUAL_HINTS = ("text/", "+xml", "application/xml", "application/json", "application/rtf", "/rtf")

# Preferred representation when Epic returns the same note body in several formats
# (content[] entries are alternative representations of ONE document). Earlier =
# better. Plain text first; HTML strips far more cleanly than RTF.
_FORMAT_PREFERENCE = (
    "text/plain",
    "application/xhtml",
    "text/html",
    "text/xml",
    "application/xml",
    "text/rtf",
    "application/rtf",
)


def _is_textual(content_type):
    ct = (content_type or "").lower()
    return any(h in ct for h in _TEXTUAL_HINTS)


class _HTMLToText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._chunks = []

    def handle_data(self, data):
        self._chunks.append(data)

    def handle_starttag(self, tag, attrs):
        if tag in ("br", "p", "div", "li", "tr", "h1", "h2", "h3"):
            self._chunks.append("\n")

    def get_text(self):
        return "".join(self._chunks)


def _strip_html(text):
    try:
        parser = _HTMLToText()
        parser.feed(text)
        out = parser.get_text()
    except Exception:
        out = re.sub(r"<[^>]+>", "", text)  # crude fallback
    return re.sub(r"\n{3,}", "\n\n", out).strip()


def _strip_rtf(text):
    """Best-effort RTF -> text. (HTML is preferred when available, so RTF is a
    fallback.) Brace-aware: skips destination groups (font/color tables, etc.)
    whose contents shouldn't appear in the body, and ignores `\\*` destinations.
    """
    # Destination groups whose *contents* are metadata, not body text.
    skip_dests = {
        "fonttbl", "colortbl", "stylesheet", "info", "generator", "pict",
        "themedata", "colorschememapping", "latentstyles", "datastore",
        "listtable", "listoverridetable", "object", "operator",
    }
    out = []
    i, n, depth = 0, len(text), 0
    skip_at_depth = None  # depth at which the current skipped group opened

    while i < n:
        c = text[i]
        if c == "{":
            depth += 1
            rest = text[i + 1 :]
            star = rest.startswith("\\*")
            m = re.match(r"\\([a-zA-Z]+)", rest[2:] if star else rest)
            if skip_at_depth is None and (star or (m and m.group(1) in skip_dests)):
                skip_at_depth = depth
            i += 1
            continue
        if c == "}":
            if skip_at_depth == depth:
                skip_at_depth = None
            depth -= 1
            i += 1
            continue
        if skip_at_depth is not None:
            i += 1
            continue
        if c == "\\":
            # \'hh hex escape
            if re.match(r"\\'[0-9a-fA-F]{2}", text[i:]):
                out.append(" ")
                i += 4
                continue
            m = re.match(r"\\([a-zA-Z]+)(-?\d+)? ?", text[i:])
            if m:
                word = m.group(1)
                if word in ("par", "line", "sect"):
                    out.append("\n")
                elif word == "tab":
                    out.append("\t")
                i += m.end()
                continue
            if i + 1 < n:  # control symbol like \\ or \{
                out.append(text[i + 1])
                i += 2
                continue
        out.append(c)
        i += 1

    return re.sub(r"\n{3,}", "\n\n", "".join(out)).strip()


def _clean(content_type, text):
    """Markup-strip text based on its content type; passthrough for plain text."""
    if not text:
        return text
    ct = (content_type or "").lower()
    if "html" in ct or "xml" in ct:
        return _strip_html(text)
    if "rtf" in ct:
        return _strip_rtf(text)
    return text.strip()


def _format_rank(content_type):
    ct = (content_type or "").lower()
    for i, pref in enumerate(_FORMAT_PREFERENCE):
        if pref in ct:
            return i
    return len(_FORMAT_PREFERENCE)  # unknown formats sort last


def _norm(text):
    # Alphanumeric-only key: lets us recognize the same body across formats even
    # when punctuation/whitespace differs (e.g. an em-dash rendered as spaces in
    # one representation and "?" in another).
    return re.sub(r"[^a-z0-9]+", "", (text or "").lower())


def _combine_parts(content_parts):
    """Collapse alternative representations of the SAME body while keeping
    genuinely distinct content.

    Epic often returns one note body in several formats (e.g. HTML + RTF). Those
    are duplicates and we keep only the preferred format. But multiple content
    entries can also carry different content -- those we keep. Dedup is by text
    containment (after markup-stripping/normalizing), with format preference
    deciding which copy of a duplicate survives.
    """
    ranked = sorted(
        [p for p in content_parts if p.get("clean_text")],
        key=lambda p: _format_rank(p.get("content_type")),
    )
    accepted = []
    for part in ranked:
        norm = _norm(part["clean_text"])
        if not norm:
            continue
        if any(norm in _norm(a["clean_text"]) or _norm(a["clean_text"]) in norm for a in accepted):
            continue  # same text as an already-accepted (preferred) format
        accepted.append(part)
    # Emit in original document order for readability.
    return [p for p in content_parts if p in accepted]



def _decode(data_b64, content_type):
    """Base64 -> text when textual, else a short binary placeholder."""
    try:
        raw = base64.b64decode(data_b64)
    except Exception:
        return f"<undecodable base64 ({content_type})>"
    if _is_textual(content_type):
        return raw.decode("utf-8", errors="replace")
    return f"<binary {content_type or 'unknown'}: {len(raw)} bytes>"


def _coding_to_str(concept):
    """Render a CodeableConcept compactly: text, else 'system|code (display)'."""
    if not concept:
        return None
    if concept.get("text"):
        return concept["text"]
    for c in concept.get("coding", []):
        bits = "|".join(filter(None, [c.get("system"), c.get("code")]))
        return f"{bits} ({c.get('display')})" if c.get("display") else bits
    return None


def _extract_content(resource, client):
    """Pull text out of every content[].attachment entry."""
    parts = []
    for content in resource.get("content", []):
        att = content.get("attachment", {}) or {}
        ctype = att.get("contentType", "")
        text = None
        source = None
        if att.get("data"):
            text = _decode(att["data"], ctype)
            source = "inline"
        elif att.get("url"):
            if client is None:
                text = f"<url not fetched (no client): {att['url']}>"
                source = "url-unfetched"
            else:
                try:
                    fetched = client.fetch_binary(att["url"])
                    ctype = fetched.get("content_type") or ctype
                    text = (
                        _decode(fetched["data"], ctype)
                        if fetched.get("data")
                        else fetched.get("text")
                    )
                    source = "binary"
                except Exception as exc:  # keep the record; flag the failure
                    text = f"<failed to fetch {att['url']}: {exc}>"
                    source = "fetch-error"
        parts.append(
            {
                "content_type": ctype,
                "format": _coding_to_str({"coding": [content["format"]]})
                if content.get("format")
                else None,
                "title": att.get("title"),
                "language": att.get("language"),
                "source": source,
                "url": att.get("url"),
                "text": text,                       # raw, as returned (markup intact)
                "clean_text": _clean(ctype, text),  # markup-stripped
            }
        )
    return parts


def _extract_related(resource, client):
    """Resolve linked documents (addenda/appends/replaces) one level deep."""
    related = []
    for rel in resource.get("relatesTo", []):
        ref = (rel.get("target", {}) or {}).get("reference", "")
        target_id = ref.split("/")[-1] if ref else None
        entry = {"relationship": rel.get("code"), "target_id": target_id, "reference": ref}
        if target_id and client is not None and hasattr(client, "get_document_reference"):
            try:
                target = client.get_document_reference(target_id)
                # Shallow extraction: don't recurse into the target's relatesTo.
                entry["note"] = extract_note(
                    target, client, original_id=target_id, resolve_related=False
                )
            except Exception as exc:
                entry["error"] = str(exc)
        related.append(entry)
    return related


def extract_note(resource, client=None, resolved_via=None, original_id=None, resolve_related=True):
    """DocumentReference resource -> normalized note dict."""
    content_parts = _extract_content(resource, client)
    related = _extract_related(resource, client) if resolve_related else []

    # Body: collapse duplicate format representations, keep distinct content,
    # then append any resolved addenda. Cleaned (markup-stripped) text is used
    # here; raw per-format text is retained in `content` for fidelity.
    accepted = _combine_parts(content_parts)
    primary_format = accepted[0]["content_type"] if accepted else None
    chunks = [p["clean_text"] for p in accepted]
    for rel in related:
        rel_note = rel.get("note")
        if rel_note and rel_note.get("combined_text"):
            chunks.append(
                f"\n--- {rel.get('relationship', 'related')} "
                f"({rel.get('target_id')}) ---\n{rel_note['combined_text']}"
            )
    combined_text = "\n\n".join(chunks).strip()

    return {
        "input_id": original_id,
        "document_reference_id": resource.get("id"),
        "resolved_via": resolved_via,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "metadata": {
            "type": _coding_to_str(resource.get("type")),
            "category": [_coding_to_str(c) for c in resource.get("category", [])],
            "status": resource.get("status"),
            "doc_status": resource.get("docStatus"),
            "date": resource.get("date"),
            "authors": [a.get("display") or a.get("reference") for a in resource.get("author", [])],
            "authenticator": (resource.get("authenticator", {}) or {}).get("display"),
            "encounter": [
                (e or {}).get("reference")
                for e in (resource.get("context", {}) or {}).get("encounter", [])
            ],
            "security_labels": [_coding_to_str(s) for s in resource.get("securityLabel", [])],
            "identifiers": [
                {"system": i.get("system"), "value": i.get("value")}
                for i in resource.get("identifier", [])
            ],
        },
        "content": content_parts,
        "primary_format": primary_format,
        "combined_text": combined_text,
        "related": related,
        "raw_document_reference": resource,
    }
