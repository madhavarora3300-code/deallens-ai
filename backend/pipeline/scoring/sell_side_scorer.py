"""
Sell-side scorer — orchestrates feature extraction + scoring + narration for one buyer candidate.
"""
import json

from openai import AsyncOpenAI

from core.config import settings
from pipeline.scoring.feature_extractor import extract_sell_side_features
from pipeline.scoring.scoring_engine import score_sell_side_pair

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _client


_NARRATION_PROMPT = """You are an M&A analyst advising a sell-side banker on buyer approach strategy.
Write 2-3 sentences explaining why this buyer would pay a premium for this asset.
Be specific. Reference the buyer's strategic gaps and the asset's fit. No boilerplate.
Return plain text only."""


async def score_buyer(
    seller_profile: dict,
    buyer_profile: dict,
    process_objective: str,
    generate_narration: bool = False,
) -> dict:
    """
    Full sell-side scoring for one seller-buyer pair.
    Returns scoring result merged with buyer identity metadata.
    """
    features = await extract_sell_side_features(seller_profile, buyer_profile)
    result = score_sell_side_pair(features)

    # Attach buyer metadata
    result["buyer_company_id"] = buyer_profile.get("company_id")
    result["buyer_legal_name"] = buyer_profile.get("legal_name")
    result["buyer_display_name"] = buyer_profile.get("display_name") or buyer_profile.get("legal_name")
    result["buyer_ticker"] = buyer_profile.get("ticker")
    result["buyer_jurisdiction"] = buyer_profile.get("jurisdiction")
    result["buyer_sector"] = buyer_profile.get("sector")
    result["buyer_listing_status"] = buyer_profile.get("listing_status")
    result["buyer_ev_usd_m"] = features.get("buyer_ev_usd_m")

    # Process architecture classification
    result["process_role"] = _classify_process_role(result, process_objective)

    if generate_narration and not result.get("excluded"):
        result["rationale"] = await _generate_narration(seller_profile, buyer_profile, result)
    else:
        result["rationale"] = result.get("rationale_hook") or ""

    return result


def _classify_process_role(scoring: dict, process_objective: str) -> str:
    """
    Assign a process architecture role:
      must_contact_strategic, price_anchor, certainty_anchor,
      tension_creator, sponsor_floor, do_not_approach
    """
    if scoring.get("excluded"):
        return "do_not_approach"

    bd = scoring.get("score_breakdown") or {}
    strategic_need = bd.get("strategic_need_buyer_urgency", 0)
    ability_to_pay = bd.get("ability_to_pay", 0)
    certainty = bd.get("certainty_of_close", 0)
    valuation_tension = bd.get("valuation_tension_potential", 0)
    sponsor = bd.get("sponsor_strategic_positioning", 0)

    if strategic_need >= 16 and ability_to_pay >= 12:
        return "must_contact_strategic"
    if valuation_tension >= 9 and ability_to_pay >= 10:
        return "price_anchor"
    if certainty >= 12 and strategic_need >= 10:
        return "certainty_anchor"
    if valuation_tension >= 7:
        return "tension_creator"
    if sponsor >= 3:
        return "sponsor_floor"
    return "tension_creator"


async def _generate_narration(seller: dict, buyer: dict, scoring: dict) -> str:
    seller_name = seller.get("display_name") or seller.get("legal_name", "Asset")
    buyer_name = buyer.get("display_name") or buyer.get("legal_name", "Buyer")
    breakdown = scoring.get("score_breakdown") or {}
    hook = scoring.get("rationale_hook") or ""

    prompt = (
        f"Asset: {seller_name} ({seller.get('sector', '')})\n"
        f"Buyer: {buyer_name} ({buyer.get('sector', '')})\n"
        f"Deal score: {scoring['deal_score']}/100 | Tier: {scoring['tier']}\n"
        f"Strategic need: {breakdown.get('strategic_need_buyer_urgency', 0)}/22 | "
        f"Ability to pay: {breakdown.get('ability_to_pay', 0)}/16\n"
        f"Process role: {scoring.get('process_role', '')}\n"
        f"Hook: {hook}\n"
        f"Write the buyer approach rationale."
    )
    try:
        r = await _get_client().chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": _NARRATION_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=150,
        )
        return r.choices[0].message.content.strip()
    except Exception:
        return hook
