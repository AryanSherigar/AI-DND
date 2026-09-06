"""POST /v1/memory/template/ingest, POST /v1/memory/playthrough/{id}/init --
Milestone 3 routes. Wire-shape only (dependency-override fake engine), same
approach as test_memory_query_route.py / test_batch_ingest_route.py.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes import get_engine, router
from context_memory.cloning.template_clone import CloneResult


class FakeEngine:
    def __init__(self):
        self.entities_written: list[tuple[str, object]] = []
        self.facts_written: list[tuple[str, object]] = []
        self.lore_ingested: list[tuple[str, str]] = []
        self.cloned: list[tuple[str, str]] = []

    def write_template_entity(self, context_id, entity):
        self.entities_written.append((context_id, entity))
        return 1

    def write_template_fact(self, context_id, fact):
        self.facts_written.append((context_id, fact))
        return 2

    def ingest_template_lore(self, context_id, lore_text):
        self.lore_ingested.append((context_id, lore_text))

    def clone_playthrough_space(self, template_context_id, playthrough_context_id):
        self.cloned.append((template_context_id, playthrough_context_id))
        return CloneResult(entities_cloned=1, facts_cloned=2, relationships_cloned=3)


def _client_with(fake_engine: FakeEngine) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_engine] = lambda: fake_engine
    return TestClient(app)


_SCENARIO_ID = "11111111-1111-1111-1111-111111111111"
_PLAYTHROUGH_ID = "22222222-2222-2222-2222-222222222222"


def test_master_mode_ingest_writes_every_entity_and_fact():
    fake = FakeEngine()
    client = _client_with(fake)
    body = {
        "scenario_id": _SCENARIO_ID,
        "mode": "master",
        "world_data": {
            "entities": [{"canonical_name": "Sukuna", "entity_type": "character", "aliases": ["King of Curses"]}],
            "facts": [{"predicate": "is_strongest", "subject_canonical_name": "Sukuna", "object_literal": "true"}],
        },
    }

    response = client.post("/v1/memory/template/ingest", json=body)

    assert response.status_code == 200
    assert response.json() == {"template_space_id": _SCENARIO_ID}
    assert len(fake.entities_written) == 1
    assert fake.entities_written[0][0] == f"scenario-template::{_SCENARIO_ID}"
    assert fake.entities_written[0][1].canonical_name == "Sukuna"
    assert len(fake.facts_written) == 1


def test_newbie_mode_ingest_calls_lore_path():
    fake = FakeEngine()
    client = _client_with(fake)
    body = {"scenario_id": _SCENARIO_ID, "mode": "newbie", "world_data": {"lore_text": "A cursed realm."}}

    response = client.post("/v1/memory/template/ingest", json=body)

    assert response.status_code == 200
    assert fake.lore_ingested == [(f"scenario-template::{_SCENARIO_ID}", "A cursed realm.")]
    assert fake.entities_written == []


def test_newbie_mode_without_lore_text_is_rejected():
    client = _client_with(FakeEngine())
    body = {"scenario_id": _SCENARIO_ID, "mode": "newbie", "world_data": {}}

    response = client.post("/v1/memory/template/ingest", json=body)

    assert response.status_code == 400


def test_master_mode_entity_missing_required_field_is_rejected():
    client = _client_with(FakeEngine())
    body = {
        "scenario_id": _SCENARIO_ID, "mode": "master",
        "world_data": {"entities": [{"canonical_name": "Sukuna"}], "facts": []},  # missing entity_type
    }

    response = client.post("/v1/memory/template/ingest", json=body)

    assert response.status_code == 400


def test_init_playthrough_clones_and_echoes_playthrough_id():
    fake = FakeEngine()
    client = _client_with(fake)

    response = client.post(
        f"/v1/memory/playthrough/{_PLAYTHROUGH_ID}/init",
        json={"scenario_id": _SCENARIO_ID, "playthrough_id": _PLAYTHROUGH_ID},
    )

    assert response.status_code == 200
    assert response.json() == {"playthrough_space_id": _PLAYTHROUGH_ID}
    assert fake.cloned == [(f"scenario-template::{_SCENARIO_ID}", _PLAYTHROUGH_ID)]


def test_init_playthrough_rejects_mismatched_body_and_path_ids():
    client = _client_with(FakeEngine())
    other_id = "33333333-3333-3333-3333-333333333333"

    response = client.post(
        f"/v1/memory/playthrough/{_PLAYTHROUGH_ID}/init",
        json={"scenario_id": _SCENARIO_ID, "playthrough_id": other_id},
    )

    assert response.status_code == 400
