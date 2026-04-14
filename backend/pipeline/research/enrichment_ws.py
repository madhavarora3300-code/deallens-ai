"""
Enrichment WebSocket Runner — streams step-by-step progress to a connected client.

Each pipeline step emits a step_complete message.
Sections emit section_ready when their data is available.
Completes with enrichment_complete or enrichment_error.
"""
import json
import time
from datetime import datetime, timezone

from fastapi import WebSocket
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import AsyncSessionLocal
from models.database_models import Company, EnrichmentProfile
from pipeline.research.company_researcher import fetch_basic_profile, research_company_deep
from pipeline.research.enrichment_service import (
    _apply_basic,
    _apply_deep,
    _compute_confidence,
    _compute_coverage_depth,
    _compute_missing_fields,
    _check_discovery_eligible,
)


async def _send(ws: WebSocket, payload: dict) -> bool:
    """Send JSON to WebSocket. Returns False if connection is closed."""
    try:
        await ws.send_json(payload)
        return True
    except Exception:
        return False


async def run_enrichment_with_stream(company_id: str, websocket: WebSocket) -> None:
    """
    Full two-pass enrichment pipeline that streams progress via WebSocket.

    Message sequence:
      step_complete  × N  (one per pipeline step)
      section_ready  × 2  (after basic pass + after deep pass)
      enrichment_complete  (final)
      enrichment_error     (on any fatal failure)
    """
    async with AsyncSessionLocal() as db:
        # --- Resolve company ---
        t0 = time.monotonic()
        stmt = select(Company).where(Company.company_id == company_id)
        result = await db.execute(stmt)
        company = result.scalar_one_or_none()

        if company is None:
            await _send(websocket, {
                "type": "enrichment_error",
                "step": "Resolving company identity",
                "error": f"Company {company_id} not found",
                "fallback": None,
                "confidence_impact": -100,
            })
            return

        await _send(websocket, {
            "type": "step_complete",
            "step": "Resolving company identity",
            "duration_ms": int((time.monotonic() - t0) * 1000),
            "overall_progress_pct": 10,
            "log_message": f"Resolved: {company.legal_name} ({company.jurisdiction})",
        })

        # --- Fetch or create enrichment profile ---
        profile_stmt = select(EnrichmentProfile).where(
            EnrichmentProfile.company_id == company_id
        )
        profile_result = await db.execute(profile_stmt)
        profile = profile_result.scalar_one_or_none()

        import uuid
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

        # --- Pass 1: Basic profile ---
        t1 = time.monotonic()
        await _send(websocket, {
            "type": "step_complete",
            "step": "Pulling latest public disclosures",
            "duration_ms": 0,
            "overall_progress_pct": 20,
            "log_message": f"Querying intelligence sources for {legal_name}...",
        })

        try:
            basic = await fetch_basic_profile(company_id, legal_name, jurisdiction)
        except Exception as e:
            basic = {}
            await _send(websocket, {
                "type": "enrichment_error",
                "step": "Pulling latest public disclosures",
                "error": str(e),
                "fallback": "Proceeding with partial data",
                "confidence_impact": -15,
            })

        basic_ms = int((time.monotonic() - t1) * 1000)
        _apply_basic(company, profile, basic)
        profile.coverage_depth = "BASIC"
        await db.commit()

        await _send(websocket, {
            "type": "step_complete",
            "step": "Reading annual report and filings",
            "duration_ms": basic_ms,
            "overall_progress_pct": 40,
            "log_message": (
                f"Extracted: revenue ${basic.get('revenue_usd', 0) or 0:,.0f}  "
                f"| EBITDA ${basic.get('ebitda_usd', 0) or 0:,.0f}"
                if basic.get("revenue_usd") else "Financial data not found — marked as null"
            ),
        })

        # Signal that financials section is ready
        await _send(websocket, {
            "type": "section_ready",
            "section": "financials",
            "data": {
                "revenue_usd": profile.revenue_usd,
                "ebitda_usd": profile.ebitda_usd,
                "enterprise_value_usd": profile.enterprise_value_usd,
                "market_cap_usd": profile.market_cap_usd,
            },
        })

        # --- Pass 2: Deep profile ---
        t2 = time.monotonic()
        await _send(websocket, {
            "type": "step_complete",
            "step": "Extracting ownership and control signals",
            "duration_ms": 0,
            "overall_progress_pct": 55,
            "log_message": "Tracing ownership structure and shareholder registry...",
        })

        try:
            deep = await research_company_deep(legal_name, jurisdiction, basic)
        except Exception as e:
            deep = {}
            await _send(websocket, {
                "type": "enrichment_error",
                "step": "Extracting ownership and control signals",
                "error": str(e),
                "fallback": "Ownership data unavailable — marked as null",
                "confidence_impact": -10,
            })

        deep_ms = int((time.monotonic() - t2) * 1000)
        _apply_deep(profile, deep)

        await _send(websocket, {
            "type": "step_complete",
            "step": "Scoring strategic fit and dealability",
            "duration_ms": deep_ms,
            "overall_progress_pct": 70,
            "log_message": (
                f"Ownership: {deep.get('ownership_structure', 'unknown')}  "
                f"| M&A appetite: {deep.get('m_and_a_appetite', 'unknown')}"
            ),
        })

        # Signal ownership section ready
        await _send(websocket, {
            "type": "section_ready",
            "section": "ownership",
            "data": {
                "ownership_structure": profile.ownership_structure,
                "controlling_shareholder": profile.controlling_shareholder,
                "controlling_stake_pct": profile.controlling_stake_pct,
            },
        })

        # --- Finalise scores ---
        profile.confidence_score = _compute_confidence(company, profile, basic, deep)
        profile.coverage_depth = _compute_coverage_depth(profile)
        profile.missing_fields = _compute_missing_fields(company, profile)
        profile.discovery_eligible = _check_discovery_eligible(company, profile)
        profile.last_enriched_at = datetime.now(timezone.utc)

        sources = []
        if basic.get("sources"):
            sources.extend(basic["sources"])
        if deep.get("sources"):
            sources.extend(deep["sources"])
        profile.sources = list(set(sources)) if sources else ["openai_knowledge"]

        await db.commit()

        await _send(websocket, {
            "type": "step_complete",
            "step": "Ranking candidates and validating confidence",
            "duration_ms": 50,
            "overall_progress_pct": 85,
            "log_message": f"Confidence score: {profile.confidence_score:.0f} | Coverage: {profile.coverage_depth}",
        })

        await _send(websocket, {
            "type": "step_complete",
            "step": "Building M&A-ready intelligence summary",
            "duration_ms": 30,
            "overall_progress_pct": 95,
            "log_message": f"Missing fields: {len(profile.missing_fields or [])} | Discovery eligible: {profile.discovery_eligible}",
        })

        # Signal strategic_features section ready
        await _send(websocket, {
            "type": "section_ready",
            "section": "strategic_features",
            "data": {
                "strategic_priorities": profile.strategic_priorities,
                "m_and_a_appetite": profile.m_and_a_appetite,
                "key_products": profile.key_products,
            },
        })

        # Final completion message
        await _send(websocket, {
            "type": "enrichment_complete",
            "coverage_depth": profile.coverage_depth,
            "confidence_score": profile.confidence_score,
            "discovery_eligible": profile.discovery_eligible,
            "missing_fields": profile.missing_fields or [],
        })
