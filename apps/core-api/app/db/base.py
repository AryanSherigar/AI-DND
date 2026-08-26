"""SQLAlchemy Declarative Base, naming conventions, mixins, and ORM registry."""

from datetime import datetime

from sqlalchemy import TIMESTAMP, MetaData, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING_CONVENTION: dict[str, str] = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Declarative Base with explicit PostgreSQL naming conventions."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class CreatedAtMixin:
    """Mixin for entity created_at timestamp."""

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=text("CURRENT_TIMESTAMP"),
        nullable=False,
    )


class TimestampMixin(CreatedAtMixin):
    """Mixin for entity created_at and updated_at timestamps."""

    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=text("CURRENT_TIMESTAMP"),
        nullable=False,
    )


# Import all ORM models so Base.metadata is fully populated.
from app.db.models.participant import Participant
from app.db.models.playthrough import Playthrough
from app.db.models.scenario import Scenario
from app.db.models.scenario_condition import ScenarioCondition
from app.db.models.share import PlaythroughShare
from app.db.models.turn_log import TurnLog
from app.db.models.user import User

__all__: list[str] = [
    "NAMING_CONVENTION",
    "Base",
    "CreatedAtMixin",
    "Participant",
    "Playthrough",
    "PlaythroughShare",
    "Scenario",
    "ScenarioCondition",
    "TimestampMixin",
    "TurnLog",
    "User",
]
