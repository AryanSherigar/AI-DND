"""Real (non-fake) `Embedder` port implementation (ADR-027, Milestone 7).

Vertex AI `text-embedding-005`, via `google-genai`'s `vertexai=True,
api_key=...` mode -- the same Express Mode auth every other provider call in
this codebase uses (see `core/llm_client.py`'s module docstring). Replaces a
prior local `sentence-transformers` model: embedding generation must run on
Google Cloud AI services, not local open-source weights.
"""

from __future__ import annotations

import time
from typing import Any

from context_memory.core.llm_client import _is_rate_limit_error, _rate_limit_delay

DEFAULT_MODEL_NAME = "text-embedding-005"

# Conservative, unverified against live Vertex AI batch/quota limits -- lower
# this if a real batch-too-large error surfaces.
_MAX_BATCH_SIZE = 100


class EmbeddingError(RuntimeError):
    """Raised when text cannot be embedded (invalid input, before any network call)."""


class EmbeddingProviderError(RuntimeError):
    """Raised when the embedding provider's own call fails: transport error,
    exhausted retries, or a response whose embedding count doesn't match the
    request -- distinct from `EmbeddingError`, which rejects invalid input
    text before any network call is made."""


class VertexEmbedder:
    """`ingestion.ports.Embedder`/`BatchEmbedder` backed by Vertex AI's
    embedding API. `task_type` is fixed per instance (Vertex's asymmetric
    embedding model wants document text and query text embedded
    differently) -- callers needing both roles get two instances, wired at
    the composition root."""

    def __init__(
        self,
        api_key: str,
        model_name: str = DEFAULT_MODEL_NAME,
        model_version: str = "1",
        task_type: str = "RETRIEVAL_DOCUMENT",
        client: Any | None = None,
        rate_limit_max_retries: int = 5,
    ) -> None:
        self.api_key = api_key
        self.model_name = model_name
        self.model_version = model_version
        self.task_type = task_type
        self.rate_limit_max_retries = rate_limit_max_retries
        self._client = client

    @property
    def client(self) -> Any:
        """Lazily constructs the underlying `google-genai` client (never at
        import time, and never if a fake was injected via `client=`) --
        mirrors `LLMClient.client`'s property."""
        if self._client is None:
            from google import genai

            self._client = genai.Client(vertexai=True, api_key=self.api_key)
        return self._client

    def embed(self, text: str) -> tuple[float, ...]:
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: list[str]) -> list[tuple[float, ...]]:
        """Embeds many texts, chunked to respect provider batch limits.
        `orchestrator.py` calls this once per chunk with every accepted
        fact instead of looping `.embed()`."""
        if not texts:
            return []
        self._validate_texts(texts)
        vectors: list[tuple[float, ...]] = []
        for start in range(0, len(texts), _MAX_BATCH_SIZE):
            chunk = texts[start : start + _MAX_BATCH_SIZE]
            vectors.extend(self._embed_chunk(chunk))
        return vectors

    def _validate_texts(self, texts: list[str]) -> None:
        for text in texts:
            if not text or not isinstance(text, str):
                raise EmbeddingError("text must be a non-empty string")

    def _embed_chunk(self, texts: list[str]) -> list[tuple[float, ...]]:
        from google.genai import types

        config = types.EmbedContentConfig(task_type=self.task_type)
        last_error: Exception | None = None
        for attempt in range(self.rate_limit_max_retries + 1):
            try:
                response = self.client.models.embed_content(
                    model=self.model_name, contents=texts, config=config
                )
                return self._extract_vectors(response, len(texts))
            except Exception as error:
                if (
                    not _is_rate_limit_error(error)
                    or attempt == self.rate_limit_max_retries
                ):
                    raise EmbeddingProviderError(
                        f"Vertex AI embed_content failed for model {self.model_name}: {error}"
                    ) from error
                last_error = error
                time.sleep(_rate_limit_delay(error, attempt))
        raise EmbeddingProviderError(f"unreachable: {last_error}")

    def _extract_vectors(self, response: Any, expected: int) -> list[tuple[float, ...]]:
        embeddings = response.embeddings or []
        if len(embeddings) != expected:
            raise EmbeddingProviderError(
                f"Vertex AI returned {len(embeddings)} embeddings for {expected} inputs"
            )
        return [tuple(float(v) for v in e.values) for e in embeddings]
