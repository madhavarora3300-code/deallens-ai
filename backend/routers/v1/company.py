from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import AsyncSessionLocal, get_db
from models.database_models import Company, EnrichmentProfile

router = APIRouter(tags=["company"])

# Minimum fields required for buy-side discovery eligibility
_BUY_SIDE_REQUIRED = [
    "revenue_usd", "enterprise_value_usd", "sector",
    "ownership_structure", "jurisdiction",
]
# Minimum fields required for sell-side discovery eligibility
_SELL_SIDE_REQUIRED = [
    "revenue_usd", "enterprise_value_usd", "sector",
    "ownership_structure", "jurisdiction", "strategic_priorities",
]

# Fields that make coverage STANDARD (beyond BASIC)
_STANDARD_FIELDS = [
    "ebitda_usd", "market_cap_usd", "employee_count",
    "key_products", "geographic_markets", "ownership_structure",
]
# Fields that make coverage DEEP
_DEEP_FIELDS = [
    "strategic_priorities", "recent_acquisitions", "competitor analysis",
    "m_and_a_appetite", "customer_concentration",
]

# Freshness thresholds in days
_FRESH_DAYS = 7
_STALE_DAYS = 30


def _compute_freshness(last_enriched_at: datetime | None) -> str:
    if last_enriched_at is None:
        return "NEVER_ENRICHED"
    delta = (datetime.now(timezone.utc) - last_enriched_at).days
    if delta <= _FRESH_DAYS:
        return "FRESH"
    if delta <= _STALE_DAYS:
        return "AGING"
    return "STALE"


def _profile_to_dict(company: Company, profile: EnrichmentProfile | None) -> dict:
    """Serialize a company + profile into the full portal response shape."""
    if profile is None:
        return {
            "company_id": company.company_id,
            "legal_name": company.legal_name,
            "display_name": company.display_name or company.legal_name,
            "ticker": company.ticker,
            "isin": company.isin,
            "jurisdiction": company.jurisdiction,
            "listing_status": company.listing_status,
            "sector": company.sector,
            "industry": company.industry,
            "hq_city": company.hq_city,
            "hq_country": company.hq_country,
            "website": company.website,
            "description": company.description,
            "portal_state": {
                "coverage_depth": "NONE",
                "confidence_score": 0,
                "freshness_status": "NEVER_ENRICHED",
                "enrichment_status": "PENDING",
                "missing_fields": _BUY_SIDE_REQUIRED + _SELL_SIDE_REQUIRED,
            },
            "financials": None,
            "ownership": None,
            "strategic_features": None,
            "sources": [],
            "missing_fields": _BUY_SIDE_REQUIRED + _SELL_SIDE_REQUIRED,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    freshness = _compute_freshness(profile.last_enriched_at)

    return {
        "company_id": company.company_id,
        "legal_name": company.legal_name,
        "display_name": company.display_name or company.legal_name,
        "ticker": company.ticker,
        "isin": company.isin,
        "jurisdiction": company.jurisdiction,
        "listing_status": company.listing_status,
        "sector": company.sector,
        "industry": company.industry,
        "employee_count": company.employee_count,
        "founded_year": company.founded_year,
        "hq_city": company.hq_city,
        "hq_country": company.hq_country,
        "website": company.website,
        "description": company.description,
        "portal_state": {
            "coverage_depth": profile.coverage_depth,
            "confidence_score": profile.confidence_score,
            "freshness_status": freshness,
            "enrichment_status": "COMPLETE" if profile.last_enriched_at else "PENDING",
            "missing_fields": profile.missing_fields or [],
        },
        "financials": {
            "revenue_usd": profile.revenue_usd,
            "revenue_year": profile.revenue_year,
            "ebitda_usd": profile.ebitda_usd,
            "ebitda_margin": profile.ebitda_margin,
            "net_income_usd": profile.net_income_usd,
            "total_assets_usd": profile.total_assets_usd,
            "total_debt_usd": profile.total_debt_usd,
            "cash_usd": profile.cash_usd,
            "enterprise_value_usd": profile.enterprise_value_usd,
            "market_cap_usd": profile.market_cap_usd,
            "ev_revenue_multiple": profile.ev_revenue_multiple,
            "ev_ebitda_multiple": profile.ev_ebitda_multiple,
            "revenue_growth_yoy": profile.revenue_growth_yoy,
        },
        "ownership": {
            "ownership_structure": profile.ownership_structure,
            "controlling_shareholder": profile.controlling_shareholder,
            "controlling_stake_pct": profile.controlling_stake_pct,
            "pe_sponsor": profile.pe_sponsor,
            "pe_vintage_year": profile.pe_vintage_year,
        },
        "strategic_features": {
            "strategic_priorities": profile.strategic_priorities,
            "key_products": profile.key_products,
            "geographic_markets": profile.geographic_markets,
            "customer_concentration": profile.customer_concentration,
            "top_customers": profile.top_customers,
            "top_competitors": profile.top_competitors,
            "recent_acquisitions": profile.recent_acquisitions,
            "recent_divestitures": profile.recent_divestitures,
            "m_and_a_appetite": profile.m_and_a_appetite,
            "rumored_target": profile.rumored_target,
            "rumored_seller": profile.rumored_seller,
            "activist_present": profile.activist_present,
            "management_change_recent": profile.management_change_recent,
            "strategic_review_underway": profile.strategic_review_underway,
        },
        "sources": profile.sources or [],
        "missing_fields": profile.missing_fields or [],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


async def _get_company_and_profile(
    company_id: str, db: AsyncSession
) -> tuple[Company, EnrichmentProfile | None]:
    """Fetch company + enrichment profile. Raises 404 if company not found."""
    stmt = select(Company).where(Company.company_id == company_id)
    result = await db.execute(stmt)
    company = result.scalar_one_or_none()

    if company is None:
        raise HTTPException(status_code=404, detail=f"Company '{company_id}' not found")

    profile_stmt = select(EnrichmentProfile).where(
        EnrichmentProfile.company_id == company_id
    )
    profile_result = await db.execute(profile_stmt)
    profile = profile_result.scalar_one_or_none()

    return company, profile


async def _run_enrichment_background(company_id: str) -> None:
    """Background task: opens its own DB session (can't share request session)."""
    from pipeline.research.enrichment_service import run_enrichment_pipeline
    async with AsyncSessionLocal() as db:
        await run_enrichment_pipeline(company_id, db)


@router.post("/{company_id}/enrich")
async def trigger_enrichment(
    company_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Trigger the two-pass GPT-4o-mini enrichment pipeline for a company.
    Runs in background — poll /enrichment-status for progress.
    Returns immediately with current status.
    """
    company, profile = await _get_company_and_profile(company_id, db)

    # Don't re-enrich if freshly done
    if profile and profile.last_enriched_at:
        freshness = _compute_freshness(profile.last_enriched_at)
        if freshness == "FRESH":
            return {
                "company_id": company_id,
                "status": "already_fresh",
                "coverage_depth": profile.coverage_depth,
                "confidence_score": profile.confidence_score,
                "last_enriched_at": profile.last_enriched_at.isoformat(),
            }

    background_tasks.add_task(_run_enrichment_background, company_id)

    return {
        "company_id": company_id,
        "status": "enrichment_queued",
        "message": "Enrichment pipeline started. Poll /enrichment-status for progress.",
    }


@router.get("/{company_id}")
async def get_company_profile(
    company_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Return full company intelligence profile.
    Returns whatever is in the DB — enrichment is triggered separately (Phase 3).
    """
    company, profile = await _get_company_and_profile(company_id, db)
    return _profile_to_dict(company, profile)


@router.get("/{company_id}/enrichment-status")
async def get_enrichment_status(
    company_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Current enrichment coverage for a company.
    Frontend polls this every 2 seconds during enrichment (Phase 3 will push via WebSocket).
    """
    company, profile = await _get_company_and_profile(company_id, db)

    if profile is None:
        return {
            "company_id": company_id,
            "overall_progress_pct": 0,
            "coverage_depth": "NONE",
            "confidence_score": 0,
            "freshness_status": "NEVER_ENRICHED",
            "pipeline_steps": [],
            "live_intelligence_log": [],
            "sections_ready": {
                "identity": True,
                "financials": False,
                "ownership": False,
                "strategic_features": False,
                "discovery_eligible": False,
            },
        }

    freshness = _compute_freshness(profile.last_enriched_at)
    depth = profile.coverage_depth or "NONE"
    depth_pct = {"NONE": 5, "BASIC": 25, "STANDARD": 60, "DEEP": 100}.get(depth, 0)

    return {
        "company_id": company_id,
        "overall_progress_pct": depth_pct,
        "coverage_depth": depth,
        "confidence_score": profile.confidence_score,
        "freshness_status": freshness,
        "last_enriched_at": profile.last_enriched_at.isoformat() if profile.last_enriched_at else None,
        "pipeline_steps": [],
        "live_intelligence_log": [],
        "sections_ready": {
            "identity": True,
            "financials": profile.revenue_usd is not None,
            "ownership": profile.ownership_structure is not None,
            "strategic_features": bool(profile.strategic_priorities),
            "discovery_eligible": profile.discovery_eligible,
        },
    }


@router.get("/{company_id}/discovery-eligibility")
async def check_eligibility(
    company_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Check if company has enough enrichment data to run discovery.
    """
    company, profile = await _get_company_and_profile(company_id, db)
    freshness = _compute_freshness(profile.last_enriched_at if profile else None)

    def _missing(required_fields: list[str]) -> list[str]:
        if profile is None:
            return required_fields
        missing = []
        for field in required_fields:
            # Check company-level fields
            if field == "jurisdiction" and not company.jurisdiction:
                missing.append(field)
            elif field == "sector" and not company.sector:
                missing.append(field)
            # Check profile-level fields
            elif field in ("revenue_usd", "enterprise_value_usd", "ebitda_usd",
                           "market_cap_usd", "ownership_structure", "strategic_priorities",
                           "key_products", "geographic_markets"):
                if getattr(profile, field, None) is None:
                    missing.append(field)
        return missing

    buy_missing = _missing(_BUY_SIDE_REQUIRED)
    sell_missing = _missing(_SELL_SIDE_REQUIRED)

    return {
        "company_id": company_id,
        "buy_side_eligible": len(buy_missing) == 0,
        "buy_side_missing": buy_missing,
        "sell_side_eligible": len(sell_missing) == 0,
        "sell_side_missing": sell_missing,
        "confidence_score": profile.confidence_score if profile else 0,
        "coverage_depth": profile.coverage_depth if profile else "NONE",
        "freshness_status": freshness,
    }
