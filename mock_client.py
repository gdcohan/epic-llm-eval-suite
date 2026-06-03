"""Offline FHIR client backed by the mock_data/ fixtures.

Implements the same surface the pipeline uses (resolve_document_reference,
get_document_reference, fetch_binary), so the full fetch -> extract -> persist
path runs with no Epic creds or network. Swap MockFHIRClient for EpicFHIRClient
to go live.
"""

import os
import json
import glob

MOCK_DIR = os.path.join(os.path.dirname(__file__), "mock_data")


class MockFHIRClient:
    def __init__(self, mock_dir=MOCK_DIR):
        self.mock_dir = mock_dir
        self._by_id = {}
        for path in glob.glob(os.path.join(mock_dir, "*.json")):
            with open(path) as f:
                res = json.load(f)
            if res.get("id"):
                self._by_id[res["id"]] = res

    def get_document_reference(self, doc_id):
        res = self._by_id.get(doc_id)
        if not res or res.get("resourceType") != "DocumentReference":
            raise LookupError(f"No mock DocumentReference '{doc_id}'")
        return res

    def resolve_document_reference(self, identifier):
        ident = str(identifier).strip().split("/")[-1]
        return {
            "resource": self.get_document_reference(ident),
            "resolved_via": "mock",
            "document_reference_id": ident,
        }

    def fetch_binary(self, url):
        bin_id = url.split("/")[-1]
        res = self._by_id.get(bin_id)
        if not res or res.get("resourceType") != "Binary":
            raise LookupError(f"No mock Binary '{bin_id}'")
        return {"content_type": res.get("contentType", ""), "data": res.get("data"), "text": None}
