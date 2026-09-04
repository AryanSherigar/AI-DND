"""Map domain service handling business logic and scenario-ownership rules.

Master-mode only: every public method starts by confirming the scenario
exists, is owned by the caller, and is a master-mode scenario
(_ensure_master_mode) — this is the concrete backend enforcement of the
"Maps are master-mode only" product decision (docs/specs/master-mode-maps
.spec.md).
"""

import uuid

from app.db.models.entity import Entity
from app.db.models.map_connection import MapConnection
from app.db.models.map_pin import MapPin
from app.db.models.scenario import Scenario
from app.db.models.scenario_map import ScenarioMap
from app.exceptions.map_exceptions import (
    MapConnectionDuplicateError,
    MapConnectionInvalidEntityError,
    MapConnectionNotFoundError,
    MapModeError,
    MapNotFoundError,
    MapPinInvalidEntityError,
    MapPinNotFoundError,
    MapStartLocationConflictError,
)
from app.exceptions.scenario_exceptions import (
    ScenarioAccessDeniedError,
    ScenarioNotFoundError,
)
from app.models.map import (
    MapConnectionCreate,
    MapConnectionResponse,
    MapCreate,
    MapPinCreate,
    MapPinResponse,
    MapPinUpdate,
    MapResponse,
    MapUpdate,
)
from app.repositories.entity_repo import EntityRepo
from app.repositories.map_repo import MapRepo
from app.repositories.scenario_repo import ScenarioRepo

LOCATION_ENTITY_TYPE = "location"


class MapService:
    """Service handling map authoring within a master-mode scenario."""

    def __init__(
        self,
        map_repo: MapRepo,
        scenario_repo: ScenarioRepo,
        entity_repo: EntityRepo,
    ) -> None:
        self.map_repo = map_repo
        self.scenario_repo = scenario_repo
        self.entity_repo = entity_repo

    # -- Maps ------------------------------------------------------------

    async def create_map(
        self, scenario_id: uuid.UUID, user_id: uuid.UUID, data: MapCreate
    ) -> MapResponse:
        """Create a new map within a master-mode scenario."""
        await self._ensure_master_mode_owner(scenario_id, user_id)
        scenario_map = ScenarioMap(
            scenario_id=scenario_id,
            name=data.name,
            display_order=data.display_order,
        )
        created = await self.map_repo.create_map(scenario_map)
        return MapResponse.model_validate(created)

    async def list_maps(
        self, scenario_id: uuid.UUID, user_id: uuid.UUID
    ) -> list[MapResponse]:
        """List all maps for a scenario, ordered by display_order."""
        await self._ensure_master_mode_owner(scenario_id, user_id)
        maps = await self.map_repo.list_maps_by_scenario(scenario_id)
        return [MapResponse.model_validate(m) for m in maps]

    async def update_map(
        self,
        scenario_id: uuid.UUID,
        map_id: uuid.UUID,
        user_id: uuid.UUID,
        data: MapUpdate,
    ) -> MapResponse:
        """Update a map's fields (name, image_url, display_order)."""
        await self._ensure_master_mode_owner(scenario_id, user_id)
        scenario_map = await self._get_scoped_map(scenario_id, map_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(scenario_map, field, value)
        updated = await self.map_repo.update_map(scenario_map)
        return MapResponse.model_validate(updated)

    async def delete_map(
        self, scenario_id: uuid.UUID, map_id: uuid.UUID, user_id: uuid.UUID
    ) -> None:
        """Delete a map. Cascades to its pins at the DB level."""
        await self._ensure_master_mode_owner(scenario_id, user_id)
        scenario_map = await self._get_scoped_map(scenario_id, map_id)
        await self.map_repo.delete_map(scenario_map)

    # -- Pins --------------------------------------------------------------

    async def create_pin(
        self,
        scenario_id: uuid.UUID,
        map_id: uuid.UUID,
        user_id: uuid.UUID,
        data: MapPinCreate,
    ) -> MapPinResponse:
        """Place a location entity's pin on a map."""
        await self._ensure_master_mode_owner(scenario_id, user_id)
        await self._get_scoped_map(scenario_id, map_id)
        await self._ensure_location_entity(scenario_id, data.entity_id)
        if data.is_start_location:
            await self._ensure_no_existing_start_pin(scenario_id)

        pin = MapPin(
            map_id=map_id,
            scenario_id=scenario_id,
            entity_id=data.entity_id,
            x=data.x,
            y=data.y,
            is_start_location=data.is_start_location,
        )
        created = await self.map_repo.create_pin(pin)
        return MapPinResponse.model_validate(created)

    async def list_pins(
        self, scenario_id: uuid.UUID, map_id: uuid.UUID, user_id: uuid.UUID
    ) -> list[MapPinResponse]:
        """List all pins placed on a map."""
        await self._ensure_master_mode_owner(scenario_id, user_id)
        await self._get_scoped_map(scenario_id, map_id)
        pins = await self.map_repo.list_pins_by_map(map_id)
        return [MapPinResponse.model_validate(p) for p in pins]

    async def update_pin(
        self,
        scenario_id: uuid.UUID,
        map_id: uuid.UUID,
        pin_id: uuid.UUID,
        user_id: uuid.UUID,
        data: MapPinUpdate,
    ) -> MapPinResponse:
        """Update a pin's position or start-location flag."""
        await self._ensure_master_mode_owner(scenario_id, user_id)
        await self._get_scoped_map(scenario_id, map_id)
        pin = await self._get_scoped_pin(map_id, pin_id)

        if data.is_start_location and not pin.is_start_location:
            await self._ensure_no_existing_start_pin(scenario_id)

        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(pin, field, value)
        updated = await self.map_repo.update_pin(pin)
        return MapPinResponse.model_validate(updated)

    async def delete_pin(
        self,
        scenario_id: uuid.UUID,
        map_id: uuid.UUID,
        pin_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        """Remove a pin from a map."""
        await self._ensure_master_mode_owner(scenario_id, user_id)
        await self._get_scoped_map(scenario_id, map_id)
        pin = await self._get_scoped_pin(map_id, pin_id)
        await self.map_repo.delete_pin(pin)

    # -- Connections ---------------------------------------------------

    async def create_connection(
        self, scenario_id: uuid.UUID, user_id: uuid.UUID, data: MapConnectionCreate
    ) -> MapConnectionResponse:
        """Connect two location entities in the scenario-wide graph."""
        await self._ensure_master_mode_owner(scenario_id, user_id)
        entity_id_a, entity_id_b = await self._ensure_valid_connection_pair(
            scenario_id, data.entity_id_a, data.entity_id_b
        )

        existing = await self.map_repo.get_connection_by_pair(
            scenario_id, entity_id_a, entity_id_b
        )
        if existing is not None:
            raise MapConnectionDuplicateError()

        connection = MapConnection(
            scenario_id=scenario_id,
            entity_id_a=entity_id_a,
            entity_id_b=entity_id_b,
            label=data.label,
        )
        created = await self.map_repo.create_connection(connection)
        return MapConnectionResponse.model_validate(created)

    async def list_connections(
        self, scenario_id: uuid.UUID, user_id: uuid.UUID
    ) -> list[MapConnectionResponse]:
        """List all connections for a scenario (may span multiple maps)."""
        await self._ensure_master_mode_owner(scenario_id, user_id)
        connections = await self.map_repo.list_connections_by_scenario(scenario_id)
        return [MapConnectionResponse.model_validate(c) for c in connections]

    async def delete_connection(
        self, scenario_id: uuid.UUID, connection_id: uuid.UUID, user_id: uuid.UUID
    ) -> None:
        """Remove a connection."""
        await self._ensure_master_mode_owner(scenario_id, user_id)
        connection = await self.map_repo.get_connection_by_id(connection_id)
        if connection is None or connection.scenario_id != scenario_id:
            raise MapConnectionNotFoundError()
        await self.map_repo.delete_connection(connection)

    # -- Shared helpers --------------------------------------------------

    async def _ensure_valid_connection_pair(
        self, scenario_id: uuid.UUID, entity_id_a: uuid.UUID, entity_id_b: uuid.UUID
    ) -> tuple[uuid.UUID, uuid.UUID]:
        """Validate both entities are distinct location entities owned by
        this scenario, and return them sorted for canonical storage."""
        if entity_id_a == entity_id_b:
            raise MapConnectionInvalidEntityError(
                "A connection cannot link a location to itself"
            )
        if not await self._is_location_entity(
            scenario_id, entity_id_a
        ) or not await self._is_location_entity(scenario_id, entity_id_b):
            raise MapConnectionInvalidEntityError()
        return (
            (entity_id_a, entity_id_b)
            if entity_id_a < entity_id_b
            else (entity_id_b, entity_id_a)
        )

    async def _ensure_location_entity(
        self, scenario_id: uuid.UUID, entity_id: uuid.UUID
    ) -> Entity:
        """Fetch an entity, rejecting anything not a location owned by this
        scenario. Used by pin creation/update, where the domain error is
        always MapPinInvalidEntityError."""
        entity = await self.entity_repo.get_by_id(entity_id)
        if (
            entity is None
            or entity.scenario_id != scenario_id
            or entity.entity_type != LOCATION_ENTITY_TYPE
        ):
            raise MapPinInvalidEntityError()
        return entity

    async def _is_location_entity(
        self, scenario_id: uuid.UUID, entity_id: uuid.UUID
    ) -> bool:
        """Non-raising check used by connection validation, where a failure
        maps to MapConnectionInvalidEntityError instead."""
        entity = await self.entity_repo.get_by_id(entity_id)
        return (
            entity is not None
            and entity.scenario_id == scenario_id
            and entity.entity_type == LOCATION_ENTITY_TYPE
        )

    async def _ensure_no_existing_start_pin(self, scenario_id: uuid.UUID) -> None:
        """Reject creating/flagging a second start pin (friendly pre-check
        before the DB's partial unique index would reject it anyway)."""
        existing = await self.map_repo.get_start_pin_by_scenario(scenario_id)
        if existing is not None:
            raise MapStartLocationConflictError()

    async def _get_scoped_map(
        self, scenario_id: uuid.UUID, map_id: uuid.UUID
    ) -> ScenarioMap:
        """Fetch a map, raising 404 if missing or owned by another scenario."""
        scenario_map = await self.map_repo.get_map_by_id(map_id)
        if scenario_map is None or scenario_map.scenario_id != scenario_id:
            raise MapNotFoundError()
        return scenario_map

    async def _get_scoped_pin(self, map_id: uuid.UUID, pin_id: uuid.UUID) -> MapPin:
        """Fetch a pin, raising 404 if missing or owned by another map."""
        pin = await self.map_repo.get_pin_by_id(pin_id)
        if pin is None or pin.map_id != map_id:
            raise MapPinNotFoundError()
        return pin

    async def _ensure_master_mode_owner(
        self, scenario_id: uuid.UUID, user_id: uuid.UUID
    ) -> Scenario:
        """Verify the scenario exists, is owned by the caller, and is a
        master-mode scenario."""
        scenario = await self.scenario_repo.get_by_id(scenario_id)
        if scenario is None or scenario.status == "archived":
            raise ScenarioNotFoundError()
        if scenario.creator_id != user_id:
            raise ScenarioAccessDeniedError()
        if scenario.mode != "master":
            raise MapModeError()
        return scenario
