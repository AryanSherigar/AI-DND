"""FastAPI router for file upload endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile, status

from app.db.models.user import User
from app.exceptions.upload_exceptions import UploadValidationError
from app.middleware.auth import get_current_user
from app.models.upload import ImageUploadResponse
from app.services.upload_service import MAX_COVER_IMAGE_BYTES, UploadService

router = APIRouter(prefix="/v1/uploads", tags=["Uploads"])


def get_upload_service() -> UploadService:
    """Dependency injector for UploadService."""
    return UploadService()


async def _read_capped(file: UploadFile, max_bytes: int) -> bytes:
    """Read an upload's body, rejecting it as soon as it exceeds max_bytes."""
    chunks: list[bytes] = []
    total = 0
    while chunk := await file.read(64 * 1024):
        total += len(chunk)
        if total > max_bytes:
            raise UploadValidationError("Image exceeds the 5MB size limit.")
        chunks.append(chunk)
    return b"".join(chunks)


@router.post(
    "/scenario-cover-image",
    response_model=ImageUploadResponse,
    status_code=status.HTTP_200_OK,
)
async def upload_scenario_cover_image(
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[UploadService, Depends(get_upload_service)],
    file: Annotated[UploadFile, File()],
) -> ImageUploadResponse:
    """Upload a scenario cover image and return its public URL."""
    content = await _read_capped(file, MAX_COVER_IMAGE_BYTES)
    url = await service.upload_cover_image(content, file.content_type or "")
    return ImageUploadResponse(url=url)


@router.post(
    "/avatar",
    response_model=ImageUploadResponse,
    status_code=status.HTTP_200_OK,
)
async def upload_avatar(
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[UploadService, Depends(get_upload_service)],
    file: Annotated[UploadFile, File()],
) -> ImageUploadResponse:
    """Upload a user avatar image and return its public URL."""
    content = await _read_capped(file, MAX_COVER_IMAGE_BYTES)
    url = await service.upload_avatar(content, file.content_type or "")
    return ImageUploadResponse(url=url)


@router.post(
    "/banner",
    response_model=ImageUploadResponse,
    status_code=status.HTTP_200_OK,
)
async def upload_banner(
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[UploadService, Depends(get_upload_service)],
    file: Annotated[UploadFile, File()],
) -> ImageUploadResponse:
    """Upload a user profile banner image and return its public URL."""
    content = await _read_capped(file, MAX_COVER_IMAGE_BYTES)
    url = await service.upload_banner(content, file.content_type or "")
    return ImageUploadResponse(url=url)


@router.post(
    "/scenario-map-image",
    response_model=ImageUploadResponse,
    status_code=status.HTTP_200_OK,
)
async def upload_scenario_map_image(
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[UploadService, Depends(get_upload_service)],
    file: Annotated[UploadFile, File()],
) -> ImageUploadResponse:
    """Upload a scenario map image and return its public URL."""
    content = await _read_capped(file, MAX_COVER_IMAGE_BYTES)
    url = await service.upload_map_image(content, file.content_type or "")
    return ImageUploadResponse(url=url)
