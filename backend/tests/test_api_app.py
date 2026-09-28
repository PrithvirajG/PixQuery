"""api/app.py middleware + wiring and api/errors.py's standard error envelope."""
import re
import unittest

from fastapi import HTTPException

from src.api.errors import APIError, _validation_message
from tests.api_client import build_client


def _add_route(client, path, exc):
    async def boom():
        raise exc

    client.app.add_api_route(path, boom, methods=["GET"])


class ErrorEnvelopeTests(unittest.TestCase):
    def setUp(self):
        self.client, _ = build_client()

    def _get(self, path, exc):
        _add_route(self.client, path, exc)
        return self.client.get(path)

    def test_http_exception_string_detail(self):
        res = self._get("/_t/str", HTTPException(status_code=409, detail="Name taken"))
        self.assertEqual(res.status_code, 409)
        self.assertEqual(res.json(), {"error": True, "code": "conflict", "message": "Name taken", "status": 409})

    def test_http_exception_dict_detail_pins_code(self):
        res = self._get("/_t/dict", HTTPException(status_code=400, detail={"code": "ws_no_pipelines", "message": "Attach one"}))
        self.assertEqual((res.json()["code"], res.json()["message"]), ("ws_no_pipelines", "Attach one"))

    def test_empty_detail_falls_back_to_default_message(self):
        res = self._get("/_t/empty", HTTPException(status_code=403, detail=""))
        self.assertEqual(res.json()["message"], "You don't have permission to do that.")

    def test_unknown_status_gets_generic_code(self):
        res = self._get("/_t/teapot", HTTPException(status_code=418, detail="teapot"))
        self.assertEqual(res.json()["code"], "error")

    def test_api_error_pins_its_code(self):
        res = self._get("/_t/api", APIError(400, "No pipelines", code="workspace_no_pipelines"))
        self.assertEqual((res.status_code, res.json()["code"]), (400, "workspace_no_pipelines"))

    def test_unhandled_exception_is_a_generic_500_that_leaks_nothing(self):
        res = self._get("/_t/crash", RuntimeError("db password is hunter2"))
        self.assertEqual(res.status_code, 500)
        self.assertEqual(res.json()["code"], "internal_error")
        self.assertNotIn("hunter2", res.text)

    def test_framework_404_and_405_use_the_envelope(self):
        self.assertEqual(self.client.get("/no/such/route").json()["code"], "not_found")
        self.assertEqual(self.client.delete("/auth/me").json()["code"], "method_not_allowed")


class ValidationMessageTests(unittest.TestCase):
    def test_single_error_names_the_field(self):
        msg = _validation_message([{"loc": ["body", "username"], "msg": "too short"}])
        self.assertEqual(msg, "username: too short")

    def test_multiple_errors_are_counted(self):
        errors = [{"loc": ["body", "a"], "msg": "bad"}, {"loc": ["body", "b"], "msg": "bad"}, {"loc": ["query", "c"], "msg": "bad"}]
        self.assertEqual(_validation_message(errors), "a: bad (and 2 more)")

    def test_no_location_says_input(self):
        self.assertEqual(_validation_message([{"loc": ["body"], "msg": "invalid json"}]), "input: invalid json")

    def test_empty_list_uses_default(self):
        self.assertEqual(_validation_message([]), "Some of the information you provided is invalid.")


class RequestIdMiddlewareTests(unittest.TestCase):
    def setUp(self):
        self.client, _ = build_client()

    def test_caller_supplied_id_is_echoed(self):
        res = self.client.get("/auth/me", headers={"X-Request-ID": "trace-abc"})
        self.assertEqual(res.headers["X-Request-ID"], "trace-abc")

    def test_id_is_generated_when_absent(self):
        rid = self.client.get("/auth/me").headers["X-Request-ID"]
        self.assertRegex(rid, r"^[0-9a-f]{12}$")

    def test_overlong_id_is_truncated_to_64(self):
        res = self.client.get("/auth/me", headers={"X-Request-ID": "x" * 200})
        self.assertEqual(len(res.headers["X-Request-ID"]), 64)

    def test_error_responses_still_carry_the_id(self):
        res = self.client.get("/no/such/route", headers={"X-Request-ID": "trace-404"})
        self.assertEqual(res.headers["X-Request-ID"], "trace-404")


class CorsTests(unittest.TestCase):
    def setUp(self):
        self.client, _ = build_client()

    def _preflight(self, origin):
        return self.client.options(
            "/auth/login",
            headers={"Origin": origin, "Access-Control-Request-Method": "POST"},
        )

    def test_dev_server_origin_is_allowed(self):
        res = self._preflight("http://localhost:3000")
        self.assertEqual(res.headers.get("access-control-allow-origin"), "http://localhost:3000")

    def test_private_lan_origin_is_allowed(self):
        res = self._preflight("http://192.168.1.4:3000")
        self.assertEqual(res.headers.get("access-control-allow-origin"), "http://192.168.1.4:3000")

    def test_public_origin_is_not_allowed(self):
        self.assertIsNone(self._preflight("http://evil.example.com").headers.get("access-control-allow-origin"))

    def test_lan_origin_on_other_port_is_not_allowed(self):
        self.assertIsNone(self._preflight("http://192.168.1.4:8080").headers.get("access-control-allow-origin"))


class RouterWiringTests(unittest.TestCase):
    def test_every_route_group_is_mounted(self):
        client, _ = build_client()
        paths = {getattr(r, "path", "") for r in client.app.routes}
        for expected in ("/auth/login", "/workspaces", "/pipelines", "/pipeline-nodes", "/ws/events", "/images_source"):
            with self.subTest(path=expected):
                self.assertTrue(any(p == expected or p.startswith(expected) for p in paths), paths)


if __name__ == "__main__":
    unittest.main()
