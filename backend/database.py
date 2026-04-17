import json
import os
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from cryptography.fernet import Fernet
from sqlalchemy import Text, TypeDecorator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

DATABASE_URL = os.getenv(
    "POSTGRES_URL", "postgresql+asyncpg://vg_user:vg_pass@localhost:5432/vg_hub"
)
SECRET_KEY = os.getenv("SECRET_KEY", "")

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class EncryptedJSON(TypeDecorator):
    """Transparently encrypts/decrypts JSON data in the database."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> Optional[str]:
        if value is None:
            return None
        if not SECRET_KEY:
            return json.dumps(value)
        f = Fernet(SECRET_KEY.encode())
        return f.encrypt(json.dumps(value).encode()).decode()

    def process_result_value(self, value: Any, dialect: Any) -> Any:
        if value is None:
            return None
        if not SECRET_KEY:
            return json.loads(value)
        try:
            f = Fernet(SECRET_KEY.encode())
            return json.loads(f.decrypt(value.encode()))
        except Exception:
            return json.loads(value)


async def get_db():
    async with async_session() as session:
        yield session
