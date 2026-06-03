"""Epic FHIR client focused on fetching clinical notes by ID.

Auth is SMART Backend Services (OAuth2 client-credentials with an RS384-signed
JWT assertion) -- carried over unchanged from the original scaffolding. The
note-centric methods are new: a tolerant DocumentReference resolver, a Binary
fetcher that handles both inline base64 and url-linked content, and a discovery
helper to list note IDs for a patient (useful when you don't have IDs yet).
"""

import os
import time
import uuid
import base64
import requests
from dotenv import load_dotenv

load_dotenv()


class EpicFHIRClient:
    def __init__(self):
        self.client_id = os.getenv("EPIC_CLIENT_ID")
        self.private_key_path = os.getenv("EPIC_PRIVATE_KEY_PATH")
        self.base_url = (os.getenv("EPIC_FHIR_BASE_URL") or "").rstrip("/")
        self.token_url = os.getenv("EPIC_TOKEN_URL")
        # Optional: comma-separated FHIR identifier systems to try when an input
        # ID is an Epic-native value (e.g. a document/note ID) with no system.
        # Fill these from your Epic environment's DocumentReference identifier
        # systems. Left empty by default since they are environment-specific.
        self.doc_identifier_systems = [
            s.strip() for s in (os.getenv("EPIC_DOC_IDENTIFIER_SYSTEMS") or "").split(",") if s.strip()
        ]
        self.access_token = None
        self.token_expiry = 0

    # ------------------------------------------------------------------ auth
    def _authenticate(self):
        """Standard OAuth2 client-credentials handshake (cached until expiry)."""
        if self.access_token and time.time() < self.token_expiry:
            return

        import jwt  # lazy: only needed for live auth, keeps offline paths light

        with open(self.private_key_path, "r") as k:
            private_key = k.read()

        now = int(time.time()) - 60
        claims = {
            "iss": self.client_id,
            "sub": self.client_id,
            "aud": self.token_url,
            "jti": str(uuid.uuid4()),
            "iat": now,
            "exp": now + 300,
        }
        signed_jwt = jwt.encode(
            claims,
            private_key,
            algorithm="RS384",
            headers={"alg": "RS384", "typ": "JWT", "kid": "my-agent-v1"},
        )

        payload = {
            "grant_type": "client_credentials",
            "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
            "client_assertion": signed_jwt,
            "scope": "system/DocumentReference.read system/Binary.read system/Patient.read",
        }
        res = requests.post(self.token_url, data=payload)
        res.raise_for_status()
        data = res.json()
        self.access_token = data["access_token"]
        self.token_expiry = time.time() + data.get("expires_in", 300) - 10

    def _headers(self, accept="application/fhir+json"):
        self._authenticate()
        return {"Authorization": f"Bearer {self.access_token}", "Accept": accept}

    def _abs(self, url):
        """Resolve a possibly-relative FHIR URL against the base."""
        if url.startswith("http"):
            return url
        return f"{self.base_url}/{url.lstrip('/')}"

    # ------------------------------------------------------- document reads
    def get_document_reference(self, doc_id):
        """Direct read: GET DocumentReference/{id}."""
        res = requests.get(
            f"{self.base_url}/DocumentReference/{doc_id}", headers=self._headers()
        )
        res.raise_for_status()
        return res.json()

    def search_document_reference(self, identifier_token):
        """Search by identifier token, e.g. 'system|value' or just 'value'.

        Returns the list of matching DocumentReference resources (may be empty).
        """
        res = requests.get(
            f"{self.base_url}/DocumentReference",
            headers=self._headers(),
            params={"identifier": identifier_token},
        )
        res.raise_for_status()
        return [e["resource"] for e in res.json().get("entry", []) if "resource" in e]

    def resolve_document_reference(self, identifier):
        """Tolerant resolver for whatever shape of 'note ID' we're handed.

        Handles: absolute URLs, 'DocumentReference/{id}' references, bare logical
        IDs, 'system|value' identifier tokens, and bare Epic-native values. Always
        returns the full DocumentReference resource plus how we found it.

        Returns dict: {"resource", "resolved_via", "document_reference_id"}.
        """
        ident = str(identifier).strip()

        # 1) Absolute URL or 'DocumentReference/{id}' reference -> direct read.
        if ident.startswith("http") or ident.startswith("DocumentReference/"):
            doc_id = ident.rstrip("/").split("/")[-1]
            return {
                "resource": self.get_document_reference(doc_id),
                "resolved_via": "reference",
                "document_reference_id": doc_id,
            }

        # 2) Explicit identifier token 'system|value' -> identifier search.
        if "|" in ident:
            matches = self.search_document_reference(ident)
            if matches:
                return self._first_match(matches, "identifier-token")
            raise LookupError(f"No DocumentReference for identifier token: {ident}")

        # 3) Bare value: try a direct logical-ID read first (the happy path).
        try:
            resource = self.get_document_reference(ident)
            return {
                "resource": resource,
                "resolved_via": "direct-get",
                "document_reference_id": resource.get("id", ident),
            }
        except requests.HTTPError as exc:
            if exc.response is None or exc.response.status_code not in (400, 404):
                raise

        # 4) Fall back to identifier search: bare value, then candidate systems.
        for token in [ident] + [f"{sys}|{ident}" for sys in self.doc_identifier_systems]:
            matches = self.search_document_reference(token)
            if matches:
                return self._first_match(matches, f"identifier-search ({token})")

        raise LookupError(f"Could not resolve note ID to a DocumentReference: {ident}")

    @staticmethod
    def _first_match(matches, resolved_via):
        resource = matches[0]
        return {
            "resource": resource,
            "resolved_via": resolved_via,
            "document_reference_id": resource.get("id"),
        }

    # -------------------------------------------------------------- binary
    def fetch_binary(self, url):
        """Fetch attachment content from a (possibly relative) url.

        Epic may return a JSON-wrapped Binary resource (base64 in `data`) or raw
        bytes/text. We normalize to {content_type, data (base64|None), text}.
        """
        res = requests.get(self._abs(url), headers=self._headers())
        res.raise_for_status()
        ctype = res.headers.get("Content-Type", "")
        if "json" in ctype:
            body = res.json()
            return {
                "content_type": body.get("contentType", ""),
                "data": body.get("data"),
                "text": None,
            }
        return {"content_type": ctype, "data": None, "text": res.text}

    # ------------------------------------------------------------ discovery
    def discover_document_references(self, patient_id, count=25):
        """List DocumentReferences for a patient (handy when you have no IDs yet)."""
        res = requests.get(
            f"{self.base_url}/DocumentReference",
            headers=self._headers(),
            params={"patient": patient_id, "_count": count},
        )
        res.raise_for_status()
        out = []
        for entry in res.json().get("entry", []):
            r = entry.get("resource", {})
            out.append(
                {
                    "id": r.get("id"),
                    "type": (r.get("type", {}) or {}).get("text"),
                    "date": r.get("date"),
                    "status": r.get("status"),
                }
            )
        return out
