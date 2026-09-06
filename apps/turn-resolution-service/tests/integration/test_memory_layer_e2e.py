"""Full-stack, 10-turn integration test against a live memory-layer deployment.

Precondition: `docker compose up -d` must already be running from the repo
root (postgres, postgres-memory, hydradb, memory-layer, core-api). This test
is skipped cleanly if the stack isn't reachable -- it never fails/hangs a
plain `pytest` run.

Stack shape (see plan §8 for why): Core API is driven over REAL network HTTP
against its live docker-compose container -- Core API's `app` package cannot
be imported into this process alongside TRS's own `app` package (both
services use the top-level module name `app`; only one can be imported per
Python process, and each has its own separate venv/pyproject.toml). TRS's
own app is mounted in-process via ASGITransport instead, which lets Gemini be
faked with a plain monkeypatch while every other call -- memory-layer,
HydraDB, Postgres -- is real. TRS's app talks to the real dev Postgres via
its own default `settings.database_url`; no dependency override is used,
since that engine is never pointed at an isolated test database anywhere in
this codebase (only `tests/conftest.py`'s own fixtures build a separate one).

Known limitation this test can surface, not fix: memory-layer's own docs
(apps/memory-layer/docs/BEGINNER_BUILD_FLOW.md §46) document that
authoring-time (master-mode) facts are written to the graph but never
projected into the Postgres retrieval indexes retrieval starts from -- so a
pre-authored fact (the hidden/when_active/superseded_fact_id fixtures below)
may never be retrievable via POST /v1/memory/query today, independent of
whether this product's own filtering code is correct. Those three
assertions are recorded as informational (not hard-failing) for exactly this
reason; the round-trip assertion (a fact stated in ordinary turn narration,
which goes through the unaffected runtime-extraction path) is the one hard
pass/fail signal in this test.
"""

from __future__ import annotations

import asyncio
import json
import statistics
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import httpx
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

pytestmark = pytest.mark.integration

CORE_API_BASE_URL = "http://localhost:8000"
HEALTH_TIMEOUT_SECONDS = 3.0
TURN_COUNT = 10
QUEST_FLAG_TURN = 6
REVEAL_TURN = 7
REPORT_PATH = Path(__file__).parent / "reports" / "memory_layer_e2e_report.md"


# --------------------------------------------------------------------------
# Reachability gate -- skip cleanly, never hang/fail, when the stack is down.
# --------------------------------------------------------------------------


async def _stack_reachable() -> str | None:
    """Return None if the full stack is reachable, else a skip reason."""
    from app.config import settings

    async with httpx.AsyncClient(timeout=HEALTH_TIMEOUT_SECONDS) as client:
        try:
            r = await client.get(f"{settings.memory_service_url}/v1/health")
            if r.status_code >= 500:
                return f"memory-layer unhealthy: {r.status_code}"
        except httpx.HTTPError as exc:
            return f"memory-layer unreachable at {settings.memory_service_url}: {exc}"
        try:
            r = await client.get(f"{CORE_API_BASE_URL}/health")
            if r.status_code >= 500:
                return f"core-api unhealthy: {r.status_code}"
        except httpx.HTTPError as exc:
            return f"core-api unreachable at {CORE_API_BASE_URL}: {exc}"
    return None


@pytest.fixture(scope="module", autouse=True)
async def require_live_stack() -> None:
    reason = await _stack_reachable()
    if reason:
        pytest.skip(f"live docker-compose stack not reachable: {reason}")


# --------------------------------------------------------------------------
# Metrics / report collection
# --------------------------------------------------------------------------


@dataclass
class Metrics:
    latencies_ms: dict[str, list[float]] = field(default_factory=dict)
    behaviors: dict[str, tuple[bool, str]] = field(default_factory=dict)
    fact_counts: dict[str, int] = field(default_factory=dict)
    started_at: float = field(default_factory=time.perf_counter)

    def record(self, call_name: str, duration_ms: float) -> None:
        self.latencies_ms.setdefault(call_name, []).append(duration_ms)

    def record_behavior(self, name: str, passed: bool, detail: str) -> None:
        self.behaviors[name] = (passed, detail)

    def _latency_table(self) -> str:
        rows = ["| call | n | min | mean | p95 | max |", "|---|---|---|---|---|---|"]
        for name, values in sorted(self.latencies_ms.items()):
            ordered = sorted(values)
            p95_index = min(len(ordered) - 1, int(len(ordered) * 0.95))
            rows.append(
                f"| {name} | {len(values)} | {ordered[0]:.1f}ms | "
                f"{statistics.mean(values):.1f}ms | {ordered[p95_index]:.1f}ms | "
                f"{ordered[-1]:.1f}ms |"
            )
        return "\n".join(rows)

    def _behavior_table(self) -> str:
        rows = ["| behavior | result | detail |", "|---|---|---|"]
        for name, (passed, detail) in self.behaviors.items():
            rows.append(f"| {name} | {'PASS' if passed else 'FAIL'} | {detail} |")
        return "\n".join(rows)

    def render(self) -> str:
        total_s = time.perf_counter() - self.started_at
        counts = "\n".join(f"- {k}: {v}" for k, v in self.fact_counts.items())
        return (
            "# Memory-layer 10-turn integration report\n\n"
            f"Total wall-clock time: {total_s:.2f}s\n\n"
            f"## Latency per call type\n\n{self._latency_table()}\n\n"
            f"## Behavior assertions\n\n{self._behavior_table()}\n\n"
            f"## Fact counts\n\n{counts}\n"
        )

    def write(self) -> None:
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        rendered = self.render()
        REPORT_PATH.write_text(rendered)
        print("\n" + rendered)


# --------------------------------------------------------------------------
# Core API helpers (real network HTTP against the live container)
# --------------------------------------------------------------------------


def _dev_headers(user_id: uuid.UUID) -> dict[str, str]:
    return {"x-dev-user-id": str(user_id)}


async def _create_scenario(client: AsyncClient, user_id: uuid.UUID, title: str) -> dict:
    payload = {
        "title": title,
        "mode": "master",
        "complexity_tier": "master",
        "content_tag": "all-ages",
        "player_count_support": "solo",
    }
    r = await client.post("/v1/scenarios", json=payload, headers=_dev_headers(user_id))
    r.raise_for_status()
    return r.json()


async def _create_entity(
    client: AsyncClient, user_id: uuid.UUID, scenario_id: str
) -> dict:
    payload = {"entity_type": "character", "canonical_name": "The King"}
    r = await client.post(
        f"/v1/scenarios/{scenario_id}/entities",
        json=payload,
        headers=_dev_headers(user_id),
    )
    r.raise_for_status()
    return r.json()


async def _create_fact(
    client: AsyncClient, user_id: uuid.UUID, scenario_id: str, payload: dict
) -> dict:
    r = await client.post(
        f"/v1/scenarios/{scenario_id}/facts",
        json=payload,
        headers=_dev_headers(user_id),
    )
    r.raise_for_status()
    return r.json()


async def _author_fixture_facts(
    client: AsyncClient, user_id: uuid.UUID, scenario_id: str, entity_id: str
) -> dict[str, dict]:
    """Author the four fixture facts exercising supersession, hidden, and
    when_active. Returns them keyed by role for later assertions."""
    fact_alive = await _create_fact(
        client,
        user_id,
        scenario_id,
        {
            "subject_entity_id": entity_id,
            "predicate": "status",
            "object_literal": "alive",
        },
    )
    fact_dead = await _create_fact(
        client,
        user_id,
        scenario_id,
        {
            "subject_entity_id": entity_id,
            "predicate": "status",
            "object_literal": "dead",
            "superseded_fact_id": fact_alive["fact_id"],
        },
    )
    fact_hidden = await _create_fact(
        client,
        user_id,
        scenario_id,
        {
            "subject_entity_id": entity_id,
            "predicate": "secret",
            "object_literal": "a passage hidden behind the throne",
            "hidden": True,
        },
    )
    fact_conditional = await _create_fact(
        client,
        user_id,
        scenario_id,
        {
            "subject_entity_id": entity_id,
            "predicate": "reward",
            "object_literal": "grants the Sunstone Amulet",
            "when_active": {
                "field": "custom_flags.quest_started",
                "op": "==",
                "value": True,
            },
        },
    )
    return {
        "alive": fact_alive,
        "dead": fact_dead,
        "hidden": fact_hidden,
        "conditional": fact_conditional,
    }


async def _publish_and_wait(
    client: AsyncClient, user_id: uuid.UUID, scenario_id: str, metrics: Metrics
) -> None:
    start = time.perf_counter()
    r = await client.post(
        f"/v1/scenarios/{scenario_id}/publish", headers=_dev_headers(user_id)
    )
    r.raise_for_status()
    for _ in range(60):
        r = await client.get(
            f"/v1/scenarios/{scenario_id}", headers=_dev_headers(user_id)
        )
        r.raise_for_status()
        status_value = r.json()["status"]
        if status_value == "published":
            break
        if status_value == "publish_failed":
            raise AssertionError(f"scenario publish failed: {r.json()}")
        await asyncio.sleep(0.5)
    else:
        raise AssertionError("scenario did not reach 'published' within 30s")
    metrics.record(
        "ingest_scenario_template (publish, wall-clock)",
        (time.perf_counter() - start) * 1000,
    )


async def _create_playthrough(
    client: AsyncClient, user_id: uuid.UUID, scenario_id: str, metrics: Metrics
) -> dict:
    start = time.perf_counter()
    r = await client.post(
        "/v1/playthroughs",
        json={"scenario_id": scenario_id},
        headers=_dev_headers(user_id),
    )
    r.raise_for_status()
    metrics.record(
        "clone_template_memory_space (wall-clock)", (time.perf_counter() - start) * 1000
    )
    return r.json()


# --------------------------------------------------------------------------
# TRS helpers (in-process ASGI app, real dev Postgres, faked Gemini)
# --------------------------------------------------------------------------


class _FakeToolResponse:
    """Duck-types `types.GenerateContentResponse` for the two attributes
    `_generate_master_mode` actually reads: `function_calls` (empty means
    "no mutation this turn, use `.text` as the final narration") and
    `.text`."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.function_calls: list[object] = []


def _canned_narration(turn_number: int) -> str:
    """Phrased as enduring state facts, not transient events -- mem1's real
    extraction system prompt targets "enduring facts about the user" (e.g.
    pet_name, location); an event-phrased sentence like "you discover X"
    reliably extracts zero facts under that prompt (verified directly
    against the live model), while a state-phrased one ("you now possess
    X") extracts reliably. Not a bug in either product's code -- a real
    content/prompt-fit finding worth the test reflecting accurately."""
    if turn_number == 2:
        return (
            "You now possess the legendary Sunstone Amulet, a rare treasure "
            "that grants its bearer immunity to fire."
        )
    return f"Turn {turn_number}: the torches flicker as you press onward."


async def _submit_turn(
    trs_client: AsyncClient,
    user_id: uuid.UUID,
    playthrough_id: str,
    participant_id: str,
    turn_number: int,
) -> None:
    r = await trs_client.post(
        "/v1/turn",
        json={
            "playthrough_id": playthrough_id,
            "participant_id": participant_id,
            "action_text": f"I look around (turn {turn_number}).",
        },
        headers=_dev_headers(user_id),
    )
    r.raise_for_status()
    assert "event: done" in r.text


async def _patch_playthrough_state(engine, playthrough_id: str, patch: dict) -> None:
    """Direct DB write used only as a test knob to flip game_state for the
    when_active/hidden assertions -- not exercising the real state-mutation
    path, which is already covered by other, non-integration tests."""
    async with engine.connect() as conn:
        await conn.execute(
            text(
                "UPDATE playthroughs SET state = state || CAST(:patch AS jsonb) WHERE playthrough_id = :pid"
            ),
            {"patch": json.dumps(patch), "pid": playthrough_id},
        )
        await conn.commit()


async def _lookup_participant_id(engine, playthrough_id: str) -> str:
    async with engine.connect() as conn:
        row = (
            await conn.execute(
                text(
                    "SELECT participant_id FROM participants WHERE playthrough_id = :pid LIMIT 1"
                ),
                {"pid": playthrough_id},
            )
        ).first()
    return str(row[0])


def _spy_memory_client(
    monkeypatch: pytest.MonkeyPatch, metrics: Metrics, batch_ids: list[str]
) -> None:
    from app.integrations import memory_client

    def _make_spy(fn_name: str, fn):
        async def _spy(*args, **kwargs):
            start = time.perf_counter()
            result = await fn(*args, **kwargs)
            metrics.record(fn_name, (time.perf_counter() - start) * 1000)
            if fn_name == "ingest_batch":
                batch_ids.append(str(result.batch_id))
            return result

        return _spy

    for name in ("query_memory", "ingest_batch", "get_batch_status", "retry_batch"):
        monkeypatch.setattr(
            memory_client, name, _make_spy(name, getattr(memory_client, name))
        )


async def _wait_for_batch_succeeded(batch_id: str, metrics: Metrics) -> int:
    """Poll batch status; retry once via the real POST .../retry endpoint on
    a retryable failure -- mem1's own documented reliability contract (the
    calling game engine drives retries, mem1 never silently retries itself).
    Not exercised by any real caller today (memory_writer.py's own known
    catch-up gap, see the module docstring), but this is the designed path."""
    from app.integrations import memory_client

    start = time.perf_counter()
    retried = False
    for _ in range(90):
        status_obj = await memory_client.get_batch_status(uuid.UUID(batch_id))
        if status_obj.status == "succeeded":
            metrics.record(
                "ingest_batch_turnaround (POST to succeeded)",
                (time.perf_counter() - start) * 1000,
            )
            return status_obj.facts_created
        if (
            status_obj.status in ("failed", "partial")
            and status_obj.retryable
            and not retried
        ):
            retried = True
            await memory_client.retry_batch(uuid.UUID(batch_id))
        elif status_obj.status in ("failed", "partial"):
            raise AssertionError(
                f"ingest batch {batch_id} {status_obj.status}: {status_obj.error}"
            )
        await asyncio.sleep(1.0)
    raise AssertionError(f"batch {batch_id} did not succeed within 90s")


# --------------------------------------------------------------------------
# The test
# --------------------------------------------------------------------------


async def test_ten_turn_full_stack_memory_integration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.db.connection import async_engine
    from app.integrations import memory_client
    from app.main import app as trs_app
    from app.models.memory import MemoryQueryRequest
    from app.turn.steps import ai_orchestrator

    metrics = Metrics()
    batch_ids: list[str] = []
    _spy_memory_client(monkeypatch, metrics, batch_ids)

    user_id = uuid.uuid4()
    marker = str(uuid.uuid4())[:8]

    async with AsyncClient(base_url=CORE_API_BASE_URL, timeout=15.0) as core_client:
        scenario = await _create_scenario(
            core_client, user_id, f"Integration Test Scenario {marker}"
        )
        scenario_id = scenario["scenario_id"]
        entity = await _create_entity(core_client, user_id, scenario_id)
        fixture_facts = await _author_fixture_facts(
            core_client, user_id, scenario_id, entity["entity_id"]
        )
        metrics.fact_counts["facts_authored"] = len(fixture_facts)

        await _publish_and_wait(core_client, user_id, scenario_id, metrics)
        playthrough = await _create_playthrough(
            core_client, user_id, scenario_id, metrics
        )
        playthrough_id = playthrough["playthrough_id"]

    participant_id = await _lookup_participant_id(async_engine, playthrough_id)
    await _patch_playthrough_state(
        async_engine,
        playthrough_id,
        {"custom_flags": {"quest_started": False}, "revealed_facts": []},
    )

    async with AsyncClient(
        transport=ASGITransport(app=trs_app), base_url="http://testserver"
    ) as trs_client:
        for turn_number in range(1, TURN_COUNT + 1):

            async def _turn_stream(
                system_instruction, prompt, timeout_seconds, _tn=turn_number
            ):
                yield _canned_narration(_tn)

            async def _turn_tools(
                system_instruction, contents, timeout_seconds, tools, _tn=turn_number
            ):
                return _FakeToolResponse(_canned_narration(_tn))

            # Master-mode turns route through `generate_with_tools` (a
            # function-calling round-trip), not `stream_narration` -- only
            # newbie-mode uses the latter. Patch both so canned narration
            # reaches memory_writer.py regardless of scenario mode.
            monkeypatch.setattr(
                ai_orchestrator.gemini_client, "stream_narration", _turn_stream
            )
            monkeypatch.setattr(
                ai_orchestrator.gemini_client, "generate_with_tools", _turn_tools
            )

            if turn_number == QUEST_FLAG_TURN:
                await _patch_playthrough_state(
                    async_engine,
                    playthrough_id,
                    {"custom_flags": {"quest_started": True}},
                )
            if turn_number == REVEAL_TURN:
                await _patch_playthrough_state(
                    async_engine,
                    playthrough_id,
                    {"revealed_facts": [fixture_facts["hidden"]["fact_id"]]},
                )

            await _submit_turn(
                trs_client, user_id, playthrough_id, participant_id, turn_number
            )

        # Behavior 1: batch ingest fires at turn 5 and turn 10, succeeds with facts_created > 0.
        assert len(batch_ids) >= 2, (
            f"expected >=2 ingest_batch calls (turns 5,10), got {len(batch_ids)}"
        )
        total_facts_created = 0
        for batch_id in batch_ids[-2:]:
            total_facts_created += await _wait_for_batch_succeeded(batch_id, metrics)
        metrics.fact_counts["facts_created_by_ingest"] = total_facts_created
        metrics.record_behavior(
            "batch_ingest_timing",
            total_facts_created > 0,
            f"{len(batch_ids)} batches fired, {total_facts_created} facts created across the last 2",
        )

        base_query = {
            "scenario_id": uuid.UUID(scenario_id),
            "playthrough_id": uuid.UUID(playthrough_id),
            "participant_id": uuid.UUID(participant_id),
            "checkpoint": "",
            "as_of_turn": TURN_COUNT,
        }

        # Behavior 2: fact round-trip (unaffected by mem1's authored-fact gap).
        round_trip_response = await memory_client.query_memory(
            MemoryQueryRequest(
                **base_query, query_text="Sunstone Amulet", game_state={}
            )
        )
        metrics.fact_counts["facts_retrieved_round_trip_query"] = len(
            round_trip_response.facts
        )
        found = any(
            "sunstone" in f.object.lower() or "sunstone" in f.subject.lower()
            for f in round_trip_response.facts
        )
        metrics.record_behavior(
            "fact_round_trip",
            found,
            "turn-2 narrated fact retrievable at turn 10"
            if found
            else "not found -- check extraction/ingestion timing or retrieval dilution",
        )

        # Behaviors 3-5: authored-fact visibility/supersession -- informational,
        # since mem1's own documented gap #46 can make ALL authored facts
        # unretrievable regardless of whether this product's filtering is correct.
        #
        # Matched by fact_id, not text substring: an earlier version of this
        # test matched "sunstone amulet" in f.object, which coincidentally
        # also matches the *runtime*-extracted turn-2 fact ("You now possess
        # the legendary Sunstone Amulet...") -- so visibility_filtering_when_gated
        # reported PASS even on a run where gap #46 meant zero authored facts
        # were indexed at all. fact_id identifies exactly one specific authored
        # fact and cannot be satisfied by an unrelated fact that merely shares
        # vocabulary.
        gated_response = await memory_client.query_memory(
            MemoryQueryRequest(
                **base_query,
                query_text="king status secret reward",
                game_state={
                    "custom_flags": {"quest_started": True},
                    "revealed_facts": [fixture_facts["hidden"]["fact_id"]],
                },
            )
        )
        gated_fact_ids = {str(f.fact_id) for f in gated_response.facts}
        authored_ids = {role: fact["fact_id"] for role, fact in fixture_facts.items()}
        any_authored_indexed = bool(gated_fact_ids & set(authored_ids.values()))
        metrics.record_behavior(
            "authored_facts_indexed_at_all",
            any_authored_indexed,
            f"{len(gated_fact_ids & set(authored_ids.values()))}/4 authored fixture "
            "facts present in gated retrieval -- 0/4 means mem1 gap #46 (authored "
            "facts never projected into the Postgres retrieval indexes), and makes "
            "the two behaviors below unevaluable rather than passing/failing",
        )

        alive_present = authored_ids["alive"] in gated_fact_ids
        dead_present = authored_ids["dead"] in gated_fact_ids
        if not any_authored_indexed:
            supersession_detail = (
                "no authored fact indexed at all -- mem1 gap #46, not evaluable"
            )
        else:
            supersession_detail = f"successor(dead)_present={dead_present} superseded(alive)_present={alive_present}"
        metrics.record_behavior(
            "superseded_fact_id_supersession",
            any_authored_indexed and dead_present and not alive_present,
            supersession_detail,
        )

        hidden_present = authored_ids["hidden"] in gated_fact_ids
        conditional_present = authored_ids["conditional"] in gated_fact_ids
        if not any_authored_indexed:
            visibility_detail = (
                "no authored fact indexed at all -- mem1 gap #46, not evaluable"
            )
        else:
            visibility_detail = f"hidden_present={hidden_present} when_active_present={conditional_present}"
        metrics.record_behavior(
            "visibility_filtering_when_gated",
            any_authored_indexed and hidden_present and conditional_present,
            visibility_detail,
        )
        metrics.fact_counts["facts_retrieved_gated_query"] = len(gated_response.facts)

    metrics.write()

    assert metrics.behaviors["fact_round_trip"][0], metrics.behaviors[
        "fact_round_trip"
    ][1]
