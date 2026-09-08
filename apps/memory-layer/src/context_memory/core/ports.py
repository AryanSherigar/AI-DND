"""Provider boundaries shared by both the ingestion (write) and retrieval (read)
sides -- as opposed to `ingestion/ports.py`'s write-path-only Protocols. Lives in
`core` so neither side has to import the other's package to depend on these.
"""

from collections.abc import Sequence
from typing import Protocol


class Embedder(Protocol):
    """Embeds validated fact text only; model selection is deferred."""

    def embed(self, text: str) -> tuple[float, ...]: ...


class GraphTransport(Protocol):
    """Local HydraDB HTTP transport; write identity is diagnostic, not durable."""

    def write(
        self, cypher: str, rows: Sequence[dict[str, object]], idempotency_key: str
    ) -> str | None: ...

    def read(
        self, cypher: str, parameters: dict[str, object], bookmark: str | None
    ) -> Sequence[dict[str, object]]: ...
