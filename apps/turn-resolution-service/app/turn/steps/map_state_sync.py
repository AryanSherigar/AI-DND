"""Deterministically maintains discovered_location_ids from current_location_id.

Runs after the tool-call loop's working_state is built, before state_writer
persists (pipeline.py is the sole sequencer — this file does not call
state_writer or ai_orchestrator itself). No AI involvement: discovery is
system-maintained infrastructure, not a tool call, per the locked decision in
docs/specs/master-mode-maps.spec.md. A no-op for any scenario without maps.
"""

import structlog

logger = structlog.get_logger()

STATE_KEY_CURRENT_LOCATION = "current_location_id"
STATE_KEY_DISCOVERED_LOCATIONS = "discovered_location_ids"
EVENT_LOCATION_DISCOVERED = "map_location_discovered"


def sync_discovered_locations(
    previous_state: dict[str, object], working_state: dict[str, object]
) -> set[str]:
    """Mutate working_state in place; return the set of paths changed."""
    previous_location = previous_state.get(STATE_KEY_CURRENT_LOCATION)
    current_location = working_state.get(STATE_KEY_CURRENT_LOCATION)
    if current_location is None or current_location == previous_location:
        return set()

    discovered = working_state.setdefault(STATE_KEY_DISCOVERED_LOCATIONS, [])
    if current_location in discovered:
        return set()

    discovered.append(current_location)
    logger.info(EVENT_LOCATION_DISCOVERED, location_entity_id=current_location)
    return {STATE_KEY_DISCOVERED_LOCATIONS}
