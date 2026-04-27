import httpx
import os

PS_DIRECTORY_URL = os.getenv(
    "PS_DIRECTORY_URL",
    "https://services.promostandards.org/WebServiceRepository/WebServiceRepository.svc/json"
)


async def get_ps_companies() -> list[dict]:
    """Fetch all 1800+ companies from PromoStandards directory."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{PS_DIRECTORY_URL}/companies", timeout=30)
        resp.raise_for_status()
        return resp.json()


async def get_ps_endpoints(company_code: str) -> list[dict]:
    """Fetch all service endpoints for a given company code."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{PS_DIRECTORY_URL}/companies/{company_code}/endpoints",
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()
