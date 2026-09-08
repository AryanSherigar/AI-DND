"""Vertex AI (Gemini) LLM client, via `google-genai`'s API-key auth mode --
NOT an OpenAI-compatible endpoint. Behind `ingestion.ports.EntityResolutionModel`
/ `TemporalUpdateModel` only. Never called from core; never called directly
from CI (see fakes.py).

Migrated from an OpenAI-SDK-compatible client (Groq by default) to Vertex AI
per the project's own decision to move every LLM call off OpenAI-SDK
compatibility. The public interface below (`structured_completion`/
`text_completion`/`chat_with_tools`, and the `.choices[0].message...` shape
`chat_with_tools` returns) is unchanged on purpose -- every caller
(`JournaledLLMClient`, `ReplayingLLMClient`, `run_tool_loop`, every
`model_adapters.py` class) is written against that shape, and
`ReplayingLLMClient` already had to reconstruct it from scratch for replay
(`_ReplayedChatResponse` et al. in `core/replay.py`) -- independent proof
it's the right seam to keep stable. Only what's behind `LLMClient` changed:
the real network call, the request/response translation, and rate-limit
detection.
"""

from __future__ import annotations

import json
import random
import re
import time
from collections.abc import Sequence
from typing import Any, Literal, Union, get_args, get_origin

from pydantic import BaseModel

from context_memory.core.logging import get_logger, timed_operation

logger = get_logger(__name__)


def _rate_limit_delay(error: Exception, attempt: int) -> float:
    """Seconds to wait before retrying a rate-limited call.

    Best-effort: looks for a structured retry delay in the error's own
    `details` payload (Google APIs commonly carry a `RetryInfo`-shaped
    hint), falling back to capped exponential backoff with jitter when none
    is found -- Vertex/Gemini doesn't share Groq's "try again in Xs" plain-
    text format this used to parse, so there's no text pattern to match
    here anymore. Jitter matters here specifically because extraction
    prefetch runs several workers concurrently -- without it, every worker
    that hit the same limit wakes at the same instant and immediately
    re-trips it.
    """
    retry_seconds = _extract_retry_delay_seconds(error)
    if retry_seconds is not None:
        return min(retry_seconds + random.uniform(0.1, 0.5), 60.0)
    return min(2.0**attempt + random.uniform(0.1, 0.5), 60.0)


_RETRY_DELAY_KEYS = ("retryDelay", "retry_delay")
_RETRY_DELAY_PATTERN = re.compile(r"([0-9.]+)\s*s")


def _extract_retry_delay_seconds(error: Exception) -> float | None:
    """Best-effort, defensive: `google.genai.errors.APIError.details` is the
    raw parsed error body, and this project has not observed a real 429
    response's exact shape to confirm where (or whether) Vertex puts a
    structured retry delay in it -- this scans a couple of plausible
    locations and returns `None` (falls back to backoff) rather than
    guessing further. Never raises: a malformed/missing detail is exactly
    the "no hint available" case, not an error in its own right.
    """
    details = getattr(error, "details", None)
    if not isinstance(details, dict):
        return None
    try:
        candidates: list[Any] = [details]
        error_body = details.get("error")
        if isinstance(error_body, dict):
            candidates.append(error_body)
            inner_details = error_body.get("details")
            if isinstance(inner_details, list):
                candidates.extend(d for d in inner_details if isinstance(d, dict))
        for candidate in candidates:
            for key in _RETRY_DELAY_KEYS:
                value = candidate.get(key)
                if isinstance(value, (int, float)):
                    return float(value)
                if isinstance(value, str):
                    match = _RETRY_DELAY_PATTERN.search(value)
                    if match:
                        return float(match.group(1))
    except Exception:
        return None
    return None


# Keys pydantic emits that constrain nothing the model needs: "title" is just a
# prettified field name it already has, and "default" describes what the caller
# does with an omitted field, not what the model may return. Stripping both, plus
# whitespace-free separators, cut the extraction schema 839 -> 479 chars (43%).
# That blob is sent on every single call, so at a tokens-per-minute rate limit it
# is a direct throughput cost, not a cosmetic one.
_JSON_DECODER = json.JSONDecoder()


def _recover_json_object(raw_text: str) -> str:
    """Returns the first parseable JSON object in `raw_text`.

    Providers wrap or corrupt the JSON body in ways `response_mime_type:
    application/json` does not prevent. Observed live, deterministically
    (6/6 calls), from Bedrock's `openai.gpt-oss-20b`: a spurious `{"`
    prefix, i.e. `{"{"facts":[...]}` where `{"facts":[...]}` was meant.
    Markdown ``` fences and leading prose are the other common shapes --
    kept as a defensive pass after the provider swap too, since Gemini can
    still wrap JSON in a markdown fence depending on the prompt.

    Scanning for the first balanced object handles all of them uniformly.
    Returns the input unchanged when nothing parses, so the caller's
    existing error path still reports the real provider output.
    """
    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    try:
        json.loads(text)
        return text
    except ValueError:
        pass

    # `raw_decode` stops at the end of the first valid value, so trailing junk
    # is tolerated; scanning every '{' also skips any leading junk.
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            value, _ = _JSON_DECODER.raw_decode(text, index)
        except ValueError:
            continue
        if isinstance(value, dict):
            # Re-serialize rather than slicing the original: raw_decode returns
            # the parsed value, and the source span may still contain the
            # corruption we are recovering from.
            return json.dumps(value)
    return raw_text


_SCHEMA_NOISE_KEYS = frozenset({"title", "default"})

_schema_cache: dict[type[BaseModel], str] = {}


def _strip_schema_noise(node: Any) -> Any:
    if isinstance(node, dict):
        return {
            k: _strip_schema_noise(v)
            for k, v in node.items()
            if k not in _SCHEMA_NOISE_KEYS
        }
    if isinstance(node, list):
        return [_strip_schema_noise(v) for v in node]
    return node


def _compact_schema_json(response_schema: type[BaseModel]) -> str:
    """Serialized once per schema class, then cached — the result is identical
    for every call with the same schema, and this runs on a per-turn hot path."""
    cached = _schema_cache.get(response_schema)
    if cached is None:
        cached = json.dumps(
            _strip_schema_noise(response_schema.model_json_schema()),
            separators=(",", ":"),
        )
        _schema_cache[response_schema] = cached
    return cached


_PRIMITIVE_TYPE_NAMES = {str: "string", int: "int", float: "float", bool: "bool"}

_typedef_cache: dict[type[BaseModel], str] = {}


def _model_name(model: type[BaseModel]) -> str:
    # Internal response models are underscore-prefixed by convention
    # (`_FactExtractionResponse`); that prefix is a Python visibility hint and
    # means nothing to the model, so it is not spent as prompt tokens.
    return model.__name__.lstrip("_")


def _render_type(annotation: Any) -> str:
    origin = get_origin(annotation)

    if origin is Literal:
        return " | ".join(json.dumps(value) for value in get_args(annotation))

    if origin is Union or origin is type(int | str):
        args = get_args(annotation)
        non_none = [a for a in args if a is not type(None)]
        suffix = "?" if type(None) in args else ""
        if not non_none:
            return "null"
        return _render_type(non_none[0]) + suffix

    if origin in (list, tuple, set, frozenset, Sequence):
        args = get_args(annotation)
        return (_render_type(args[0]) if args else "any") + "[]"

    if origin is dict:
        return "map"

    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return _model_name(annotation)

    return _PRIMITIVE_TYPE_NAMES.get(annotation, getattr(annotation, "__name__", "any"))


def _render_typedef(
    model: type[BaseModel], emitted: list[type[BaseModel]] | None = None
) -> str:
    """Renders a pydantic model as a compact TypeScript/BAML-style type
    declaration instead of JSON Schema.

    Measured on the extraction schema: 839 chars as pydantic JSON Schema, 479
    with the noise keys stripped, 225 as a typedef — 73% off the original, on a
    blob sent with every single call. JSON Schema spends most of its length on
    structural scaffolding (`"properties"`, `"type":"string"`, `"$defs"`,
    `"$ref"`) that a typedef expresses positionally. `response_mime_type` is
    still set to `application/json`, so JSON output remains provider-enforced;
    this only changes how the *shape* is described in the prompt.
    """
    emitted = [] if emitted is None else emitted
    if model in emitted:
        return ""
    emitted.append(model)

    nested_blocks: list[str] = []
    lines: list[str] = []
    for field_name, field in model.model_fields.items():
        annotation = field.annotation
        inner = annotation
        origin = get_origin(annotation)
        if origin in (list, tuple, set, frozenset, Sequence):
            args = get_args(annotation)
            inner = args[0] if args else None
        elif origin is Union or origin is type(int | str):
            non_none = [a for a in get_args(annotation) if a is not type(None)]
            inner = non_none[0] if non_none else None
        if isinstance(inner, type) and issubclass(inner, BaseModel):
            block = _render_typedef(inner, emitted)
            if block:
                nested_blocks.append(block)
        lines.append(f"  {field_name} {_render_type(annotation)}")

    block = "\n".join([f"class {_model_name(model)} {{", *lines, "}"])
    return "\n".join([*nested_blocks, block])


def _compact_schema_typedef(response_schema: type[BaseModel]) -> str:
    cached = _typedef_cache.get(response_schema)
    if cached is None:
        cached = _render_typedef(response_schema)
        _typedef_cache[response_schema] = cached
    return cached


def _is_rate_limit_error(error: Exception) -> bool:
    """`google.genai.errors.APIError` (and its `ClientError`/`ServerError`
    subclasses) exposes `.code` (the numeric HTTP status) and `.status`
    (Google's string enum, e.g. `RESOURCE_EXHAUSTED`) -- neither named
    `status_code`/`RateLimitError` the way the OpenAI SDK's did."""
    if getattr(error, "code", None) == 429:
        return True
    return getattr(error, "status", None) == "RESOURCE_EXHAUSTED"


class LLMClientError(RuntimeError):
    """Raised when a provider response cannot be parsed or validated."""


class LLMClient:
    """Thin structured/text/tool-calling wrapper over Vertex AI (Gemini),
    via `google-genai`'s `vertexai=True, api_key=...` mode -- not an
    OpenAI-compatible endpoint. See this module's own docstring for why the
    public shape below hasn't changed even though the transport has."""

    def __init__(
        self,
        api_key: str,
        model_name: str,
        *,
        client: Any | None = None,
        sdk_max_retries: int = 1,
        reasoning_effort: str = "",
        rate_limit_max_retries: int = 5,
        schema_format: str = "typedef",
        seed: int | None = None,
        service_tier: str = "",
    ) -> None:
        if not model_name:
            raise ValueError("model_name must be non-empty")
        self.api_key = api_key
        self.model = model_name
        self.sdk_max_retries = sdk_max_retries
        self.rate_limit_max_retries = rate_limit_max_retries
        # Vertex AI `service_tier`: "" (default) leaves it unset. "flex"
        # opts into Flex Processing -- see Config.llm_service_tier's field
        # comment for why real Batch mode isn't a value this accepts.
        self.service_tier = service_tier
        # "typedef" (compact TS/BAML-style) or "json_schema" (pydantic's own).
        # Provider-side JSON enforcement comes from `response_mime_type`, not
        # from this -- it only describes the shape, so switching formats
        # cannot make output non-JSON, only differently guided.
        self.schema_format = schema_format
        # Maps to Gemini's `thinking_config.thinking_level` (e.g. "low"/
        # "medium"/"high") -- forwarded verbatim, since the exact accepted
        # enum is a per-model-tier detail this client doesn't police, the
        # same posture the OpenAI-SDK client took toward
        # `reasoning_effort`'s own per-model-family enum differences.
        self.reasoning_effort = reasoning_effort
        # Best-effort determinism only: providers honour seed per backend
        # build and may ignore it. None omits the param.
        self.seed = seed
        self._client = client

    @property
    def client(self) -> Any:
        """Lazily constructs the underlying `google-genai` client (never at
        import time, and never if a fake was injected via `client=`) --
        `sdk_max_retries` maps to `HttpOptions.retry_options`, so a caller
        that already passes a fake `client=` never needs `google-genai`
        installed at all (this property is never touched)."""
        if self._client is None:
            from google import genai

            self._client = genai.Client(vertexai=True, api_key=self.api_key)
        return self._client

    def _apply_reasoning_effort(self, config_kwargs: dict[str, Any]) -> None:
        if self.reasoning_effort:
            from google.genai import types

            config_kwargs["thinking_config"] = types.ThinkingConfig(
                thinking_level=self.reasoning_effort
            )
        if self.seed is not None:
            config_kwargs["seed"] = self.seed

    def _generate_with_rate_limit_retry(self, *, contents: Any, config: Any) -> Any:
        """Issues the API call, retrying only on rate limiting.

        Distinct from `structured_completion`'s own retry loop, which handles a
        different failure: a successful response whose *content* is empty/
        unparseable. A 429 never reaches that loop -- it raises out of
        `.generate_content()` -- so it was previously not retried at all here,
        and the SDK's own retry budget (`sdk_max_retries`, deliberately
        lowered to 1 because it silently multiplies timeouts) is far too
        small for a token-per-minute limiter that can need multiple waits in
        a row. Confirmed live (pre-migration, against the prior OpenAI-
        compatible provider) that a rate limit without this retry failed
        outright and silently dropped a turn's facts -- the failure mode
        this exists to prevent, not a hypothetical one specific to the old
        transport.
        """
        last_error: Exception | None = None
        for attempt in range(self.rate_limit_max_retries + 1):
            try:
                return self.client.models.generate_content(
                    model=self.model, contents=contents, config=config
                )
            except Exception as error:
                if (
                    not _is_rate_limit_error(error)
                    or attempt == self.rate_limit_max_retries
                ):
                    raise
                last_error = error
                delay = _rate_limit_delay(error, attempt)
                logger.warning(
                    "Rate limited (attempt %d/%d); waiting %.1fs before retry",
                    attempt + 1,
                    self.rate_limit_max_retries + 1,
                    delay,
                )
                time.sleep(delay)
        raise last_error if last_error else RuntimeError("unreachable")

    def _build_config(
        self,
        *,
        system_instruction: str | None,
        temperature: float,
        max_tokens: int | None,
        timeout: float | None,
        json_mode: bool,
        tools: Any | None = None,
    ) -> Any:
        from google.genai import types

        config_kwargs: dict[str, Any] = {"temperature": temperature}
        if system_instruction is not None:
            config_kwargs["system_instruction"] = system_instruction
        if max_tokens is not None:
            config_kwargs["max_output_tokens"] = max_tokens
        if json_mode:
            config_kwargs["response_mime_type"] = "application/json"
        if timeout is not None:
            # `HttpOptions.timeout` is milliseconds; every call site here
            # passes seconds (this client's own pre-migration convention).
            config_kwargs["http_options"] = types.HttpOptions(
                timeout=int(timeout * 1000)
            )
        if tools:
            config_kwargs["tools"] = tools
            # This client drives its own tool-calling loop (`run_tool_loop`)
            # -- the SDK must never execute a function on its own behalf.
            config_kwargs["automatic_function_calling"] = (
                types.AutomaticFunctionCallingConfig(disable=True)
            )
        if self.service_tier:
            config_kwargs["service_tier"] = types.ServiceTier(self.service_tier)
        self._apply_reasoning_effort(config_kwargs)
        return types.GenerateContentConfig(**config_kwargs)

    def structured_completion(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema: type[BaseModel],
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        timeout: float | None = None,
        max_retries: int = 1,
    ) -> BaseModel:
        """Call the model with a JSON-object response constrained to `response_schema`.

        `max_tokens`/`timeout` default to `None` (provider default, unbounded) only
        for direct callers that don't go through `Config` — every real call site in
        this codebase passes both, specifically because an uncapped call has hung
        for minutes and returned nothing (empty completion, hit the model's own
        output ceiling before producing valid JSON) — confirmed against a live
        provider (pre-migration), not a hypothetical. See `core/config.py`'s
        per-role `<role>_max_tokens`/`<role>_timeout_seconds` fields (sized
        differently per role — extraction reasons before emitting JSON and
        needs more headroom than a one-word classification call).

        A capped budget bounds worst-case latency but doesn't stop the model from
        spending the *entire* cap on hidden reasoning and returning empty content.
        `max_retries` (default 1) recovers from that: on an empty/unparseable
        response, retries with a blunter "stop reasoning, emit JSON now" nudge,
        and — only when the failure's `finish_reason` was `MAX_TOKENS` (budget
        genuinely exhausted, not malformed content) — a doubled token budget
        for that one retry. (Gemini's finish-reason enum uses `MAX_TOKENS`
        where the prior OpenAI-compatible provider used `length`.)
        """
        schema_name = response_schema.__name__
        with timed_operation(
            logger,
            f"llm.structured_completion[{schema_name}]",
            {"model": self.model, "prompt_chars": len(user_prompt)},
        ) as ctx:
            if self.schema_format == "typedef":
                augmented_system = f"{system_prompt}\n\nReturn JSON matching:\n{_compact_schema_typedef(response_schema)}"
            else:
                augmented_system = f"{system_prompt}\n\nReturn JSON matching this schema:\n{_compact_schema_json(response_schema)}"
            current_user_prompt = user_prompt
            current_max_tokens = max_tokens
            last_error: Exception | None = None

            from google.genai import types

            for attempt in range(max_retries + 1):
                config = self._build_config(
                    system_instruction=augmented_system,
                    temperature=temperature,
                    max_tokens=current_max_tokens,
                    timeout=timeout,
                    json_mode=True,
                )
                contents = [
                    types.Content(
                        role="user", parts=[types.Part(text=current_user_prompt)]
                    )
                ]
                response = self._generate_with_rate_limit_retry(
                    contents=contents, config=config
                )
                usage = response.usage_metadata
                if usage is not None:
                    ctx["prompt_tokens"] = usage.prompt_token_count
                    ctx["completion_tokens"] = usage.candidates_token_count
                    ctx["total_tokens"] = usage.total_token_count
                candidates = response.candidates or []
                finish_reason = candidates[0].finish_reason if candidates else None

                raw_text = response.text
                try:
                    if not raw_text:
                        raise ValueError("empty completion content")
                    return response_schema.model_validate_json(
                        _recover_json_object(raw_text)
                    )
                except Exception as error:  # pydantic ValidationError, malformed JSON, or empty content
                    last_error = error
                    if attempt < max_retries:
                        ran_out_of_budget = (
                            finish_reason == types.FinishReason.MAX_TOKENS
                        )
                        logger.warning(
                            "structured_completion[%s] attempt %d/%d returned unparseable output "
                            "(finish_reason=%s) — retrying%s",
                            schema_name,
                            attempt + 1,
                            max_retries + 1,
                            finish_reason,
                            " with a doubled token budget"
                            if ran_out_of_budget and current_max_tokens
                            else "",
                        )
                        current_user_prompt = (
                            f"{user_prompt}\n\n(Your previous response was empty or not valid JSON. Stop "
                            "reasoning and respond with ONLY the JSON object now — no other text.)"
                        )
                        if ran_out_of_budget and current_max_tokens is not None:
                            current_max_tokens = min(current_max_tokens * 2, 16384)
                        continue
                    logger.error(
                        "Failed to parse LLM structured completion to %s after %d attempt(s): raw_response=%r",
                        schema_name,
                        max_retries + 1,
                        raw_text,
                    )
                    raise LLMClientError(
                        f"model response did not match {response_schema.__name__}"
                    ) from last_error

    def text_completion(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
        *,
        max_tokens: int | None = None,
        timeout: float | None = None,
    ) -> str:
        """Plain text generation, used for reader/answer-generation."""
        with timed_operation(
            logger,
            "llm.text_completion",
            {"model": self.model, "prompt_chars": len(user_prompt)},
        ) as ctx:
            from google.genai import types

            config = self._build_config(
                system_instruction=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
                json_mode=False,
            )
            contents = [
                types.Content(role="user", parts=[types.Part(text=user_prompt)])
            ]
            response = self._generate_with_rate_limit_retry(
                contents=contents, config=config
            )
            usage = response.usage_metadata
            if usage is not None:
                ctx["prompt_tokens"] = usage.prompt_token_count
                ctx["completion_tokens"] = usage.candidates_token_count
                ctx["total_tokens"] = usage.total_token_count

            content = response.text or ""
            ctx["response_chars"] = len(content)
            return content

    def chat_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        timeout: float | None = None,
    ) -> Any:
        """Phase 9: one turn of a tool-calling loop. Returns an object shaped
        like the OpenAI SDK's `ChatCompletion` (`.choices[0].message.content`/
        `.tool_calls[].function.name`/`.arguments` as a JSON string) --
        `run_tool_loop` (`core/tool_loop.py`) is the one place that inspects
        this, and every other caller of this client's shape (`journal.py`,
        `agent_tools.py`) already assumes it. Internally this is a genuine
        Vertex/Gemini call (`function_declarations`/`function_call.args` as a
        dict) -- this method's job is the network call, its rate-limit
        retry, and translating Gemini's real response into that stable
        shape, same division of labor as `structured_completion`/
        `text_completion`.
        """

        with timed_operation(
            logger,
            "llm.chat_with_tools",
            {"model": self.model, "message_count": len(messages)},
        ) as ctx:
            system_instruction, contents = _messages_to_gemini_contents(messages)
            genai_tools = _tools_to_gemini(tools) if tools else None
            config = self._build_config(
                system_instruction=system_instruction,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
                json_mode=False,
                tools=genai_tools,
            )
            response = self._generate_with_rate_limit_retry(
                contents=contents, config=config
            )
            usage = response.usage_metadata
            if usage is not None:
                ctx["prompt_tokens"] = usage.prompt_token_count
                ctx["completion_tokens"] = usage.candidates_token_count
                ctx["total_tokens"] = usage.total_token_count
            wrapped = _GeminiChatResponse(response)
            message = wrapped.choices[0].message
            ctx["tool_calls"] = len(message.tool_calls) if message.tool_calls else 0
            return wrapped


def _messages_to_gemini_contents(
    messages: list[dict[str, Any]],
) -> tuple[str | None, list[Any]]:
    """Translates `run_tool_loop`'s OpenAI-shaped message history (`role`:
    system/user/assistant/tool, assistant `tool_calls`, tool `content`) into
    Gemini's `(system_instruction, contents)` shape: Gemini takes the system
    prompt as a separate field, never a message in the list, and uses
    `role: user/model` (an assistant turn is `"model"`, never
    `"assistant"`); a tool result becomes a `function_response` part on a
    `user`-role turn, Gemini's own convention for feeding a tool's output
    back to the model."""
    from google.genai import types

    system_instruction: str | None = None
    contents: list[Any] = []
    # `tool_call_id -> function name`, needed because Gemini's
    # `function_response` part is keyed by name, not by the OpenAI-style
    # opaque call id `run_tool_loop` tracks in `tool_call_id`.
    name_by_call_id: dict[str, str] = {}

    for message in messages:
        role = message.get("role")
        if role == "system":
            system_instruction = message.get("content") or None
            continue
        if role == "user":
            contents.append(
                types.Content(
                    role="user", parts=[types.Part(text=message.get("content") or "")]
                )
            )
            continue
        if role == "assistant":
            parts: list[Any] = []
            if message.get("content"):
                parts.append(types.Part(text=message["content"]))
            for tool_call in message.get("tool_calls") or []:
                function = tool_call["function"]
                name_by_call_id[tool_call["id"]] = function["name"]
                try:
                    args = json.loads(function.get("arguments") or "{}")
                except ValueError:
                    args = {}
                parts.append(
                    types.Part(
                        function_call=types.FunctionCall(
                            name=function["name"], args=args
                        )
                    )
                )
            contents.append(types.Content(role="model", parts=parts))
            continue
        if role == "tool":
            call_id = message.get("tool_call_id")
            name = name_by_call_id.get(call_id, call_id or "unknown_tool")
            try:
                response_payload = json.loads(message.get("content") or "{}")
            except ValueError:
                response_payload = {"result": message.get("content")}
            if not isinstance(response_payload, dict):
                response_payload = {"result": response_payload}
            contents.append(
                types.Content(
                    role="user",
                    parts=[
                        types.Part(
                            function_response=types.FunctionResponse(
                                name=name,
                                response=response_payload,
                            )
                        )
                    ],
                )
            )
            continue
    return system_instruction, contents


def _tools_to_gemini(tools: list[dict[str, Any]]) -> list[Any]:
    """Translates `ToolRegistry.to_openai_tools()`'s shape
    (`{"type": "function", "function": {"name", "description", "parameters"}}`)
    into `[types.Tool(function_declarations=[...])]` -- Gemini groups every
    declared function under one `Tool`, rather than one entry per tool the
    OpenAI shape uses."""
    from google.genai import types

    declarations = [
        types.FunctionDeclaration(
            name=tool["function"]["name"],
            description=tool["function"].get("description"),
            parameters=tool["function"].get("parameters"),
        )
        for tool in tools
        if tool.get("type") == "function"
    ]
    return [types.Tool(function_declarations=declarations)] if declarations else []


class _FunctionCallShape:
    def __init__(self, name: str, arguments: str) -> None:
        self.name = name
        self.arguments = arguments


class _ToolCallShape:
    def __init__(self, call_id: str, name: str, arguments: str) -> None:
        self.id = call_id
        self.function = _FunctionCallShape(name, arguments)


class _MessageShape:
    def __init__(self, content: str | None, tool_calls: list[_ToolCallShape]) -> None:
        self.content = content
        self.tool_calls = tool_calls


class _ChoiceShape:
    def __init__(self, message: _MessageShape) -> None:
        self.message = message


class _GeminiChatResponse:
    """Adapts a real `google.genai.types.GenerateContentResponse` into the
    OpenAI-SDK-shaped `.choices[0].message.content`/`.tool_calls[]` object
    every caller of `chat_with_tools` already expects -- see
    `LLMClient.chat_with_tools`'s docstring for why this shape is kept
    rather than propagated as a provider-specific one. Mirrors
    `core/replay.py`'s `_ReplayedChatResponse` (built independently, for
    the opposite direction: reconstructing this same shape from a journaled
    payload instead of a live SDK response) -- consistent proof this is
    the one true shape to converge on.
    """

    def __init__(self, response: Any) -> None:
        candidates = response.candidates or []
        content_parts = (
            candidates[0].content.parts if candidates and candidates[0].content else []
        )
        content_parts = content_parts or []

        text_parts = [p.text for p in content_parts if getattr(p, "text", None)]
        tool_calls = [
            _ToolCallShape(
                call_id=getattr(p.function_call, "id", None) or f"call_{i}",
                name=p.function_call.name,
                arguments=json.dumps(p.function_call.args or {}),
            )
            for i, p in enumerate(content_parts)
            if getattr(p, "function_call", None) is not None
        ]
        message = _MessageShape(
            content="".join(text_parts) or None, tool_calls=tool_calls
        )
        self.choices = [_ChoiceShape(message)]
