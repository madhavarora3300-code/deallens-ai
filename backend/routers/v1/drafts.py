"""
Drafts router — GPT-4o-mini powered M&A document generation.

Supported document types:
  investment_thesis   — IC-ready investment thesis with bullets + risks
  teaser              — 1-page blind teaser for sell-side process
  cim_outline         — CIM chapter outline with key messages
  loi_points          — LOI key commercial terms summary
  board_memo_bullets  — Board memo bullet points
  synergy_analysis    — Revenue + cost synergy quantification
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
from models.database_models import Company, Draft, EnrichmentProfile

router = APIRouter(tags=["drafts"])

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _client


SUPPORTED_TYPES = {
    "investment_thesis", "teaser", "cim_outline",
    "loi_points", "board_memo_bullets", "synergy_analysis",
}

# ---------------------------------------------------------------------------
# System prompts per document type
# ---------------------------------------------------------------------------

_SYSTEM_PROMPTS = {
    "investment_thesis": """You are a senior M&A analyst writing an investment thesis for an Investment Committee.
Write in professional, direct language. Be specific — use actual company names, figures, and strategic rationale.
No boilerplate. Every bullet must add a specific insight.

Return ONLY valid JSON:
{
  "title": "string",
  "executive_summary": "2-3 sentence paragraph",
  "thesis_bullets": ["string (specific insight)", ...],
  "strategic_rationale": "paragraph",
  "financial_highlights": ["string", ...],
  "key_risks": ["string", ...],
  "why_now": "paragraph explaining timing",
  "why_not_now_risks": ["string", ...],
  "recommended_next_steps": ["string", ...]
}""",

    "teaser": """You are an M&A banker writing a blind teaser for a sell-side process.
Do NOT name the company. Describe the business in terms that attract buyers without identifying it.
Professional, punchy language. Highlight investment highlights and transaction rationale.

Return ONLY valid JSON:
{
  "title": "string (e.g. 'Project Apollo — Investment Overview')",
  "situation_overview": "paragraph",
  "investment_highlights": ["string", ...],
  "financial_snapshot": ["string (e.g. '$X revenue, XX% EBITDA margin')", ...],
  "transaction_rationale": "paragraph",
  "process_overview": "1-2 sentences on timeline/structure"
}""",

    "cim_outline": """You are an M&A banker structuring a Confidential Information Memorandum (CIM).
Create a detailed chapter outline with key messages per section.

Return ONLY valid JSON:
{
  "title": "string",
  "chapters": [
    {
      "chapter": "string",
      "key_messages": ["string", ...],
      "data_required": ["string", ...]
    }
  ]
}""",

    "loi_points": """You are an M&A lawyer summarising key commercial terms for a Letter of Intent.
Be specific about structure, price anchors, conditions, and protections.

Return ONLY valid JSON:
{
  "title": "string",
  "deal_structure": "string",
  "indicative_valuation": "string",
  "key_commercial_terms": ["string", ...],
  "conditions_precedent": ["string", ...],
  "exclusivity_period": "string",
  "key_protections": ["string", ...]
}""",

    "board_memo_bullets": """You are a CFO writing board memo bullet points to recommend an M&A transaction.
Crisp, executive-level language. Each bullet is a complete insight, not a heading.

Return ONLY valid JSON:
{
  "title": "string",
  "recommendation": "string (one sentence: Approve/Decline + reason)",
  "strategic_case": ["string", ...],
  "financial_case": ["string", ...],
  "risk_factors": ["string", ...],
  "decision_required": "string"
}""",

    "synergy_analysis": """You are an M&A integration specialist quantifying deal synergies.
Be specific. Cite revenue synergy sources and cost categories. Use ranges where uncertain.

Return ONLY valid JSON:
{
  "title": "string",
  "total_synergy_range_usd_m": {"low": number, "high": number},
  "revenue_synergies": [
    {"category": "string", "value_usd_m": number, "confidence": "HIGH|MEDIUM|LOW", "rationale": "string"}
  ],
  "cost_synergies": [
    {"category": "string", "value_usd_m": number, "confidence": "HIGH|MEDIUM|LOW", "rationale": "string"}
  ],
  "one_time_costs_usd_m": number,
  "synergy_realisation_years": integer,
  "key_risks": ["string", ...]
}""",
}


# ---------------------------------------------------------------------------
# Request / response
# ---------------------------------------------------------------------------

class DraftRequest(BaseModel):
    company_id: str
    counterparty_id: str | None = None
    draft_type: str = "investment_thesis"
    project_name: str | None = None


@router.post("/generate")
async def generate_draft(
    request: DraftRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Generate an M&A document using GPT-4o-mini from enriched company profiles.
    Saves draft to DB and returns structured content.
    """
    if request.draft_type not in SUPPORTED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"draft_type must be one of: {', '.join(sorted(SUPPORTED_TYPES))}",
        )

    # Load primary company
    r = await db.execute(select(Company).where(Company.company_id == request.company_id))
    company = r.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail=f"Company '{request.company_id}' not found")

    pr = await db.execute(
        select(EnrichmentProfile).where(EnrichmentProfile.company_id == request.company_id)
    )
    profile = pr.scalar_one_or_none()

    # Load counterparty if provided
    counterparty = None
    counterparty_profile = None
    if request.counterparty_id:
        cr = await db.execute(select(Company).where(Company.company_id == request.counterparty_id))
        counterparty = cr.scalar_one_or_none()
        if counterparty:
            cpr = await db.execute(
                select(EnrichmentProfile).where(EnrichmentProfile.company_id == request.counterparty_id)
            )
            counterparty_profile = cpr.scalar_one_or_none()

    # Build user message
    user_msg = _build_user_message(company, profile, counterparty, counterparty_profile, request)

    # Call GPT-4o-mini
    system_prompt = _SYSTEM_PROMPTS[request.draft_type]
    raw_content = {}
    prompt_tokens = 0
    completion_tokens = 0

    try:
        resp = await _get_client().chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.3,
            max_tokens=1500,
            response_format={"type": "json_object"},
        )
        raw_content = json.loads(resp.choices[0].message.content)
        prompt_tokens = resp.usage.prompt_tokens
        completion_tokens = resp.usage.completion_tokens
    except Exception:
        pass

    # Flatten to markdown for storage
    content_md = json.dumps(raw_content, indent=2)
    word_count = len(content_md.split())

    project_name = request.project_name or f"Project {company.display_name or company.legal_name}"
    draft_id = f"dft_{uuid.uuid4().hex[:12]}"
    generated_at = datetime.now(timezone.utc)

    # Persist draft
    draft = Draft(
        draft_id=draft_id,
        company_id=request.company_id,
        document_type=request.draft_type,
        title=raw_content.get("title", project_name),
        content_markdown=content_md,
        word_count=word_count,
        model_used="gpt-4o-mini",
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        generation_params={"draft_type": request.draft_type, "counterparty_id": request.counterparty_id},
    )
    db.add(draft)
    await db.commit()

    # Build response — surface the most useful fields at top level
    response = {
        "draft_id": draft_id,
        "draft_type": request.draft_type,
        "project_name": project_name,
        "company_id": request.company_id,
        "counterparty_id": request.counterparty_id,
        "word_count": word_count,
        "model_used": "gpt-4o-mini",
        "sources": ["openai_knowledge", "enrichment_profile"],
        "confidence_score": profile.confidence_score if profile else 0,
        "generated_at": generated_at.isoformat(),
    }
    response.update(raw_content)
    return response


@router.get("/{draft_id}")
async def get_draft(draft_id: str, db: AsyncSession = Depends(get_db)):
    """Retrieve a previously generated draft by ID."""
    r = await db.execute(select(Draft).where(Draft.draft_id == draft_id))
    draft = r.scalar_one_or_none()
    if not draft:
        raise HTTPException(status_code=404, detail=f"Draft '{draft_id}' not found")

    content = {}
    try:
        content = json.loads(draft.content_markdown or "{}")
    except Exception:
        pass

    return {
        "draft_id": draft.draft_id,
        "draft_type": draft.document_type,
        "company_id": draft.company_id,
        "title": draft.title,
        "word_count": draft.word_count,
        "model_used": draft.model_used,
        "created_at": draft.created_at.isoformat() if draft.created_at else None,
        **content,
    }


@router.get("")
async def list_drafts(
    company_id: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """List all drafts, optionally filtered by company_id."""
    stmt = select(Draft).order_by(Draft.created_at.desc()).limit(50)
    if company_id:
        stmt = stmt.where(Draft.company_id == company_id)
    r = await db.execute(stmt)
    drafts = r.scalars().all()
    return [
        {
            "draft_id": d.draft_id,
            "draft_type": d.document_type,
            "company_id": d.company_id,
            "title": d.title,
            "word_count": d.word_count,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        for d in drafts
    ]


# ---------------------------------------------------------------------------
# Context builder
# ---------------------------------------------------------------------------

def _build_user_message(
    company: Company,
    profile: EnrichmentProfile | None,
    counterparty: Company | None,
    counterparty_profile: EnrichmentProfile | None,
    request: DraftRequest,
) -> str:
    lines = [f"Primary company: {company.legal_name}"]
    if company.sector:
        lines.append(f"Sector: {company.sector}")
    if company.jurisdiction:
        lines.append(f"Jurisdiction: {company.jurisdiction}")
    if company.description:
        lines.append(f"Description: {company.description}")

    if profile:
        if profile.revenue_usd:
            lines.append(f"Revenue: ${profile.revenue_usd/1e9:.2f}B")
        if profile.ebitda_usd:
            lines.append(f"EBITDA: ${profile.ebitda_usd/1e9:.2f}B (margin: {profile.ebitda_margin or 'N/A'}%)")
        if profile.enterprise_value_usd:
            lines.append(f"Enterprise value: ${profile.enterprise_value_usd/1e9:.2f}B")
        if profile.ownership_structure:
            lines.append(f"Ownership: {profile.ownership_structure}")
        if profile.strategic_priorities:
            lines.append(f"Strategic priorities: {', '.join(profile.strategic_priorities[:4])}")
        if profile.key_products:
            lines.append(f"Key products: {', '.join(profile.key_products[:4])}")
        if profile.geographic_markets:
            lines.append(f"Markets: {', '.join(profile.geographic_markets[:6])}")
        if profile.m_and_a_appetite:
            lines.append(f"M&A appetite: {profile.m_and_a_appetite}")

    if counterparty:
        lines.append(f"\nCounterparty: {counterparty.legal_name}")
        if counterparty.sector:
            lines.append(f"Counterparty sector: {counterparty.sector}")
        if counterparty.description:
            lines.append(f"Counterparty description: {counterparty.description}")
        if counterparty_profile:
            if counterparty_profile.revenue_usd:
                lines.append(f"Counterparty revenue: ${counterparty_profile.revenue_usd/1e9:.2f}B")
            if counterparty_profile.enterprise_value_usd:
                lines.append(f"Counterparty EV: ${counterparty_profile.enterprise_value_usd/1e9:.2f}B")

    lines.append(f"\nDocument type: {request.draft_type}")
    if request.project_name:
        lines.append(f"Project name: {request.project_name}")

    return "\n".join(lines)
