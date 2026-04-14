"""
Company Researcher — GPT-4o-mini powered company intelligence extraction.

Two-pass design:
  Pass 1 (fast, ~3s): identity + basic financials + description → BASIC coverage
  Pass 2 (deep, ~8s): ownership + strategic features + M&A signals → DEEP coverage

All extracted data carries source attribution and confidence signals.
"""
import json

from openai import AsyncOpenAI

from core.config import settings

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _client


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

_BASIC_PROFILE_PROMPT = """You are an M&A intelligence analyst. Extract factual, publicly available information about the given company.

Return ONLY valid JSON. No markdown. No explanation.
Use null for any field you are not confident about. Never fabricate numbers.
All financial figures in USD (convert if needed). Revenue/EBITDA = most recent fiscal year you have reliable data for.
IMPORTANT: market_cap_usd and enterprise_value_usd should reflect the approximate figures from the most recent period in your training data — be conservative and note the year. Do NOT use current real-time prices.

Required JSON structure:
{
  "legal_name": "string",
  "display_name": "string",
  "ticker": "string or null",
  "isin": "string or null",
  "jurisdiction": "ISO2 country code",
  "listing_status": "public|private|subsidiary|spac|defunct",
  "sector": "string",
  "industry": "string",
  "employee_count": integer or null,
  "founded_year": integer or null,
  "hq_city": "string or null",
  "hq_country": "ISO2 country code",
  "website": "string or null",
  "description": "2-3 sentence company description for M&A analysts",
  "revenue_usd": number or null,
  "revenue_year": integer or null,
  "ebitda_usd": number or null,
  "ebitda_margin": number or null,
  "net_income_usd": number or null,
  "total_assets_usd": number or null,
  "total_debt_usd": number or null,
  "cash_usd": number or null,
  "enterprise_value_usd": number or null,
  "market_cap_usd": number or null,
  "financials_as_of_year": integer or null,
  "ev_revenue_multiple": number or null,
  "ev_ebitda_multiple": number or null,
  "revenue_growth_yoy": number or null,
  "data_confidence": integer,
  "sources": ["openai_knowledge"]
}

financials_as_of_year: the fiscal year the financial figures relate to (e.g. 2023).
data_confidence: 0-100. Deduct points for: private company (−20), old data (−10 per year stale), missing financials (−5 each), non-public jurisdiction (−10)."""


_DEEP_PROFILE_PROMPT = """You are an M&A intelligence analyst specialising in ownership structures and strategic positioning.

Given company context, extract ownership, strategic, and M&A signal information.
Return ONLY valid JSON. No markdown. Use null for uncertain fields. Never fabricate.

Required JSON structure:
{
  "ownership_structure": "public|pe_backed|family|state_owned|founder_led|unknown",
  "controlling_shareholder": "string or null",
  "controlling_stake_pct": number or null,
  "pe_sponsor": "string or null",
  "pe_vintage_year": integer or null,
  "key_products": ["string", ...],
  "geographic_markets": ["ISO2", ...],
  "customer_concentration": number or null,
  "top_customers": ["string", ...],
  "top_competitors": ["string", ...],
  "strategic_priorities": ["string", ...],
  "recent_acquisitions": [{"name": "string", "year": integer, "value_usd": number or null}, ...],
  "recent_divestitures": [{"name": "string", "year": integer, "value_usd": number or null}, ...],
  "m_and_a_appetite": "active_acquirer|selective|defensive|unknown",
  "rumored_target": false,
  "rumored_seller": false,
  "activist_present": false,
  "management_change_recent": false,
  "strategic_review_underway": false,
  "ownership_confidence": integer,
  "strategic_confidence": integer
}

ownership_confidence / strategic_confidence: 0-100 each."""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def fetch_basic_profile(
    company_id: str,
    legal_name: str,
    jurisdiction: str,
) -> dict:
    """
    Pass 1: identity + financials. Target < 5s.
    Returns partial profile dict or empty dict on failure.
    """
    user_msg = (
        f"Company: {legal_name}\n"
        f"Jurisdiction: {jurisdiction}\n"
        f"Extract the basic M&A intelligence profile."
    )
    return await _call_gpt(
        system_prompt=_BASIC_PROFILE_PROMPT,
        user_message=user_msg,
        label="basic_profile",
    )


async def research_company_deep(
    legal_name: str,
    jurisdiction: str,
    basic_data: dict,
) -> dict:
    """
    Pass 2: ownership + strategic features. Uses basic_data as context.
    Returns deep profile dict or empty dict on failure.
    """
    context_parts = [f"Company: {legal_name}", f"Jurisdiction: {jurisdiction}"]
    if basic_data.get("sector"):
        context_parts.append(f"Sector: {basic_data['sector']}")
    if basic_data.get("revenue_usd"):
        context_parts.append(f"Revenue: ${basic_data['revenue_usd']:,.0f}")
    if basic_data.get("listing_status"):
        context_parts.append(f"Listing: {basic_data['listing_status']}")
    if basic_data.get("description"):
        context_parts.append(f"Description: {basic_data['description']}")

    user_msg = "\n".join(context_parts) + "\nExtract ownership and strategic M&A intelligence."

    return await _call_gpt(
        system_prompt=_DEEP_PROFILE_PROMPT,
        user_message=user_msg,
        label="deep_profile",
    )


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------

async def _call_gpt(system_prompt: str, user_message: str, label: str) -> dict:
    """Single GPT-4o-mini call. Returns parsed dict or {} on any error."""
    try:
        response = await _get_client().chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=0.1,
            max_tokens=1200,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content
        return json.loads(raw)
    except Exception:
        return {}
