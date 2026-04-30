import asyncio
from database import engine
from sqlalchemy import text

async def test_conn():
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            print("Successfully connected to database")
    except Exception as e:
        print(f"Failed to connect: {e}")

if __name__ == "__main__":
    asyncio.run(test_conn())
