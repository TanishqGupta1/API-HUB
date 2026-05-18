import logging
import os
import secrets

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import User
from .security import hash_password

DEFAULT_EMAIL = "admin@localhost"

logger = logging.getLogger(__name__)


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
    # Never log the raw password in production — a prod operator must reset via
    # the admin-reset flow, not pluck it from stdout.
    if os.getenv("ENVIRONMENT", "development").lower() == "production":
        logger.warning(
            "[auth] Created default admin %s — generated random password; reset via admin flow",
            DEFAULT_EMAIL,
        )
    else:
        logger.warning(
            "[auth] Created default admin — email: %s  password: %s",
            DEFAULT_EMAIL,
            password,
        )
        logger.warning("[auth] IMPORTANT: Change this password immediately after first login.")
