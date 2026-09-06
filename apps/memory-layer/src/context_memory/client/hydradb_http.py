"""HTTP transport for the checked-in local HydraDB graph-node."""

from __future__ import annotations

import http.client
import json
import threading
from collections.abc import Callable, Mapping, Sequence
from urllib.parse import urlsplit

from context_memory.core.logging import get_logger, timed_operation

logger = get_logger(__name__)


class HydraHttpError(RuntimeError):
    """Local graph-node HTTP failure; bearer token never appears in this error."""


HttpRequester = Callable[[str, str, Mapping[str, str], bytes], Mapping[str, object]]


class HydraHttpTransport:
    def __init__(
        self,
        base_url: str,
        auth_token: str | None = None,
        *,
        bearer_token: str | None = None,
        namespace: str = "default",
        graph_id: str = "default",
        database: str | None = None,
        cell_id: str = "cell-0",
        timeout_seconds: float = 15.0,
        requester: HttpRequester | None = None,
    ) -> None:
        token = auth_token or bearer_token or "context-memory-local-smoke-token-32b"
        effective_graph_id = database if database is not None else graph_id
        if not base_url.startswith(("http://", "https://")) or not token or not namespace or not effective_graph_id or not cell_id:
            raise ValueError("base_url, auth token, namespace, graph_id, and cell_id must be non-empty")
        self._url = f"{base_url.rstrip('/')}/v1/graphs/{effective_graph_id}/query"
        self._headers = {"Authorization": f"Bearer {token}", "X-Graph-Namespace": namespace, "Content-Type": "application/json", "Accept": "application/json"}
        self._cell_id = cell_id
        self._requester = requester or (
            lambda method, url, headers, body: _request_json(method, url, headers, body, timeout=timeout_seconds)
        )

    def write(self, cypher: str, rows: Sequence[dict[str, object]], idempotency_key: str) -> str | None:
        with timed_operation(logger, "hydradb.write", {"rows_count": len(rows), "idempotency_key": idempotency_key}) as ctx:
            response = self._query(cypher, {"rows": list(rows)}, query_id=idempotency_key)
            bookmark = response.get("bookmark")
            if bookmark is not None and not isinstance(bookmark, str):
                raise HydraHttpError("HydraDB returned an invalid bookmark")
            ctx["bookmark"] = bookmark
            return bookmark

    def read(self, cypher: str, parameters: dict[str, object], bookmark: str | None) -> Sequence[dict[str, object]]:
        snippet = cypher[:60].replace("\n", " ") + "..." if len(cypher) > 60 else cypher
        with timed_operation(logger, "hydradb.read", {"query_snippet": snippet}) as ctx:
            response = self._query(cypher, parameters, bookmark=bookmark)
            columns, rows = response.get("columns"), response.get("rows")
            if not isinstance(columns, list) or not all(isinstance(column, str) for column in columns) or not isinstance(rows, list):
                raise HydraHttpError("HydraDB returned invalid query rows")
            result: list[dict[str, object]] = []
            for row in rows:
                if not isinstance(row, list) or len(row) != len(columns):
                    raise HydraHttpError("HydraDB returned a malformed query row")
                result.append({column: _decode_value(value) for column, value in zip(columns, row, strict=True)})
            ctx["result_rows"] = len(result)
            return result

    def _query(self, cypher: str, parameters: Mapping[str, object], *, query_id: str | None = None, bookmark: str | None = None) -> Mapping[str, object]:
        payload: dict[str, object] = {"cell_id": self._cell_id, "query": cypher, "parameters": parameters}
        if query_id is not None:
            payload["query_id"] = query_id
        if bookmark is not None:
            payload["bookmark"] = bookmark
        body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        try:
            return self._requester("POST", self._url, self._headers, body)
        except HydraHttpError:
            raise
        except Exception as error:
            raise HydraHttpError(f"local HydraDB request failed: {type(error).__name__}") from error


def _decode_value(value: object) -> object:
    if not isinstance(value, Mapping):
        raise HydraHttpError("HydraDB returned an untyped query value")
    value_type = value.get("type")
    if value_type == "null":
        return None
    if value_type in {"vertex_id", "integer", "signed_integer", "float", "boolean", "string"}:
        return value.get("value")
    if value_type == "list" and isinstance(value.get("value"), list):
        return [_decode_value(item) for item in value["value"]]
    raise HydraHttpError("HydraDB returned an unsupported query value")


# One keep-alive connection per (thread, host:port), not one per call.
# GraphExpander._fetch_node fires ~134 reads/query across a thread pool
# (HydraDB's Cypher subset rejects every batched-read form -- see
# graph_expander.py's own comments and its docstring's list of live-confirmed
# rejections); each read was previously its own fresh TCP handshake via
# urlopen. Reusing the connection per worker thread removes that handshake
# from every request but the pool's first, which is the only lever left once
# genuine query batching is off the table.
_connections = threading.local()


def _get_connection(scheme: str, host: str, port: int | None, timeout: float) -> http.client.HTTPConnection:
    cache: dict[tuple[str, str, int | None], http.client.HTTPConnection] = getattr(_connections, "cache", None)
    if cache is None:
        cache = {}
        _connections.cache = cache
    key = (scheme, host, port)
    conn = cache.get(key)
    if conn is None:
        conn_cls = http.client.HTTPSConnection if scheme == "https" else http.client.HTTPConnection
        conn = conn_cls(host, port, timeout=timeout)
        cache[key] = conn
    return conn


def _request_json(method: str, url: str, headers: Mapping[str, str], body: bytes, *, timeout: float = 15.0) -> Mapping[str, object]:
    parts = urlsplit(url)
    path = parts.path + (f"?{parts.query}" if parts.query else "")
    key = (parts.scheme, parts.hostname or "", parts.port)

    def _send(conn: http.client.HTTPConnection) -> Mapping[str, object]:
        conn.request(method, path, body=body, headers=dict(headers))
        response = conn.getresponse()
        raw = response.read()
        if response.status >= 400:
            detail = raw.decode("utf-8", errors="replace")[:500]
            raise HydraHttpError(f"HydraDB returned HTTP {response.status}: {detail}")
        try:
            decoded = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise HydraHttpError("HydraDB returned invalid JSON") from error
        if not isinstance(decoded, dict):
            raise HydraHttpError("HydraDB returned non-object JSON")
        return decoded

    conn = _get_connection(*key, timeout)
    try:
        return _send(conn)
    except HydraHttpError:
        # Don't trust this connection for the NEXT call on this thread just
        # because THIS call failed cleanly at the application level -- evict
        # it, but don't retry here (a genuine bad request/response wouldn't
        # produce a different result on a fresh connection; retrying would
        # only double the cost of a real failure).
        conn.close()
        _connections.cache.pop(key, None)
        raise
    except (http.client.HTTPException, OSError) as error:
        # A reused connection the server has since closed (idle timeout, HTTP
        # keep-alive max) surfaces here, not as a clean error -- indistinguishable
        # from a real fault until retried once on a fresh connection.
        conn.close()
        cache = _connections.cache
        cache.pop(key, None)
        fresh = _get_connection(*key, timeout)
        try:
            return _send(fresh)
        except (http.client.HTTPException, OSError) as retry_error:
            raise HydraHttpError(f"HydraDB network error: {retry_error}") from retry_error
