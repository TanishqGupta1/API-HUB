import asyncio
import os
import sys
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

# Ensure we can import from backend
sys.path.append(os.getcwd())

from database import Base
from modules.auth.models import User
from modules.auth.security import hash_password

async def create_admin():
    postgres_url = os.getenv("POSTGRES_URL", "postgresql+asyncpg://vg_user:vg_pass@localhost:5432/vg_hub")
    engine = create_async_engine(postgres_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Check if user already exists
        result = await session.execute(select(User).where(User.email == "user@demo.com"))
        user = result.scalar_one_or_none()
        
        if user:
            print("User user@demo.com already exists.")
            return

        admin = User(
            email="user@demo.com",
            hashed_password=hash_password("Adminapihub@1234"),
            role="vg_admin"
        )
        session.add(admin)
        await session.commit()
        print("Admin user created: user@demo.com / AdminApiHub@1234")

if __name__ == "__main__":
    asyncio.run(create_admin())
