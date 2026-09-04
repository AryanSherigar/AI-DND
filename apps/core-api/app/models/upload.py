"""Pydantic models for upload endpoints."""

from pydantic import BaseModel


class ImageUploadResponse(BaseModel):
    """Response returned after a successful image upload."""

    url: str
