"""Bootstrap a vg_admin user.

Reads credentials from env so secrets never live in source:

    ADMIN_EMAIL=admin@example.com \\
    ADMIN_PASSWORD='hunter2' \\
    python create_admin.py

Idempotent: if a user with ADMIN_EMAIL already exists, the script exits 0.
"""
import asyncio
import os
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

sys.path.append(os.getcwd())

from modules.auth.models import User
from modules.auth.security import hash_password


async def create_admin() -> None:
    email = os.getenv("ADMIN_EMAIL", "").strip()
    password = os.getenv("ADMIN_PASSWORD", "")
    if not email or not password:
        print("ERROR: ADMIN_EMAIL and ADMIN_PASSWORD env vars are required.", file=sys.stderr)
        sys.exit(2)

    postgres_url = os.getenv(
        "POSTGRES_URL",
        "postgresql+asyncpg://vg_user:vg_pass@localhost:5432/vg_hub",
    )
    engine = create_async_engine(postgres_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        existing = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if existing:
            print(f"User {email} already exists.")
            return

        admin = User(email=email, hashed_password=hash_password(password), role="vg_admin")
        session.add(admin)
        await session.commit()
        print(f"Admin user created: {email}")


if __name__ == "__main__":
    asyncio.run(create_admin())
