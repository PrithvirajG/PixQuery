"""PipelineService.create_pipeline_node: node-library creation is disabled.

Product decision (2026-09-03): no user may add a brand-new node type to the
shared pipeline-node library for now — only existing nodes' per-pipeline
settings (``config_overrides``) may be configured. This is deliberately a
blanket, unconditional block (not a per-node-type check), so it's covered as
its own thing rather than folded into node_type validation.
"""
import unittest

from src.errors.pipelines import PipelineNodeCreationDisabledError
from src.services.pipeline_service import PipelineService
from tests.repo_factory import new_repos


def _service(r):
    return PipelineService(
        pipelines=r.pipelines, nodes=r.nodes, runs=r.runs, outputs=r.outputs,
        jobs=r.jobs, workspaces=r.workspaces,
    )


class CreatePipelineNodeDisabledTests(unittest.TestCase):
    def setUp(self):
        self.r = new_repos()
        self.service = _service(self.r)

    def test_rejects_creation_even_with_a_valid_node_type(self):
        # The block is unconditional — a well-formed request naming a real,
        # registered node_type is rejected too, not just malformed ones.
        with self.assertRaises(PipelineNodeCreationDisabledError):
            self.service.create_pipeline_node(
                owner_id="o",
                data={"name": "My Resize", "node_type": "resize"},
            )

    def test_rejected_node_is_not_persisted(self):
        with self.assertRaises(PipelineNodeCreationDisabledError):
            self.service.create_pipeline_node(
                owner_id="o",
                data={"name": "My Resize", "node_type": "resize"},
            )
        self.assertEqual(
            [n for n in self.r.nodes.list_all(owner_id="o") if n["name"] == "My Resize"],
            [],
        )


if __name__ == "__main__":
    unittest.main()
