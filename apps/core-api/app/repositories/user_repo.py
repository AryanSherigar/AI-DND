import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models.user import User

class UserRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_auth_provider_id(self, auth_provider_id: str) -> User | None:
        result = await self.session.execute(
            select(User).where(User.auth_provider_id == auth_provider_id)
        )
        return result.scalars().first()

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        result = await self.session.execute(
            select(User).where(User.user_id == user_id)
        )
        return result.scalars().first()

    async def create(self, auth_provider_id: str, display_name: str) -> User:
        user = User(
            auth_provider_id=auth_provider_id,
            display_name=display_name,
        )
        self.session.add(user)
        await self.session.flush()
        return user
