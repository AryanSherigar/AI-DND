from pydantic import BaseModel, ConfigDict
import uuid

class UserResponse(BaseModel):
    user_id: uuid.UUID
    display_name: str
    
    model_config = ConfigDict(from_attributes=True)

class TokenExchangeRequest(BaseModel):
    firebase_id_token: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse
