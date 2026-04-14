"""
Enrichment Service — orchestrates the two-pass GPT-4o-mini research pipeline.

Pass 1 → BASIC coverage (identity + financials)
Pass 2 → DEEP coverage (ownership + strategic features)

Confidence scoring:
  Filing recency:     0-30 pts  (30=current year, -5/yr stale, min 0)
  Data completeness:  0-40 pts  (5 pts each of 8 key fields)
  GPT signal quality: 0-30 pts  (from model's self-reported confidence)

Coverage depth:
  NONE:     no enrichment run
  BASIC:    identity + description + any financials
  STANDARD: BASIC + full financials (revenue + EBITDA + EV)
  DEEP:     STANDARD + ownership + strategic features + M&A signals
"""
import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.database_models import Company, EnrichmentProfile
from pipeline.research.company_researcher import fetch_basic_profile, research_company_deep

# Minimum fields for discovery eligibility
_BUY_SIDE_MIN = ["revenue_usd", "enterprise_value_usd", "sector",
                  "ownership_structure", "jurisdiction"]
_SELL_SIDE_MIN = ["revenue_usd", "enterprise_value_usd", "sector",
                   "ownership_structure", "jurisdiction", "strategic_priorities"]


# ---------------------------------------------------------------------------
# Main pipeline entry point
# ---------------------------------------------------------------------------

async def run_enrichment_pipeline(company_id: str, db: AsyncSession) -> dict:
    """
    Full two-pass enrichment. Persists results to DB after each pass.
    Returns final enrichment status dict.
    """
    # Fetch company record
    stmt = select(Company).where(Company.company_id == company_id)
    result = await db.execute(stmt)
    company = result.scalar_one_or_none()
    if company is None:
        return {"error": f"Company {company_id} not found"}

    # Fetch or create enrichment profile
    profile_stmt = select(EnrichmentProfile).where(
        EnrichmentProfile.company_id == company_id
    )
    profile_result = await db.execute(profile_stmt)
    profile = profile_result.scalar_one_or_none()

    if profile is None:
        profile = EnrichmentProfile(
            profile_id=f"enr_{uuid.uuid4().hex[:12]}",
            company_id=company_id,
            coverage_depth="NONE",
            confidence_score=0.0,
            discovery_eligible=False,
            missing_fields=[],
            sources=[],
        )
        db.add(profile)
        await db.flush()

    legal_name = company.legal_name
    jurisdiction = company.jurisdiction or "US"

    # ---- Pass 1: basic profile ----
    basic = await fetch_basic_profile(company_id, legal_name, jurisdiction)
    _apply_basic(company, profile, basic)
    profile.coverage_depth = "BASIC"
    await db.commit()

    # ---- Pass 2: deep profile ----
    deep = await research_company_deep(legal_name, jurisdiction, basic)
    _apply_deep(profile, deep)

    # ---- Compute final scores ----
    profile.confidence_score = _compute_confidence(company, profile, basic, deep)
    profile.coverage_depth = _compute_coverage_depth(profile)
    profile.missing_fields = _compute_missing_fields(company, profile)
    profile.discovery_eligible = _check_discovery_eligible(company, profile)
    profile.last_enriched_at = datetime.now(timezone.utc)

    # Merge sources
    sources = []
    if basic.get("sources"):
        sources.extend(basic["sources"])
    if deep.get("sources"):
        sources.extend(deep["sources"])
    profile.sources = list(set(sources)) if sources else ["openai_knowledge"]

    await db.commit()

    return {
        "company_id": company_id,
        "coverage_depth": profile.coverage_depth,
        "confidence_score": profile.confidence_score,
        "discovery_eligible": profile.discovery_eligible,
        "missing_fields": profile.missing_fields,
    }


# ---------------------------------------------------------------------------
# Apply extracted data to ORM objects
# ---------------------------------------------------------------------------

def _apply_basic(company: Company, profile: EnrichmentProfile, data: dict) -> None:
    """Merge basic profile data into company + enrichment_profile rows."""
    # Update company identity fields if blank
    for field in ("display_name", "ticker", "isin", "sector", "industry",
                  "employee_count", "founded_year", "hq_city", "hq_country",
                  "website", "description", "listing_status"):
        val = data.get(field)
        if val is not None and not getattr(company, field):
            setattr(company, field, val)

    # Financial fields go to profile
    for field in ("revenue_usd", "revenue_year", "ebitda_usd", "ebitda_margin",
                  "net_income_usd", "total_assets_usd", "total_debt_usd", "cash_usd",
                  "enterprise_value_usd", "market_cap_usd", "ev_revenue_multiple",
                  "ev_ebitda_multiple", "revenue_growth_yoy"):
        val = data.get(field)
        if val is not None:
            setattr(profile, field, val)

    # Use financials_as_of_year as revenue_year fallback if revenue_year not set
    if not profile.revenue_year and data.get("financials_as_of_year"):
        profile.revenue_year = data["financials_as_of_year"]

    # Store raw GPT output
    profile.gpt_research_raw = json.dumps(data)


def _apply_deep(profile: EnrichmentProfile, data: dict) -> None:
    """Merge deep profile data into enrichment_profile."""
    for field in ("ownership_structure", "controlling_shareholder", "controlling_stake_pct",
                  "pe_sponsor", "pe_vintage_year", "customer_concentration",
                  "m_and_a_appetite"):
        val = data.get(field)
        if val is not None:
            setattr(profile, field, val)

    for field in ("key_products", "geographic_markets", "top_customers",
                  "top_competitors", "strategic_priorities",
                  "recent_acquisitions", "recent_divestitures"):
        val = data.get(field)
        if val is not None:
            setattr(profile, field, val)

    for bool_field in ("rumored_target", "rumored_seller", "activist_present",
                       "management_change_recent", "strategic_review_underway"):
        val = data.get(bool_field)
        if val is not None:
            setattr(profile, bool_field, bool(val))


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def _compute_confidence(
    company: Company,
    profile: EnrichmentProfile,
    basic: dict,
    deep: dict,
) -> float:
    score = 0.0

    # Filing recency (0-30 pts)
    revenue_year = profile.revenue_year
    if revenue_year:
        current_year = datetime.now(timezone.utc).year
        years_stale = max(0, current_year - revenue_year)
        recency = max(0, 30 - years_stale * 5)
    else:
        recency = 0
    score += recency

    # Data completeness (0-40 pts, 5 per field)
    completeness_fields = [
        profile.revenue_usd,
        profile.ebitda_usd,
        profile.enterprise_value_usd,
        profile.ownership_structure,
        profile.strategic_priorities,
        company.sector,
        company.jurisdiction,
        profile.key_products,
    ]
    score += sum(5 for f in completeness_fields if f is not None)

    # GPT signal quality (0-30 pts)
    gpt_confidence = basic.get("data_confidence", 0)
    own_confidence = deep.get("ownership_confidence", 0)
    strategic_confidence = deep.get("strategic_confidence", 0)
    avg_gpt = (gpt_confidence + own_confidence + strategic_confidence) / 3
    score += (avg_gpt / 100) * 30

    return round(min(score, 100.0), 1)


def _compute_coverage_depth(profile: EnrichmentProfile) -> str:
    has_financials = profile.revenue_usd is not None and profile.ebitda_usd is not None
    has_ev = profile.enterprise_value_usd is not None
    has_ownership = profile.ownership_structure is not None
    has_strategic = bool(profile.strategic_priorities)
    has_signals = (profile.m_and_a_appetite and profile.m_and_a_appetite != "unknown")

    if has_ownership and has_strategic and has_signals:
        return "DEEP"
    if has_financials and has_ev and has_ownership:
        return "STANDARD"
    if has_financials or has_ev:
        return "BASIC"
    return "NONE"


def _compute_missing_fields(company: Company, profile: EnrichmentProfile) -> list[str]:
    missing = []
    checks = {
        "revenue_usd": profile.revenue_usd,
        "ebitda_usd": profile.ebitda_usd,
        "enterprise_value_usd": profile.enterprise_value_usd,
        "market_cap_usd": profile.market_cap_usd,
        "ownership_structure": profile.ownership_structure,
        "strategic_priorities": profile.strategic_priorities,
        "key_products": profile.key_products,
        "geographic_markets": profile.geographic_markets,
        "employee_count": company.employee_count,
        "founded_year": company.founded_year,
    }
    for field, val in checks.items():
        if val is None:
            missing.append(field)
    return missing


def _check_discovery_eligible(company: Company, profile: EnrichmentProfile) -> bool:
    """Eligible if all buy-side minimum fields are present."""
    for field in _BUY_SIDE_MIN:
        if field == "jurisdiction" and not company.jurisdiction:
            return False
        elif field == "sector" and not company.sector:
            return False
        elif field in ("revenue_usd", "enterprise_value_usd", "ownership_structure"):
            if getattr(profile, field, None) is None:
                return False
    return True


# ---------------------------------------------------------------------------
# Standalone helpers (used by company router)
# ---------------------------------------------------------------------------

async def compute_confidence_score(company_id: str) -> float:
    """Thin wrapper — confidence is computed during run_enrichment_pipeline."""
    return 0.0


async def compute_coverage_depth(company_id: str) -> str:
    return "BASIC"


async def check_discovery_eligibility(company_id: str) -> dict:
    return {
        "buy_side_eligible": False,
        "buy_side_missing": [],
        "sell_side_eligible": False,
        "sell_side_missing": [],
    }
