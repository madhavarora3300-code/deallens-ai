"""
Feature Extractor — bridges enriched company profiles to scoring features.

Two feature types:
  Deterministic: derived directly from financial/ownership data
  AI-extracted:  GPT-4o-mini reads business context and returns structured signals

Both buyer and target profiles are dicts as returned by _profile_to_dict() in company router.
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

_STRATEGIC_FEATURES_PROMPT = """You are an M&A analyst assessing strategic fit for an acquisition.
Return ONLY valid JSON. No markdown. Be conservative — score 0 if no clear evidence.
Never score above 7 without explicit, specific evidence.

Scoring keys and max values:
- product_overlap (0-10): how similar are their products/services
- customer_overlap (0-10): shared customer base
- channel_fit (0-8): distribution/sales channel synergies
- capability_gap_fill (0-10): target fills a real gap in buyer's capabilities
- geographic_logic (0-8): target opens new markets or strengthens existing ones
- defensive_value (0-4): prevents competitor from acquiring target
- rationale_hook: one specific, concrete sentence (not generic boilerplate)

JSON structure:
{
  "product_overlap": 0-10,
  "customer_overlap": 0-10,
  "channel_fit": 0-8,
  "capability_gap_fill": 0-10,
  "geographic_logic": 0-8,
  "defensive_value": 0-4,
  "rationale_hook": "string",
  "signal_quality": 0-100
}"""

_MOMENTUM_FEATURES_PROMPT = """You are an M&A analyst assessing deal process momentum signals.
Return ONLY valid JSON. Score 0 if no evidence. Score 5 only for explicit, public signals.

JSON structure:
{
  "strategic_review_signal": 0-5,
  "advisor_hiring_signal": 0-5,
  "activist_pressure_signal": 0-5,
  "divestiture_signal": 0-5,
  "management_commentary_signal": 0-5
}"""

_SELL_SIDE_FEATURES_PROMPT = """You are an M&A analyst assessing a potential buyer's strategic need for an acquisition target.
Return ONLY valid JSON. Be conservative — score 0 without clear evidence.

Scoring keys:
- strategic_need_score (0-22): how urgently does this buyer need this asset
- ability_to_pay_score (0-16): financial capacity relative to deal size
- certainty_of_close_score (0-16): likelihood they can actually close
- regulatory_path_score (0-12): likely regulatory hurdles (higher = cleaner)
- valuation_tension_score (0-12): will this buyer stretch on price
- process_credibility_score (0-8): experienced acquirer, board support, decision speed
- execution_compatibility_score (0-6): cultural/operational fit
- sponsor_positioning_score (0-4): PE/financial sponsor positioning advantage
- momentum_score (0-4): recent signals of interest or activity
- rationale_hook: one specific sentence
- signal_quality: 0-100

JSON structure:
{
  "strategic_need_score": 0-22,
  "ability_to_pay_score": 0-16,
  "certainty_of_close_score": 0-16,
  "regulatory_path_score": 0-12,
  "valuation_tension_score": 0-12,
  "process_credibility_score": 0-8,
  "execution_compatibility_score": 0-6,
  "sponsor_positioning_score": 0-4,
  "momentum_score": 0-4,
  "rationale_hook": "string",
  "signal_quality": 0-100
}"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def extract_features_from_profiles(
    buyer_profile: dict,
    target_profile: dict,
    strategy_mode: str,
) -> dict:
    """
    Main feature extraction. Returns complete feature dict for the scoring engine.
    Calls GPT-4o-mini for strategic + momentum signals.
    Deterministic fields are computed directly from profile data.
    """
    # Deterministic features
    det = _extract_deterministic(buyer_profile, target_profile, strategy_mode)

    # AI-extracted strategic features
    strategic = await _extract_strategic_features(buyer_profile, target_profile)

    # AI-extracted momentum features (target only)
    momentum = await _extract_momentum_features(target_profile)

    return {**det, **strategic, **momentum, "hard_gate": None}


async def extract_sell_side_features(
    seller_profile: dict,
    buyer_profile: dict,
) -> dict:
    """Feature extraction for sell-side (buyer perspective)."""
    det = _extract_deterministic(buyer_profile, seller_profile, "sell_side")
    sell_ai = await _extract_sell_side_ai_features(seller_profile, buyer_profile)
    momentum = await _extract_momentum_features(buyer_profile)
    return {**det, **sell_ai, **momentum, "hard_gate": None}


# ---------------------------------------------------------------------------
# Deterministic extraction
# ---------------------------------------------------------------------------

def _extract_deterministic(
    buyer_profile: dict,
    target_profile: dict,
    strategy_mode: str,
) -> dict:
    """Pull numeric fields directly from profiles. No AI."""
    def _fin(profile: dict) -> dict:
        return profile.get("financials") or {}

    def _own(profile: dict) -> dict:
        return profile.get("ownership") or {}

    def _strat(profile: dict) -> dict:
        return profile.get("strategic_features") or {}

    bf = _fin(buyer_profile)
    tf = _fin(target_profile)
    to = _own(target_profile)
    ts = _strat(target_profile)
    bs = _strat(buyer_profile)

    buyer_ev = (bf.get("enterprise_value_usd") or 0) / 1e6
    target_ev = (tf.get("enterprise_value_usd") or 0) / 1e6
    target_mc = (tf.get("market_cap_usd") or 0) / 1e6
    target_rev = (tf.get("revenue_usd") or 0) / 1e6
    target_ebitda = (tf.get("ebitda_usd") or 0) / 1e6
    buyer_cash = (bf.get("cash_usd") or 0) / 1e6
    target_debt = (tf.get("total_debt_usd") or 0) / 1e6
    target_cash = (tf.get("cash_usd") or 0) / 1e6

    target_net_debt = (target_debt - target_cash) if (target_debt or target_cash) else None

    buyer_j = (buyer_profile.get("jurisdiction") or "").upper()
    target_j = (target_profile.get("jurisdiction") or "").upper()

    return {
        "buyer_company_id": buyer_profile.get("company_id"),
        "target_company_id": target_profile.get("company_id"),
        "buyer_market_cap_usd_m": (bf.get("market_cap_usd") or 0) / 1e6 or None,
        "buyer_ev_usd_m": buyer_ev or None,
        "buyer_cash_usd_m": buyer_cash or None,
        "buyer_revenue_usd_m": (bf.get("revenue_usd") or 0) / 1e6 or None,
        "target_ev_usd_m": target_ev or None,
        "target_market_cap_usd_m": target_mc or None,
        "target_revenue_usd_m": target_rev or None,
        "target_ebitda_usd_m": target_ebitda or None,
        "target_ebitda_margin_pct": tf.get("ebitda_margin"),
        "target_revenue_growth_pct": tf.get("revenue_growth_yoy"),
        "target_net_debt_usd_m": target_net_debt,
        "target_ev_revenue": tf.get("ev_revenue_multiple"),
        "target_ev_ebitda": tf.get("ev_ebitda_multiple"),
        "target_promoter_holding_pct": to.get("controlling_stake_pct"),
        "target_free_float_pct": (100 - (to.get("controlling_stake_pct") or 0))
            if to.get("controlling_stake_pct") else None,
        "target_is_soe": (to.get("ownership_structure") == "state_owned"),
        "target_ownership_structure": to.get("ownership_structure"),
        "target_pe_backed": (to.get("ownership_structure") == "pe_backed"),
        "target_pe_vintage_year": to.get("pe_vintage_year"),
        "target_jurisdiction": target_j or None,
        "buyer_jurisdiction": buyer_j or None,
        "cross_border": buyer_j != target_j if (buyer_j and target_j) else False,
        "target_sector": target_profile.get("sector"),
        "buyer_sector": buyer_profile.get("sector"),
        "target_listing_status": target_profile.get("listing_status"),
        "buyer_listing_status": buyer_profile.get("listing_status"),
        "target_m_and_a_appetite": ts.get("m_and_a_appetite"),
        "target_strategic_review": ts.get("strategic_review_underway", False),
        "target_activist_present": ts.get("activist_present", False),
        "buyer_m_and_a_appetite": bs.get("m_and_a_appetite"),
        "buyer_recent_acquisitions": bs.get("recent_acquisitions") or [],
        "strategy_mode": strategy_mode,
        "target_geographic_markets": ts.get("geographic_markets") or [],
        "buyer_geographic_markets": bs.get("geographic_markets") or [],
    }


# ---------------------------------------------------------------------------
# AI feature extraction
# ---------------------------------------------------------------------------

async def _extract_strategic_features(buyer: dict, target: dict) -> dict:
    buyer_name = buyer.get("display_name") or buyer.get("legal_name", "Buyer")
    target_name = target.get("display_name") or target.get("legal_name", "Target")
    buyer_sector = buyer.get("sector", "unknown")
    target_sector = target.get("sector", "unknown")

    def _profile_brief(p: dict, role: str) -> str:
        lines = [f"{role}: {p.get('display_name') or p.get('legal_name', role)}"]
        lines.append(f"  Sector: {p.get('sector', 'unknown')} | Industry: {p.get('industry', 'unknown')}")
        lines.append(f"  Jurisdiction: {p.get('jurisdiction', 'unknown')} | Listing: {p.get('listing_status', 'unknown')}")

        f = p.get("financials") or {}
        fin_parts = []
        if f.get("revenue_usd"):
            fin_parts.append(f"Revenue ${f['revenue_usd']/1e9:.1f}B")
        if f.get("enterprise_value_usd"):
            fin_parts.append(f"EV ${f['enterprise_value_usd']/1e9:.1f}B")
        if f.get("ebitda_margin"):
            fin_parts.append(f"EBITDA margin {f['ebitda_margin']:.0f}%")
        if f.get("revenue_growth_yoy"):
            fin_parts.append(f"Revenue growth {f['revenue_growth_yoy']:.0f}%")
        if fin_parts:
            lines.append(f"  Financials: {' | '.join(fin_parts)}")

        o = p.get("ownership") or {}
        if o.get("ownership_structure"):
            lines.append(f"  Ownership: {o['ownership_structure']}")
            if o.get("controlling_shareholder"):
                lines.append(f"  Controlling shareholder: {o['controlling_shareholder']}")

        sf = p.get("strategic_features") or {}
        if sf.get("key_products"):
            lines.append(f"  Key products: {', '.join(sf['key_products'][:5])}")
        if sf.get("strategic_priorities"):
            lines.append(f"  Strategic priorities: {', '.join(sf['strategic_priorities'][:4])}")
        if sf.get("geographic_markets"):
            lines.append(f"  Geographic markets: {', '.join(sf['geographic_markets'][:6])}")
        if sf.get("top_competitors"):
            lines.append(f"  Key competitors: {', '.join(sf['top_competitors'][:4])}")

        if p.get("description"):
            lines.append(f"  Description: {p['description']}")

        return "\n".join(lines)

    user_msg = (
        f"{_profile_brief(buyer, 'BUYER')}\n\n"
        f"{_profile_brief(target, 'TARGET')}\n\n"
        f"Assess the strategic fit of the TARGET as an acquisition for the BUYER."
    )

    data = await _call_gpt(_STRATEGIC_FEATURES_PROMPT, user_msg)

    # Deterministic fallback: if GPT returns all zeros, compute baseline from sector/geography match
    product_overlap = int(data.get("product_overlap") or 0)
    geographic_logic = int(data.get("geographic_logic") or 0)
    capability_gap_fill = int(data.get("capability_gap_fill") or 0)

    if product_overlap == 0 and geographic_logic == 0 and capability_gap_fill == 0:
        # Sector match → base product_overlap
        if buyer_sector and target_sector:
            if buyer_sector.lower() == target_sector.lower():
                product_overlap = 5
                capability_gap_fill = 4
            elif any(w in target_sector.lower() for w in buyer_sector.lower().split()):
                product_overlap = 3
        # Geography complement → base geographic_logic
        buyer_j = (buyer.get("jurisdiction") or "").upper()
        target_j = (target.get("jurisdiction") or "").upper()
        if buyer_j and target_j and buyer_j != target_j:
            geographic_logic = 4  # cross-border has inherent geographic logic
        elif buyer_j and target_j and buyer_j == target_j:
            geographic_logic = 3  # same market consolidation

    return {
        "product_overlap": product_overlap,
        "customer_overlap": int(data.get("customer_overlap") or 0),
        "channel_fit": int(data.get("channel_fit") or 0),
        "capability_gap_fill": capability_gap_fill,
        "geographic_logic": geographic_logic,
        "defensive_value": int(data.get("defensive_value") or 0),
        "rationale_hook": data.get("rationale_hook", ""),
        "strategic_signal_quality": int(data.get("signal_quality") or 50),
    }


async def _extract_momentum_features(target: dict) -> dict:
    target_name = target.get("display_name") or target.get("legal_name", "Company")
    desc = target.get("description") or ""
    sf = target.get("strategic_features") or {}
    signals = []
    if sf.get("strategic_review_underway"):
        signals.append("strategic review underway")
    if sf.get("activist_present"):
        signals.append("activist investor present")
    if sf.get("management_change_recent"):
        signals.append("recent management change")
    if sf.get("rumored_target"):
        signals.append("rumored acquisition target")

    context = desc
    if signals:
        context += f" Known signals: {', '.join(signals)}."

    user_msg = f"Company: {target_name}\nContext: {context}"
    data = await _call_gpt(_MOMENTUM_FEATURES_PROMPT, user_msg)

    return {
        "strategic_review_signal": int(data.get("strategic_review_signal") or 0),
        "advisor_hiring_signal": int(data.get("advisor_hiring_signal") or 0),
        "activist_pressure_signal": int(data.get("activist_pressure_signal") or 0),
        "divestiture_signal": int(data.get("divestiture_signal") or 0),
        "management_commentary_signal": int(data.get("management_commentary_signal") or 0),
    }


async def _extract_sell_side_ai_features(seller: dict, buyer: dict) -> dict:
    seller_name = seller.get("display_name") or seller.get("legal_name", "Target")
    buyer_name = buyer.get("display_name") or buyer.get("legal_name", "Buyer")

    def _summary(p: dict) -> str:
        parts = []
        if p.get("description"):
            parts.append(p["description"])
        f = p.get("financials") or {}
        if f.get("revenue_usd"):
            parts.append(f"Revenue: ${f['revenue_usd']/1e9:.1f}B")
        if f.get("enterprise_value_usd"):
            parts.append(f"EV: ${f['enterprise_value_usd']/1e9:.1f}B")
        o = p.get("ownership") or {}
        if o.get("ownership_structure"):
            parts.append(f"Ownership: {o['ownership_structure']}")
        return " | ".join(parts) or "No data."

    user_msg = (
        f"Asset for sale: {seller_name}\n"
        f"Asset context: {_summary(seller)}\n\n"
        f"Potential buyer: {buyer_name}\n"
        f"Buyer context: {_summary(buyer)}"
    )
    data = await _call_gpt(_SELL_SIDE_FEATURES_PROMPT, user_msg)

    return {
        "ss_strategic_need": int(data.get("strategic_need_score") or 0),
        "ss_ability_to_pay": int(data.get("ability_to_pay_score") or 0),
        "ss_certainty_of_close": int(data.get("certainty_of_close_score") or 0),
        "ss_regulatory_path": int(data.get("regulatory_path_score") or 0),
        "ss_valuation_tension": int(data.get("valuation_tension_score") or 0),
        "ss_process_credibility": int(data.get("process_credibility_score") or 0),
        "ss_execution_compatibility": int(data.get("execution_compatibility_score") or 0),
        "ss_sponsor_positioning": int(data.get("sponsor_positioning_score") or 0),
        "ss_momentum": int(data.get("momentum_score") or 0),
        "rationale_hook": data.get("rationale_hook", ""),
        "sell_side_signal_quality": int(data.get("signal_quality") or 50),
    }


async def _call_gpt(system_prompt: str, user_msg: str) -> dict:
    try:
        r = await _get_client().chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.1,
            max_tokens=500,
            response_format={"type": "json_object"},
        )
        return json.loads(r.choices[0].message.content)
    except Exception:
        return {}
