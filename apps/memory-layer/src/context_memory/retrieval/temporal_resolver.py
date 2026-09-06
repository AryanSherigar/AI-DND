"""Resolves a question's temporal reference (e.g. "before I moved") into a
validity window, one structured LLM call, before retrieval filters on it.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from context_memory.core.config import Config
from context_memory.core.llm_client import LLMClient
from context_memory.core.logging import get_logger, timed_operation
from context_memory.retrieval.models import DateRange

logger = get_logger(__name__)


class TemporalQueryResolver:
    def __init__(self, llm_client: LLMClient, config: Config | None = None) -> None:
        self._llm = llm_client
        self._config = config or Config()

    def resolve(self, question: str, question_date: datetime) -> DateRange:
        with timed_operation(logger, "retrieval.phase0.temporal_resolver", {"question_len": len(question)}) as ctx:
            system_prompt = self._config.temporal_resolver_system_prompt_template.format(
                question_date=question_date.isoformat()
            )
            try:
                response = self._llm.structured_completion(
                    system_prompt, question, DateRange,
                    temperature=self._config.llm_temperature, max_tokens=self._config.temporal_resolver_max_tokens,
                    timeout=self._config.temporal_resolver_timeout_seconds,
                    max_retries=self._config.llm_structured_retry_attempts,
                )
                if isinstance(response, DateRange):
                    buffer = timedelta(days=self._config.retrieval_temporal_buffer_days)
                    if response.valid_from:
                        response.valid_from -= buffer
                    if response.valid_to:
                        response.valid_to += buffer
                    ctx["valid_from"] = str(response.valid_from)
                    ctx["valid_to"] = str(response.valid_to)
                    return response
            except Exception as e:
                logger.warning("Temporal query resolver error: %s", e)
            return DateRange()
