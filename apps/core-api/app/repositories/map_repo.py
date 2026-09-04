"""Map/MapPin/MapConnection data repository for direct database operations."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.map_connection import MapConnection
from app.db.models.map_pin import MapPin
from app.db.models.scenario_map import ScenarioMap


class MapRepo:
    """Repository managing direct SQLAlchemy queries for scenario maps."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # -- ScenarioMap ---------------------------------------------------

    async def create_map(self, scenario_map: ScenarioMap) -> ScenarioMap:
        self.session.add(scenario_map)
        await self.session.flush()
        return scenario_map

    async def get_map_by_id(self, map_id: uuid.UUID) -> ScenarioMap | None:
        stmt = select(ScenarioMap).where(ScenarioMap.map_id == map_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_maps_by_scenario(self, scenario_id: uuid.UUID) -> list[ScenarioMap]:
        stmt = (
            select(ScenarioMap)
            .where(ScenarioMap.scenario_id == scenario_id)
            .order_by(ScenarioMap.display_order)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_maps_by_scenario(self, scenario_id: uuid.UUID) -> int:
        maps = await self.list_maps_by_scenario(scenario_id)
        return len(maps)

    async def update_map(self, scenario_map: ScenarioMap) -> ScenarioMap:
        await self.session.flush()
        await self.session.refresh(scenario_map)
        return scenario_map

    async def delete_map(self, scenario_map: ScenarioMap) -> None:
        await self.session.delete(scenario_map)
        await self.session.flush()

    # -- MapPin ----------------------------------------------------------

    async def create_pin(self, pin: MapPin) -> MapPin:
        self.session.add(pin)
        await self.session.flush()
        return pin

    async def get_pin_by_id(self, pin_id: uuid.UUID) -> MapPin | None:
        stmt = select(MapPin).where(MapPin.pin_id == pin_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_pins_by_map(self, map_id: uuid.UUID) -> list[MapPin]:
        stmt = select(MapPin).where(MapPin.map_id == map_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_start_pin_by_scenario(self, scenario_id: uuid.UUID) -> MapPin | None:
        stmt = select(MapPin).where(
            MapPin.scenario_id == scenario_id, MapPin.is_start_location.is_(True)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def update_pin(self, pin: MapPin) -> MapPin:
        await self.session.flush()
        await self.session.refresh(pin)
        return pin

    async def delete_pin(self, pin: MapPin) -> None:
        await self.session.delete(pin)
        await self.session.flush()

    # -- MapConnection -----------------------------------------------------

    async def create_connection(self, connection: MapConnection) -> MapConnection:
        self.session.add(connection)
        await self.session.flush()
        return connection

    async def get_connection_by_id(
        self, connection_id: uuid.UUID
    ) -> MapConnection | None:
        stmt = select(MapConnection).where(MapConnection.connection_id == connection_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_connection_by_pair(
        self, scenario_id: uuid.UUID, entity_id_a: uuid.UUID, entity_id_b: uuid.UUID
    ) -> MapConnection | None:
        stmt = select(MapConnection).where(
            MapConnection.scenario_id == scenario_id,
            MapConnection.entity_id_a == entity_id_a,
            MapConnection.entity_id_b == entity_id_b,
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_connections_by_scenario(
        self, scenario_id: uuid.UUID
    ) -> list[MapConnection]:
        stmt = select(MapConnection).where(MapConnection.scenario_id == scenario_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def delete_connection(self, connection: MapConnection) -> None:
        await self.session.delete(connection)
        await self.session.flush()
