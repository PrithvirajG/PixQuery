---
project: PixQuery
type: knowledge-note
created: 2026-09-02
status: parked
---

# DAG Branch-Level Parallelism — Tech Debt

Parked 2026-09-02 in favor of auditing pipeline-stage (model) quality — see [[Stage Model Quality Audit]]. Revisit once the model-quality pass is done and the pipeline's actual output is trustworthy; parallelizing execution is pointless if the nodes being executed are giving wrong answers.

## Current state (verified against code, 2026-09-02)

Pipeline execution is a **graph model**, not a relational one: a pipeline definition is stored as two plain arrays on one `pipeline_definitions` MongoDB document (`nodes`, `edges`), and executed with a hand-rolled Kahn's-algorithm topological sort (`backend/src/utils/graph.py::topological_order`), shared by two call sites:
- **Save time** — `PipelineService._build_graph`/`_assert_acyclic` rejects a cyclic graph before it can ever be persisted.
- **Run time** — `PipelineExecutionService._run_graph` (`pipeline_execution_service.py:300-372`) walks the same structure per job.

**Sibling-branch context isolation is correct.** Verified directly against a real workspace ("Test 1 a"): a graph shaped `embedding → face_detection → {object_detection, grayscale → image_write}` executes with `object_detection` and `grayscale` each building an independent context copy from `face_detection`'s output — no cross-contamination between branches. Confirmed via the persisted `order` field in `model_outputs` matching the expected topological sequence.

**But nothing executes concurrently, at any level:**
1. **Within one job's DAG** — `_run_graph` is a flat Python `for` loop over the topological order. Kahn's algorithm's `ready` list *can* contain multiple simultaneously-runnable nodes (true siblings), but `_topological_order` flattens that into one sequential list before `_run_graph` ever sees it — sibling information is discarded. Node b fully completes (incl. persistence + stage event) before node c starts, even when b and c have no dependency on each other.
2. **Across jobs, within one worker process** — `RabbitConsumer.connect()` sets `prefetch_count=1` (`rabbitmq_consumer.py:16`), so a single `pipeline_worker_main.py` process holds only one unacked job at a time. `asyncio.to_thread(self.pipeline.run_job, job_id)` in `image_task_consumer.py` moves the CPU-bound run off the event loop thread (so heartbeats/shutdown stay responsive) but does not create job-level concurrency — the next message isn't delivered until the current one acks.
3. **The only parallelism that exists today is horizontal and per-job**, not per-branch: `image_task` is a named durable queue (competing-consumers pattern), so running multiple `pipeline_worker_main.py` OS processes lets RabbitMQ spread *different images'* jobs across them concurrently. Two branches of the *same* image's pipeline cannot run at once today, regardless of how many worker processes are running.

## What branch-level (intra-job) parallelism would require

Not a flag flip — a real, scoped change:

1. **Level-batched execution in `_run_graph`.** Replace the flat order with a BFS-by-level walk: at each step, run every currently-ready node concurrently (`asyncio.gather` over `asyncio.to_thread(executor.run, ...)` per node in the batch), then advance indegrees and move to the next batch.
2. **Stage-progress eventing needs rework.** `pipeline_stage_event(index=topo_index+1, total=len(order))` assumes one node finishes at a time in a fixed sequence ("stage 3 of 5"). Concurrent siblings break that single linear counter — would need to key off level or completed-count instead.
3. **Tighten "last write wins" for the final context merge.** Safe today only because execution order is fully deterministic. If two *concurrent* siblings in the same batch wrote the same context key, the winner would depend on coroutine completion order — nondeterministic. Needs an explicit conflict rule (or a documented "sibling nodes must not share output keys" constraint) rather than relying on ordering.
4. **Model thread-safety / GPU contention is unverified.** Executors are cached singletons per node type (`test_executors_are_cached_so_models_load_once_per_process`), so two *different* node types running concurrently (e.g. `object_detection` + `grayscale`) is probably safe, but on a single GPU, concurrent inference calls may just serialize at the CUDA level anyway — needs measuring before assuming a real speedup. Pipelines here are also small (a handful of nodes per image), so thread/process overhead could rival the savings.

## Why parked

Reordering *how* pipeline stages execute doesn't matter if the stages themselves are producing wrong output — e.g. object detection misclassifying a tiger as a zebra, or CLIP embeddings not being accurate enough for search to surface the right images. That's a correctness problem in the product's core AI feature; execution speed is a secondary concern once correctness holds. See [[Stage Model Quality Audit]] for the active work.

Related: [[Backend Architecture Standards]] · [[Current Implementation Audit]]
