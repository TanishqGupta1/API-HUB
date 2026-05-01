import asyncio
import logging
import sys
import os

# Add backend to sys.path so we can import modules
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from modules.import_jobs.scheduler import run_all_active_imports

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout
)

if __name__ == "__main__":
    asyncio.run(run_all_active_imports())
