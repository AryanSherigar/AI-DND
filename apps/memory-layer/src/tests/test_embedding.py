from __future__ import annotations

import os
import unittest

from context_memory.ingestion.embedding import (
    EmbeddingError,
    EmbeddingProviderError,
    VertexEmbedder,
)


class _FakeEmbedding:
    def __init__(self, values: list[float]) -> None:
        self.values = values


class _FakeEmbedContentResponse:
    def __init__(self, embeddings: list[_FakeEmbedding]) -> None:
        self.embeddings = embeddings


class _FakeModels:
    """Deterministic stand-in for `client.models`; no network call."""

    def __init__(self, calls: list[list[str]]) -> None:
        self._calls = calls

    def embed_content(self, *, model: str, contents: list[str], config: object):
        self._calls.append(list(contents))
        embeddings = [
            _FakeEmbedding([_stable_value(text), _stable_value(text) / 2, 1.0])
            for text in contents
        ]
        return _FakeEmbedContentResponse(embeddings)


def _stable_value(text: str) -> float:
    return float(ord(text[0]) % 7) if text else 0.0


class _FakeClient:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []
        self.models = _FakeModels(self.calls)


class VertexEmbedderTests(unittest.TestCase):
    def test_embed_returns_float_tuple(self) -> None:
        embedder = VertexEmbedder(api_key="fake", client=_FakeClient())
        vector = embedder.embed("hello world")
        self.assertIsInstance(vector, tuple)
        self.assertTrue(all(isinstance(v, float) for v in vector))
        self.assertEqual(len(vector), 3)

    def test_injected_client_is_reused_across_calls(self) -> None:
        fake = _FakeClient()
        embedder = VertexEmbedder(api_key="fake", client=fake)
        embedder.embed("first")
        embedder.embed("second")
        self.assertEqual(fake.calls, [["first"], ["second"]])

    def test_empty_text_is_rejected(self) -> None:
        embedder = VertexEmbedder(api_key="fake", client=_FakeClient())
        with self.assertRaises(EmbeddingError):
            embedder.embed("")

    def test_non_string_text_is_rejected(self) -> None:
        embedder = VertexEmbedder(api_key="fake", client=_FakeClient())
        with self.assertRaises(EmbeddingError):
            embedder.embed(None)  # type: ignore[arg-type]

    def test_embed_batch_chunks_large_inputs(self) -> None:
        fake = _FakeClient()
        embedder = VertexEmbedder(api_key="fake", client=fake)
        texts = [f"text-{i}" for i in range(150)]
        vectors = embedder.embed_batch(texts)
        self.assertEqual(len(vectors), 150)
        self.assertEqual(len(fake.calls), 2)
        self.assertEqual(len(fake.calls[0]), 100)
        self.assertEqual(len(fake.calls[1]), 50)

    def test_mismatched_response_count_raises_provider_error(self) -> None:
        class _BadModels:
            def embed_content(self, *, model: str, contents: list[str], config: object):
                return _FakeEmbedContentResponse([_FakeEmbedding([1.0])])

        class _BadClient:
            def __init__(self) -> None:
                self.models = _BadModels()

        embedder = VertexEmbedder(api_key="fake", client=_BadClient())
        with self.assertRaises(EmbeddingProviderError):
            embedder.embed_batch(["one", "two"])


@unittest.skipUnless(
    os.environ.get("GOOGLE_CLOUD_API_KEY"),
    "opt-in: makes a real, billed Vertex AI embedding call",
)
class RealVertexEmbedderSmokeTest(unittest.TestCase):
    def test_real_model_embeds_text(self) -> None:
        embedder = VertexEmbedder(api_key=os.environ["GOOGLE_CLOUD_API_KEY"])
        vector = embedder.embed("Parth joined Clinsta Labs on 2024-01-15.")
        self.assertGreater(len(vector), 0)


if __name__ == "__main__":
    unittest.main()
