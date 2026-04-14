from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from pipeline.research.entity_resolver import resolve_entity

router = APIRouter(tags=["entity"])


class EntityResolveRequest(BaseModel):
    query: str
    query_type: str = "auto"
    jurisdiction_hint: str | None = None


@router.post("/resolve")
async def resolve_entity_endpoint(
    request: EntityResolveRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Resolve any company identifier (name, ticker, ISIN, LEI) to a canonical record.
    Searches DB cache first; falls back to GPT-4o-mini live resolution.

    Resolution statuses:
    - resolved: single unambiguous match, company_id available
    - ambiguous: 2-5 candidates returned for user selection
    - not_found: could not identify any real company
    """
    if not request.query or not request.query.strip():
        raise HTTPException(status_code=400, detail="query must not be empty")

    result = await resolve_entity(
        query=request.query,
        query_type=request.query_type,
        jurisdiction_hint=request.jurisdiction_hint,
        db=db,
    )
    return result
