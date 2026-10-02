"""ImageEventHandler event filtering and WorkspaceWatcher's observer lifecycle.

watchdog's Observer is replaced with a recorder, and each workspace's
ReconciliationService with a fake, so no threads start and no files are
hashed. Both classes now only ever *publish* a raw observation — neither
hashes a file nor touches jobs/pipelines directly anymore (see
filesystem_watcher.py's module docstring for why).
"""
import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from src.consumer.ingestion import filesystem_watcher as fw
from src.logging_config import get_request_id
from tests.repo_factory import new_repos


class FakePublisher:
    def __init__(self):
        self.messages = []
        self.request_ids = []

    async def publish(self, message):
        self.messages.append(json.loads(message))
        self.request_ids.append(get_request_id())


class FakeReconciler:
    def __init__(self, extensions=(".jpg",), error=None, found=("/w/a.jpg", "/w/b.jpg")):
        self.extensions = set(extensions)
        self.error = error
        self.found = [Path(p) for p in found]
        self.scans = 0

    def scan(self):
        self.scans += 1
        if self.error:
            raise self.error
        return self.found


def fs_event(path, *, is_directory=False, dest_path=None):
    return SimpleNamespace(src_path=path, dest_path=dest_path, is_directory=is_directory)


class ImageEventHandlerTests(unittest.TestCase):
    def setUp(self):
        self.publisher = FakePublisher()
        self.handler = fw.ImageEventHandler("ws1", {".jpg"}, self.publisher, loop=None)
        self.scheduled = []
        patcher = mock.patch.object(
            fw.asyncio, "run_coroutine_threadsafe", lambda coro, loop: self.scheduled.append(coro)
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(lambda: [c.close() for c in self.scheduled])

    def _run_scheduled(self):
        for coro in self.scheduled:
            asyncio.run(coro)
        self.scheduled.clear()

    def test_created_image_is_published_with_a_fresh_request_id(self):
        self.handler.on_created(fs_event("/w/a.jpg"))
        self._run_scheduled()
        (msg,) = self.publisher.messages
        self.assertEqual(msg["workspace_id"], "ws1")
        self.assertEqual(msg["path"], str(Path("/w/a.jpg")))
        self.assertFalse(msg["redispatch_failed"])
        self.assertRegex(self.publisher.request_ids[0], r"^[0-9a-f]{12}$")

    def test_extension_match_is_case_insensitive(self):
        self.handler.on_modified(fs_event("/w/B.JPG"))
        self.assertEqual(len(self.scheduled), 1)

    def test_other_extensions_and_directories_are_ignored(self):
        self.handler.on_created(fs_event("/w/notes.txt"))
        self.handler.on_created(fs_event("/w/folder.jpg", is_directory=True))
        self.assertEqual(self.scheduled, [])

    def test_move_publishes_the_destination(self):
        self.handler.on_moved(fs_event("/w/tmp.part", dest_path="/w/final.jpg"))
        self._run_scheduled()
        self.assertEqual(self.publisher.messages[0]["path"], str(Path("/w/final.jpg")))

    def test_publish_failure_does_not_raise(self):
        async def boom(message):
            raise RuntimeError("amqp down")

        self.publisher.publish = boom
        self.handler.on_created(fs_event("/w/a.jpg"))
        self._run_scheduled()  # must not raise


class FakeObserver:
    instances = []

    def __init__(self):
        self.scheduled, self.started, self.stopped, self.joined = [], False, False, False
        FakeObserver.instances.append(self)

    def schedule(self, handler, path, recursive):
        self.scheduled.append((path, recursive))

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True

    def join(self):
        self.joined = True


class WorkspaceWatcherTests(unittest.TestCase):
    def setUp(self):
        FakeObserver.instances = []
        patcher = mock.patch.object(fw, "Observer", FakeObserver)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.r = new_repos()
        self.publisher = FakePublisher()
        self.reconcilers = {}
        self.watcher = fw.WorkspaceWatcher(
            workspaces=self.r.workspaces, assets=self.r.assets, observations=self.r.observations,
            publisher=self.publisher, loop=None,
        )
        self.watcher._make_reconciler = lambda ws: self.reconcilers.setdefault(ws["_id"], FakeReconciler())

    def _ws(self, name, **kw):
        return self.r.workspaces.create(
            owner_id="o", name=name, workspace_path=str(Path(self.tmp.name) / name),
            pipeline_ids=kw.get("pipeline_ids", ["p1"]), extensions=[".jpg"], active=kw.get("active", True),
        )

    def test_sync_starts_active_workspaces_and_reconciles_once_without_redispatch(self):
        a, _ = self._ws("a"), self._ws("b", active=False)
        asyncio.run(self.watcher.sync())
        self.assertEqual(list(self.watcher._watchers), [a["_id"]])
        self.assertTrue(FakeObserver.instances[0].started)
        self.assertEqual(self.reconcilers[a["_id"]].scans, 1)
        self.assertEqual(len(self.publisher.messages), 2)
        self.assertFalse(any(m["redispatch_failed"] for m in self.publisher.messages))
        self.assertTrue((Path(self.tmp.name) / "a").is_dir())  # root created

    def test_sync_stops_deactivated_workspaces(self):
        a = self._ws("a")
        asyncio.run(self.watcher.sync())
        self.r.workspaces.update(a["_id"], {"active": False})
        asyncio.run(self.watcher.sync())
        self.assertEqual(self.watcher._watchers, {})
        self.assertTrue(FakeObserver.instances[0].stopped and FakeObserver.instances[0].joined)

    def test_sync_rebuilds_when_the_definition_changes(self):
        a = self._ws("a")
        asyncio.run(self.watcher.sync())
        self.r.workspaces.update(a["_id"], {"pipeline_ids": ["p1", "p2"]})
        del self.reconcilers[a["_id"]]
        asyncio.run(self.watcher.sync())
        self.assertEqual(len(FakeObserver.instances), 2)
        self.assertTrue(FakeObserver.instances[0].stopped)

    def test_manual_reconcile_publishes_and_returns_the_count(self):
        a = self._ws("a")
        asyncio.run(self.watcher.sync())
        self.publisher.messages.clear()
        self.assertEqual(asyncio.run(self.watcher.reconcile_workspace(a["_id"], redispatch_failed=True)), 2)
        self.assertTrue(all(m["redispatch_failed"] for m in self.publisher.messages))

    def test_reconcile_unknown_workspace_is_zero(self):
        self.assertEqual(asyncio.run(self.watcher.reconcile_workspace("nope")), 0)

    def test_reconcile_failure_is_zero_not_an_exception(self):
        a = self._ws("a")
        asyncio.run(self.watcher.sync())
        self.reconcilers[a["_id"]].error = RuntimeError("disk gone")
        self.assertEqual(asyncio.run(self.watcher.reconcile_workspace(a["_id"])), 0)

    def test_reconcile_all_and_stop_all(self):
        a, b = self._ws("a"), self._ws("b")
        asyncio.run(self.watcher.sync())
        self.publisher.messages.clear()
        asyncio.run(self.watcher.reconcile_all())
        self.assertEqual(self.reconcilers[a["_id"]].scans, 2)
        self.assertEqual(self.reconcilers[b["_id"]].scans, 2)
        self.assertEqual(len(self.publisher.messages), 4)
        self.watcher.stop_all()
        self.assertEqual(self.watcher._watchers, {})

    def test_legacy_watch_root_field_is_honoured(self):
        self.assertEqual(fw.WorkspaceWatcher._get_path({"watch_root": "/legacy"}), "/legacy")


if __name__ == "__main__":
    unittest.main()
