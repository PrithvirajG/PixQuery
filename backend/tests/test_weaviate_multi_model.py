"""Per-model Weaviate class naming and routing (WeaviateEmbeddingStore).

Weaviate's HNSW index requires every vector within one class to share a single
length, so each embedding model must get its own class — see weaviate.py's
module docstring on image_class_name/text_class_name. These tests pin: the
naming scheme, that "clip" (the pre-existing model) keeps the legacy unsuffixed
names so old data needs no migration, that a class is created at most once per
process, and that upsert_* routes to the right class.
"""
import io
import json
import unittest
import urllib.error
from unittest.mock import MagicMock, patch

from src.infrastructure.vector_store.weaviate import (
    WeaviateEmbeddingStore,
    _pascal,
    image_class_name,
    text_class_name,
)


class ClassNameTests(unittest.TestCase):
    def test_pascal_case_conversion(self):
        self.assertEqual(_pascal("clip_vit_l14"), "ClipVitL14")
        self.assertEqual(_pascal("dinov2"), "Dinov2")
        self.assertEqual(_pascal("a-b_c"), "ABC")

    def test_the_pre_existing_model_keeps_the_legacy_unsuffixed_names(self):
        # No migration: every vector ever written for "clip" already lives here.
        self.assertEqual(image_class_name("clip"), "ImageEmbedding")
        self.assertEqual(text_class_name("clip"), "TextEmbedding")

    def test_every_other_model_gets_its_own_derived_class(self):
        self.assertEqual(image_class_name("clip_vit_l14"), "ImageEmbeddingClipVitL14")
        self.assertEqual(text_class_name("clip_vit_l14"), "TextEmbeddingClipVitL14")
        self.assertEqual(image_class_name("dinov2"), "ImageEmbeddingDinov2")

    def test_different_models_never_collide_on_a_class_name(self):
        ids = ["clip", "clip_vit_l14", "dinov2"]
        self.assertEqual(len({image_class_name(i) for i in ids}), len(ids))


def _response(body=b""):
    response = MagicMock()
    response.read.return_value = body
    cm = MagicMock()
    cm.__enter__.return_value = response
    cm.__exit__.return_value = False
    return cm


def _http_error(code, message="error"):
    body = json.dumps({"error": [{"message": message}]}).encode()
    return urllib.error.HTTPError("http://weaviate.test/x", code, "reason", {}, io.BytesIO(body))


class StoreRoutingTests(unittest.TestCase):
    """Exercised at the HTTP layer (urlopen mocked) so no live Weaviate is needed."""

    def setUp(self):
        # ensure_schema() (called from __init__) would otherwise hit urlopen too;
        # give it real-looking "already exists" responses instead of mocking it away,
        # so its own class-creation behavior is exercised, not bypassed.
        patcher = patch("src.infrastructure.vector_store.weaviate.urllib.request.urlopen")
        self.urlopen = patcher.start()
        self.addCleanup(patcher.stop)
        self.urlopen.side_effect = [_response(b'{"class":"ImageEmbedding"}'), _response(b'{"class":"TextEmbedding"}')]
        self.store = WeaviateEmbeddingStore(url="http://weaviate.test")
        self.urlopen.reset_mock()

    def _requests(self):
        return [c.args[0] for c in self.urlopen.call_args_list]

    def test_default_model_upsert_uses_the_legacy_class_with_no_schema_check(self):
        # __init__ already confirmed ImageEmbedding/TextEmbedding exist and cached
        # that — a "clip" upsert must not re-check schema on every call.
        self.urlopen.side_effect = [_response()]
        self.store.upsert_image_embedding(vector=[0.1, 0.2], properties={"asset_id": "a1", "pipeline_id": "p1", "pipeline_version": "v1"})

        self.assertEqual(len(self._requests()), 1)  # only the object POST, no /v1/schema call
        self.assertEqual(self._requests()[0].full_url, "http://weaviate.test/v1/objects")
        self.assertEqual(json.loads(self._requests()[0].data)["class"], "ImageEmbedding")

    def test_a_new_models_first_upsert_creates_its_class_first(self):
        self.urlopen.side_effect = [
            _http_error(404),  # GET /v1/schema/ImageEmbeddingClipVitL14 -> not found
            _response(),       # POST /v1/schema (create it)
            _response(),       # POST /v1/objects (the actual upsert)
        ]
        self.store.upsert_image_embedding(
            vector=[0.1] * 768, properties={"asset_id": "a1", "pipeline_id": "p1", "pipeline_version": "v1"}, model_id="clip_vit_l14"
        )

        requests = self._requests()
        self.assertEqual(len(requests), 3)
        self.assertEqual(requests[0].full_url, "http://weaviate.test/v1/schema/ImageEmbeddingClipVitL14")
        create_body = json.loads(requests[1].data)
        self.assertEqual(create_body["class"], "ImageEmbeddingClipVitL14")
        self.assertEqual(create_body["vectorizer"], "none")
        self.assertEqual(json.loads(requests[2].data)["class"], "ImageEmbeddingClipVitL14")

    def test_the_new_class_is_created_at_most_once_per_process(self):
        self.urlopen.side_effect = [
            _http_error(404), _response(),  # first upsert: class missing, then created
            _response(),                     # first upsert: the object write
            _response(),                     # second upsert: object write only
        ]
        self.store.upsert_image_embedding(vector=[0.1], properties={"asset_id": "a1", "pipeline_id": "p1", "pipeline_version": "v1"}, model_id="clip_vit_l14")
        self.store.upsert_image_embedding(vector=[0.2], properties={"asset_id": "a2", "pipeline_id": "p1", "pipeline_version": "v1"}, model_id="clip_vit_l14")

        # No second /v1/schema/... existence check on the class the store already
        # confirmed — 4 total requests (create-check + create + 2 object writes),
        # not 5.
        self.assertEqual(len(self._requests()), 4)

    def test_image_and_text_embeddings_for_the_same_model_land_in_different_classes(self):
        props = {"asset_id": "a1", "pipeline_id": "p1", "pipeline_version": "v1"}

        # Image and text are different classes for the same model, so each needs
        # its own create-check-then-create sequence the first time it's written.
        self.urlopen.side_effect = [_http_error(404), _response(), _response()]
        self.store.upsert_image_embedding(vector=[0.1], properties=props, model_id="clip_vit_l14")
        self.assertEqual(json.loads(self._requests()[-1].data)["class"], "ImageEmbeddingClipVitL14")

        self.urlopen.reset_mock()
        self.urlopen.side_effect = [_http_error(404), _response(), _response()]
        self.store.upsert_text_embedding(vector=[0.1], properties=props, model_id="clip_vit_l14")
        self.assertEqual(json.loads(self._requests()[-1].data)["class"], "TextEmbeddingClipVitL14")

    def test_a_third_models_class_is_independent_of_the_second(self):
        # Regression guard for the _known_classes cache being keyed correctly —
        # a shared/global flag instead of a per-class set would make this a no-op.
        self.urlopen.side_effect = [_http_error(404), _response(), _response()]
        self.store.upsert_image_embedding(vector=[0.1], properties={"asset_id": "a1", "pipeline_id": "p1", "pipeline_version": "v1"}, model_id="clip_vit_l14")

        self.urlopen.reset_mock()
        self.urlopen.side_effect = [_http_error(404), _response(), _response()]
        self.store.upsert_image_embedding(vector=[0.1] * 768, properties={"asset_id": "a1", "pipeline_id": "p1", "pipeline_version": "v1"}, model_id="dinov2")

        self.assertEqual(json.loads(self._requests()[1].data)["class"], "ImageEmbeddingDinov2")


if __name__ == "__main__":
    unittest.main()
