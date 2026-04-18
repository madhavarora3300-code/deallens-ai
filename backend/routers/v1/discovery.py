"""
Discovery router — buy-side target discovery and sell-side buyer universe.

Buy-side flow:
  1. HTTP endpoint queues a Celery task and returns job_id immediately
  2. Celery task: seed relevant candidates via GPT (web search model)
  3. Resolve + enrich each candidate in parallel (asyncio.Semaphore(6))
  4. Apply hard gates (deterministic, no AI)
  5. Score survivors concurrently via GPT-4o-mini
  6. Generate narrations for top 15
  7. Result stored in Redis via Celery result backend
  8. Frontend polls GET /v1/discovery/job/{job_id} every 3s

Sell-side flow: same pattern with sell-side scoring + process architecture.
"""
import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from openai import AsyncOpenAI
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.database import get_db, AsyncSessionLocal
from models.database_models import Company, EnrichmentProfile
from pipeline.scoring.scoring_engine import check_hard_gates
from pipeline.scoring.buy_side_scorer import score_target
from pipeline.scoring.sell_side_scorer import score_buyer
from pipeline.research.entity_resolver import _create_canonical_record
from pipeline.research.enrichment_service import run_enrichment_pipeline

logger = logging.getLogger(__name__)

_openai_client: AsyncOpenAI | None = None

def _get_openai() -> AsyncOpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _openai_client

# Per-run metadata store: company_id → {rationale_category, why_now, estimated_synergy_value_usd_m}
# Populated during _seed_candidates(), consumed in _load_all_enriched_profiles() and scoring response.
# Uses a simple dict — safe for single-process async FastAPI.
_seeded_meta: dict[str, dict] = {}

router = APIRouter(tags=["discovery"])

# Max concurrent GPT scoring calls
_SCORE_SEMAPHORE_LIMIT = 8
# Generate narration only for top N results
_NARRATE_TOP_N = 15


class DiscoveryFilters(BaseModel):
    # Legacy fields (kept for backward compat)
    jurisdiction: list[str] | None = None
    sector: str | None = None
    revenue_min_usd_m: float | None = None
    revenue_max_usd_m: float | None = None
    min_deal_score: int | None = None
    buyer_type: list[str] | None = None
    min_buyer_ev_b: float | None = None
    cash_reserves_min_b: float | None = None

    # Target size filters
    ev_min_usd_b: float | None = None
    ev_max_usd_b: float | None = None
    employee_count_min: int | None = None
    employee_count_max: int | None = None

    # Geography
    regions: list[str] | None = None  # ["north_america", "europe", "asia_pacific", "latam", "middle_east", "india", "global"]

    # Ownership / listing
    ownership_types: list[str] | None = None  # ["public", "private", "pe_backed", "family_founder", "state_owned"]
    listing_statuses: list[str] | None = None  # ["public", "private", "subsidiary", "distressed"]

    # Sector focus
    sector_focus: str | None = None  # "same", "adjacent", "any"

    # Deal structure preference
    deal_structures: list[str] | None = None  # ["friendly_only", "hostile_acceptable", "minority_stake", "full_acquisition"]

    # Financial floors
    min_revenue_growth_pct: float | None = None
    min_ebitda_margin_pct: float | None = None
    max_net_debt_ebitda: float | None = None


class BuySideRequest(BaseModel):
    buyer_company_id: str
    strategy_mode: str = "capability_bolt_on"
    filters: DiscoveryFilters = DiscoveryFilters()
    limit: int = 50


class SellSideRequest(BaseModel):
    seller_company_id: str
    process_objective: str = "maximize_price"
    filters: DiscoveryFilters = DiscoveryFilters()
    limit: int = 25


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _load_profile(company_id: str, db: AsyncSession) -> dict | None:
    """Load company + enrichment profile as a dict. Returns None if not found."""
    stmt = select(Company).where(Company.company_id == company_id)
    r = await db.execute(stmt)
    company = r.scalar_one_or_none()
    if not company:
        return None

    pstmt = select(EnrichmentProfile).where(EnrichmentProfile.company_id == company_id)
    pr = await db.execute(pstmt)
    profile = pr.scalar_one_or_none()

    return _serialize_profile(company, profile)


async def _load_all_enriched_profiles(
    exclude_id: str,
    filters: DiscoveryFilters,
    db: AsyncSession,
    company_ids: list[str] | None = None,
) -> list[dict]:
    """Load enriched companies except the anchor.
    When company_ids is provided (scoped seeding run): load those specific companies
    regardless of discovery_eligible — any company that was enriched is included.
    When None: fall back to only discovery_eligible=True companies (full DB scan mode).
    """
    if company_ids is not None:
        # Scoped run — include any enriched company in the seeded set
        stmt = (
            select(Company, EnrichmentProfile)
            .join(EnrichmentProfile, Company.company_id == EnrichmentProfile.company_id)
            .where(
                Company.company_id != exclude_id,
                Company.company_id.in_(company_ids),
                EnrichmentProfile.last_enriched_at.isnot(None),
            )
        )
    else:
        # Fallback full-DB scan — only discovery_eligible companies
        stmt = (
            select(Company, EnrichmentProfile)
            .join(EnrichmentProfile, Company.company_id == EnrichmentProfile.company_id)
            .where(
                Company.company_id != exclude_id,
                EnrichmentProfile.discovery_eligible == True,  # noqa: E712
            )
        )

    if filters.jurisdiction:
        stmt = stmt.where(Company.jurisdiction.in_(filters.jurisdiction))
    if filters.sector:
        stmt = stmt.where(Company.sector == filters.sector)

    result = await db.execute(stmt)
    rows = result.all()

    # Region → jurisdiction prefix mapping
    REGION_JURISDICTIONS = {
        "north_america": ["US", "CA", "MX"],
        "europe": ["GB", "DE", "FR", "IT", "ES", "NL", "SE", "CH", "BE", "AT", "DK", "NO", "FI", "PL", "IE"],
        "asia_pacific": ["CN", "JP", "AU", "KR", "SG", "HK", "TW", "IN", "TH", "MY", "ID", "PH", "NZ", "VN"],
        "latam": ["BR", "AR", "CL", "CO", "PE", "MX"],
        "middle_east": ["AE", "SA", "QA", "KW", "BH", "OM", "IL", "EG", "TR"],
        "india": ["IN"],
        "global": None,  # No filter
    }

    region_jx: set[str] | None = None
    if filters.regions and "global" not in filters.regions:
        region_jx = set()
        for r in filters.regions:
            codes = REGION_JURISDICTIONS.get(r)
            if codes:
                region_jx.update(codes)

    profiles = []
    for company, profile in rows:
        p = _serialize_profile(company, profile)

        # Revenue filter
        rev_m = (profile.revenue_usd or 0) / 1e6
        if filters.revenue_min_usd_m and rev_m < filters.revenue_min_usd_m:
            continue
        if filters.revenue_max_usd_m and rev_m > filters.revenue_max_usd_m:
            continue

        # EV filter
        ev_b = (profile.enterprise_value_usd or 0) / 1e9
        if filters.ev_min_usd_b and ev_b > 0 and ev_b < filters.ev_min_usd_b:
            continue
        if filters.ev_max_usd_b and ev_b > filters.ev_max_usd_b:
            continue

        # Region filter
        if region_jx is not None and company.jurisdiction not in region_jx:
            continue

        # Ownership type filter
        if filters.ownership_types:
            own_str = (profile.ownership_structure or "").lower()
            listing = (company.listing_status or "").lower()
            match = False
            for ot in filters.ownership_types:
                if ot == "public" and listing == "public": match = True
                elif ot == "private" and listing in ("private", ""): match = True
                elif ot == "pe_backed" and ("pe" in own_str or "private equity" in own_str or "sponsor" in own_str): match = True
                elif ot == "family_founder" and ("family" in own_str or "founder" in own_str): match = True
                elif ot == "state_owned" and ("state" in own_str or "government" in own_str or "sovereign" in own_str): match = True
            if not match:
                continue

        # Listing status filter
        if filters.listing_statuses:
            listing = (company.listing_status or "").lower()
            if listing not in [ls.lower() for ls in filters.listing_statuses]:
                continue

        # EBITDA margin filter (post-query)
        if filters.min_ebitda_margin_pct is not None and profile.ebitda_usd and profile.revenue_usd and profile.revenue_usd > 0:
            margin = (profile.ebitda_usd / profile.revenue_usd) * 100
            if margin < filters.min_ebitda_margin_pct:
                continue

        # Attach seeded metadata (rationale_category, why_now, synergy estimate) if available
        cid = company.company_id
        meta = _seeded_meta.get(cid, {})
        if meta:
            p["rationale_category"] = meta.get("rationale_category") or ""
            p["why_now"] = meta.get("why_now") or ""
            p["estimated_synergy_value_usd_m"] = meta.get("estimated_synergy_value_usd_m")
            # Use seeded rationale as fallback if no narration yet
            if meta.get("seeded_rationale"):
                p.setdefault("seeded_rationale", meta["seeded_rationale"])

        profiles.append(p)

    return profiles


def _serialize_profile(company: Company, profile: EnrichmentProfile | None) -> dict:
    """Convert ORM objects to the same shape used by scoring engine."""
    fin = {}
    own = {}
    sf = {}

    if profile:
        fin = {
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
        }
        own = {
            "ownership_structure": profile.ownership_structure,
            "controlling_shareholder": profile.controlling_shareholder,
            "controlling_stake_pct": profile.controlling_stake_pct,
            "pe_sponsor": profile.pe_sponsor,
            "pe_vintage_year": profile.pe_vintage_year,
        }
        sf = {
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
        }

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
        "hq_city": company.hq_city,
        "hq_country": company.hq_country,
        "website": company.website,
        "description": company.description,
        "financials": fin,
        "ownership": own,
        "strategic_features": sf,
    }


def _quick_gate_check(buyer_profile: dict, target_profile: dict, strategy_mode: str) -> str | None:
    """Fast pre-flight hard gate using only deterministic data. No AI needed."""
    features = {
        "buyer_company_id": buyer_profile.get("company_id"),
        "target_company_id": target_profile.get("company_id"),
        "target_jurisdiction": target_profile.get("jurisdiction"),
        "buyer_ev_usd_m": (buyer_profile.get("financials", {}).get("enterprise_value_usd") or 0) / 1e6,
        "target_ev_usd_m": (target_profile.get("financials", {}).get("enterprise_value_usd") or 0) / 1e6,
        "target_market_cap_usd_m": (target_profile.get("financials", {}).get("market_cap_usd") or 0) / 1e6,
        "buyer_market_cap_usd_m": (buyer_profile.get("financials", {}).get("market_cap_usd") or 0) / 1e6,
    }
    return check_hard_gates(features, strategy_mode)


# ---------------------------------------------------------------------------
# Candidate seeding — ask GPT for relevant companies, resolve + enrich them
# ---------------------------------------------------------------------------

_STRATEGY_CONTEXT = {
    "capability_bolt_on": (
        "STRATEGY: Capability Bolt-On. Focus on companies with proprietary technology, IP, talent, or "
        "unique capabilities that directly fill a gap in the buyer's product portfolio or service offering. "
        "Prefer PE-backed, founder-led, and private companies with niche expertise. Avoid large public peers."
    ),
    "geographic_expansion": (
        "STRATEGY: Geographic Expansion. Focus on companies that give the buyer a meaningful market presence "
        "in geographies where it has little or no footprint. Spread candidates across multiple regions: "
        "US, UK, Europe (Germany, France, Nordics), Asia-Pacific (India, China, SE Asia, Japan, ANZ), "
        "LatAm (Brazil, Mexico), Middle East. Local market leaders preferred."
    ),
    "scale_consolidation": (
        "STRATEGY: Scale Consolidation. Focus on direct competitors and near-competitors in the same sector "
        "and subsector. The goal is market share gain and cost synergies. Include both public and private players. "
        "Prioritise companies with overlapping customer bases and similar revenue profiles."
    ),
    "distressed_opportunity": (
        "STRATEGY: Distressed Opportunity. Focus on companies showing financial stress signals: high leverage, "
        "revenue decline, covenant breaches, recent credit downgrades, layoffs, or asset sales. "
        "Include companies under PE ownership approaching fund end-of-life. Prefer situations where the buyer "
        "can acquire at a discount and implement a turnaround."
    ),
    "merger_of_equals": (
        "STRATEGY: Merger of Equals. Focus on companies of comparable size (between 0.5x and 2x the buyer's "
        "enterprise value) where a combination creates a dominant sector player. Both parties should benefit "
        "symmetrically. Prefer companies in adjacent or identical sectors. No tuck-ins or bolt-ons."
    ),
    "platform_build": (
        "STRATEGY: Platform Build. Focus on founder-led or PE-backed businesses that could serve as the anchor "
        "for a buy-and-build platform. Prefer fragmented sectors with roll-up potential. Targets should be "
        "scalable, operationally lean, and open to a controlling acquisition. Include companies with recurring revenue."
    ),
    "minority_to_control": (
        "STRATEGY: Minority to Control. Focus on listed companies with available float, or private companies "
        "with existing institutional minority shareholders. Prefer situations where a creep acquisition or "
        "negotiated block purchase is feasible. Include companies where the buyer may already have a small stake."
    ),
}

# Sector-to-rationale-category mapping: tells GPT which M&A rationale types are most relevant
_SECTOR_RATIONALE_HINT = {
    "Materials":              ["VERTICAL_INTEGRATION", "SUPPLY_CHAIN_RESILIENCE", "SCALE_CONSOLIDATION", "ESG_GREEN_TRANSITION"],
    "Industrials":            ["VERTICAL_INTEGRATION", "SCALE_CONSOLIDATION", "CAPABILITY_BOLTON", "GEOGRAPHIC_EXPANSION"],
    "Technology":             ["CAPABILITY_BOLTON", "SECTOR_CONVERGENCE", "GEOGRAPHIC_EXPANSION", "SCALE_CONSOLIDATION"],
    "Information Technology": ["CAPABILITY_BOLTON", "SECTOR_CONVERGENCE", "GEOGRAPHIC_EXPANSION"],
    "Healthcare":             ["CAPABILITY_BOLTON", "SCALE_CONSOLIDATION", "SECTOR_CONVERGENCE"],
    "Financials":             ["SCALE_CONSOLIDATION", "CAPABILITY_BOLTON", "GEOGRAPHIC_EXPANSION"],
    "Energy":                 ["VERTICAL_INTEGRATION", "ESG_GREEN_TRANSITION", "SUPPLY_CHAIN_RESILIENCE"],
    "Consumer Staples":       ["GEOGRAPHIC_EXPANSION", "SCALE_CONSOLIDATION", "SECTOR_CONVERGENCE"],
    "Consumer Discretionary": ["GEOGRAPHIC_EXPANSION", "SCALE_CONSOLIDATION", "CAPABILITY_BOLTON"],
    "Real Estate":            ["GEOGRAPHIC_EXPANSION", "SCALE_CONSOLIDATION"],
    "Utilities":              ["ESG_GREEN_TRANSITION", "SCALE_CONSOLIDATION", "GEOGRAPHIC_EXPANSION"],
    "Telecom":                ["SCALE_CONSOLIDATION", "CAPABILITY_BOLTON", "GEOGRAPHIC_EXPANSION"],
    "Media":                  ["CAPABILITY_BOLTON", "SECTOR_CONVERGENCE", "GEOGRAPHIC_EXPANSION"],
}

_MA_RATIONALE_FRAMEWORK = """\
GLOBAL M&A RATIONALE FRAMEWORK (evidence-based, 2024-2026 trends):

1. SCALE_CONSOLIDATION — 59% of major deals in 2024
   Target profile: Same-sector competitors with overlapping customers; cost synergies from headcount,
   procurement, facilities consolidation. Public or PE-backed, similar revenue.
   Example synergy: "Combined procurement reduces COGS by ~$X M/yr"

2. CAPABILITY_BOLTON — 33% of top deals cite AI/tech capability
   Target profile: Niche IP, proprietary technology, or talent pool buyer cannot build in <3 years.
   Smaller EV (<30% of buyer), PE/founder-owned. Time-to-market premium justifies price.
   Example synergy: "Acquires AI platform saving 2-year R&D build, adds $X M ARR"

3. GEOGRAPHIC_EXPANSION — Market leaders in new geographies
   Target profile: Dominant local player in same sector but different jurisdiction.
   Access to distribution, brand recognition, regulatory licenses in new market.
   Example synergy: "Enters {market} with $X B addressable market via established channel"

4. VERTICAL_INTEGRATION — Upstream/downstream supply chain control
   Target profile: Supplier (mining, raw materials) or downstream (distribution, retail, services).
   Reduces input cost volatility, captures margin, secures supply chain.
   Example synergy: "Eliminates $X M/yr third-party input cost, secures {material} supply"

5. SECTOR_CONVERGENCE — Cross-sector synergies (industrial+tech, consumer+healthcare)
   Target profile: Adjacent sector with shared customer base or complementary product.
   Example: Steel + automation tech, healthcare + consumer goods, energy + digital infrastructure.

6. DISTRESSED_OPPORTUNISTIC — Discount acquisition + turnaround
   Target profile: High leverage (Net Debt/EBITDA >5x), revenue decline, PE fund end-of-life (vintage ≥5yr),
   activist pressure, or strategic review announcement.
   Example synergy: "Acquires at ~40% discount to fair value; turnaround adds $X M EBITDA in 3yr"

7. ESG_GREEN_TRANSITION — Low-carbon assets, sustainability capability
   Target profile: Renewable energy producers, low-carbon process technology, circular economy assets,
   carbon credit platforms. Driven by net-zero commitments and regulatory pressure.
   Example synergy: "Reduces Scope 2 emissions by X%, unlocks green financing at -X bps"

8. SUPPLY_CHAIN_RESILIENCE — Strategic material/logistics security
   Target profile: Mines, ports, logistics operators, critical material processors.
   Motivated by post-COVID de-risking, near-shoring, strategic material security (lithium, rare earths, iron ore).
   Example synergy: "Secures X% of annual {input} demand at cost, removes market price risk"
"""

async def _seed_candidates(
    anchor_profile: dict,
    mode: str,
    limit: int = 20,
    strategy_hint: str = "",
    session_factory=None,
) -> list[str]:
    """
    Ask GPT for relevant acquisition targets (buy-side) or potential buyers (sell-side).

    Uses a 3-layer intelligence prompt:
      Layer 1 — Full anchor financial + strategic context
      Layer 2 — Evidence-based M&A rationale framework (8 global categories)
      Layer 3 — Anti-hallucination diversity rules (geography, ownership mix, sector discipline)

    Each candidate now carries rationale_category + why_now + estimated_synergy_value_usd_m
    which flow through to the scoring output for display on the frontend.

    Returns list of company_ids (resolved + enriched).
    """
    anchor_name = anchor_profile.get("display_name") or anchor_profile.get("legal_name", "")
    anchor_ticker = anchor_profile.get("ticker") or "private"
    anchor_sector = anchor_profile.get("sector") or "unknown"
    anchor_industry = anchor_profile.get("industry") or ""
    anchor_jurisdiction = anchor_profile.get("jurisdiction") or "unknown"
    anchor_listing = anchor_profile.get("listing_status") or "unknown"
    anchor_description = (anchor_profile.get("description") or "")[:400]

    fin = anchor_profile.get("financials") or {}
    rev_usd = fin.get("revenue_usd") or 0
    ev_usd = fin.get("enterprise_value_usd") or 0
    mc_usd = fin.get("market_cap_usd") or 0
    ebitda_margin = fin.get("ebitda_margin") or 0
    rev_b = f"${rev_usd / 1e9:.1f}B" if rev_usd else "undisclosed"
    ev_b = f"${ev_usd / 1e9:.1f}B" if ev_usd else "undisclosed"
    mc_b = f"${mc_usd / 1e9:.1f}B" if mc_usd else "undisclosed"
    margin_str = f"{ebitda_margin:.0f}%" if ebitda_margin else "undisclosed"

    sf = anchor_profile.get("strategic_features") or {}
    priorities = sf.get("strategic_priorities") or []
    priorities_str = "; ".join(priorities[:5]) if priorities else "not available"
    key_products = sf.get("key_products") or []
    products_str = ", ".join(key_products[:5]) if key_products else "not available"
    geo_markets = sf.get("geographic_markets") or []
    markets_str = ", ".join(geo_markets[:6]) if geo_markets else anchor_jurisdiction
    recent_acq = sf.get("recent_acquisitions") or []
    acq_str = ", ".join(recent_acq[:4]) if recent_acq else "none on record"

    strategy_context = _STRATEGY_CONTEXT.get(strategy_hint, "")

    # Pick most relevant rationale categories for this sector
    sector_hints = _SECTOR_RATIONALE_HINT.get(anchor_sector, ["SCALE_CONSOLIDATION", "CAPABILITY_BOLTON", "GEOGRAPHIC_EXPANSION"])
    relevant_categories = ", ".join(sector_hints[:4])

    _LIVE_SIGNALS_CONTEXT = (
        "CURRENT M&A ENVIRONMENT (2025-2026) — use these macro signals to sharpen why_now:\n"
        "  • PE dry powder at record $3.9T → PE-backed portfolio companies facing exit urgency\n"
        "  • Interest rates declining globally → LBO costs falling, leveraged buyouts reviving\n"
        "  • AI capability gap → non-tech companies acquiring AI/automation/data assets urgently\n"
        "  • ESG regulation tightening → carbon-intensive assets under divestiture pressure\n"
        "  • Supply chain near-shoring → manufacturing assets in allied nations commanding premiums\n"
        "  • Sector convergence wave: healthcare+tech, industrial+digital, energy+infrastructure\n"
        "  • Corporate activism rising → activist-held companies under pressure to do deals\n"
    )

    if mode == "buy_side":
        system_msg = (
            "You are a senior M&A analyst at a top-tier investment bank (Goldman Sachs / Morgan Stanley / JP Morgan). "
            "Your job is to identify realistic, specific global acquisition targets with rigorous strategic rationale. "
            "You draw on your knowledge of global capital markets, industry dynamics, and M&A deal patterns. "
            "You ONLY suggest real, named companies that actually exist in the global market. "
            "You apply the M&A Rationale Framework below to ensure each candidate has genuine strategic logic.\n\n"
            + _MA_RATIONALE_FRAMEWORK
            + "\n\n" + _LIVE_SIGNALS_CONTEXT
        )
        user_msg = (
            f"BUYER PROFILE:\n"
            f"  Name: {anchor_name} ({anchor_ticker})\n"
            f"  Sector: {anchor_sector} | Industry: {anchor_industry}\n"
            f"  Jurisdiction: {anchor_jurisdiction} | Listing: {anchor_listing}\n"
            f"  Revenue: {rev_b} | Enterprise Value: {ev_b} | Market Cap: {mc_b} | EBITDA Margin: {margin_str}\n"
            f"  Key products/services: {products_str}\n"
            f"  Geographic markets: {markets_str}\n"
            f"  Strategic priorities: {priorities_str}\n"
            f"  Recent acquisitions: {acq_str}\n"
            f"  Description: {anchor_description}\n\n"
            f"{strategy_context}\n\n"
            f"MOST RELEVANT M&A RATIONALE CATEGORIES FOR {anchor_sector.upper()} SECTOR:\n"
            f"  Priority categories: {relevant_categories}\n\n"
            f"TASK: Identify {limit} specific, real acquisition targets for {anchor_name}.\n\n"
            f"STRICT RULES:\n"
            f"  1. SECTOR DISCIPLINE: Candidates must be in {anchor_sector} or directly adjacent sectors. "
            f"     DO NOT suggest IT services, software, or financial companies for an industrial/materials buyer "
            f"     unless there is explicit sector convergence rationale (e.g., industrial automation, steel tech).\n"
            f"  2. GEOGRAPHY DIVERSITY: Include candidates from at least 4 different countries/regions. "
            f"     Do NOT put all candidates in {anchor_jurisdiction}.\n"
            f"  3. OWNERSHIP MIX: Include at least: 2 publicly listed companies, 2 PE-backed, 1 family/founder-led.\n"
            f"  4. SIZE MIX: Include bolt-ons (<$500M EV), mid-size ($500M-5B), and 1-2 larger plays (>$5B if buyer EV permits).\n"
            f"  5. REAL COMPANIES ONLY: Every company named must be a real, verifiable entity with known operations.\n"
            f"  6. DO NOT include {anchor_name}, its subsidiaries, or companies it already owns.\n"
            f"  7. WHY NOW: For each candidate, provide a specific why-now trigger using the macro signals above.\n"
            f"  8. SYNERGY VALUE: Estimate a specific dollar synergy value (e.g., '$150M/yr procurement savings').\n"
            f"  9. NON-OBVIOUS MATCHES: Include 2-3 candidates that are NOT obvious sector fits but have a strong "
            f"     cross-sector strategic bridge (e.g., a materials buyer acquiring an industrial AI platform to "
            f"     achieve smart factory capabilities). For these, set is_non_obvious=true and provide a "
            f"     non_obvious_bridge explaining the strategic logic in one sentence.\n"
            f"  10. PRECEDENT DEALS: For each candidate, cite 1 real comparable M&A transaction that validates "
            f"      the thesis (format: 'Acquirer / Target (Year, ~EV/EBITDAx) — rationale').\n\n"
            f"Return ONLY valid JSON:\n"
            f"{{\"candidates\": [\n"
            f"  {{\"legal_name\": \"str\", \"display_name\": \"str\", \"ticker\": \"str or null\",\n"
            f"   \"jurisdiction\": \"ISO2 code\", \"listing_status\": \"public|private|pe_backed|subsidiary\",\n"
            f"   \"sector\": \"str\", \"rationale\": \"1-2 sentence M&A rationale with specific synergy\",\n"
            f"   \"rationale_category\": \"one of the 8 categories above\",\n"
            f"   \"why_now\": \"specific current trigger for this deal (use macro signals where applicable)\",\n"
            f"   \"estimated_synergy_value_usd_m\": number_or_null,\n"
            f"   \"is_non_obvious\": true_or_false,\n"
            f"   \"non_obvious_bridge\": \"one sentence cross-sector strategic logic (only if is_non_obvious=true)\",\n"
            f"   \"precedent_deals\": \"Acquirer / Target (Year, ~Xx EBITDA) — rationale\"}}\n"
            f"]}}"
        )
    else:
        system_msg = (
            "You are a senior M&A analyst at a top-tier investment bank. "
            "Your job is to identify realistic, specific global acquirers for a company being positioned for sale. "
            "You apply rigorous buy-side logic — who would strategically benefit from owning this asset and why now.\n\n"
            + _MA_RATIONALE_FRAMEWORK
            + "\n\n" + _LIVE_SIGNALS_CONTEXT
        )
        user_msg = (
            f"SELLER / ASSET PROFILE:\n"
            f"  Name: {anchor_name} ({anchor_ticker})\n"
            f"  Sector: {anchor_sector} | Industry: {anchor_industry}\n"
            f"  Jurisdiction: {anchor_jurisdiction} | Listing: {anchor_listing}\n"
            f"  Revenue: {rev_b} | Enterprise Value: {ev_b} | Market Cap: {mc_b} | EBITDA Margin: {margin_str}\n"
            f"  Key products/services: {products_str}\n"
            f"  Geographic markets: {markets_str}\n"
            f"  Strategic priorities: {priorities_str}\n"
            f"  Description: {anchor_description}\n"
            f"  Process Objective: {strategy_hint or 'maximize_price'}\n\n"
            f"TASK: Identify {limit} specific, real potential acquirers for {anchor_name}.\n\n"
            f"STRICT RULES:\n"
            f"  1. Include a mix: large strategic corporates, mid-market PE sponsors, cross-sector conglomerates.\n"
            f"  2. Diversify globally — at least 4 different jurisdictions.\n"
            f"  3. If objective is maximize_price, prioritise strategic buyers with highest synergy potential.\n"
            f"  4. Classify each acquirer's rationale using the M&A framework categories above.\n"
            f"  5. REAL COMPANIES ONLY — no fictional entities.\n"
            f"  6. DO NOT include {anchor_name} itself.\n"
            f"  7. Include 2 non-obvious potential acquirers from adjacent sectors — set is_non_obvious=true "
            f"     and provide a non_obvious_bridge explaining the strategic logic.\n"
            f"  8. WHY NOW: Use the macro signals above to give specific current triggers.\n"
            f"  9. PRECEDENT DEALS: For each acquirer, cite 1 real comparable deal that validates their M&A appetite.\n\n"
            f"Return ONLY valid JSON:\n"
            f"{{\"candidates\": [\n"
            f"  {{\"legal_name\": \"str\", \"display_name\": \"str\", \"ticker\": \"str or null\",\n"
            f"   \"jurisdiction\": \"ISO2 code\", \"listing_status\": \"public|private|pe_backed\",\n"
            f"   \"sector\": \"str\", \"rationale\": \"1-2 sentence acquisition rationale\",\n"
            f"   \"rationale_category\": \"one of the 8 categories above\",\n"
            f"   \"why_now\": \"specific current trigger (use macro signals)\",\n"
            f"   \"estimated_synergy_value_usd_m\": number_or_null,\n"
            f"   \"is_non_obvious\": true_or_false,\n"
            f"   \"non_obvious_bridge\": \"cross-sector strategic logic (only if is_non_obvious=true)\",\n"
            f"   \"precedent_deals\": \"Acquirer / Target (Year, ~Xx EBITDA) — rationale\"}}\n"
            f"]}}"
        )

    try:
        # Use web search model for live M&A intelligence
        full_prompt = f"{system_msg}\n\n{user_msg}"
        response = await _get_openai().responses.create(
            model="gpt-4o-mini-search-preview",
            tools=[{"type": "web_search_preview"}],
            input=full_prompt,
        )
        raw = ""
        for block in response.output:
            if hasattr(block, "content"):
                for chunk in block.content:
                    if hasattr(chunk, "text"):
                        raw += chunk.text
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()
        data = json.loads(raw)
        candidates = data.get("candidates", [])
        if not candidates and isinstance(data, dict):
            candidates = next((v for v in data.values() if isinstance(v, list)), [])
    except Exception as e:
        logger.warning("SEED CANDIDATES: web-search GPT failed (%s), falling back to plain gpt-4o-mini", e)
        # Fallback to plain gpt-4o-mini without web search
        try:
            fb = await _get_openai().chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0.25,
                max_tokens=3000,
                response_format={"type": "json_object"},
            )
            data = json.loads(fb.choices[0].message.content)
            candidates = data.get("candidates", [])
            if not candidates and isinstance(data, dict):
                candidates = next((v for v in data.values() if isinstance(v, list)), [])
        except Exception as e2:
            logger.error("SEED CANDIDATES: both GPT attempts failed for mode=%s. Error: %s", mode, e2, exc_info=True)
            return []

    if not candidates:
        return []

    # Store rationale metadata keyed by legal_name for later attachment
    _candidate_meta: dict[str, dict] = {}
    for c in candidates:
        name_key = (c.get("legal_name") or "").lower().strip()
        if name_key:
            _candidate_meta[name_key] = {
                "rationale_category": c.get("rationale_category") or "",
                "why_now": c.get("why_now") or "",
                "estimated_synergy_value_usd_m": c.get("estimated_synergy_value_usd_m"),
                "seeded_rationale": c.get("rationale") or "",
                "is_non_obvious": bool(c.get("is_non_obvious")),
                "non_obvious_bridge": c.get("non_obvious_bridge") or "",
                "precedent_deals": c.get("precedent_deals") or "",
            }

    seeded_ids: list[str] = []
    seed_sem = asyncio.Semaphore(6)  # cap concurrent enrichment calls

    # Use provided session_factory (NullPool from Celery) or fall back to web-tier pool
    _SessionFactory = session_factory if session_factory is not None else AsyncSessionLocal

    async def _resolve_and_enrich(c: dict) -> str | None:
        """Resolve + enrich one candidate. Each gets its own DB session."""
        if not c.get("legal_name"):
            return None
        async with seed_sem:
            try:
                async with _SessionFactory() as db:
                    # Check if already in DB (by ticker or name match)
                    ticker = c.get("ticker")
                    existing = None
                    if ticker:
                        r = await db.execute(select(Company).where(Company.ticker == ticker.upper()))
                        existing = r.scalar_one_or_none()
                    if not existing:
                        r = await db.execute(
                            select(Company).where(Company.legal_name.ilike(c["legal_name"]))
                        )
                        existing = r.scalar_one_or_none()

                    if existing:
                        company_id = existing.company_id
                        # Check if already enriched
                        pr = await db.execute(
                            select(EnrichmentProfile).where(EnrichmentProfile.company_id == company_id)
                        )
                        prof = pr.scalar_one_or_none()
                        if not (prof and prof.last_enriched_at):
                            await run_enrichment_pipeline(company_id, db)
                    else:
                        company_id = await _create_canonical_record(db, c)
                        await run_enrichment_pipeline(company_id, db)

                    return company_id
            except Exception as e:
                logger.error("RESOLVE+ENRICH failed for candidate '%s': %s",
                             c.get("legal_name"), e, exc_info=True)
                return None

    # Run all candidates concurrently (up to semaphore limit)
    results = await asyncio.gather(*[_resolve_and_enrich(c) for c in candidates[:limit]])
    seeded_ids = [cid for cid in results if cid]

    # Attach metadata to each seeded_id so load function can pass it to scoring
    # We use a module-level dict keyed by company_id → metadata
    # (populated after resolve so we know company_ids)
    for c, cid in zip(candidates[:limit], [cid for cid in results]):
        if cid:
            name_key = (c.get("legal_name") or "").lower().strip()
            meta = _candidate_meta.get(name_key, {})
            if meta:
                _seeded_meta[cid] = meta

    return seeded_ids


# ---------------------------------------------------------------------------
# Core pipeline functions (called by Celery tasks, not directly by HTTP handlers)
# ---------------------------------------------------------------------------

async def _run_buy_side_pipeline(payload: dict, session_factory=None) -> dict:
    """
    Full buy-side discovery: seed → enrich → gate → score → narrate.
    Called from Celery task so no HTTP timeout applies.

    session_factory: async_sessionmaker instance. When called from Celery, pass a
    NullPool factory (created by make_task_session_factory()) to avoid asyncpg connection
    reuse across destroyed event loops. Defaults to the web-tier AsyncSessionLocal.
    """
    global _seeded_meta
    _seeded_meta = {}  # Clear cross-run contamination at the start of every pipeline run
    logger.info("_seeded_meta cleared for new buy-side run")

    t_start = datetime.now(timezone.utc)
    buyer_company_id = payload["buyer_company_id"]
    strategy_mode = payload.get("strategy_mode", "capability_bolt_on")
    limit = payload.get("limit", 50)
    filters_data = payload.get("filters", {})
    filters = DiscoveryFilters(**filters_data)

    _SessionFactory = session_factory if session_factory is not None else AsyncSessionLocal

    logger.info("BUY-SIDE PIPELINE START | buyer=%s strategy=%s session_factory=%s",
                buyer_company_id, strategy_mode,
                "NullPool(task)" if session_factory is not None else "SharedPool(web)")

    async with _SessionFactory() as db:
        buyer_profile = await _load_profile(buyer_company_id, db)
        if not buyer_profile:
            return {"error": f"Buyer '{buyer_company_id}' not found"}

        logger.info("Buyer loaded: %s (%s)", buyer_profile.get("display_name"), buyer_profile.get("sector"))

        # Seed relevant target companies from GPT
        seeded_ids = await _seed_candidates(
            buyer_profile, "buy_side",
            limit=max(limit, 20),
            strategy_hint=strategy_mode,
            session_factory=_SessionFactory,
        )
        logger.info("GPT seeded %d candidates for buyer %s", len(seeded_ids), buyer_company_id)

        candidates = await _load_all_enriched_profiles(
            buyer_company_id, filters, db,
            company_ids=seeded_ids if seeded_ids else None,
        )
        logger.info("Loaded %d enriched candidate profiles", len(candidates))

    if not candidates:
        logger.warning("No candidates after seeding+load for buyer %s", buyer_company_id)
        return _empty_buy_side_response(buyer_company_id, strategy_mode, t_start)

    # Hard gate pass — O(n), no AI
    survivors = []
    excluded = []
    for target in candidates:
        gate = _quick_gate_check(buyer_profile, target, strategy_mode)
        if gate:
            excluded.append({
                "target_company_id": target["company_id"],
                "target_display_name": target.get("display_name"),
                "hard_gate": gate,
            })
        else:
            survivors.append(target)

    logger.info("After hard gates: %d survivors, %d excluded", len(survivors), len(excluded))

    # Score survivors concurrently
    semaphore = asyncio.Semaphore(_SCORE_SEMAPHORE_LIMIT)

    async def _score_one(target: dict) -> dict:
        async with semaphore:
            logger.info("Scoring target: %s", target.get("display_name"))
            return await score_target(buyer_profile, target, strategy_mode, generate_narration=False)

    scored_raw = list(await asyncio.gather(*[_score_one(t) for t in survivors]))
    scored_raw.sort(key=lambda x: x.get("deal_score", 0), reverse=True)

    logger.info("Scored %d targets. Top score: %.1f", len(scored_raw), scored_raw[0].get("deal_score", 0) if scored_raw else 0)

    # Generate narrations for top N
    top_ids = {r["target_company_id"] for r in scored_raw[:_NARRATE_TOP_N]}
    narration_tasks = []
    for i, result in enumerate(scored_raw):
        if result["target_company_id"] in top_ids:
            target = next(t for t in survivors if t["company_id"] == result["target_company_id"])
            narration_tasks.append((i, target))

    async def _narrate(idx: int, target: dict):
        async with semaphore:
            narrated = await score_target(buyer_profile, target, strategy_mode, generate_narration=True)
            scored_raw[idx]["rationale"] = narrated.get("rationale", "")

    await asyncio.gather(*[_narrate(i, t) for i, t in narration_tasks])

    # Inject seeded metadata
    for r in scored_raw:
        cid = r.get("target_company_id")
        if cid and cid in _seeded_meta:
            meta = _seeded_meta[cid]
            r.setdefault("rationale_category", meta.get("rationale_category") or "")
            r.setdefault("why_now", meta.get("why_now") or "")
            r.setdefault("estimated_synergy_value_usd_m", meta.get("estimated_synergy_value_usd_m"))
            r.setdefault("is_non_obvious", meta.get("is_non_obvious", False))
            r.setdefault("non_obvious_bridge", meta.get("non_obvious_bridge") or "")
            r.setdefault("precedent_deals", meta.get("precedent_deals") or "")
            if not r.get("rationale") and meta.get("seeded_rationale"):
                r["rationale"] = meta["seeded_rationale"]

    min_score = filters.min_deal_score or 0
    final = [r for r in scored_raw if r.get("deal_score", 0) >= min_score]
    final = final[:limit]

    tier_counts = {"Tier 1": 0, "Tier 2": 0, "Tier 3": 0, "Excluded": 0}
    for r in scored_raw:
        k = r.get("tier", "Tier 3")
        tier_counts[k] = tier_counts.get(k, 0) + 1

    elapsed_ms = int((datetime.now(timezone.utc) - t_start).total_seconds() * 1000)
    logger.info("BUY-SIDE PIPELINE DONE | buyer=%s results=%d elapsed=%dms", buyer_company_id, len(final), elapsed_ms)

    return {
        "buyer_company_id": buyer_company_id,
        "strategy_mode": strategy_mode,
        "summary": {
            "total_scanned": len(candidates),
            "total_gated": len(excluded),
            "total_scored": len(scored_raw),
            "tier_1_count": tier_counts.get("Tier 1", 0),
            "tier_2_count": tier_counts.get("Tier 2", 0),
            "tier_3_count": tier_counts.get("Tier 3", 0),
            "excluded_count": len(excluded),
        },
        "targets": final,
        "excluded_targets": excluded,
        "computation_time_ms": elapsed_ms,
        "generated_at": t_start.isoformat(),
    }


async def _run_sell_side_pipeline(payload: dict, session_factory=None) -> dict:
    """
    Full sell-side discovery: seed → enrich → gate → score → narrate → process arch.
    Called from Celery task so no HTTP timeout applies.

    session_factory: NullPool factory from Celery tasks; defaults to web-tier AsyncSessionLocal.
    """
    global _seeded_meta
    _seeded_meta = {}  # Clear cross-run contamination at the start of every pipeline run
    logger.info("_seeded_meta cleared for new sell-side run")

    t_start = datetime.now(timezone.utc)
    seller_company_id = payload["seller_company_id"]
    process_objective = payload.get("process_objective", "maximize_price")
    limit = payload.get("limit", 25)
    filters_data = payload.get("filters", {})
    filters = DiscoveryFilters(**filters_data)

    _SessionFactory = session_factory if session_factory is not None else AsyncSessionLocal

    logger.info("SELL-SIDE PIPELINE START | seller=%s objective=%s session_factory=%s",
                seller_company_id, process_objective,
                "NullPool(task)" if session_factory is not None else "SharedPool(web)")

    async with _SessionFactory() as db:
        seller_profile = await _load_profile(seller_company_id, db)
        if not seller_profile:
            return {"error": f"Seller '{seller_company_id}' not found"}

        logger.info("Seller loaded: %s (%s)", seller_profile.get("display_name"), seller_profile.get("sector"))

        seeded_ids = await _seed_candidates(
            seller_profile, "sell_side",
            limit=max(limit, 20),
            strategy_hint=process_objective,
            session_factory=_SessionFactory,
        )
        logger.info("GPT seeded %d buyer candidates for seller %s", len(seeded_ids), seller_company_id)

        candidates = await _load_all_enriched_profiles(
            seller_company_id, filters, db,
            company_ids=seeded_ids if seeded_ids else None,
        )
        logger.info("Loaded %d enriched buyer profiles", len(candidates))

    if not candidates:
        logger.warning("No candidates after seeding+load for seller %s", seller_company_id)
        return _empty_sell_side_response(seller_company_id, process_objective, t_start)

    survivors = []
    excluded = []
    for buyer in candidates:
        gate = _quick_gate_check(buyer, seller_profile, "sell_side")
        if gate:
            excluded.append({
                "buyer_company_id": buyer["company_id"],
                "buyer_display_name": buyer.get("display_name"),
                "hard_gate": gate,
            })
        else:
            survivors.append(buyer)

    logger.info("After hard gates: %d survivors, %d excluded", len(survivors), len(excluded))

    semaphore = asyncio.Semaphore(_SCORE_SEMAPHORE_LIMIT)

    async def _score_one(buyer: dict) -> dict:
        async with semaphore:
            logger.info("Scoring buyer: %s", buyer.get("display_name"))
            return await score_buyer(seller_profile, buyer, process_objective, generate_narration=False)

    scored_raw = list(await asyncio.gather(*[_score_one(b) for b in survivors]))
    scored_raw.sort(key=lambda x: x.get("deal_score", 0), reverse=True)

    logger.info("Scored %d buyers. Top score: %.1f", len(scored_raw), scored_raw[0].get("deal_score", 0) if scored_raw else 0)

    top_ids = {r["buyer_company_id"] for r in scored_raw[:_NARRATE_TOP_N]}
    narration_tasks = []
    for i, result in enumerate(scored_raw):
        if result["buyer_company_id"] in top_ids:
            buyer = next(b for b in survivors if b["company_id"] == result["buyer_company_id"])
            narration_tasks.append((i, buyer))

    async def _narrate(idx: int, buyer: dict):
        async with semaphore:
            narrated = await score_buyer(seller_profile, buyer, process_objective, generate_narration=True)
            scored_raw[idx]["rationale"] = narrated.get("rationale", "")

    await asyncio.gather(*[_narrate(i, b) for i, b in narration_tasks])

    for r in scored_raw:
        cid = r.get("buyer_company_id")
        if cid and cid in _seeded_meta:
            meta = _seeded_meta[cid]
            r.setdefault("rationale_category", meta.get("rationale_category") or "")
            r.setdefault("why_now", meta.get("why_now") or "")
            r.setdefault("estimated_synergy_value_usd_m", meta.get("estimated_synergy_value_usd_m"))
            r.setdefault("is_non_obvious", meta.get("is_non_obvious", False))
            r.setdefault("non_obvious_bridge", meta.get("non_obvious_bridge") or "")
            r.setdefault("precedent_deals", meta.get("precedent_deals") or "")
            if not r.get("rationale") and meta.get("seeded_rationale"):
                r["rationale"] = meta["seeded_rationale"]

    min_score = filters.min_deal_score or 0
    final = [r for r in scored_raw if r.get("deal_score", 0) >= min_score]
    final = final[:limit]

    process_arch: dict[str, list[str]] = {
        "must_contact_strategic": [], "price_anchors": [], "certainty_anchors": [],
        "tension_creators": [], "sponsor_floor": [], "do_not_approach": [],
    }
    role_map = {
        "must_contact_strategic": "must_contact_strategic",
        "price_anchor": "price_anchors",
        "certainty_anchor": "certainty_anchors",
        "tension_creator": "tension_creators",
        "sponsor_floor": "sponsor_floor",
        "do_not_approach": "do_not_approach",
    }
    for r in final:
        role = r.get("process_role", "tension_creator")
        key = role_map.get(role, "tension_creators")
        name = r.get("buyer_display_name") or r.get("buyer_company_id")
        process_arch[key].append(name)

    elapsed_ms = int((datetime.now(timezone.utc) - t_start).total_seconds() * 1000)
    logger.info("SELL-SIDE PIPELINE DONE | seller=%s results=%d elapsed=%dms", seller_company_id, len(final), elapsed_ms)

    ev_usd = seller_profile.get("financials", {}).get("enterprise_value_usd") or 0
    ev_b = round(ev_usd / 1e9, 1) if ev_usd else None

    return {
        "seller_name": seller_profile.get("display_name") or seller_profile.get("legal_name"),
        "seller_company_id": seller_company_id,
        "seller_context": {
            "enterprise_value_usd_b": ev_b,
            "process_objective": process_objective,
            "target_valuation_range_low_b": round(ev_b * 0.9, 1) if ev_b else None,
            "target_valuation_range_high_b": round(ev_b * 1.1, 1) if ev_b else None,
            "process_stage": "Discovery Phase",
        },
        "process_objective": process_objective,
        "summary": {
            "total_scanned": len(candidates),
            "total_gated": len(excluded),
            "total_scored": len(scored_raw),
            "tier_1_count": sum(1 for r in scored_raw if r.get("tier") == "Tier 1"),
            "tier_2_count": sum(1 for r in scored_raw if r.get("tier") == "Tier 2"),
            "tier_3_count": sum(1 for r in scored_raw if r.get("tier") == "Tier 3"),
        },
        "buyers": final,
        "process_architecture": process_arch,
        "excluded_buyers": excluded,
        "computation_time_ms": elapsed_ms,
        "generated_at": t_start.isoformat(),
    }


# ---------------------------------------------------------------------------
# HTTP endpoints — queue task + return job_id immediately
# ---------------------------------------------------------------------------

@router.post("/buy-side")
async def run_buy_side_discovery(
    request: BuySideRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Queues the buy-side discovery pipeline as a Celery background task.
    Returns job_id immediately. Poll GET /v1/discovery/job/{job_id} for results.
    """
    # Verify buyer exists before queuing
    buyer_profile = await _load_profile(request.buyer_company_id, db)
    if not buyer_profile:
        raise HTTPException(status_code=404, detail=f"Buyer '{request.buyer_company_id}' not found")

    payload = {
        "buyer_company_id": request.buyer_company_id,
        "strategy_mode": request.strategy_mode,
        "filters": request.filters.model_dump(),
        "limit": request.limit,
    }

    from workers.tasks import run_buy_side_discovery as _celery_task
    task = _celery_task.delay(payload)
    logger.info("Queued buy-side discovery job %s for buyer %s", task.id, request.buyer_company_id)

    return {
        "job_id": task.id,
        "status": "queued",
        "buyer_company_id": request.buyer_company_id,
        "strategy_mode": request.strategy_mode,
        "message": "Discovery pipeline queued. Poll /v1/discovery/job/{job_id} every 3s for results.",
    }


@router.post("/sell-side")
async def run_sell_side_discovery(
    request: SellSideRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Queues the sell-side discovery pipeline as a Celery background task.
    Returns job_id immediately. Poll GET /v1/discovery/job/{job_id} for results.
    """
    seller_profile = await _load_profile(request.seller_company_id, db)
    if not seller_profile:
        raise HTTPException(status_code=404, detail=f"Seller '{request.seller_company_id}' not found")

    payload = {
        "seller_company_id": request.seller_company_id,
        "process_objective": request.process_objective,
        "filters": request.filters.model_dump(),
        "limit": request.limit,
    }

    from workers.tasks import run_sell_side_discovery as _celery_task
    task = _celery_task.delay(payload)
    logger.info("Queued sell-side discovery job %s for seller %s", task.id, request.seller_company_id)

    return {
        "job_id": task.id,
        "status": "queued",
        "seller_company_id": request.seller_company_id,
        "process_objective": request.process_objective,
        "message": "Discovery pipeline queued. Poll /v1/discovery/job/{job_id} every 3s for results.",
    }


@router.get("/job/{job_id}")
async def get_discovery_job_status(job_id: str):
    """
    Poll this endpoint every 3s after starting a discovery run.
    Returns {"status": "queued"|"running"|"complete"|"failed", "result": {...}}
    """
    from celery.result import AsyncResult
    from workers.celery_app import celery_app

    task = AsyncResult(job_id, app=celery_app)
    state = task.state  # PENDING, STARTED, SUCCESS, FAILURE, RETRY

    if state == "SUCCESS":
        result = task.result
        if isinstance(result, dict) and "error" in result:
            return {"status": "failed", "error": result["error"]}
        return {"status": "complete", "result": result}
    elif state == "FAILURE":
        return {"status": "failed", "error": str(task.result)}
    elif state in ("STARTED", "RETRY"):
        return {"status": "running"}
    else:
        # PENDING = queued or unknown
        return {"status": "queued"}


# ---------------------------------------------------------------------------
# Empty response helpers
# ---------------------------------------------------------------------------

def _empty_buy_side_response(buyer_id: str, strategy_mode: str, t_start: datetime) -> dict:
    return {
        "buyer_company_id": buyer_id,
        "strategy_mode": strategy_mode,
        "summary": {
            "total_scanned": 0, "total_gated": 0, "total_scored": 0,
            "tier_1_count": 0, "tier_2_count": 0, "tier_3_count": 0, "excluded_count": 0,
        },
        "targets": [],
        "excluded_targets": [],
        "computation_time_ms": 0,
        "generated_at": t_start.isoformat(),
    }


def _empty_sell_side_response(seller_id: str, process_objective: str, t_start: datetime) -> dict:
    return {
        "seller_company_id": seller_id,
        "process_objective": process_objective,
        "summary": {
            "total_scanned": 0, "total_gated": 0, "total_scored": 0,
            "tier_1_count": 0, "tier_2_count": 0, "tier_3_count": 0,
        },
        "buyers": [],
        "process_architecture": {
            "must_contact_strategic": [], "price_anchors": [],
            "certainty_anchors": [], "tension_creators": [],
            "sponsor_floor": [], "do_not_approach": [],
        },
        "excluded_buyers": [],
        "computation_time_ms": 0,
        "generated_at": t_start.isoformat(),
    }
