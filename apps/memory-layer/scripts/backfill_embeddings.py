"""One-off backfill: re-embeds every active/inactive fact currently tagged
under the old local `sentence-transformers/all-MiniLM-L6-v2` model with the
new Vertex AI `text-embedding-005` model, then (only after verifying row
counts match) deletes the old rows.

Verify-then-delete, not delete-first: deleting before confirming the new
rows are complete risks facts going fully dark on a mid-run API failure,
with no way to reconstruct the source text from `memory_embeddings` alone.

Usage:
    set -a && source src/.env && set +a
    PYTHONPATH=src .venv/bin/python3 scripts/backfill_embeddings.py

    # Once the printed verification shows every context's old/new counts
    # match, delete the old-model rows:
    PYTHONPATH=src .venv/bin/python3 scripts/backfill_embeddings.py --delete-old
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys

sys.path.insert(0, "src")

from psycopg_pool import ConnectionPool

from context_memory.core.config import Config
from context_memory.core.models import Embedding
from context_memory.ingestion.embedding import VertexEmbedder
from context_memory.persistence.postgres import PostgresEmbeddingStore

_OLD_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
_OLD_MODEL_VERSION = "1"
_ROWS_PER_INSERT_BATCH = 200

_DISCOVER_SQL = """
SELECT me.context_id, me.subject_id, me.source_chunk_id, me.is_active, fsi.raw_text
FROM memory_embeddings me
JOIN fact_search_index fsi
  ON fsi.fact_id::text = me.subject_id AND fsi.context_id = me.context_id
WHERE me.subject_kind = 'fact'
  AND me.model_name = %s
  AND me.model_version = %s
ORDER BY me.context_id, me.subject_id
"""

_VERIFY_SQL = """
SELECT
    context_id,
    COUNT(*) FILTER (WHERE model_name = %s AND model_version = %s) AS old_count,
    COUNT(*) FILTER (WHERE model_name = %s AND model_version = %s) AS new_count
FROM memory_embeddings
WHERE subject_kind = 'fact'
GROUP BY context_id
"""

_DELETE_SQL = """
DELETE FROM memory_embeddings WHERE model_name = %s AND model_version = %s
"""


def _fetch_old_rows(pool: ConnectionPool) -> list[dict[str, object]]:
    with pool.connection() as conn, conn.cursor() as cursor:
        cursor.execute(_DISCOVER_SQL, (_OLD_MODEL_NAME, _OLD_MODEL_VERSION))
        columns = [d.name for d in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _re_embed_and_insert(
    pool: ConnectionPool, embedder: VertexEmbedder, config: Config, rows: list[dict]
) -> int:
    store = PostgresEmbeddingStore(pool)
    inserted = 0
    for start in range(0, len(rows), _ROWS_PER_INSERT_BATCH):
        chunk = rows[start : start + _ROWS_PER_INSERT_BATCH]
        texts = [row["raw_text"] for row in chunk]
        vectors = embedder.embed_batch(texts)
        embeddings = [
            Embedding(
                context_id=row["context_id"],
                subject_kind="fact",
                subject_id=row["subject_id"],
                source_chunk_id=row["source_chunk_id"],
                model_name=config.embedding_model_name,
                model_version=config.embedding_model_version,
                values=vector,
                embedded_content_hash=f"sha256:{hashlib.sha256(row['raw_text'].encode('utf-8')).hexdigest()}",
                is_active=row["is_active"],
            )
            for row, vector in zip(chunk, vectors)
        ]
        store.put_batch(embeddings)
        inserted += len(embeddings)
        print(f"backfill: embedded+inserted {inserted}/{len(rows)}")
    return inserted


def _verify(pool: ConnectionPool, config: Config) -> bool:
    with pool.connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            _VERIFY_SQL,
            (
                _OLD_MODEL_NAME,
                _OLD_MODEL_VERSION,
                config.embedding_model_name,
                config.embedding_model_version,
            ),
        )
        rows = cursor.fetchall()
    all_match = True
    for context_id, old_count, new_count in rows:
        if old_count and old_count != new_count:
            print(
                f"verify: MISMATCH context_id={context_id} old={old_count} new={new_count}"
            )
            all_match = False
    print(f"verify: {'PASS' if all_match else 'FAIL'} ({len(rows)} contexts checked)")
    return all_match


def _delete_old_rows(pool: ConnectionPool) -> None:
    with pool.connection() as conn, conn.transaction(), conn.cursor() as cursor:
        cursor.execute(_DELETE_SQL, (_OLD_MODEL_NAME, _OLD_MODEL_VERSION))
        print(f"delete: removed {cursor.rowcount} old-model embedding rows")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--database-url",
        default=os.getenv(
            "CONTEXT_MEMORY_DATABASE_URL",
            "postgresql://context_memory@127.0.0.1:54329/context_memory",
        ),
    )
    ap.add_argument(
        "--delete-old",
        action="store_true",
        help="Delete old-model rows after verification passes. Without this "
        "flag the script only backfills+verifies (safe to re-run).",
    )
    args = ap.parse_args()

    config = Config()
    pool = ConnectionPool(
        args.database_url,
        min_size=1,
        max_size=4,
        kwargs={"autocommit": True},
        open=True,
    )
    pool.wait()

    embedder = VertexEmbedder(
        api_key=config.embedding_api_key,
        model_name=config.embedding_model_name,
        model_version=config.embedding_model_version,
        task_type="RETRIEVAL_DOCUMENT",
    )

    rows = _fetch_old_rows(pool)
    print(f"backfill: {len(rows)} old-model fact embeddings to migrate")
    if rows:
        _re_embed_and_insert(pool, embedder, config, rows)

    verified = _verify(pool, config)
    if args.delete_old:
        if not verified:
            print("delete: skipped -- verification did not pass")
            return 1
        _delete_old_rows(pool)

    return 0 if verified else 1


if __name__ == "__main__":
    raise SystemExit(main())
