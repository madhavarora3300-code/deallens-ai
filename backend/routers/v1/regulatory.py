"""
Regulatory Lens — GPT-4o-mini antitrust + regulatory clearance analysis.

Returns a per-jurisdiction risk map, clearance probability, recommended actions,
and precedent deals. All deterministic rules applied first; GPT fills narrative gaps.
"""
import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from openai import AsyncOpenAI

from core.config import settings
from core.database import get_db
from models.database_models import Company, EnrichmentProfile, RegulatoryPrediction

router = APIRouter(tags=["regulatory"])

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _client


# ---------------------------------------------------------------------------
# Deterministic jurisdiction rules
# ---------------------------------------------------------------------------

# (buyer_j, target_j) → list of authorities that will review
_JURISDICTION_AUTHORITIES = {
    ("US", "US"): ["DOJ Antitrust Division", "FTC"],
    ("US", "CN"): ["DOJ", "FTC", "CFIUS", "MOFCOM"],
    ("CN", "US"): ["MOFCOM", "SAMR", "CFIUS"],
    ("GB", "GB"): ["CMA"],
    ("DE", "DE"): ["Bundeskartellamt"],
    ("EU", "EU"): ["European Commission DG COMP"],
    ("IN", "IN"): ["CCI (Competition Commission of India)"],
    ("IN", "US"): ["CCI", "DOJ/FTC"],
    ("US", "IN"): ["DOJ/FTC", "CCI"],
    ("AU", "AU"): ["ACCC"],
    ("JP", "JP"): ["JFTC"],
}

_DEFAULT_AUTHORITIES_BY_JURISDICTION = {
    "US": ["DOJ Antitrust Division", "FTC"],
    "CN": ["SAMR", "MOFCOM"],
    "GB": ["CMA"],
    "DE": ["Bundeskartellamt"],
    "IN": ["CCI"],
    "AU": ["ACCC"],
    "JP": ["JFTC"],
    "FR": ["Autorité de la concurrence"],
    "IT": ["AGCM"],
    "BR": ["CADE"],
    "KR": ["KFTC"],
    "CA": ["Competition Bureau Canada"],
    "ZA": ["Competition Commission South Africa"],
    "SG": ["CCCS"],
}

# Deal size thresholds triggering mandatory filings (USD billions)
_FILING_THRESHOLDS = {
    "US": 0.1,   # HSR threshold ~$111M (2024)
    "EU": 0.25,  # EC notification threshold simplified
    "GB": 0.07,
    "DE": 0.07,
    "IN": 0.2,
    "CN": 0.5,
    "AU": 0.1,
    "JP": 0.2,
    "BR": 0.1,
    "CA": 0.1,
}

# High-scrutiny sector pairs (buyer_sector, target_sector) → additional risk
_HIGH_SCRUTINY_HORIZONTALS = {
    ("Technology", "Technology"),
    ("Healthcare", "Healthcare"),
    ("Pharmaceuticals", "Pharmaceuticals"),
    ("Financials", "Financials"),
    ("Telecom", "Telecom"),
    ("Media", "Media"),
    ("Defense", "Defense"),
}

_REGULATORY_PROMPT = """You are an M&A regulatory specialist. Analyse the antitrust and regulatory clearance outlook for this deal.

Return ONLY valid JSON. No markdown. Be specific to the actual companies and sectors involved.

Required structure:
{
  "overall_risk": "LOW|MEDIUM|HIGH|VERY_HIGH",
  "combined_market_share_pct": number or null,
  "hhi_delta_estimate": number or null,
  "primary_concerns": ["string", ...],
  "jurisdictions_flagged": ["ISO2", ...],
  "likely_remedies": ["string", ...],
  "expected_timeline_months": integer,
  "clearance_probability_pct": integer,
  "precedent_deals": [
    {"deal": "string", "year": integer, "outcome": "cleared|cleared_with_remedies|blocked"}
  ],
  "recommended_actions": ["string", ...],
  "rationale": "2-3 sentences summarising the regulatory outlook",
  "confidence": integer
}

Rules:
- combined_market_share_pct: only if you can reasonably estimate; else null
- hhi_delta_estimate: Herfindahl–Hirschman Index change; null if insufficient data
- precedent_deals: real deals only, max 3
- Be conservative: default to MEDIUM risk for cross-border deals > $1B
"""


class RegulatoryRequest(BaseModel):
    company_a_id: str
    company_b_id: str
    deal_size_usd_b: float
    deal_type: str = "acquisition"


@router.post("/predict")
async def predict_regulatory(
    request: RegulatoryRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Full regulatory clearance analysis for any two-company deal pair.
    GPT-4o-mini analyses antitrust risk; deterministic rules populate filing requirements.
    Saves result to DB.
    """
    if request.deal_size_usd_b <= 0:
        raise HTTPException(status_code=400, detail="deal_size_usd_b must be positive")

    # Load both companies
    async def _load(cid: str) -> tuple[Company, EnrichmentProfile | None]:
        r = await db.execute(select(Company).where(Company.company_id == cid))
        c = r.scalar_one_or_none()
        if not c:
            raise HTTPException(status_code=404, detail=f"Company '{cid}' not found")
        pr = await db.execute(select(EnrichmentProfile).where(EnrichmentProfile.company_id == cid))
        p = pr.scalar_one_or_none()
        return c, p

    company_a, profile_a = await _load(request.company_a_id)
    company_b, profile_b = await _load(request.company_b_id)

    j_a = (company_a.jurisdiction or "").upper()
    j_b = (company_b.jurisdiction or "").upper()
    s_a = company_a.sector or ""
    s_b = company_b.sector or ""

    # Deterministic authority list
    authority_key = (j_a, j_b)
    authorities = list(_JURISDICTION_AUTHORITIES.get(authority_key, []))
    for j in {j_a, j_b}:
        for auth in _DEFAULT_AUTHORITIES_BY_JURISDICTION.get(j, []):
            if auth not in authorities:
                authorities.append(auth)

    # Filing threshold check
    filing_required = []
    for j in {j_a, j_b}:
        threshold = _FILING_THRESHOLDS.get(j)
        if threshold and request.deal_size_usd_b >= threshold:
            filing_required.append(j)

    # Build GPT context
    def _company_summary(c: Company, p: EnrichmentProfile | None) -> str:
        parts = [f"{c.legal_name} ({c.sector or 'unknown sector'}, {c.jurisdiction or 'unknown jurisdiction'})"]
        if p:
            if p.revenue_usd:
                parts.append(f"Revenue: ${p.revenue_usd/1e9:.1f}B")
            if p.enterprise_value_usd:
                parts.append(f"EV: ${p.enterprise_value_usd/1e9:.1f}B")
            if p.key_products:
                parts.append(f"Products: {', '.join(p.key_products[:3])}")
            if p.geographic_markets:
                parts.append(f"Markets: {', '.join(p.geographic_markets[:5])}")
        return " | ".join(parts)

    user_msg = (
        f"Company A (acquirer): {_company_summary(company_a, profile_a)}\n"
        f"Company B (target): {_company_summary(company_b, profile_b)}\n"
        f"Deal size: ${request.deal_size_usd_b:.1f}B {request.deal_type}\n"
        f"Cross-border: {j_a != j_b}\n"
        f"Horizontal deal: {s_a == s_b and bool(s_a)}\n"
        f"Regulatory authorities involved: {', '.join(authorities)}"
    )

    # GPT analysis
    gpt = {}
    try:
        resp = await _get_client().chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": _REGULATORY_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.1,
            max_tokens=800,
            response_format={"type": "json_object"},
        )
        gpt = json.loads(resp.choices[0].message.content)
    except Exception:
        pass

    overall_risk = gpt.get("overall_risk", "MEDIUM")
    risk_score = {"LOW": 25, "MEDIUM": 50, "HIGH": 75, "VERY_HIGH": 95}.get(overall_risk, 50)

    # Boost risk score for high-scrutiny horizontals
    if (s_a, s_b) in _HIGH_SCRUTINY_HORIZONTALS or (s_b, s_a) in _HIGH_SCRUTINY_HORIZONTALS:
        risk_score = min(100, risk_score + 10)

    clearance_prob = gpt.get("clearance_probability_pct", max(10, 95 - risk_score))

    generated_at = datetime.now(timezone.utc)

    # Persist to DB
    pred = RegulatoryPrediction(
        prediction_id=f"reg_{uuid.uuid4().hex[:12]}",
        buyer_company_id=request.company_a_id,
        target_company_id=request.company_b_id,
        overall_risk=overall_risk,
        combined_market_share=gpt.get("combined_market_share_pct"),
        hhi_delta=gpt.get("hhi_delta_estimate"),
        jurisdictions_flagged=gpt.get("jurisdictions_flagged", list({j_a, j_b})),
        likely_remedies=gpt.get("likely_remedies", []),
        expected_timeline_months=gpt.get("expected_timeline_months", 6),
        clearance_probability=clearance_prob / 100,
        rationale=gpt.get("rationale", ""),
        sources=["openai_knowledge"],
        confidence_score=gpt.get("confidence", 60),
    )
    db.add(pred)
    await db.commit()

    return {
        "prediction_id": pred.prediction_id,
        "company_a_id": request.company_a_id,
        "company_a_name": company_a.display_name or company_a.legal_name,
        "company_b_id": request.company_b_id,
        "company_b_name": company_b.display_name or company_b.legal_name,
        "deal_size_usd_b": request.deal_size_usd_b,
        "deal_type": request.deal_type,
        "overall_risk": overall_risk,
        "jurisdictional_risk_score": risk_score,
        "risk_label": overall_risk.replace("_", " "),
        "authorities": authorities,
        "filing_required_jurisdictions": filing_required,
        "combined_market_share_pct": gpt.get("combined_market_share_pct"),
        "hhi_delta_estimate": gpt.get("hhi_delta_estimate"),
        "primary_concerns": gpt.get("primary_concerns", []),
        "jurisdictions_flagged": pred.jurisdictions_flagged,
        "likely_remedies": pred.likely_remedies,
        "expected_timeline_months": pred.expected_timeline_months,
        "overall_clearance_probability_pct": clearance_prob,
        "precedent_deals": gpt.get("precedent_deals", []),
        "recommended_actions": gpt.get("recommended_actions", []),
        "rationale": pred.rationale,
        "confidence_score": pred.confidence_score,
        "sources": ["openai_knowledge"],
        "missing_fields": [],
        "generated_at": generated_at.isoformat(),
    }
