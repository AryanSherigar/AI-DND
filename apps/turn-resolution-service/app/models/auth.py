from pydantic import BaseModel
import uuid

class CurrentUser(BaseModel):
    user_id: uuid.UUID
    token_version: int
