"""POST /v1/memory/ingest, GET /v1/memory/batch/{id}/status,
POST /v1/memory/batch/{id}/retry -- Milestone 2 of the AI-DND bridge.

Wire-shape only (dependency-override fake engine), same approach as
`test_memory_query_route.py`.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes import get_engine, router
from context_memory.ingestion.batch_models import BatchStatus


class FakeEngine:
    def __init__(self) -> None:
        self.submitted: list[tuple[str, list]] = []
        self.retried: list[str] = []
        self._status = BatchStatus(batch_id="ingest-fake", status="pending", facts_created=0)

    def submit_batch(self, context_id, turns_batch):
        self.submitted.append((context_id, turns_batch))
        return "ingest-fake"

    def get_batch_status(self, batch_id):
        return self._status

    def retry_batch(self, batch_id):
        if batch_id != "ingest-fake":
            raise ValueError(f"unknown batch_id: {batch_id}")
        self.retried.append(batch_id)
        return batch_id


def _client_with(fake_engine: FakeEngine) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_engine] = lambda: fake_engine
    return TestClient(app)


_INGEST_BODY = {
    "scenario_id": "11111111-1111-1111-1111-111111111111",
    "playthrough_id": "22222222-2222-2222-2222-222222222222",
    "turns_batch": [
        {"turn_number": 1, "text": "The player enters the cave.", "participant_id": "33333333-3333-3333-3333-333333333333"},
        {"turn_number": 2, "text": "A ghost appears.", "participant_id": "33333333-3333-3333-3333-333333333333"},
    ],
    "recent_context_turns": [],
}


def test_ingest_returns_202_and_batch_id():
    client = _client_with(FakeEngine())

    response = client.post("/v1/memory/ingest", json=_INGEST_BODY)

    assert response.status_code == 202
    assert response.json() == {"batch_id": "ingest-fake"}


def test_ingest_forwards_playthrough_id_as_context_id_and_all_turns():
    fake = FakeEngine()
    client = _client_with(fake)

    client.post("/v1/memory/ingest", json=_INGEST_BODY)

    context_id, entries = fake.submitted[0]
    assert context_id == _INGEST_BODY["playthrough_id"]
    assert len(entries) == 2
    assert entries[0].turn_number == 1
    assert entries[0].text == "The player enters the cave."


def test_batch_status_round_trips_wire_shape():
    fake = FakeEngine()
    fake._status = BatchStatus(batch_id="ingest-fake", status="partial", facts_created=4, error="mem1 flaky", retryable=True)
    client = _client_with(fake)

    response = client.get("/v1/memory/batch/ingest-fake/status")

    assert response.status_code == 200
    assert response.json() == {
        "batch_id": "ingest-fake", "status": "partial", "facts_created": 4,
        "error": "mem1 flaky", "retryable": True,
    }


def test_retry_batch_calls_engine_and_returns_batch_id():
    fake = FakeEngine()
    client = _client_with(fake)

    response = client.post("/v1/memory/batch/ingest-fake/retry")

    assert response.status_code == 200
    assert response.json() == {"batch_id": "ingest-fake"}
    assert fake.retried == ["ingest-fake"]


def test_retry_unknown_batch_returns_404():
    client = _client_with(FakeEngine())

    response = client.post("/v1/memory/batch/does-not-exist/retry")

    assert response.status_code == 404
