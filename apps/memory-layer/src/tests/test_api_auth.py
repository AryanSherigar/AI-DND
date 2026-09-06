"""§12 fix: opt-in bearer-token auth for the FastAPI router
(`api/routes.py::require_api_key`).

Tested directly against the dependency function rather than via
`TestClient` -- `api.routes` pulls in `context_memory.composition`, which
requires optional ML dependencies (sentence-transformers) this repo's test
environment doesn't always have installed; `require_api_key` itself needs
none of that.
"""

from __future__ import annotations

import os
import unittest

from fastapi import HTTPException

from api.routes import require_api_key


class RequireApiKeyTests(unittest.TestCase):
    def setUp(self) -> None:
        self._original = os.environ.pop("CONTEXT_MEMORY_API_KEY", None)

    def tearDown(self) -> None:
        if self._original is not None:
            os.environ["CONTEXT_MEMORY_API_KEY"] = self._original
        else:
            os.environ.pop("CONTEXT_MEMORY_API_KEY", None)

    def test_unset_env_var_allows_every_request(self) -> None:
        """Default behavior -- must never break a deployment that hasn't
        opted in."""
        require_api_key(authorization=None)  # must not raise

    def test_configured_key_rejects_a_missing_header(self) -> None:
        os.environ["CONTEXT_MEMORY_API_KEY"] = "secret-123"
        with self.assertRaises(HTTPException) as ctx:
            require_api_key(authorization=None)
        self.assertEqual(ctx.exception.status_code, 401)

    def test_configured_key_rejects_the_wrong_value(self) -> None:
        os.environ["CONTEXT_MEMORY_API_KEY"] = "secret-123"
        with self.assertRaises(HTTPException):
            require_api_key(authorization="Bearer wrong-value")

    def test_configured_key_accepts_the_correct_bearer_token(self) -> None:
        os.environ["CONTEXT_MEMORY_API_KEY"] = "secret-123"
        require_api_key(authorization="Bearer secret-123")  # must not raise


if __name__ == "__main__":
    unittest.main()
