"""POST /v1/memory/query -- Milestone 1 of the AI-DND bridge (see the review
finding: AI-DND's mock client expects structured facts + a real `abstained`
flag, not `/v1/memory/search`'s synthesized prose).

Exercises only the route/wire-shape contract via a fake engine (dependency
override) -- retrieval logic itself is covered by
`tests/test_retrieval_engine.py::RetrieveFactsTests`.
"""

from __future__ import annotations

from uuid import UUID

from fastapi.testclient import TestClient

from api.routes import _stable_fact_uuid, get_engine, router
from context_memory.retrieval.models import RetrievedFact, RetrievedFacts
from fastapi import FastAPI


class FakeEngine:
    def __init__(self, result: RetrievedFacts) -> None:
        self._result = result
        self.last_call: dict | None = None

    def retrieve_facts(
        self, context_id, query_text, question_date, game_state, checkpoint, as_of_turn,
        template_context_id=None, participant_id=None, scenario_id=None,
    ):
        self.last_call = {
            "context_id": context_id,
            "query_text": query_text,
            "game_state": game_state,
            "checkpoint": checkpoint,
            "as_of_turn": as_of_turn,
            "template_context_id": template_context_id,
            "participant_id": participant_id,
            "scenario_id": scenario_id,
        }
        return self._result


def _client_with(fake_engine: FakeEngine) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_engine] = lambda: fake_engine
    return TestClient(app)


_REQUEST_BODY = {
    "scenario_id": "11111111-1111-1111-1111-111111111111",
    "playthrough_id": "22222222-2222-2222-2222-222222222222",
    "participant_id": "33333333-3333-3333-3333-333333333333",
    "query_text": "where is the dog?",
    "checkpoint": "chapter_1",
    "game_state": {"player": {"health": 10}},
    "as_of_turn": 3,
}


def test_returns_structured_facts_matching_ai_dnd_contract():
    fake = FakeEngine(RetrievedFacts(
        facts=[RetrievedFact(
            fact_id="1", subject="dog", predicate="located_at", object="the dog is in the park",
            valid_from=None, valid_until=None, confidence=0.91,
        )],
        abstained=False,
        resolved_time_point="3",
    ))
    client = _client_with(fake)

    response = client.post("/v1/memory/query", json=_REQUEST_BODY)

    assert response.status_code == 200
    body = response.json()
    assert body["abstained"] is False
    assert body["resolved_time_point"] == "3"
    assert body["facts"] == [{
        "fact_id": _stable_fact_uuid("1"), "subject": "dog", "predicate": "located_at",
        "object": "the dog is in the park", "valid_from": None, "valid_until": None,
        "confidence": 0.91, "hidden": False, "when_active": None,
    }]


def test_fact_id_is_a_valid_uuid_on_the_wire():
    """AI-DND's real `Fact.fact_id` is typed `UUID`
    (`apps/*/app/models/memory.py`) -- mem1's own internal fact_id (a bare
    graph_id or a `fact:direct:<hash>` logical key) never parses as one, so
    the route must translate it before it reaches the response."""
    fake = FakeEngine(RetrievedFacts(
        facts=[RetrievedFact(
            fact_id="142", subject="dog", predicate="located_at", object="park",
            valid_from=None, valid_until=None, confidence=0.5,
        )],
        abstained=False, resolved_time_point=None,
    ))
    client = _client_with(fake)

    response = client.post("/v1/memory/query", json=_REQUEST_BODY)

    fact_id = response.json()["facts"][0]["fact_id"]
    assert UUID(fact_id) == UUID(_stable_fact_uuid("142"))
    # Deterministic: the same internal fact_id always maps to the same UUID.
    assert fact_id == _stable_fact_uuid("142")


def test_abstention_returns_empty_facts_and_true_flag():
    fake = FakeEngine(RetrievedFacts(facts=[], abstained=True, resolved_time_point=None))
    client = _client_with(fake)

    response = client.post("/v1/memory/query", json=_REQUEST_BODY)

    assert response.status_code == 200
    body = response.json()
    assert body["abstained"] is True
    assert body["facts"] == []


def test_playthrough_id_is_forwarded_as_context_id():
    """Identifier mapping per the bridge plan: AI-DND's `playthrough_id` is
    mem1's fact-isolation key (`context_id`)."""
    fake = FakeEngine(RetrievedFacts(facts=[], abstained=True, resolved_time_point=None))
    client = _client_with(fake)

    client.post("/v1/memory/query", json=_REQUEST_BODY)

    assert fake.last_call["context_id"] == _REQUEST_BODY["playthrough_id"]
    assert fake.last_call["query_text"] == _REQUEST_BODY["query_text"]
    assert fake.last_call["checkpoint"] == _REQUEST_BODY["checkpoint"]
    assert fake.last_call["game_state"] == _REQUEST_BODY["game_state"]
    assert fake.last_call["as_of_turn"] == _REQUEST_BODY["as_of_turn"]
    assert fake.last_call["template_context_id"] == f"scenario-template::{_REQUEST_BODY['scenario_id']}"
    # §5 fix: both used to be silently dropped before reaching the engine.
    assert fake.last_call["participant_id"] == _REQUEST_BODY["participant_id"]
    assert fake.last_call["scenario_id"] == _REQUEST_BODY["scenario_id"]


def test_missing_required_field_is_rejected_with_422():
    bad_body = dict(_REQUEST_BODY)
    del bad_body["query_text"]
    client = _client_with(FakeEngine(RetrievedFacts(facts=[], abstained=True, resolved_time_point=None)))

    response = client.post("/v1/memory/query", json=bad_body)

    assert response.status_code == 422
