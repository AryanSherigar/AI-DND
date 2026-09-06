"""Phase 3: LLM selection over the fused candidate pool (§23)."""

from __future__ import annotations

from context_memory.core.config import Config
from context_memory.core.llm_client import LLMClient
from context_memory.core.logging import get_logger, timed_operation
from context_memory.retrieval.models import RerankSelection, ScoredFact

logger = get_logger(__name__)


class Reranker:
    def __init__(self, rerank_client: LLMClient, config: Config | None = None) -> None:
        self._rerank_client = rerank_client
        self._config = config or Config()

    def rerank(self, question: str, ranked: list[ScoredFact], top_k: int) -> list[ScoredFact]:
        """Reorders the fused candidate pool with one LLM selection call (§23).

        Selected facts are promoted, in the model's own order, ahead of the rest;
        nothing is discarded, so a fact the model overlooks can still make the
        window on its RRF standing. Any failure (bad JSON, timeout, empty
        selection) returns `ranked` untouched -- reranking can only reorder, it
        can never lose a candidate or fail a query.
        """
        if not self._config.retrieval_rerank_enabled or len(ranked) <= top_k:
            return ranked
        pool = ranked[: self._config.retrieval_rerank_candidates]
        with timed_operation(logger, "retrieval.phase3.rerank", {"candidates": len(pool), "top_k": top_k}) as ctx:
            listing = "\n".join(f"[{i}] {(f.text or '').strip()[:220]}" for i, f in enumerate(pool))
            user_prompt = f"Question: {question}\n\nCandidates:\n{listing}\n\nSelect the relevant idx values."
            try:
                result = self._rerank_client.structured_completion(
                    self._config.rerank_system_prompt, user_prompt, RerankSelection,
                    temperature=self._config.llm_temperature,
                    max_tokens=self._config.retrieval_rerank_max_tokens,
                    timeout=self._config.retrieval_rerank_timeout_seconds,
                    max_retries=self._config.llm_structured_retry_attempts,
                )
            except Exception as error:
                logger.warning("Rerank failed, keeping RRF order: %s", error)
                ctx["rerank_applied"] = False
                return ranked

            seen: set[int] = set()
            promoted: list[ScoredFact] = []
            for idx in result.selected:
                if 0 <= idx < len(pool) and idx not in seen:
                    seen.add(idx)
                    promoted.append(pool[idx])
            if not promoted:
                ctx["rerank_applied"] = False
                return ranked
            ctx["rerank_applied"] = True
            ctx["rerank_selected"] = len(promoted)
            remainder = [f for i, f in enumerate(pool) if i not in seen] + ranked[len(pool):]
            return promoted + remainder
