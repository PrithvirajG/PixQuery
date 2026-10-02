"""Regression test for the embedding upsert's duplicate-id fallback.

This Weaviate version answers a duplicate deterministic-id create with 422, not
the documented 409 — reprocessing any already-embedded asset used to raise
that 422 straight through _upsert, fail the job, and (via the monitor's
periodic reconcile re-dispatching every "failed" job) retry forever.
"""
import io
import json
import unittest
import urllib.error
from unittest.mock import MagicMock, patch

from src.infrastructure.vector_store.weaviate import WeaviateEmbeddingStore


def _http_error(code, message):
    body = json.dumps({"error": [{"message": message}]}).encode()
    return urllib.error.HTTPError(
        "http://weaviate.test/v1/objects", code, "reason", {}, io.BytesIO(body)
    )


def _success_response(body=b""):
    response = MagicMock()
    response.read.return_value = body
    cm = MagicMock()
    cm.__enter__.return_value = response
    cm.__exit__.return_value = False
    return cm


class WeaviateUpsertConflictTests(unittest.TestCase):
    def setUp(self):
        # This file is about the 409/422-falls-back-to-PUT behavior of _upsert,
        # not schema creation — _ensure_class (called both at construction, via
        # ensure_schema(), and again per-upsert to route to the right model's
        # class) is stubbed out so neither path makes its own schema request,
        # which would otherwise eat into the urlopen side_effect queue these
        # tests set up for the object create/update calls.
        patcher = patch.object(WeaviateEmbeddingStore, "_ensure_class", lambda self, *a: None)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.store = WeaviateEmbeddingStore(url="http://weaviate.test")
        self.props = {"asset_id": "a1", "pipeline_id": "p1", "pipeline_version": "v1"}

    @patch("src.infrastructure.vector_store.weaviate.urllib.request.urlopen")
    def test_422_duplicate_id_falls_back_to_put(self, mock_urlopen):
        mock_urlopen.side_effect = [
            _http_error(422, "id 'abc' already exists"),
            _success_response(),
        ]
        self.store.upsert_image_embedding(vector=[0.1, 0.2], properties=self.props)

        self.assertEqual(mock_urlopen.call_count, 2)
        first_request = mock_urlopen.call_args_list[0][0][0]
        second_request = mock_urlopen.call_args_list[1][0][0]
        self.assertEqual(first_request.get_method(), "POST")
        self.assertEqual(second_request.get_method(), "PUT")

    @patch("src.infrastructure.vector_store.weaviate.urllib.request.urlopen")
    def test_409_conflict_also_falls_back_to_put(self, mock_urlopen):
        mock_urlopen.side_effect = [
            _http_error(409, "already exists"),
            _success_response(),
        ]
        self.store.upsert_image_embedding(vector=[0.1, 0.2], properties=self.props)
        self.assertEqual(mock_urlopen.call_count, 2)

    @patch("src.infrastructure.vector_store.weaviate.urllib.request.urlopen")
    def test_other_errors_still_raise(self, mock_urlopen):
        mock_urlopen.side_effect = [_http_error(500, "internal error")]
        with self.assertRaises(urllib.error.HTTPError):
            self.store.upsert_image_embedding(vector=[0.1], properties=self.props)


if __name__ == "__main__":
    unittest.main()
