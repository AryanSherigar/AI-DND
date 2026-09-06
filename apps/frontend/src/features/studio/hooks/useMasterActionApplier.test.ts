import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { server } from "@/test/msw/server";
import { ActionBlock } from "../types/assistant.types";
import { useMasterActionApplier } from "./useMasterActionApplier";

const API_URL = "http://localhost:8000";
const SCENARIO_ID = "scenario-1";

const mockScenarioRead = (): void => {
  server.use(
    http.get(`${API_URL}/v1/scenarios/${SCENARIO_ID}`, () =>
      HttpResponse.json({
        scenario_id: SCENARIO_ID,
        state_schema: { gold: { type: "number", initial: 0 } },
      }),
    ),
    http.get(`${API_URL}/v1/scenarios/${SCENARIO_ID}/entities`, () =>
      HttpResponse.json({ items: [] }),
    ),
    http.get(`${API_URL}/v1/scenarios/${SCENARIO_ID}/facts`, () =>
      HttpResponse.json({ items: [] }),
    ),
  );
};

const renderApplier = (onError: (message: string) => void) => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const wrapper: React.FC<{ children: React.ReactNode }> = ({ children }) =>
    React.createElement(QueryClientProvider, { client: queryClient }, children);
  const hookResult = renderHook(
    () => useMasterActionApplier(SCENARIO_ID, onError),
    { wrapper },
  );
  return { ...hookResult, queryClient };
};

const entityBlock = (tempId: string, name: string): ActionBlock => ({
  target: "entity",
  metadata: { temp_id: tempId },
  content: JSON.stringify({ entity_type: "character", canonical_name: name }),
});

const factBlock = (subjectRef: string, predicate: string): ActionBlock => ({
  target: "fact",
  content: JSON.stringify({
    subject_ref: subjectRef,
    predicate,
    object_literal: "the crown",
  }),
});

describe("useMasterActionApplier", () => {
  beforeEach(() => {
    mockScenarioRead();
  });

  const REAL_ENTITY_ID = "11111111-1111-1111-1111-111111111111";
  const EXISTING_ENTITY_ID = "22222222-2222-2222-2222-222222222222";

  it("resolves a temp_id to the real entity_id before creating a dependent fact", async () => {
    let capturedFactPayload: unknown = null;
    server.use(
      http.post(`${API_URL}/v1/scenarios/${SCENARIO_ID}/entities`, () =>
        HttpResponse.json(
          { entity_id: REAL_ENTITY_ID, scenario_id: SCENARIO_ID },
          { status: 201 },
        ),
      ),
      http.post(
        `${API_URL}/v1/scenarios/${SCENARIO_ID}/facts`,
        async ({ request }) => {
          capturedFactPayload = await request.json();
          return HttpResponse.json(
            { fact_id: "fact-1", scenario_id: SCENARIO_ID },
            { status: 201 },
          );
        },
      ),
    );
    const onError = vi.fn();
    const { result } = renderApplier(onError);

    await result.current.applyBatch([
      entityBlock("villain", "The Warden"),
      factBlock("villain", "owns"),
    ]);

    expect(capturedFactPayload).toMatchObject({
      subject_entity_id: REAL_ENTITY_ID,
      predicate: "owns",
      object_literal: "the crown",
    });
    expect(onError).not.toHaveBeenCalled();
  });

  it("treats a ref as a real entity_id when it isn't a known temp_id", async () => {
    let capturedFactPayload: unknown = null;
    server.use(
      http.post(
        `${API_URL}/v1/scenarios/${SCENARIO_ID}/facts`,
        async ({ request }) => {
          capturedFactPayload = await request.json();
          return HttpResponse.json(
            { fact_id: "fact-1", scenario_id: SCENARIO_ID },
            { status: 201 },
          );
        },
      ),
    );
    const onError = vi.fn();
    const { result } = renderApplier(onError);

    await result.current.applyBlock(factBlock(EXISTING_ENTITY_ID, "guards"));

    expect(capturedFactPayload).toMatchObject({
      subject_entity_id: EXISTING_ENTITY_ID,
    });
    expect(onError).not.toHaveBeenCalled();
  });

  it("fails clearly instead of sending a request when the subject entity was never created", async () => {
    let factRequestSent = false;
    server.use(
      http.post(`${API_URL}/v1/scenarios/${SCENARIO_ID}/facts`, () => {
        factRequestSent = true;
        return HttpResponse.json(
          { fact_id: "fact-1", scenario_id: SCENARIO_ID },
          { status: 201 },
        );
      }),
    );
    const onError = vi.fn();
    const { result } = renderApplier(onError);

    await result.current.applyBlock(factBlock("goblin_scout", "guards"));

    expect(factRequestSent).toBe(false);
    expect(onError).toHaveBeenCalledWith(
      expect.stringContaining("goblin_scout"),
    );
    expect(onError).toHaveBeenCalledWith(
      expect.stringContaining("hasn't been created yet"),
    );
  });

  it("normalizes an informally-shaped attributes_schema before creating the entity", async () => {
    let createdPayload: unknown = null;
    server.use(
      http.post(
        `${API_URL}/v1/scenarios/${SCENARIO_ID}/entities`,
        async ({ request }) => {
          createdPayload = await request.json();
          return HttpResponse.json(
            { entity_id: REAL_ENTITY_ID, scenario_id: SCENARIO_ID },
            { status: 201 },
          );
        },
      ),
    );
    const onError = vi.fn();
    const { result } = renderApplier(onError);

    await result.current.applyBlock({
      target: "entity",
      content: JSON.stringify({
        entity_type: "character",
        canonical_name: "Elia",
        attributes_schema: {
          hunger: "number",
          role: "Captain",
          isAlive: true,
          reach: { type: "number", initial: 3 },
        },
      }),
    });

    expect(createdPayload).toMatchObject({
      attributes_schema: {
        hunger: { type: "number" },
        role: { type: "string", initial: "Captain" },
        isAlive: { type: "boolean", initial: true },
        reach: { type: "number", initial: 3 },
      },
    });
    expect(onError).not.toHaveBeenCalled();
  });

  it("calls onError instead of throwing when entity creation fails", async () => {
    server.use(
      http.post(`${API_URL}/v1/scenarios/${SCENARIO_ID}/entities`, () =>
        HttpResponse.json(
          { detail: "Duplicate entity name." },
          { status: 409 },
        ),
      ),
    );
    const onError = vi.fn();
    const { result } = renderApplier(onError);

    await result.current.applyBlock(entityBlock("villain", "The Warden"));

    expect(onError).toHaveBeenCalledWith(
      expect.stringContaining("Duplicate entity name."),
    );
  });

  it("merges a state_field suggestion into the existing state_schema", async () => {
    let capturedScenarioPatch: unknown = null;
    server.use(
      http.patch(
        `${API_URL}/v1/scenarios/${SCENARIO_ID}`,
        async ({ request }) => {
          capturedScenarioPatch = await request.json();
          return HttpResponse.json({
            scenario_id: SCENARIO_ID,
            state_schema: (capturedScenarioPatch as { state_schema: unknown })
              .state_schema,
          });
        },
      ),
    );
    const onError = vi.fn();
    const { result, queryClient } = renderApplier(onError);

    await waitFor(() =>
      expect(queryClient.getQueryData(["scenario", SCENARIO_ID])).toBeTruthy(),
    );

    await result.current.applyBlock({
      target: "state_field",
      metadata: { key: "reputation" },
      content: JSON.stringify({ type: "number", label: "Reputation" }),
    });

    await waitFor(() =>
      expect(capturedScenarioPatch).toMatchObject({
        state_schema: {
          gold: { type: "number", initial: 0 },
          reputation: { type: "number", label: "Reputation" },
        },
      }),
    );
    expect(onError).not.toHaveBeenCalled();
  });

  it("reads the key from inside the state_field JSON body (no metadata needed)", async () => {
    let capturedScenarioPatch: unknown = null;
    server.use(
      http.patch(
        `${API_URL}/v1/scenarios/${SCENARIO_ID}`,
        async ({ request }) => {
          capturedScenarioPatch = await request.json();
          return HttpResponse.json({
            scenario_id: SCENARIO_ID,
            state_schema: (capturedScenarioPatch as { state_schema: unknown })
              .state_schema,
          });
        },
      ),
    );
    const onError = vi.fn();
    const { result, queryClient } = renderApplier(onError);

    await waitFor(() =>
      expect(queryClient.getQueryData(["scenario", SCENARIO_ID])).toBeTruthy(),
    );

    await result.current.applyBlock({
      target: "state_field",
      content: JSON.stringify({
        key: "player_health",
        type: "number",
        label: "Your Health",
        initial: 100,
      }),
    });

    await waitFor(() =>
      expect(capturedScenarioPatch).toMatchObject({
        state_schema: {
          gold: { type: "number", initial: 0 },
          player_health: { type: "number", label: "Your Health", initial: 100 },
        },
      }),
    );
    expect(onError).not.toHaveBeenCalled();
  });

  it("recovers a state_field key split into its own JSON blob ahead of the definition", async () => {
    let capturedScenarioPatch: unknown = null;
    server.use(
      http.patch(
        `${API_URL}/v1/scenarios/${SCENARIO_ID}`,
        async ({ request }) => {
          capturedScenarioPatch = await request.json();
          return HttpResponse.json({ scenario_id: SCENARIO_ID });
        },
      ),
    );
    const onError = vi.fn();
    const { result } = renderApplier(onError);

    await result.current.applyBlock({
      target: "state_field",
      content:
        '{"key":"elia_health"}\n{"type": "number", "label": "Elia\'s Health", "initial": 100}',
    });

    expect(capturedScenarioPatch).toMatchObject({
      state_schema: {
        elia_health: { type: "number", label: "Elia's Health", initial: 100 },
      },
    });
    expect(onError).not.toHaveBeenCalled();
  });

  it("recovers an entity temp_id split into its own JSON blob ahead of the entity fields", async () => {
    let createdPayload: unknown = null;
    server.use(
      http.post(
        `${API_URL}/v1/scenarios/${SCENARIO_ID}/entities`,
        async ({ request }) => {
          createdPayload = await request.json();
          return HttpResponse.json(
            { entity_id: REAL_ENTITY_ID, scenario_id: SCENARIO_ID },
            { status: 201 },
          );
        },
      ),
    );
    const onError = vi.fn();
    const { result } = renderApplier(onError);

    await result.current.applyBlock({
      target: "entity",
      content:
        '{"temp_id":"elia_char"}\n{"entity_type": "character", "canonical_name": "Elia"}',
    });

    expect(createdPayload).toMatchObject({
      entity_type: "character",
      canonical_name: "Elia",
    });
    expect(createdPayload).not.toHaveProperty("temp_id");
    expect(onError).not.toHaveBeenCalled();
  });

  it("applies an 'instructions' suggestion to rules.text, not narrator_persona", async () => {
    let capturedScenarioPatch: unknown = null;
    server.use(
      http.patch(
        `${API_URL}/v1/scenarios/${SCENARIO_ID}`,
        async ({ request }) => {
          capturedScenarioPatch = await request.json();
          return HttpResponse.json({ scenario_id: SCENARIO_ID });
        },
      ),
    );
    const onError = vi.fn();
    const { result } = renderApplier(onError);

    await result.current.applyBlock({
      target: "instructions",
      content: "Guards never attack unprovoked.",
    });

    expect(capturedScenarioPatch).toMatchObject({
      rules: { text: "Guards never attack unprovoked." },
    });
    expect(onError).not.toHaveBeenCalled();
  });

  it("deletes an entity via applyDestructive after being told to", async () => {
    let deleteCalled = false;
    server.use(
      http.delete(
        `${API_URL}/v1/scenarios/${SCENARIO_ID}/entities/entity-1`,
        () => {
          deleteCalled = true;
          return new HttpResponse(null, { status: 204 });
        },
      ),
    );
    const onError = vi.fn();
    const { result } = renderApplier(onError);

    await result.current.applyDestructive({
      target: "entity",
      metadata: { op: "delete" },
      content: JSON.stringify({ entity_id: "entity-1" }),
    });

    expect(deleteCalled).toBe(true);
    expect(onError).not.toHaveBeenCalled();
  });
});
