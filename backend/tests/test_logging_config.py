"""logging_config: logger namespacing, request-id context, formatters, setup."""
import logging
import os
import tempfile
import unittest
from unittest import mock

from src import logging_config as lc


class GetLoggerTests(unittest.TestCase):
    def test_module_paths_map_under_pixquery(self):
        self.assertEqual(lc.get_logger("src.services.image_service").name, "pixquery.services.image_service")
        self.assertEqual(lc.get_logger("__main__").name, "pixquery.main")
        self.assertEqual(lc.get_logger("src").name, "pixquery.main")
        self.assertEqual(lc.get_logger("tests.x").name, "pixquery.tests.x")


class RequestIdTests(unittest.TestCase):
    def test_default_is_dash(self):
        self.assertEqual(lc.get_request_id(), "-")

    def test_bind_strips_truncates_and_generates(self):
        value, token = lc.bind_request_id("  abc  ")
        self.assertEqual(value, "abc")
        lc.reset_request_id(token)
        value, token = lc.bind_request_id("y" * 100)
        self.assertEqual(len(value), 64)
        lc.reset_request_id(token)
        value, token = lc.bind_request_id("   ")
        self.assertRegex(value, r"^[0-9a-f]{12}$")
        lc.reset_request_id(token)

    def test_request_scope_nests_and_restores(self):
        with lc.request_scope("outer"):
            with lc.request_scope("inner"):
                self.assertEqual(lc.get_request_id(), "inner")
            self.assertEqual(lc.get_request_id(), "outer")
        self.assertEqual(lc.get_request_id(), "-")

    def test_scope_restores_even_on_error(self):
        with self.assertRaises(ValueError):
            with lc.request_scope("x"):
                raise ValueError
        self.assertEqual(lc.get_request_id(), "-")


class FormatterAndFilterTests(unittest.TestCase):
    def _record(self, level=logging.WARNING):
        return logging.LogRecord("pixquery.t", level, __file__, 1, "hello", None, None)

    def test_filter_stamps_the_ambient_request_id(self):
        record = self._record()
        with lc.request_scope("rid-7"):
            self.assertTrue(lc._RequestIdFilter().filter(record))
        self.assertEqual(record.request_id, "rid-7")

    def test_color_formatter_colours_level_then_restores_it(self):
        record = self._record(logging.ERROR)
        out = lc._ColorFormatter("%(levelname)s %(message)s").format(record)
        self.assertIn("\x1b[31m", out)
        self.assertEqual(record.levelname, "ERROR")  # not left mutated for other handlers


class LevelOverrideTests(unittest.TestCase):
    def setUp(self):
        self.target = logging.getLogger("pixquery.tests.override")
        self.addCleanup(self.target.setLevel, logging.NOTSET)

    def test_valid_entries_apply_and_junk_is_ignored(self):
        lc._apply_level_overrides(" pixquery.tests.override=debug , junk, =, ")
        self.assertEqual(self.target.level, logging.DEBUG)

    def test_invalid_level_warns_instead_of_raising(self):
        with self.assertLogs("pixquery", level="WARNING") as logs:
            lc._apply_level_overrides("pixquery.tests.override=LOUD")
        self.assertIn("Ignoring invalid LOG_LEVELS entry", logs.output[0])


class SetupTests(unittest.TestCase):
    def setUp(self):
        root = logging.getLogger("pixquery")
        saved = (root.handlers[:], root.level, root.propagate, lc._configured)

        def restore():
            for h in root.handlers:
                if h not in saved[0]:
                    h.close()
            root.handlers[:] = saved[0]
            root.setLevel(saved[1])
            root.propagate = saved[2]
            lc._configured = saved[3]

        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(restore)

    def test_file_handler_writes_process_log_into_log_dir(self):
        with mock.patch.object(lc, "LOG_DIR", self.tmp.name):
            handler = lc._make_file_handler("unit")
        self.addCleanup(handler.close)
        self.assertEqual(handler.baseFilename, os.path.join(os.path.abspath(self.tmp.name), "unit.log"))

    def test_configure_is_idempotent_and_applies_overrides(self):
        lc._configured = False
        with mock.patch.object(lc, "LOG_TO_FILE", True), \
                mock.patch.object(lc, "LOG_DIR", self.tmp.name), \
                mock.patch.object(lc, "LOG_LEVELS", "pixquery.tests.cfg=ERROR"):
            lc.configure_logging("unit")
            lc.configure_logging("unit")
        root = logging.getLogger("pixquery")
        self.addCleanup(logging.getLogger("pixquery.tests.cfg").setLevel, logging.NOTSET)
        self.assertEqual(len(root.handlers), 2)  # console + file, not duplicated
        self.assertFalse(root.propagate)
        self.assertEqual(logging.getLogger("pixquery.tests.cfg").level, logging.ERROR)


if __name__ == "__main__":
    unittest.main()
