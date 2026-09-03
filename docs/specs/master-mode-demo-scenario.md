# Reference: Master-Mode Demo Scenario — "The Hollow Cairn"

> **Not an implementation spec.** This is shared reference data, used as the running example across `master-mode-data-model.spec.md`, `master-mode-turn-pipeline.spec.md`, `master-mode-end-conditions.spec.md`, `master-mode-memory-contract.spec.md`, and `master-mode-studio-ui.spec.md`. Every one of those specs cites entities, fields, and expressions from here rather than inventing its own examples. It exists to make every design decision from the Q&A pass concrete before any spec is drafted against it. Update this file, not the individual specs, if the example itself needs to change.

## Premise (one line, for the tagline field)

A dying warden guards a cairn that swallows grief. Enter, and it remembers you.

## Why this scenario

Small enough to read in one sitting, but it deliberately exercises every locked decision from the Q&A pass at least once: entity instance attributes (HP), hidden facts + reveal, a mechanically-enforced invariant, multiple named end-condition outcomes (including a secret one), checkpoint-based persona switching, Effect C (pre-turn direct mutation), the `roll_dice` tool, derived/computed state, custom terminology relabeling, and setup archetypes.

---

## 1. Scenario metadata

| Field | Value |
|---|---|
| `title` | The Hollow Cairn |
| `mode` | `master` |
| `logline` / tagline | A dying warden guards a cairn that swallows grief. Enter, and it remembers you. |
| `complexity_tier` | `master` |
| `player_count_support` | `solo` |
| `genre_tags` | `["dark-fantasy", "dungeon-crawl"]` |
| `content_tag` | `teen` |
| `narrator_persona` (base, checkpoint 1) | "You narrate with dry, weary humor — a storyteller who has told this tale before and finds the player's optimism a little funny." |
| opening scene / intro narration | "Ashfall Village smells of wet ash long after the fires stopped. They say the cairn on the hill takes what you're most afraid to lose. You've come to get it back." |
| rules (house rules, prompt-level) | "This is a low-magic setting — no spellcasting, only relics. The Warden never speaks first." |

## 2. Entities

Fixed taxonomy `entity_type`; `predicate` on facts is freeform with autocomplete.

| `entity_id` (slug) | `entity_type` | `canonical_name` | `aliases` | `description` | instance attributes |
|---|---|---|---|---|---|
| `kestrel_vane` | `character` | Kestrel Vane | `["Kestrel", "the Scout"]` | A former cairn-warden's apprentice, now a wandering scout. | `health: 40/40`, `loyalty: 0` (0–100) |
| `the_warden` | `character` | The Warden | `["the Warden", "It"]` | The cairn's undying guardian. Speaks rarely. | `health: 150/150`, `awareness: 0` (derived, see §4) |
| `hollow_cairn` | `location` | The Hollow Cairn | `[]` | A barrow sunk into the hill above Ashfall. | — |
| `ashfall_village` | `location` | Ashfall Village | `[]` | A burned-out village at the cairn's foot. | — |
| `the_vigil` | `faction` | The Vigil | `[]` | A dwindling order once sworn to guard the cairn from outside. | — |
| `ember_sigil` | `item` | Ember Sigil | `["the sigil"]` | A warded relic said to burn what the cairn has claimed. `obtainable: true` | `charges: 3` |
| `rustbound_blade` | `item` | Rustbound Blade | `[]` | A plain sword, better than bare hands. `obtainable: true` (starting item, Warrior archetype) | `durability: 100` |

## 3. Facts

`subject`/`object` are strict FKs to entities where the value is an entity (per the entity/fact table design); literal object values are typed strings/numbers. `when_active` uses the shared expression grammar (§6).

| subject | predicate | object | `when_active` | `hidden` | notes |
|---|---|---|---|---|---|
| `kestrel_vane` | `member_of` | `the_vigil` | — | `false` | always known |
| `kestrel_vane` | `located_at` | `ashfall_village` | `checkpoint == "arrival"` | `false` | supersession via `when_active`, not an explicit link |
| `kestrel_vane` | `located_at` | `hollow_cairn` | `flags.rescued_kestrel == true` | `false` | |
| `the_warden` | `located_at` | `hollow_cairn` | — | `false` | |
| `the_warden` | `guards` | `hollow_cairn` | — | `false` | |
| `the_warden` | `vulnerable_to` | `ember_sigil` | — | **`true`** | secret weakness — reveal mechanism in §5 |
| `hollow_cairn` | `entrance_guarded_by` | `the_vigil` | — | `false` | |

## 4. State schema (`state_schema`)

Demonstrates every supported field shape: primitives, nested object, list, entity reference, derived field.

```jsonc
{
  "player": {
    "type": "object",
    "fields": {
      "health":    { "type": "number", "min": 0, "max": 100, "initial": 100, "label": "Health" },
      "sanity":    { "type": "number", "min": 0, "max": 100, "initial": 100, "label": "Sanity" },  // relabel example: creator can rename display label to "Resolve" without changing the field key
      "location":  { "type": "entity_ref", "entity_type": "location", "initial": "ashfall_village" },
      "inventory": { "type": "list", "item_type": "entity_ref", "item_entity_type": "item", "initial": [] }
    }
  },
  "flags": {
    "type": "object",
    "fields": {
      "entered_cairn":      { "type": "boolean", "initial": false },
      "rescued_kestrel":    { "type": "boolean", "initial": false },
      "investigated_lore":  { "type": "boolean", "initial": false },
      "made_pact":          { "type": "boolean", "initial": false }
    }
  },
  "warden_awareness": {
    "type": "number",
    "derived": true,
    "formula": "the_warden.awareness",   // mirrors the entity-instance field; read-only to tools, written only by condition_evaluator/Effect C
    "label": "Warden's Awareness"
  }
}
```

Entity instance attributes (`the_warden.health`, `the_warden.awareness`, `kestrel_vane.health`, `kestrel_vane.loyalty`, `ember_sigil.charges`, `rustbound_blade.durability`) live on the entities themselves (§2), validated the same way as `state_schema` fields but scoped per-entity.

## 5. Hidden fact + reveal mechanism

- Fact `the_warden vulnerable_to ember_sigil` is authored `hidden: true` — excluded from anything shown to the player and from default memory retrieval surfacing, but still usable by conditions.
- Reveal path: when `flags.investigated_lore == true` (set by the AI calling `set_field` after a successful `roll_dice` investigation check), a condition flips the fact's `hidden` flag to `false` via the same Effect C mutation path used for direct state changes — from that point on, the fact is eligible for normal memory retrieval and can appear in narration context.

## 6. Active conditions (`scenario_conditions`)

Shared `condition_expression` grammar: comparison, `AND`/`OR`/`NOT` nesting, `in`/`contains`, string match.

| `label` | `condition_expression` | `narrator_instruction` |
|---|---|---|
| Kestrel Accompanies | `{ "field": "flags.rescued_kestrel", "op": "==", "value": true }` | "Kestrel Vane now travels with the player, offering guidance and stepping into fights at their side." |
| Warden Is Wary | `{ "field": "the_warden.awareness", "op": ">=", "value": 50 }` | "The Warden has noticed the player. Its patience is thinning; describe it as watchful and less passive." |

## 7. World-rule invariant (mechanically enforced)

Demonstrates the hybrid enforcement model: checked by `state_validator` on every mutation, **and** included as prompt text.

```jsonc
{
  "label": "Health cannot exceed its cap",
  "invariant_expression": { "field": "player.health", "op": "<=", "value": "player.max_health" },
  "applies_to": "player",
  "narrator_text": "The player's body has hard physical limits — health can never be restored beyond its maximum, regardless of what a relic or ritual claims to do."
}
```

A second invariant on the antagonist: `the_warden.health >= 0` (a tool call that would drive it negative is rejected and clamped at the validator level, with the narration recovering by describing the Warden as "at death's door" rather than dead, until the killing blow is the one that actually triggers the win condition in §9).

## 8. Effect C example (pre-turn, condition-triggered direct mutation)

| `label` | `condition_expression` | mutation | timing |
|---|---|---|---|
| The Cairn Presses In | `{ "field": "flags.entered_cairn", "op": "==", "value": true }` | `player.sanity -= 2` every turn while inside | Fires in `condition_evaluator`, **before** the Gemini call, so the AI narrates against the already-reduced sanity value rather than deciding to lower it itself. |

## 9. End conditions (`end_conditions`, multiple named outcomes)

| `label` | `condition_expression` | `outcome_tag` | `outcome_title` | `outcome_text` (excerpt) |
|---|---|---|---|---|
| Warden Defeated | `{ "field": "the_warden.health", "op": "<=", "value": 0 }` | `win` | The Ashen Ending | "The Warden kneels, and the cairn exhales for the first time in a hundred years..." |
| Player Falls | `{ "field": "player.health", "op": "<=", "value": 0 }` | `lose` | Consumed | "The cairn does not release what it takes. Ashfall will wait for the next one who comes looking..." |
| Secret Pact | `{ "field": "flags.made_pact", "op": "==", "value": true, "AND": { "field": "flags.entered_cairn", "op": "==", "value": true } }` | `win` | The Vigil's Ending *(secret)* | "You do not kill the Warden. You relieve it. Ashfall will need a new one, and it looks at you..." |

## 10. Checkpoints & persona switching

| checkpoint | `narrator_persona` override |
|---|---|
| `arrival` (default) | Dry, weary humor (base persona above). |
| `entered_cairn` | "Drop the humor. Narrate in short, tense sentences — the cairn is listening." |
| `confronted_warden` | "Grave and formal, as if narrating a rite rather than a fight." |

## 11. Setup screen

- System-level: character name.
- Archetype template (setup archetype/preset feature): `Warrior` (starting inventory: `rustbound_blade`, `player.health` initial 100) vs. `Scholar` (starting inventory: `ember_sigil`, `player.sanity` initial 90, `player.health` initial 80).
- Suggested action chips: `Investigate`, `Fight`, `Persuade`, `Move` — freeform text underneath, no hardcoded mechanic binding.

## 12. Tool-call walkthrough (illustrates the fixed generic tool set + `roll_dice`)

1. Player action: *"I search the altar for anything useful."*
2. Gemini calls `roll_dice(sides=20, modifier=0)` — description on the tool: "use only when the outcome is genuinely uncertain and consequential, not for routine actions." Result: 17.
3. On a result ≥ 15, Gemini calls `set_field(path="flags.investigated_lore", value=true)`.
4. `state_validator` checks the mutation against `state_schema` (type: boolean, valid path) — passes. No invariant violated.
5. Effect C / condition_evaluator on the *next* turn's pre-step notices `flags.investigated_lore == true` and flips the hidden fact from §5 to visible.
6. Narration streams describing the discovery; `state_update` event carries the validated new state.

---

This example is intentionally small — it is a reference for spec examples and task-checklist test fixtures, not a scenario meant to demo the entire feature surface simultaneously (map/images are out of scope this round, per the locked decisions).
