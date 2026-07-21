import asyncio
from app.core.security import hash_password
from app.infrastructure.db.models.enums import UserRole
from app.infrastructure.db.models.user import User
from app.infrastructure.db.session import AsyncSessionLocal

async def main():
    async with AsyncSessionLocal() as session:
        session.add(User(
            username="admin", email="admin@smartgrid.in",
            password_hash=hash_password("change-me-immediately"),
            full_name="System Administrator", role=UserRole.ADMIN,
        ))
        await session.commit()
    print("Admin user created.")

asyncio.run(main())