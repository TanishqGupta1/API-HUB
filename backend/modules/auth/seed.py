import secrets

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import User
from .security import hash_password

DEFAULT_EMAIL = "admin@localhost"


async def ensure_default_admin(db: AsyncSession) -> None:
    count = (await db.execute(select(func.count()).select_from(User))).scalar()
    if count and count > 0:
        return
    password = secrets.token_urlsafe(16)
    user = User(
        email=DEFAULT_EMAIL,
        hashed_password=hash_password(password),
        role="vg_admin",
    )
    db.add(user)
    await db.commit()
    print(f"[auth] Created default admin — email: {DEFAULT_EMAIL}  password: {password}")
    print("[auth] IMPORTANT: Change this password immediately after first login.")
