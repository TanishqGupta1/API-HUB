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
    """Idempotent admin seed.

    Email/password come from DEMO_ADMIN_EMAIL / DEMO_ADMIN_PASSWORD when set
    (dev + CI use this to share a fixed login across machines), otherwise
    fall back to admin@localhost + a random password printed to logs.

    In production: never seed via env-provided plaintext — only the random
    branch runs, so the operator has to use the admin-reset flow rather
    than read a password out of compose env.
    """
    count = (await db.execute(select(func.count()).select_from(User))).scalar()
    if count and count > 0:
        return

    is_prod = os.getenv("ENVIRONMENT", "development").lower() == "production"
    env_email = os.getenv("DEMO_ADMIN_EMAIL")
    env_password = os.getenv("DEMO_ADMIN_PASSWORD")

    if not is_prod and env_email and env_password:
        email = env_email
        password = env_password
        source = "env"
    else:
        email = DEFAULT_EMAIL
        password = secrets.token_urlsafe(16)
        source = "random"

    db.add(User(
        email=email,
        hashed_password=hash_password(password),
        role="vg_admin",
        is_active=True,
    ))
    await db.commit()

    if is_prod:
        logger.warning(
            "[auth] Created default admin %s — generated random password; reset via admin flow",
            email,
        )
    else:
        logger.warning(
            "[auth] Created default admin (%s) — email: %s  password: %s",
            source,
            email,
            password,
        )
        logger.warning("[auth] IMPORTANT: Change this password immediately after first login.")
