"""JWT/password primitives (api/security.py), get_current_user, and /auth/* routes."""
import unittest
import warnings
from datetime import timedelta

import jwt

from src.api import security
from tests.api_client import auth_headers, build_client, make_user
from tests.repo_factory import new_repos

# The hardcoded dev key is 31 bytes; PyJWT warns on every encode/decode. Known
# finding (see the plan) — silence it so test output stays readable.
warnings.filterwarnings("ignore", category=jwt.warnings.InsecureKeyLengthWarning)


class PasswordHashingTests(unittest.TestCase):
    def test_hash_then_verify_round_trips(self):
        hashed = security.hash_password("s3cret!")
        self.assertTrue(security.verify_password("s3cret!", hashed))

    def test_wrong_password_is_rejected(self):
        self.assertFalse(security.verify_password("nope", security.hash_password("s3cret!")))

    def test_hashes_are_salted(self):
        self.assertNotEqual(security.hash_password("same"), security.hash_password("same"))

    def test_malformed_stored_hash_returns_false_instead_of_raising(self):
        self.assertFalse(security.verify_password("x", "not-a-bcrypt-hash"))


class TokenTests(unittest.TestCase):
    def test_round_trip_carries_subject_and_expiry(self):
        payload = security.decode_access_token(security.create_access_token({"sub": "u1"}))
        self.assertEqual(payload["sub"], "u1")
        self.assertIn("exp", payload)

    def test_expired_token_is_rejected(self):
        token = security.create_access_token({"sub": "u1"}, expires_delta=timedelta(seconds=-5))
        self.assertIsNone(security.decode_access_token(token))

    def test_token_signed_with_another_key_is_rejected(self):
        forged = jwt.encode({"sub": "u1"}, "x" * 32, algorithm="HS256")
        self.assertIsNone(security.decode_access_token(forged))

    def test_garbage_is_rejected(self):
        self.assertIsNone(security.decode_access_token("not.a.jwt"))


class AuthenticateFromTokenTests(unittest.TestCase):
    def setUp(self):
        self.repos = new_repos()
        self.user = make_user(self.repos, "alice")

    def test_valid_token_resolves_the_user(self):
        token = security.create_access_token({"sub": self.user["_id"]})
        self.assertEqual(security.authenticate_from_token(token, self.repos.users)["_id"], self.user["_id"])

    def test_missing_token(self):
        self.assertIsNone(security.authenticate_from_token(None, self.repos.users))
        self.assertIsNone(security.authenticate_from_token("", self.repos.users))

    def test_invalid_token(self):
        self.assertIsNone(security.authenticate_from_token("garbage", self.repos.users))

    def test_token_without_subject(self):
        token = security.create_access_token({"name": "alice"})
        self.assertIsNone(security.authenticate_from_token(token, self.repos.users))

    def test_token_for_unknown_user(self):
        token = security.create_access_token({"sub": "deleted-user"})
        self.assertIsNone(security.authenticate_from_token(token, self.repos.users))


class AuthRouteTests(unittest.TestCase):
    def setUp(self):
        self.client, self.repos = build_client()

    def test_register_creates_a_user(self):
        res = self.client.post("/auth/register", json={"username": "alice", "password": "secret1"})
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.json()["username"], "alice")
        self.assertIsNotNone(self.repos.users.get_by_username("alice"))

    def test_register_never_stores_the_plain_password(self):
        self.client.post("/auth/register", json={"username": "alice", "password": "secret1"})
        stored = self.repos.users.get_by_username("alice")["hashed_password"]
        self.assertNotEqual(stored, "secret1")
        self.assertTrue(security.verify_password("secret1", stored))

    def test_duplicate_username_is_400(self):
        make_user(self.repos, "alice")
        res = self.client.post("/auth/register", json={"username": "alice", "password": "secret1"})
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()["message"], "Username already registered")

    def test_register_validation_uses_the_error_envelope(self):
        res = self.client.post("/auth/register", json={"username": "ab", "password": "secret1"})
        self.assertEqual(res.status_code, 422)
        body = res.json()
        self.assertEqual((body["error"], body["code"], body["status"]), (True, "validation_error", 422))
        self.assertTrue(body["message"].startswith("username:"))

    def test_first_user_claims_unowned_assets(self):
        asset = self.repos.assets.upsert(
            content_sha256="h", mime_type="image/jpeg", size_bytes=1, current_path="/a.jpg"
        )
        res = self.client.post("/auth/register", json={"username": "alice", "password": "secret1"})
        self.assertEqual(self.repos.assets.get(asset["_id"])["owner_id"], res.json()["id"])

    def test_login_returns_a_bearer_token(self):
        make_user(self.repos, "alice", "secret1")
        res = self.client.post("/auth/login", json={"username": "alice", "password": "secret1"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["token_type"], "bearer")
        self.assertIsNotNone(security.decode_access_token(res.json()["access_token"]))

    def test_wrong_password_and_unknown_user_give_the_same_401(self):
        # Same message for both, so login can't be used to probe for usernames.
        make_user(self.repos, "alice", "secret1")
        bad_pw = self.client.post("/auth/login", json={"username": "alice", "password": "wrong!"})
        no_user = self.client.post("/auth/login", json={"username": "ghost", "password": "wrong!"})
        self.assertEqual((bad_pw.status_code, no_user.status_code), (401, 401))
        self.assertEqual(bad_pw.json()["message"], no_user.json()["message"])


class CurrentUserTests(unittest.TestCase):
    """get_current_user, exercised through GET /auth/me."""

    def setUp(self):
        self.client, self.repos = build_client()
        self.user = make_user(self.repos, "alice")

    def _me(self, headers=None):
        return self.client.get("/auth/me", headers=headers or {})

    def test_valid_token(self):
        res = self._me(auth_headers(self.user["_id"]))
        self.assertEqual(res.json(), {"id": self.user["_id"], "username": "alice"})

    def test_no_token_is_401_with_bearer_challenge(self):
        res = self._me()
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json()["message"], "Not authenticated")
        self.assertEqual(res.headers["WWW-Authenticate"], "Bearer")

    def test_expired_token_is_401(self):
        token = security.create_access_token({"sub": self.user["_id"]}, expires_delta=timedelta(seconds=-5))
        res = self._me({"Authorization": f"Bearer {token}"})
        self.assertEqual((res.status_code, res.json()["message"]), (401, "Invalid or expired token"))

    def test_forged_token_is_401(self):
        forged = jwt.encode({"sub": self.user["_id"]}, "x" * 32, algorithm="HS256")
        res = self._me({"Authorization": f"Bearer {forged}"})
        self.assertEqual((res.status_code, res.json()["code"]), (401, "unauthorized"))

    def test_token_without_subject_is_401(self):
        token = security.create_access_token({"name": "alice"})
        res = self._me({"Authorization": f"Bearer {token}"})
        self.assertEqual((res.status_code, res.json()["message"]), (401, "Token missing subject"))

    def test_token_for_deleted_user_is_401(self):
        res = self._me(auth_headers("deleted-user-id"))
        self.assertEqual((res.status_code, res.json()["message"]), (401, "User not found"))


if __name__ == "__main__":
    unittest.main()
