"""Turn a FHIR DocumentReference into a normalized note record.

Captures more than just the body text: every attachment (inline base64 *and*
url-linked Binary, across formats), linked/embedded content via `relatesTo`
(addenda/appends/replaces -- which matter a lot for clinical notes), and the
metadata you'd want for downstream eval (LOINC type, category, status, authors,
encounter, security labels).
"""

import base64
from datetime import datetime, timezone

# Content types we can confidently render as text.
_TEXTUAL_HINTS = ("text/", "+xml", "application/xml", "application/json", "application/rtf", "/rtf")


def _is_textual(content_type):
    ct = (content_type or "").lower()
    return any(h in ct for h in _TEXTUAL_HINTS)


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
                "text": text,
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

    # Combined body: each content part, then any resolved addenda text.
    chunks = [p["text"] for p in content_parts if p.get("text")]
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
        "combined_text": combined_text,
        "related": related,
        "raw_document_reference": resource,
    }
