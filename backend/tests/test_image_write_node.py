"""Tests for the ``image_write`` sink node.

Covers: registry wiring, that writing does NOT touch the source file, the default
output landing inside the workspace, absolute-path override, the recorded
``written_image`` output, and — critically — that the reconciler never re-ingests
images the node writes into its output folder (which would otherwise loop).
"""
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from src.config import PIPELINE_OUTPUT_DIRNAME
from src.errors.executors import NodeExecutionError
from src.services.reconciliation_service import ReconciliationService
from src.services.executors import get_executor
from src.services.executors.builtin import ImageWriteExecutor
from tests.repo_factory import new_repos


class ImageWriteExecutorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.source = self.root / "photo.png"
        Image.new("RGB", (8, 8), "red").save(self.source)
        self.source_bytes = self.source.read_bytes()

    def tearDown(self):
        self.tmp.cleanup()

    def _context(self):
        return {
            "image": Image.new("RGB", (4, 6), "blue"),
            "asset": {"_id": "asset-1", "current_path": str(self.source)},
            "workspace_root": str(self.root),
        }

    def test_registered_in_registry(self):
        self.assertIsInstance(get_executor("image_write"), ImageWriteExecutor)

    def test_default_writes_inside_workspace_and_leaves_source_untouched(self):
        result = ImageWriteExecutor().run(self._context(), {"format": "jpeg"})
        out = Path(result["written_image"]["path"])

        self.assertTrue(out.exists())
        # Landed in the managed output folder at the workspace root — not next
        # to wherever the source file happens to sit.
        self.assertEqual(out.parent, self.root / PIPELINE_OUTPUT_DIRNAME)
        self.assertEqual(out.name, "photo.jpg")
        self.assertEqual(result["written_image"], {
            "path": str(out), "format": "jpeg", "width": 4, "height": 6,
        })
        # The original file is byte-for-byte unchanged.
        self.assertEqual(self.source.read_bytes(), self.source_bytes)

    def test_nested_source_still_writes_to_the_workspace_root_output_folder(self):
        # A source living inside a subfolder (or a previous run's own output)
        # must not shift the anchor — that's what caused the output folder to
        # nest one level deeper on every run.
        nested = self.root / "sub" / "photo2.png"
        nested.parent.mkdir()
        Image.new("RGB", (8, 8), "green").save(nested)
        context = {
            "image": Image.new("RGB", (4, 6), "blue"),
            "asset": {"_id": "asset-2", "current_path": str(nested)},
            "workspace_root": str(self.root),
        }
        result = ImageWriteExecutor().run(context, {"format": "jpeg"})
        out = Path(result["written_image"]["path"])
        self.assertEqual(out.parent, self.root / PIPELINE_OUTPUT_DIRNAME)

    def test_relative_directory_is_a_subfolder_of_the_output_root(self):
        result = ImageWriteExecutor().run(
            self._context(), {"directory": "thumbnails", "format": "jpeg"}
        )
        out = Path(result["written_image"]["path"])
        self.assertEqual(out.parent, self.root / PIPELINE_OUTPUT_DIRNAME / "thumbnails")

    def test_absolute_directory_is_honored(self):
        dest = self.root / "elsewhere"
        result = ImageWriteExecutor().run(
            self._context(), {"directory": str(dest), "format": "png", "filename": "out.{ext}"}
        )
        out = Path(result["written_image"]["path"])
        self.assertEqual(out, dest / "out.png")
        self.assertTrue(out.exists())

    def test_missing_workspace_root_raises_when_directory_is_relative(self):
        context = dict(self._context())
        context.pop("workspace_root")
        with self.assertRaises(NodeExecutionError):
            ImageWriteExecutor().run(context, {"format": "jpeg"})

    def test_filename_template_cannot_escape_directory(self):
        # A malicious template with traversal collapses to just the basename.
        result = ImageWriteExecutor().run(
            self._context(), {"filename": "../../etc/{stem}.{ext}", "format": "png"}
        )
        out = Path(result["written_image"]["path"])
        self.assertEqual(out.parent, self.root / PIPELINE_OUTPUT_DIRNAME)
        self.assertEqual(out.name, "photo.png")


class ReconcilerSkipsOutputFolderTests(unittest.IsolatedAsyncioTestCase):
    async def test_written_outputs_are_not_reingested(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            Image.new("RGB", (8, 8), "red").save(root / "source.png")
            # A previously-written output sitting in the managed folder.
            out_dir = root / PIPELINE_OUTPUT_DIRNAME
            out_dir.mkdir()
            Image.new("RGB", (8, 8), "blue").save(out_dir / "source.jpg")

            r = new_repos()
            reconciler = ReconciliationService(
                assets=r.assets, observations=r.observations, jobs=r.jobs, pipelines=r.pipelines,
                publisher=None,
                workspace_path=str(root),
                workspace_id="ws-1",
                stable_interval_seconds=0.01,
                stable_timeout_seconds=1,
            )
            found = {Path(p).name for p in reconciler.iter_image_files()}
            self.assertEqual(found, {"source.png"})

    async def test_observe_file_also_skips_managed_output_directly(self):
        # The live filesystem watcher calls observe_file() straight off a
        # watchdog event, never through iter_image_files() — this is the path
        # that used to re-ingest every image_write output as a new asset and
        # loop forever. A nested pixquery_output path must be rejected here too.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            nested_out = root / PIPELINE_OUTPUT_DIRNAME / PIPELINE_OUTPUT_DIRNAME
            nested_out.mkdir(parents=True)
            written = nested_out / "source.jpg"
            Image.new("RGB", (8, 8), "blue").save(written)

            r = new_repos()
            reconciler = ReconciliationService(
                assets=r.assets, observations=r.observations, jobs=r.jobs, pipelines=r.pipelines,
                publisher=None,
                workspace_path=str(root),
                workspace_id="ws-1",
                stable_interval_seconds=0.01,
                stable_timeout_seconds=1,
            )
            queued = await reconciler.observe_file(written)
            self.assertEqual(queued, [])
            self.assertEqual(r.assets.list_all_ids(), [])


if __name__ == "__main__":
    unittest.main()
