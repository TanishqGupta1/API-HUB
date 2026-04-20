import httpx
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class OnPrintShopClient:
    def __init__(self, base_url: str, client_id: str, client_secret: str, token_url: str):
        self.base_url = base_url.rstrip("/")
        self.client_id = client_id
        self.client_secret = client_secret
        self.token_url = token_url
        self._token = None

    async def _get_token(self):
        if self._token:
            return self._token
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self.token_url,
                    data={
                        "grant_type": "client_credentials",
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                    },
                )
                response.raise_for_status()
                data = response.json()
                self._token = data.get("access_token")
                return self._token
            except Exception as e:
                logger.error(f"Failed to get OPS token: {e}")
                raise e

    async def query(self, query: str, variables: Dict[str, Any] = None) -> Dict[str, Any]:
        token = await self._get_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/graphql",
                json={"query": query, "variables": variables or {}},
                headers=headers,
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()

    async def get_categories(self) -> List[Dict[str, Any]]:
        query = """
        query GetCategories {
            getCategories {
                id
                name
                description
            }
        }
        """
        result = await self.query(query)
        return result.get("data", {}).get("getCategories", [])

    async def get_master_options(self) -> List[Dict[str, Any]]:
        query = """
        query GetMasterOptions {
            getMasterOptions {
                id
                name
                attributes {
                    id
                    name
                }
            }
        }
        """
        result = await self.query(query)
        return result.get("data", {}).get("getMasterOptions", [])
