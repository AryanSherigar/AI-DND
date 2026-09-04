"""Map domain exception classes."""

from app.exceptions.base import BaseAppException


class MapModeError(BaseAppException):
    """Raised when a Maps operation is attempted on a non-master-mode scenario."""

    def __init__(
        self, message: str = "Maps are only available for master-mode scenarios"
    ):
        super().__init__(message=message, status_code=422)


class MapNotFoundError(BaseAppException):
    """Raised when a map is not found or does not belong to the scenario."""

    def __init__(self, message: str = "Map not found"):
        super().__init__(message=message, status_code=404)


class MapPinNotFoundError(BaseAppException):
    """Raised when a pin is not found or does not belong to the map/scenario."""

    def __init__(self, message: str = "Map pin not found"):
        super().__init__(message=message, status_code=404)


class MapPinInvalidEntityError(BaseAppException):
    """Raised when a pin references an entity that isn't a location entity
    owned by the same scenario."""

    def __init__(
        self, message: str = "Pin must reference a location entity in this scenario"
    ):
        super().__init__(message=message, status_code=422)


class MapStartLocationConflictError(BaseAppException):
    """Raised when a second pin is flagged as the scenario's start location."""

    def __init__(
        self,
        message: str = "This scenario already has a starting location pin",
    ):
        super().__init__(message=message, status_code=422)


class MapConnectionNotFoundError(BaseAppException):
    """Raised when a connection is not found or does not belong to the scenario."""

    def __init__(self, message: str = "Map connection not found"):
        super().__init__(message=message, status_code=404)


class MapConnectionInvalidEntityError(BaseAppException):
    """Raised when a connection references an invalid entity pair."""

    def __init__(
        self,
        message: str = (
            "A connection must link two distinct location entities in this scenario"
        ),
    ):
        super().__init__(message=message, status_code=422)


class MapConnectionDuplicateError(BaseAppException):
    """Raised when a connection between the same two entities already exists."""

    def __init__(self, message: str = "This connection already exists"):
        super().__init__(message=message, status_code=422)


class MapPublishValidationError(BaseAppException):
    """Raised at publish time when a scenario with maps has no start pin."""

    def __init__(
        self,
        message: str = (
            "A scenario with maps must have exactly one location flagged as "
            "the starting location before it can be published"
        ),
    ):
        super().__init__(message=message, status_code=422)
