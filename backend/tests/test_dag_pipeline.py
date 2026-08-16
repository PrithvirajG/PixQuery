"""Tests for branching (DAG) pipelines: graph build/validation + execution.

Orchestration only — executors are faked, so no model weights or PIL are needed.
"""
import unittest

from src.pipelines.processing.executors import NodeExecutionError
from src.pipelines.processing.pipeline import DynamicPipeline
from src.repositories import InMemoryPipelineRepository
from src.services.pipeline_service import (
    PipelineValidationError,
    _assert_acyclic,
    _build_graph,
)


class FakeExec:
    def __init__(self, node_type, fn):
        self.node_type = node_type
        self.model_name = node_type
        self.model_version = "v"
        self._fn = fn

    def run(self, context, config):
        return self._fn(context, config)


def get_executor_from(table):
    def _get(node_type):
        if node_type not in table:
            raise NodeExecutionError(f"no fake executor for {node_type}")
        return table[node_type]

    return _get


# ── graph build / validation (service layer) ─────────────────────────────────

class BuildGraphTests(unittest.TestCase):
    def test_no_edges_synthesizes_linear_chain(self):
        nodes, edges = _build_graph(
            [{"pipeline_node_id": "x"}, {"pipeline_node_id": "y"}, {"pipeline_node_id": "z"}]
        )
        self.assertEqual(len(edges), 2)
        chain = [(e["from_node_id"], e["to_node_id"]) for e in edges]
        ids = [n["node_id"] for n in nodes]
        self.assertEqual(chain, [(ids[0], ids[1]), (ids[1], ids[2])])

    def test_explicit_edges_preserved_and_id_assigned(self):
        nodes, edges = _build_graph(
            [{"pipeline_node_id": "x", "node_id": "A"}, {"pipeline_node_id": "y", "node_id": "B"}],
            [{"from_node_id": "A", "to_node_id": "B", "from_output": "image", "to_input": "img"}],
        )
        self.assertEqual(len(edges), 1)
        self.assertTrue(edges[0]["edge_id"])
        self.assertEqual(edges[0]["to_input"], "img")

    def test_edge_to_unknown_node_rejected(self):
        with self.assertRaises(PipelineValidationError):
            _build_graph(
                [{"pipeline_node_id": "x", "node_id": "A"}],
                [{"from_node_id": "A", "to_node_id": "ghost"}],
            )

    def test_cycle_rejected(self):
        nodes = [{"node_id": "A"}, {"node_id": "B"}]
        edges = [
            {"from_node_id": "A", "to_node_id": "B"},
            {"from_node_id": "B", "to_node_id": "A"},
        ]
        with self.assertRaises(PipelineValidationError):
            _assert_acyclic(nodes, edges)


# ── DAG execution (executor layer) ───────────────────────────────────────────

class DagExecutionTests(unittest.TestCase):
    def setUp(self):
        self.repo = InMemoryPipelineRepository()
        self.asset = self.repo.upsert_asset(
            content_sha256="h", mime_type="image/jpeg", size_bytes=1, current_path="/x.jpg"
        )

    def _node(self, node_type, inputs, outputs):
        return self.repo.create_pipeline_node(
            name=node_type, description="", node_type=node_type,
            context_inputs=inputs, context_outputs=outputs,
            config_schema={}, default_config={}, owner_id="o",
        )

    def _run(self, pipeline_id, table):
        job, _ = self.repo.ensure_processing_job(
            asset_id=self.asset["_id"], pipeline_id=pipeline_id, pipeline_version="v"
        )
        DynamicPipeline(
            get_executor=get_executor_from(table), image_loader=lambda a: "IMG"
        ).run_job(self.repo, job["_id"])
        return {
            o["output_type"]: o["payload"]
            for o in self.repo.model_outputs.find({"asset_id": self.asset["_id"]})
        }

    def test_branches_do_not_clobber_each_other(self):
        # A → B → sinkB  and  A → C → sinkC. Each branch transforms "image"
        # independently; the two sinks must see their own branch's result.
        a, b, c = (self._node(t, ["image"], ["image"]) for t in ("tagA", "tagB", "tagC"))
        sb = self._node("sinkB", ["image"], ["outB"])
        sc = self._node("sinkC", ["image"], ["outC"])
        nodes = [
            {"node_id": "A", "pipeline_node_id": a["_id"]},
            {"node_id": "B", "pipeline_node_id": b["_id"]},
            {"node_id": "C", "pipeline_node_id": c["_id"]},
            {"node_id": "SB", "pipeline_node_id": sb["_id"]},
            {"node_id": "SC", "pipeline_node_id": sc["_id"]},
        ]
        edges = [
            {"from_node_id": "A", "to_node_id": "B"},
            {"from_node_id": "A", "to_node_id": "C"},
            {"from_node_id": "B", "to_node_id": "SB"},
            {"from_node_id": "C", "to_node_id": "SC"},
        ]
        pl = self.repo.create_pipeline(owner_id="o", name="dag", nodes=nodes, edges=edges)
        table = {
            "tagA": FakeExec("tagA", lambda ctx, cfg: {"image": ctx["image"] + "|A"}),
            "tagB": FakeExec("tagB", lambda ctx, cfg: {"image": ctx["image"] + "|B"}),
            "tagC": FakeExec("tagC", lambda ctx, cfg: {"image": ctx["image"] + "|C"}),
            "sinkB": FakeExec("sinkB", lambda ctx, cfg: {"outB": ctx["image"]}),
            "sinkC": FakeExec("sinkC", lambda ctx, cfg: {"outC": ctx["image"]}),
        }
        outs = self._run(pl["_id"], table)
        self.assertEqual(outs["outB"]["outB"], "IMG|A|B")
        self.assertEqual(outs["outC"]["outC"], "IMG|A|C")

    def test_fan_in_with_port_mapping(self):
        # Two producers feed one merge node via explicit port remapping.
        p = self._node("prodP", ["image"], ["valP"])
        q = self._node("prodQ", ["image"], ["valQ"])
        m = self._node("merge", ["a", "b"], ["merged"])
        nodes = [
            {"node_id": "P", "pipeline_node_id": p["_id"]},
            {"node_id": "Q", "pipeline_node_id": q["_id"]},
            {"node_id": "M", "pipeline_node_id": m["_id"]},
        ]
        edges = [
            {"from_node_id": "P", "to_node_id": "M", "from_output": "valP", "to_input": "a"},
            {"from_node_id": "Q", "to_node_id": "M", "from_output": "valQ", "to_input": "b"},
        ]
        pl = self.repo.create_pipeline(owner_id="o", name="fanin", nodes=nodes, edges=edges)
        table = {
            "prodP": FakeExec("prodP", lambda ctx, cfg: {"valP": "P"}),
            "prodQ": FakeExec("prodQ", lambda ctx, cfg: {"valQ": "Q"}),
            "merge": FakeExec("merge", lambda ctx, cfg: {"merged": ctx["a"] + ctx["b"]}),
        }
        outs = self._run(pl["_id"], table)
        self.assertEqual(outs["merged"]["merged"], "PQ")

    def test_cycle_in_stored_definition_fails_job(self):
        # Build a cyclic graph directly in the repo (bypassing service validation);
        # the executor must still refuse to run it.
        n = self._node("noop", ["image"], ["image"])
        nodes = [
            {"node_id": "A", "pipeline_node_id": n["_id"]},
            {"node_id": "B", "pipeline_node_id": n["_id"]},
        ]
        edges = [
            {"from_node_id": "A", "to_node_id": "B"},
            {"from_node_id": "B", "to_node_id": "A"},
        ]
        pl = self.repo.create_pipeline(owner_id="o", name="cyclic", nodes=nodes, edges=edges)
        job, _ = self.repo.ensure_processing_job(
            asset_id=self.asset["_id"], pipeline_id=pl["_id"], pipeline_version="v"
        )
        table = {"noop": FakeExec("noop", lambda ctx, cfg: {"image": ctx["image"]})}
        with self.assertRaises(NodeExecutionError):
            DynamicPipeline(
                get_executor=get_executor_from(table), image_loader=lambda a: "IMG"
            ).run_job(self.repo, job["_id"])
        self.assertNotEqual(self.repo.get_job(job["_id"])["status"], "completed")


if __name__ == "__main__":
    unittest.main()
