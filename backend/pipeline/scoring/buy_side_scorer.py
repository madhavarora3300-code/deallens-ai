"""
Buy-side scorer — orchestrates feature extraction + scoring + narration for one pair.
"""
import json

from openai import AsyncOpenAI

from core.config import settings
from pipeline.scoring.feature_extractor import extract_features_from_profiles
from pipeline.scoring.scoring_engine import score_buy_side_pair

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _client


_NARRATION_PROMPT = """You are an M&A analyst writing a concise deal rationale for an investment banker.
Write 2-3 sentences. Be specific. Reference actual company names, products, and strategic logic.
No boilerplate. No generic statements. Focus on WHY this deal makes strategic sense right now.
Return plain text only."""


async def score_target(
    buyer_profile: dict,
    target_profile: dict,
    strategy_mode: str,
    generate_narration: bool = False,
) -> dict:
    """
    Full buy-side scoring for one buyer-target pair.
    Returns scoring result merged with target identity metadata.
    """
    features = await extract_features_from_profiles(buyer_profile, target_profile, strategy_mode)
    result = score_buy_side_pair(features, strategy_mode)

    # Attach target metadata
    result["target_company_id"] = target_profile.get("company_id")
    result["target_legal_name"] = target_profile.get("legal_name")
    result["target_display_name"] = target_profile.get("display_name") or target_profile.get("legal_name")
    result["target_ticker"] = target_profile.get("ticker")
    result["target_jurisdiction"] = target_profile.get("jurisdiction")
    result["target_sector"] = target_profile.get("sector")
    result["target_listing_status"] = target_profile.get("listing_status")
    result["target_ev_usd_m"] = features.get("target_ev_usd_m")
    result["target_revenue_usd_m"] = features.get("target_revenue_usd_m")
    result["target_ebitda_margin_pct"] = features.get("target_ebitda_margin_pct")

    # GPT-4o-mini narration for top results only
    if generate_narration and not result.get("excluded"):
        result["rationale"] = await _generate_narration(buyer_profile, target_profile, result)
    else:
        result["rationale"] = result.get("rationale_hook") or ""

    return result


async def _generate_narration(buyer: dict, target: dict, scoring: dict) -> str:
    buyer_name = buyer.get("display_name") or buyer.get("legal_name", "Buyer")
    target_name = target.get("display_name") or target.get("legal_name", "Target")
    breakdown = scoring.get("score_breakdown") or {}
    hook = scoring.get("rationale_hook") or ""

    prompt = (
        f"Buyer: {buyer_name} ({buyer.get('sector', '')})\n"
        f"Target: {target_name} ({target.get('sector', '')})\n"
        f"Deal score: {scoring['deal_score']}/100 | Tier: {scoring['tier']}\n"
        f"Strategic alpha: {breakdown.get('strategic_alpha', 0)}/24 | "
        f"Dealability: {breakdown.get('dealability_ownership', 0)}/16\n"
        f"Strategic hook: {hook}\n"
        f"Write the deal rationale."
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
