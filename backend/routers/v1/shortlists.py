"""
Shortlists router — save, organise, and retrieve company shortlists.

Supports: create shortlist, add companies, list all, get one (with profiles), remove entry, delete list.
"""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from models.database_models import Company, EnrichmentProfile, Shortlist, ShortlistEntry

router = APIRouter(tags=["shortlists"])


class ShortlistAddRequest(BaseModel):
    shortlist_name: str
    company_id: str
    list_type: str = "buy_side"       # buy_side | sell_side | watchlist
    anchor_company_id: str | None = None
    deal_score: float | None = None
    confidence_score: float | None = None
    tier: str | None = None
    notes: str | None = None


class ShortlistCreateRequest(BaseModel):
    name: str
    description: str | None = None
    list_type: str = "buy_side"
    anchor_company_id: str | None = None


@router.post("")
async def add_to_shortlist(
    request: ShortlistAddRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Add a company to a named shortlist. Creates the shortlist if it doesn't exist.
    Idempotent — adding the same company twice updates notes/scores.
    """
    # Verify company exists
    r = await db.execute(select(Company).where(Company.company_id == request.company_id))
    if not r.scalar_one_or_none():
        raise HTTPException(status_code=404, detail=f"Company '{request.company_id}' not found")

    # Find or create shortlist by name
    sl_r = await db.execute(
        select(Shortlist).where(Shortlist.name == request.shortlist_name)
    )
    shortlist = sl_r.scalar_one_or_none()

    if not shortlist:
        shortlist = Shortlist(
            shortlist_id=f"sl_{uuid.uuid4().hex[:12]}",
            name=request.shortlist_name,
            list_type=request.list_type,
            anchor_company_id=request.anchor_company_id,
        )
        db.add(shortlist)
        await db.flush()

    # Find or create entry
    entry_r = await db.execute(
        select(ShortlistEntry).where(
            ShortlistEntry.shortlist_id == shortlist.shortlist_id,
            ShortlistEntry.company_id == request.company_id,
        )
    )
    entry = entry_r.scalar_one_or_none()

    if entry:
        # Update existing entry
        if request.deal_score is not None:
            entry.deal_score = request.deal_score
        if request.confidence_score is not None:
            entry.confidence_score = request.confidence_score
        if request.tier is not None:
            entry.tier = request.tier
        if request.notes is not None:
            entry.notes = request.notes
    else:
        entry = ShortlistEntry(
            entry_id=f"sle_{uuid.uuid4().hex[:12]}",
            shortlist_id=shortlist.shortlist_id,
            company_id=request.company_id,
            deal_score=request.deal_score,
            confidence_score=request.confidence_score,
            tier=request.tier,
            notes=request.notes,
        )
        db.add(entry)

    await db.commit()

    # Count total entries
    count_r = await db.execute(
        select(ShortlistEntry).where(ShortlistEntry.shortlist_id == shortlist.shortlist_id)
    )
    total = len(count_r.scalars().all())

    return {
        "shortlist_id": shortlist.shortlist_id,
        "shortlist_name": shortlist.name,
        "list_type": shortlist.list_type,
        "company_added": request.company_id,
        "total_companies": total,
    }


@router.post("/create")
async def create_shortlist(
    request: ShortlistCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create a named shortlist without adding any companies yet."""
    # Check for duplicate name
    r = await db.execute(select(Shortlist).where(Shortlist.name == request.name))
    if r.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Shortlist '{request.name}' already exists")

    shortlist = Shortlist(
        shortlist_id=f"sl_{uuid.uuid4().hex[:12]}",
        name=request.name,
        description=request.description,
        list_type=request.list_type,
        anchor_company_id=request.anchor_company_id,
    )
    db.add(shortlist)
    await db.commit()

    return {
        "shortlist_id": shortlist.shortlist_id,
        "name": shortlist.name,
        "list_type": shortlist.list_type,
        "created_at": shortlist.created_at.isoformat() if shortlist.created_at else None,
    }


@router.get("")
async def list_shortlists(db: AsyncSession = Depends(get_db)):
    """Returns all shortlists with entry counts and metadata."""
    r = await db.execute(select(Shortlist).order_by(Shortlist.updated_at.desc()))
    shortlists = r.scalars().all()

    result = []
    for sl in shortlists:
        count_r = await db.execute(
            select(ShortlistEntry).where(ShortlistEntry.shortlist_id == sl.shortlist_id)
        )
        entries = count_r.scalars().all()
        result.append({
            "shortlist_id": sl.shortlist_id,
            "name": sl.name,
            "description": sl.description,
            "list_type": sl.list_type,
            "anchor_company_id": sl.anchor_company_id,
            "company_count": len(entries),
            "created_at": sl.created_at.isoformat() if sl.created_at else None,
            "updated_at": sl.updated_at.isoformat() if sl.updated_at else None,
        })

    return result


@router.get("/{shortlist_id}")
async def get_shortlist(
    shortlist_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Returns all companies in a shortlist with their enrichment profiles."""
    r = await db.execute(select(Shortlist).where(Shortlist.shortlist_id == shortlist_id))
    shortlist = r.scalar_one_or_none()
    if not shortlist:
        raise HTTPException(status_code=404, detail=f"Shortlist '{shortlist_id}' not found")

    entries_r = await db.execute(
        select(ShortlistEntry)
        .where(ShortlistEntry.shortlist_id == shortlist_id)
        .order_by(ShortlistEntry.deal_score.desc().nullslast())
    )
    entries = entries_r.scalars().all()

    companies = []
    for entry in entries:
        cr = await db.execute(select(Company).where(Company.company_id == entry.company_id))
        company = cr.scalar_one_or_none()
        pr = await db.execute(
            select(EnrichmentProfile).where(EnrichmentProfile.company_id == entry.company_id)
        )
        profile = pr.scalar_one_or_none()

        companies.append({
            "entry_id": entry.entry_id,
            "company_id": entry.company_id,
            "legal_name": company.legal_name if company else None,
            "display_name": (company.display_name or company.legal_name) if company else None,
            "ticker": company.ticker if company else None,
            "jurisdiction": company.jurisdiction if company else None,
            "sector": company.sector if company else None,
            "deal_score": entry.deal_score,
            "confidence_score": entry.confidence_score,
            "tier": entry.tier,
            "notes": entry.notes,
            "coverage_depth": profile.coverage_depth if profile else None,
            "revenue_usd": profile.revenue_usd if profile else None,
            "enterprise_value_usd": profile.enterprise_value_usd if profile else None,
            "added_at": entry.added_at.isoformat() if entry.added_at else None,
        })

    return {
        "shortlist_id": shortlist.shortlist_id,
        "name": shortlist.name,
        "description": shortlist.description,
        "list_type": shortlist.list_type,
        "anchor_company_id": shortlist.anchor_company_id,
        "company_count": len(entries),
        "companies": companies,
        "created_at": shortlist.created_at.isoformat() if shortlist.created_at else None,
        "updated_at": shortlist.updated_at.isoformat() if shortlist.updated_at else None,
    }


@router.delete("/{shortlist_id}/company/{company_id}")
async def remove_from_shortlist(
    shortlist_id: str,
    company_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Remove a company from a shortlist."""
    r = await db.execute(
        select(ShortlistEntry).where(
            ShortlistEntry.shortlist_id == shortlist_id,
            ShortlistEntry.company_id == company_id,
        )
    )
    entry = r.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found in shortlist")

    await db.delete(entry)
    await db.commit()
    return {"removed": True, "shortlist_id": shortlist_id, "company_id": company_id}


@router.delete("/{shortlist_id}")
async def delete_shortlist(
    shortlist_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete an entire shortlist and all its entries."""
    r = await db.execute(select(Shortlist).where(Shortlist.shortlist_id == shortlist_id))
    shortlist = r.scalar_one_or_none()
    if not shortlist:
        raise HTTPException(status_code=404, detail=f"Shortlist '{shortlist_id}' not found")

    await db.delete(shortlist)
    await db.commit()
    return {"deleted": True, "shortlist_id": shortlist_id}
