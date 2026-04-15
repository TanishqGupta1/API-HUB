from fastapi import APIRouter

from .client import get_ps_companies, get_ps_endpoints
from .schemas import PSCompany, PSEndpoint

router = APIRouter(prefix="/api/ps-directory", tags=["promostandards"])


@router.get("/companies", response_model=list[PSCompany])
async def list_companies():
    return await get_ps_companies()


@router.get("/companies/{code}/endpoints", response_model=list[PSEndpoint])
async def list_endpoints(code: str):
    return await get_ps_endpoints(code)
