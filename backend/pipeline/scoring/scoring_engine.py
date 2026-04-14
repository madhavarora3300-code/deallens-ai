"""
Scoring Engine — pure Python scoring. No AI calls. Deterministic and auditable.

Buy-side weights (total 100):
  strategic_alpha: 24, dealability: 16, financial_health: 14,
  execution_complexity: 10, regulatory_path: 10,
  valuation_burden: 10, size_feasibility: 10,
  process_momentum: 4, scarcity: 2

Sell-side weights (total 100):
  strategic_need: 22, ability_to_pay: 16, certainty_of_close: 16,
  regulatory_path: 12, valuation_tension: 12, process_credibility: 8,
  execution_compatibility: 6, sponsor_positioning: 4, momentum: 4
"""

SANCTIONED_JURISDICTIONS = {"RU", "IR", "KP", "SY", "CU", "BY"}

# Sector EV/Revenue medians for valuation benchmarking
_SECTOR_EV_REV = {
    "Technology": 5.0, "Software": 7.0, "Healthcare": 4.0,
    "Pharmaceuticals": 5.0, "Consumer": 2.0, "Retail": 1.0,
    "Energy": 1.5, "Financials": 2.0, "Industrials": 1.8,
    "Materials": 1.5, "Utilities": 2.5, "Real Estate": 3.0,
    "Telecom": 2.5, "Media": 3.0,
}
_DEFAULT_EV_REV = 2.5


# ---------------------------------------------------------------------------
# Hard gate check
# ---------------------------------------------------------------------------

def check_hard_gates(features: dict, strategy_mode: str) -> str | None:
    """Returns gate name if triggered, else None."""
    target_j = (features.get("target_jurisdiction") or "").upper()
    if target_j in SANCTIONED_JURISDICTIONS:
        return "SANCTIONED_JURISDICTION"

    buyer_id = features.get("buyer_company_id")
    target_id = features.get("target_company_id")
    if buyer_id and target_id and buyer_id == target_id:
        return "SAME_ENTITY"

    buyer_ev = features.get("buyer_ev_usd_m") or features.get("buyer_market_cap_usd_m") or 0
    target_ev = features.get("target_ev_usd_m") or features.get("target_market_cap_usd_m") or 0
    if strategy_mode != "merger_of_equals" and buyer_ev > 0 and target_ev > buyer_ev * 1.2:
        return "TARGET_TOO_LARGE"

    if not features.get("target_jurisdiction"):
        return "NO_MINIMUM_DATA"

    return None


# ---------------------------------------------------------------------------
# Buy-side component scorers
# ---------------------------------------------------------------------------

def score_strategic_alpha(features: dict) -> int:
    """0-24. Weighted sum of AI-extracted strategic signals."""
    raw = (
        (features.get("product_overlap") or 0) * 0.8
        + (features.get("capability_gap_fill") or 0) * 1.2
        + (features.get("customer_overlap") or 0) * 0.5
        + (features.get("channel_fit") or 0) * 0.4
        + (features.get("geographic_logic") or 0) * 0.4
        + (features.get("defensive_value") or 0) * 0.5
    )
    return min(24, int(raw))


def score_dealability(features: dict) -> int:
    """
    0-16. Ownership/control signals.
    Full score for public float, discounted for promoter control / SOE / PE lock-up.
    """
    score = 10  # base for a public, liquid company

    ownership = (features.get("target_ownership_structure") or "").lower()

    if ownership == "state_owned" or features.get("target_is_soe"):
        return 3  # sovereign approval typically kills deals
    if ownership == "family":
        score -= 3  # family resistance common
    if ownership == "pe_backed":
        vintage = features.get("target_pe_vintage_year")
        if vintage:
            from datetime import datetime
            age = datetime.utcnow().year - vintage
            if age >= 4:
                score += 4  # PE ready to exit
            elif age >= 2:
                score += 2
        else:
            score += 2  # assume some exit pressure

    promoter = features.get("target_promoter_holding_pct")
    if promoter is not None:
        if promoter > 75:
            score -= 5  # promoter controls, hard to acquire
        elif promoter > 50:
            score -= 2
        elif promoter < 10:
            score += 2  # low promoter = dispersed ownership, easier tender

    if features.get("target_strategic_review"):
        score += 2  # actively exploring sale
    if features.get("target_activist_present"):
        score += 1  # activist may push sale

    return max(0, min(16, score))


def score_financial_health(features: dict, sector: str = "") -> int:
    """0-14. Profitability, leverage, growth quality."""
    score = 7  # neutral base

    margin = features.get("target_ebitda_margin_pct")
    if margin is not None:
        if margin >= 30:
            score += 3
        elif margin >= 15:
            score += 1
        elif margin < 0:
            score -= 3
        elif margin < 5:
            score -= 1

    growth = features.get("target_revenue_growth_pct")
    if growth is not None:
        if growth >= 20:
            score += 3
        elif growth >= 10:
            score += 1
        elif growth < 0:
            score -= 2

    # Leverage: net_debt / ebitda
    net_debt = features.get("target_net_debt_usd_m")
    ebitda = features.get("target_ebitda_usd_m")
    if net_debt is not None and ebitda and ebitda > 0:
        leverage = net_debt / ebitda
        if leverage > 5:
            score -= 3
        elif leverage > 3:
            score -= 1
        elif leverage < 1:
            score += 1

    return max(0, min(14, score))


def score_execution_complexity(features: dict) -> int:
    """0-10. Structural complexity — cross-border, SOE, size."""
    score = 10  # start at max, deduct for complexity

    if features.get("cross_border"):
        score -= 2

    if features.get("target_is_soe"):
        score -= 4

    target_ev = features.get("target_ev_usd_m") or 0
    buyer_ev = features.get("buyer_ev_usd_m") or features.get("buyer_market_cap_usd_m") or 1
    if buyer_ev > 0:
        size_ratio = target_ev / buyer_ev
        if size_ratio > 0.5:
            score -= 2  # transformative deal = complex integration
        elif size_ratio > 0.3:
            score -= 1

    if features.get("target_listing_status") == "private":
        score += 1  # private = no hostile takeover complexity

    return max(0, min(10, score))


def score_regulatory_path(features: dict) -> int:
    """0-10. Regulatory headwinds from jurisdiction and sector overlap."""
    score = 10

    if features.get("cross_border"):
        score -= 1

    target_j = (features.get("target_jurisdiction") or "").upper()
    buyer_j = (features.get("buyer_jurisdiction") or "").upper()

    # High-scrutiny combinations
    if target_j == "CN" and buyer_j == "US":
        score -= 5
    elif target_j == "CN":
        score -= 3
    elif target_j in ("IN",) and buyer_j not in ("IN",):
        score -= 1  # India FDI in some sectors
    elif target_j == "DE" and buyer_j not in ("DE", "FR", "NL", "GB"):
        score -= 1  # Germany strategic asset reviews

    # Sector overlap adds antitrust risk
    if features.get("target_sector") == features.get("buyer_sector"):
        score -= 2  # horizontal deal = antitrust scrutiny

    return max(0, min(10, score))


def score_valuation_burden(features: dict) -> int:
    """0-10. How stretched is the implied acquisition premium?"""
    score = 7  # neutral

    ev_rev = features.get("target_ev_revenue")
    sector = features.get("target_sector") or ""
    sector_median = _SECTOR_EV_REV.get(sector, _DEFAULT_EV_REV)

    if ev_rev is not None:
        premium_vs_median = ev_rev / sector_median if sector_median else 1
        if premium_vs_median <= 0.8:
            score += 3   # cheap vs sector
        elif premium_vs_median <= 1.2:
            score += 1   # fair value
        elif premium_vs_median <= 2.0:
            score -= 2   # elevated
        else:
            score -= 4   # very expensive

    ev_ebitda = features.get("target_ev_ebitda")
    if ev_ebitda is not None:
        if ev_ebitda > 25:
            score -= 2
        elif ev_ebitda > 15:
            score -= 1
        elif ev_ebitda < 8:
            score += 2

    return max(0, min(10, score))


def score_size_feasibility(features: dict, strategy_mode: str) -> int:
    """0-10. Can the buyer practically finance this deal?"""
    score = 8

    target_ev = features.get("target_ev_usd_m") or 0
    buyer_cash = features.get("buyer_cash_usd_m") or 0
    buyer_ev = features.get("buyer_ev_usd_m") or features.get("buyer_market_cap_usd_m") or 0

    if target_ev > 0 and buyer_ev > 0:
        size_ratio = target_ev / buyer_ev
        if size_ratio > 0.8 and strategy_mode != "merger_of_equals":
            score -= 3
        elif size_ratio > 0.5:
            score -= 2
        elif size_ratio > 0.3:
            score -= 1
        elif size_ratio < 0.05:
            score += 1  # small tuck-in, very manageable

    # Cash coverage
    if target_ev > 0 and buyer_cash > 0:
        cash_coverage = buyer_cash / target_ev
        if cash_coverage >= 0.5:
            score += 1  # can partially self-fund
        elif cash_coverage < 0.1:
            score -= 1  # heavy debt financing needed

    if strategy_mode == "merger_of_equals":
        score = min(10, score + 2)

    return max(0, min(10, score))


def score_process_momentum(features: dict) -> int:
    """0-4. AI-extracted momentum signals."""
    raw = sum([
        features.get("strategic_review_signal") or 0,
        features.get("advisor_hiring_signal") or 0,
        features.get("activist_pressure_signal") or 0,
        features.get("divestiture_signal") or 0,
        (features.get("management_commentary_signal") or 0) * 0.5,
    ])

    # Also boost if deterministic signals are set
    if features.get("target_strategic_review"):
        raw += 2
    if features.get("target_activist_present"):
        raw += 1

    return min(4, int(raw * 0.35))


def score_scarcity(features: dict) -> int:
    """0-2. Scarcity / uniqueness premium."""
    score = 1  # base

    # Unique asset in a niche sector
    sector = (features.get("target_sector") or "").lower()
    niche_sectors = {"semiconductor", "defense", "aerospace", "biotech", "rare"}
    if any(n in sector for n in niche_sectors):
        score = 2

    # PE-backed with long vintage = auction likely → scarcity pressure
    if features.get("target_pe_backed") and (features.get("target_pe_vintage_year") or 0) < 2020:
        score = 2

    return min(2, score)


# ---------------------------------------------------------------------------
# Sell-side score rationale builder
# ---------------------------------------------------------------------------

def _build_sell_side_score_rationale(features: dict,
                                     strategic_need: int, ability_to_pay: int,
                                     certainty_of_close: int, regulatory_path: int,
                                     valuation_tension: int, process_credibility: int,
                                     execution_compat: int, sponsor_positioning: int,
                                     momentum: int) -> dict:
    """
    Build human-readable formula strings for each sell-side score component.
    Returns dict keyed by the same names as score_breakdown.
    """
    buyer_j = (features.get("buyer_jurisdiction") or "").upper()
    seller_j = (features.get("target_jurisdiction") or features.get("seller_jurisdiction") or "").upper()
    buyer_sector = features.get("buyer_sector") or ""
    seller_sector = features.get("target_sector") or features.get("seller_sector") or ""
    buyer_ev = features.get("buyer_ev_usd_m") or features.get("buyer_market_cap_usd_m") or 0
    buyer_rev = features.get("buyer_revenue_usd_m") or 0
    buyer_cash = features.get("buyer_cash_usd_m") or 0
    target_ev = features.get("target_ev_usd_m") or 0
    buyer_net_debt = features.get("buyer_net_debt_usd_m") or 0
    ownership = (features.get("buyer_ownership_structure") or "public").lower()

    # 1. Strategic Need / Buyer Urgency (max 22)
    rationale_sn = (
        f"GPT-extracted signal: How urgently does this buyer need the seller's capabilities?\n"
        f"Inputs scored 0–22 by AI based on: sector adjacency ({buyer_sector} → {seller_sector}), "
        f"capability gap, geographic logic, defensive urgency.\n"
        f"Score {strategic_need}/22 reflects: "
        + ("Strong strategic pull — sector match and capability gap identified." if strategic_need >= 16 else
           "Moderate strategic pull — some overlap but not a critical gap fill." if strategic_need >= 10 else
           "Limited strategic urgency detected.")
    )

    # 2. Ability to Pay (max 16)
    leverage_notes = []
    if buyer_ev > 0 and target_ev > 0:
        size_ratio = round(target_ev / buyer_ev, 2)
        leverage_notes.append(f"Deal size: target EV ${target_ev:.0f}M / buyer EV ${buyer_ev:.0f}M = {size_ratio:.2f}x")
    if buyer_cash > 0 and target_ev > 0:
        cash_cov = round(buyer_cash / target_ev, 2)
        leverage_notes.append(f"Cash coverage: ${buyer_cash:.0f}M / ${target_ev:.0f}M = {cash_cov:.2f}x")
    if buyer_net_debt > 0:
        leverage_notes.append(f"Buyer net debt: ${buyer_net_debt:.0f}M (leverage constraint)")
    rationale_atp = (
        f"GPT-assessed ability to pay based on: buyer balance sheet strength, leverage capacity, "
        f"EV vs deal size, access to financing.\n"
        + ("\n".join(leverage_notes) + "\n" if leverage_notes else "Financial data not available for formula.\n")
        + f"Score {ability_to_pay}/16 reflects: "
        + ("Strong — buyer has balance sheet capacity and financing access." if ability_to_pay >= 12 else
           "Moderate — deal possible but likely requires debt financing." if ability_to_pay >= 8 else
           "Constrained — buyer balance sheet stretched; complex financing needed.")
    )

    # 3. Certainty of Close (max 16)
    cross_border = buyer_j and seller_j and buyer_j != seller_j
    rationale_coc = (
        f"Assesses likelihood the deal actually closes: ownership dealability, regulatory path, "
        f"cultural/execution fit.\n"
        f"Cross-border: {'Yes (' + buyer_j + ' → ' + seller_j + ')' if cross_border else 'No (same jurisdiction)'}\n"
        f"Buyer ownership: {ownership}\n"
        f"Score {certainty_of_close}/16: "
        + ("High certainty — clean structure, same jurisdiction, motivated buyer." if certainty_of_close >= 12 else
           "Moderate certainty — some complexity in execution or jurisdiction." if certainty_of_close >= 8 else
           "Low certainty — structural, regulatory or financing hurdles present.")
    )

    # 4. Regulatory Path (max 12)
    reg_notes = ["Base: 12"]
    if cross_border:
        reg_notes.append("Cross-border: -1")
    if buyer_j == "CN" and seller_j == "US":
        reg_notes.append("CN buyer + US seller: -5 (CFIUS review)")
    elif buyer_j == "US" and seller_j == "CN":
        reg_notes.append("US buyer + CN seller: -4 (SAMR review)")
    elif buyer_j != seller_j:
        reg_notes.append(f"Cross-border ({buyer_j}→{seller_j}): potential FDI/sector review")
    if buyer_sector == seller_sector and buyer_sector:
        reg_notes.append(f"Horizontal deal ({buyer_sector}): antitrust scrutiny -2")
    reg_notes.append(f"Result: {regulatory_path}/12")
    rationale_reg = "\n".join(reg_notes)

    # 5. Valuation Tension (max 12)
    rationale_vt = (
        f"Measures competitive tension: are multiple bidders likely? Is the seller's valuation "
        f"aspirations achievable vs what the buyer will pay?\n"
        f"Inputs: sector PE activity, comparable transaction multiples, auction process signals.\n"
        f"Score {valuation_tension}/12: "
        + ("High tension — likely competitive auction with premium pricing." if valuation_tension >= 9 else
           "Moderate tension — some competing interest but not a full auction." if valuation_tension >= 6 else
           "Low tension — bilateral process likely, pricing may be negotiable.")
    )

    # 6. Process Credibility (max 8)
    rationale_pc = (
        f"Assesses if the seller has a credible, organised sale process: board approval, "
        f"advisor mandate, management alignment, data room readiness.\n"
        f"Score {process_credibility}/8: "
        + ("Credible process — advisor engaged, board mandate evident." if process_credibility >= 6 else
           "Early-stage process — some signals of preparation but not formalised." if process_credibility >= 4 else
           "No formal process detected — opportunistic approach required.")
    )

    # 7. Execution Compatibility (max 6)
    rationale_ec = (
        f"Compatibility of buyer + seller on execution: cultural fit, technology stack, "
        f"workforce integration, ERP/systems overlap.\n"
        f"Buyer sector: {buyer_sector} | Seller sector: {seller_sector}\n"
        f"Score {execution_compat}/6: "
        + ("High compatibility — same sector, integration risk low." if execution_compat >= 5 else
           "Moderate compatibility — some integration complexity expected." if execution_compat >= 3 else
           "Complex integration — different business models or geographies.")
    )

    # 8. Sponsor Strategic Positioning (max 4)
    rationale_sp = (
        f"Assesses strategic importance beyond pure financials: platform-building, anchor investment, "
        f"ESG alignment, or sovereign fund participation.\n"
        f"Score {sponsor_positioning}/4: "
        + ("Strong strategic positioning signal." if sponsor_positioning >= 3 else
           "Some positioning rationale present." if sponsor_positioning >= 2 else
           "No distinct strategic positioning premium identified.")
    )

    # 9. Momentum / Market Signaling (max 4)
    rationale_mom = (
        f"Market timing signals: deal market sentiment, sector M&A activity, "
        f"comparable recent transactions, advisor commentary.\n"
        f"Score {momentum}/4: "
        + ("Strong momentum — active deal market in sector, recent precedents." if momentum >= 3 else
           "Moderate momentum — some deal activity but not peak cycle." if momentum >= 2 else
           "Low momentum — quiet deal market; timing may be challenging.")
    )

    return {
        "strategic_need_buyer_urgency": rationale_sn,
        "ability_to_pay": rationale_atp,
        "certainty_of_close": rationale_coc,
        "regulatory_path": rationale_reg,
        "valuation_tension_potential": rationale_vt,
        "process_credibility": rationale_pc,
        "execution_compatibility": rationale_ec,
        "sponsor_strategic_positioning": rationale_sp,
        "momentum_market_signaling": rationale_mom,
    }


# ---------------------------------------------------------------------------
# Sell-side component scorers
# ---------------------------------------------------------------------------

def score_sell_side_pair(features: dict) -> dict:
    """Score a seller-buyer pair using sell-side weights. Returns full result dict."""
    hard_gate = check_hard_gates(features, features.get("strategy_mode", "sell_side"))

    if hard_gate:
        return {
            "deal_score": 0,
            "confidence_score": 0,
            "tier": "Excluded",
            "tier_label": "EXCLUDED",
            "excluded": True,
            "hard_gates_triggered": [hard_gate],
            "dealability_verdict": "AVOID",
            "acquisition_route": "unclear",
            "score_breakdown": {},
            "rationale_hook": "",
        }

    strategic_need = min(22, int(features.get("ss_strategic_need") or 0))
    ability_to_pay = min(16, int(features.get("ss_ability_to_pay") or 0))
    certainty_of_close = min(16, int(features.get("ss_certainty_of_close") or 0))
    regulatory_path = min(12, int(features.get("ss_regulatory_path") or 0))
    valuation_tension = min(12, int(features.get("ss_valuation_tension") or 0))
    process_credibility = min(8, int(features.get("ss_process_credibility") or 0))
    execution_compat = min(6, int(features.get("ss_execution_compatibility") or 0))
    sponsor_positioning = min(4, int(features.get("ss_sponsor_positioning") or 0))
    momentum = min(4, int(features.get("ss_momentum") or 0))

    deal_score = (
        strategic_need + ability_to_pay + certainty_of_close
        + regulatory_path + valuation_tension + process_credibility
        + execution_compat + sponsor_positioning + momentum
    )
    deal_score = min(100, deal_score)

    confidence_score = _compute_sell_side_confidence(features)
    tier = assign_tier(deal_score, confidence_score, None)
    tier_label = f"TIER {tier.split()[-1]} MATCH" if "Tier" in tier else "EXCLUDED"

    return {
        "deal_score": deal_score,
        "confidence_score": confidence_score,
        "tier": tier,
        "tier_label": tier_label,
        "excluded": False,
        "hard_gates_triggered": [],
        "dealability_verdict": compute_dealability_verdict(
            int(certainty_of_close * 16 / 16), int(regulatory_path * 10 / 12)
        ),
        "acquisition_route": compute_acquisition_route(features),
        "score_breakdown": {
            "strategic_need_buyer_urgency": strategic_need,
            "ability_to_pay": ability_to_pay,
            "certainty_of_close": certainty_of_close,
            "regulatory_path": regulatory_path,
            "valuation_tension_potential": valuation_tension,
            "process_credibility": process_credibility,
            "execution_compatibility": execution_compat,
            "sponsor_strategic_positioning": sponsor_positioning,
            "momentum_market_signaling": momentum,
        },
        "score_rationale": _build_sell_side_score_rationale(
            features, strategic_need, ability_to_pay, certainty_of_close,
            regulatory_path, valuation_tension, process_credibility,
            execution_compat, sponsor_positioning, momentum,
        ),
        "rationale_hook": features.get("rationale_hook", ""),
    }


# ---------------------------------------------------------------------------
# IB Valuation Metrics (additive — no scoring weights changed)
# ---------------------------------------------------------------------------

def compute_ib_metrics(features: dict) -> dict:
    """
    Compute standard investment-banking valuation metrics from available features.
    All inputs come from the features dict — no new data fetches.
    Any metric with missing data returns None rather than raising.
    Called from score_buy_side_pair(); result attached as 'ib_metrics'.
    """
    results: dict = {}

    ebitda = features.get("target_ebitda_usd_m")
    ev = features.get("target_ev_usd_m") or 0
    net_debt = features.get("target_net_debt_usd_m") or 0
    ev_rev = features.get("target_ev_revenue")
    ev_ebitda = features.get("target_ev_ebitda")
    sector = features.get("target_sector") or ""
    buyer_ev = features.get("buyer_ev_usd_m") or features.get("buyer_market_cap_usd_m") or 0
    buyer_ebitda_margin = features.get("buyer_ebitda_margin_pct")
    target_margin = features.get("target_ebitda_margin_pct")
    synergy_est = features.get("estimated_synergy_value_usd_m") or 0

    # 1. FCF Yield  ≈ (EBITDA × 0.65) / EV  (0.65 = 1 - blended 35% tax+CapEx haircut)
    if ebitda and ev > 0:
        fcf_approx = ebitda * 0.65
        results["fcf_yield_pct"] = round((fcf_approx / ev) * 100, 1)
        results["fcf_yield_note"] = (
            f"Approx FCF = EBITDA ${ebitda:.0f}M × 0.65 (35% tax+CapEx) = ${fcf_approx:.0f}M; "
            f"FCF Yield = ${fcf_approx:.0f}M / EV ${ev:.0f}M = {results['fcf_yield_pct']}%"
        )

    # 2. Additional Debt Capacity  = (EBITDA × 5.5x IB ceiling) − existing net debt
    if ebitda:
        capacity = round(ebitda * 5.5 - net_debt, 0)
        results["additional_debt_capacity_usd_m"] = capacity
        results["debt_capacity_note"] = (
            f"IB leverage ceiling: EBITDA ${ebitda:.0f}M × 5.5x = ${ebitda*5.5:.0f}M; "
            f"minus existing net debt ${net_debt:.0f}M = ${capacity:.0f}M headroom"
        )

    # 3. Implied Control Premium vs sector EV/Rev median (standard 30% control premium)
    sector_median = _SECTOR_EV_REV.get(sector, _DEFAULT_EV_REV)
    if ev_rev and ev_rev > 0:
        typical_acq_multiple = sector_median * 1.30
        prem = round(((typical_acq_multiple / ev_rev) - 1) * 100, 1)
        results["implied_control_premium_pct"] = prem
        results["control_premium_note"] = (
            f"Sector ({sector}) median EV/Rev: {sector_median:.1f}x; "
            f"typical acquisition multiple (30% premium): {typical_acq_multiple:.1f}x; "
            f"vs current {ev_rev:.1f}x → implied premium to pay: {prem:+.1f}%"
        )

    # 4. EV/EBITDA context vs IB rule-of-thumb thresholds
    if ev_ebitda:
        cheap = ev_ebitda < 8
        fair = 8 <= ev_ebitda <= 15
        expensive = 15 < ev_ebitda <= 25
        very_expensive = ev_ebitda > 25
        label = "Cheap entry" if cheap else "Fair value" if fair else "Elevated" if expensive else "Premium priced"
        results["ev_ebitda_context"] = f"{ev_ebitda:.1f}x EV/EBITDA — {label} (IB thresholds: <8x cheap, 8–15x fair, 15–25x elevated, >25x premium)"

    # 5. Simplified Accretion / Dilution (Year 2 EPS proxy, assumes all-cash deal)
    if buyer_ebitda_margin is not None and target_margin is not None:
        margin_gap = round(target_margin - buyer_ebitda_margin, 1)
        if margin_gap >= 0:
            signal = "ACCRETIVE"
            note = (
                f"Target EBITDA margin ({target_margin:.0f}%) ≥ buyer margin ({buyer_ebitda_margin:.0f}%) "
                f"→ margin-accretive even before synergies."
            )
        elif synergy_est > 0 and ev > 0:
            # Synergy as % of deal price — if synergy yield > margin drag, accretive
            synergy_yield = round((synergy_est / ev) * 100, 1)
            if synergy_yield > abs(margin_gap):
                signal = "POTENTIALLY ACCRETIVE"
                note = (
                    f"Margin gap: {margin_gap:.0f}pp drag. Synergy ${synergy_est:.0f}M = {synergy_yield:.1f}% of EV "
                    f"— if realised, offsets dilution by Year 2."
                )
            else:
                signal = "LIKELY DILUTIVE"
                note = (
                    f"Margin gap: {margin_gap:.0f}pp. Synergy yield {synergy_yield:.1f}% < margin drag "
                    f"— EPS dilutive in near term; Year 3+ dependent on full synergy capture."
                )
        else:
            signal = "LIKELY DILUTIVE"
            note = (
                f"Target margin ({target_margin:.0f}%) < buyer ({buyer_ebitda_margin:.0f}%) by {abs(margin_gap):.0f}pp. "
                f"No synergy estimate — assume dilutive absent cost restructuring."
            )
        results["accretion_dilution"] = signal
        results["accretion_note"] = note

    # 6. Size vs peer median (deal sizing context)
    if ev > 0 and buyer_ev > 0:
        size_ratio = round(ev / buyer_ev, 2)
        sizing = (
            "Tuck-in (<5% buyer EV)" if size_ratio < 0.05 else
            "Small bolt-on (5–15%)" if size_ratio < 0.15 else
            "Material acquisition (15–30%)" if size_ratio < 0.30 else
            "Transformative (30–80%)" if size_ratio < 0.80 else
            "Merger-scale (>80%)"
        )
        results["deal_size_classification"] = f"Target EV ${ev:.0f}M / Buyer EV ${buyer_ev:.0f}M = {size_ratio:.2f}x — {sizing}"

    return results


# ---------------------------------------------------------------------------
# Tier and verdict logic
# ---------------------------------------------------------------------------

def assign_tier(deal_score: int, confidence_score: float, hard_gate: str | None) -> str:
    if hard_gate:
        return "Excluded"
    # Tier 1: strong deal score with reasonable confidence
    if deal_score >= 65 and confidence_score >= 45:
        return "Tier 1"
    # Tier 2: good deal score OR decent confidence
    if deal_score >= 45 or confidence_score >= 40:
        return "Tier 2"
    return "Tier 3"


def compute_dealability_verdict(dealability: int, regulatory: int) -> str:
    if dealability >= 12 and regulatory >= 7:
        return "APPROACHABLE"
    if 6 <= dealability <= 11 or 4 <= regulatory <= 6:
        return "NEEDS STRUCTURING"
    if 3 <= dealability <= 5 or 2 <= regulatory <= 3:
        return "COMPLEX"
    return "AVOID"


def compute_acquisition_route(features: dict) -> str:
    if features.get("target_is_soe"):
        return "sovereign_negotiation"
    target_j = (features.get("target_jurisdiction") or "").upper()
    if target_j == "IN":
        return "open_offer_required"
    promoter = features.get("target_promoter_holding_pct")
    free_float = features.get("target_free_float_pct")
    if promoter is None:
        if features.get("target_listing_status") == "private":
            return "friendly_negotiated"
        return "unclear"
    if free_float and free_float > 50 and promoter < 20:
        return "block_purchase"
    if promoter < 35:
        return "friendly_negotiated"
    if promoter <= 75:
        return "tender_offer"
    return "unclear"


# ---------------------------------------------------------------------------
# Score rationale builder — generates formula strings for each component
# ---------------------------------------------------------------------------

def _build_score_rationale(features: dict, strategy_mode: str,
                           strategic_alpha: int, dealability: int,
                           financial_health: int, execution_complexity: int,
                           regulatory_path: int, valuation_burden: int,
                           size_feasibility: int, process_momentum: int,
                           scarcity: int) -> dict:
    """
    Build human-readable formula strings for each score component.
    Shows the actual input values and computation steps — for display in Deep Analysis.
    """
    po = features.get("product_overlap") or 0
    cf_fill = features.get("capability_gap_fill") or 0
    co = features.get("customer_overlap") or 0
    ch = features.get("channel_fit") or 0
    gl = features.get("geographic_logic") or 0
    dv = features.get("defensive_value") or 0
    raw_sa = round(po * 0.8 + cf_fill * 1.2 + co * 0.5 + ch * 0.4 + gl * 0.4 + dv * 0.5, 1)

    target_j = (features.get("target_jurisdiction") or "").upper()
    buyer_j = (features.get("buyer_jurisdiction") or "").upper()
    target_sector = features.get("target_sector") or ""
    buyer_sector = features.get("buyer_sector") or ""
    ownership = (features.get("target_ownership_structure") or "public").lower()
    promoter = features.get("target_promoter_holding_pct")
    pe_vintage = features.get("target_pe_vintage_year")
    is_soe = features.get("target_is_soe")
    strategic_review = features.get("target_strategic_review")
    activist = features.get("target_activist_present")

    margin = features.get("target_ebitda_margin_pct")
    growth = features.get("target_revenue_growth_pct")
    net_debt = features.get("target_net_debt_usd_m")
    ebitda = features.get("target_ebitda_usd_m")
    leverage = round(net_debt / ebitda, 2) if (net_debt is not None and ebitda and ebitda > 0) else None

    target_ev = features.get("target_ev_usd_m") or 0
    buyer_ev = features.get("buyer_ev_usd_m") or features.get("buyer_market_cap_usd_m") or 1
    buyer_cash = features.get("buyer_cash_usd_m") or 0
    size_ratio = round(target_ev / buyer_ev, 2) if buyer_ev > 0 else None
    cash_cov = round(buyer_cash / target_ev, 2) if target_ev > 0 and buyer_cash > 0 else None

    ev_rev = features.get("target_ev_revenue")
    ev_ebitda = features.get("target_ev_ebitda")
    sector_median = _SECTOR_EV_REV.get(target_sector, _DEFAULT_EV_REV)
    prem_ratio = round(ev_rev / sector_median, 2) if (ev_rev and sector_median) else None

    sr_sig = features.get("strategic_review_signal") or 0
    adv_sig = features.get("advisor_hiring_signal") or 0
    act_sig = features.get("activist_pressure_signal") or 0
    div_sig = features.get("divestiture_signal") or 0
    mgmt_sig = features.get("management_commentary_signal") or 0

    cross_border = features.get("cross_border", False)

    # 1. Strategic Alpha
    rationale_sa = (
        f"Formula: (product_overlap×0.8) + (capability_gap_fill×1.2) + (customer_overlap×0.5) "
        f"+ (channel_fit×0.4) + (geographic_logic×0.4) + (defensive_value×0.5)\n"
        f"Inputs: product_overlap={po}/10, capability_gap_fill={cf_fill}/10, "
        f"customer_overlap={co}/10, channel_fit={ch}/8, geographic_logic={gl}/8, defensive_value={dv}/4\n"
        f"= ({po}×0.8) + ({cf_fill}×1.2) + ({co}×0.5) + ({ch}×0.4) + ({gl}×0.4) + ({dv}×0.5) "
        f"= {raw_sa} → capped at {min(24, int(raw_sa))}/24"
    )

    # 2. Dealability/Ownership
    deal_steps = ["Base: 10 (public company baseline)"]
    if is_soe:
        deal_steps.append("SOE penalty → floor at 3 (sovereign approval required)")
    elif ownership == "family":
        deal_steps.append("Family-owned: -3 (resistance to sale common)")
    elif ownership == "pe_backed":
        if pe_vintage:
            from datetime import datetime as _dt
            age = _dt.utcnow().year - pe_vintage
            adj = 4 if age >= 4 else (2 if age >= 2 else 0)
            deal_steps.append(f"PE-backed, vintage {pe_vintage} (age {age}yr): +{adj} (exit pressure)")
        else:
            deal_steps.append("PE-backed (no vintage): +2 (assumed exit pressure)")
    if promoter is not None:
        if promoter > 75:
            deal_steps.append(f"Promoter {promoter:.0f}%: -5 (control block, hard to acquire)")
        elif promoter > 50:
            deal_steps.append(f"Promoter {promoter:.0f}%: -2 (majority held)")
        elif promoter < 10:
            deal_steps.append(f"Promoter {promoter:.0f}%: +2 (dispersed ownership, easier tender)")
    if strategic_review:
        deal_steps.append("Strategic review underway: +2")
    if activist:
        deal_steps.append("Activist investor present: +1")
    deal_steps.append(f"Result: {dealability}/16 | Acquisition route: {features.get('acquisition_route','—')}")
    rationale_deal = "\n".join(deal_steps)

    # 3. Financial Health
    fin_steps = ["Base: 7 (neutral)"]
    if margin is not None:
        adj = 3 if margin >= 30 else (1 if margin >= 15 else (-1 if margin < 5 else (-3 if margin < 0 else 0)))
        fin_steps.append(f"EBITDA margin {margin:.1f}%: {'+' if adj >= 0 else ''}{adj} (thresholds: ≥30%→+3, ≥15%→+1, <5%→-1, <0%→-3)")
    else:
        fin_steps.append("EBITDA margin: not available")
    if growth is not None:
        adj_g = 3 if growth >= 20 else (1 if growth >= 10 else (-2 if growth < 0 else 0))
        fin_steps.append(f"Revenue growth {growth:.1f}% YoY: {'+' if adj_g >= 0 else ''}{adj_g} (thresholds: ≥20%→+3, ≥10%→+1, <0%→-2)")
    else:
        fin_steps.append("Revenue growth: not available")
    if leverage is not None:
        adj_l = -3 if leverage > 5 else (-1 if leverage > 3 else (1 if leverage < 1 else 0))
        fin_steps.append(f"Net Debt/EBITDA leverage {leverage:.1f}x: {'+' if adj_l >= 0 else ''}{adj_l} (thresholds: >5x→-3, >3x→-1, <1x→+1)")
    else:
        fin_steps.append("Net Debt/EBITDA: not available")
    fin_steps.append(f"Result: {financial_health}/14")
    rationale_fin = "\n".join(fin_steps)

    # 4. Execution Complexity
    exec_steps = ["Base: 10 (simple deal — deductions applied for complexity)"]
    if cross_border:
        exec_steps.append(f"Cross-border ({buyer_j}→{target_j}): -2")
    if is_soe:
        exec_steps.append("SOE target: -4 (government approval, political risk)")
    if size_ratio is not None:
        adj_sz = -2 if size_ratio > 0.5 else (-1 if size_ratio > 0.3 else 0)
        if adj_sz:
            exec_steps.append(f"Size ratio (target EV / buyer EV) = {size_ratio:.2f}x: {adj_sz} (>0.5x transformative)")
    if features.get("target_listing_status") == "private":
        exec_steps.append("Private target: +1 (no hostile takeover complexity)")
    exec_steps.append(f"Result: {execution_complexity}/10")
    rationale_exec = "\n".join(exec_steps)

    # 5. Regulatory Path
    reg_steps = ["Base: 10"]
    if cross_border:
        reg_steps.append("Cross-border: -1")
    if target_j == "CN" and buyer_j == "US":
        reg_steps.append("CN target + US buyer: -5 (CFIUS/SAMR dual scrutiny)")
    elif target_j == "CN":
        reg_steps.append(f"CN target (non-US buyer): -3 (SAMR market review)")
    elif target_j == "IN" and buyer_j != "IN":
        reg_steps.append("IN target (cross-border): -1 (FDI screening in some sectors)")
    elif target_j == "DE" and buyer_j not in ("DE", "FR", "NL", "GB"):
        reg_steps.append("DE target (non-EU buyer): -1 (strategic asset review)")
    if target_sector == buyer_sector and target_sector:
        reg_steps.append(f"Horizontal deal (same sector: {target_sector}): -2 (antitrust scrutiny)")
    reg_steps.append(f"Result: {regulatory_path}/10")
    rationale_reg = "\n".join(reg_steps)

    # 6. Valuation Burden
    val_steps = ["Base: 7 (neutral)"]
    if ev_rev is not None:
        val_steps.append(f"EV/Revenue: {ev_rev:.1f}x vs {target_sector or 'sector'} median {sector_median:.1f}x (premium ratio: {prem_ratio:.2f}x)")
        adj_v = 3 if prem_ratio and prem_ratio <= 0.8 else (1 if prem_ratio and prem_ratio <= 1.2 else (-2 if prem_ratio and prem_ratio <= 2.0 else -4))
        val_steps.append(f"  → Premium adjustment: {'+' if adj_v >= 0 else ''}{adj_v} (≤0.8x→+3, ≤1.2x→+1, ≤2.0x→-2, >2.0x→-4)")
    else:
        val_steps.append("EV/Revenue multiple: not available")
    if ev_ebitda is not None:
        adj_eb = -2 if ev_ebitda > 25 else (-1 if ev_ebitda > 15 else (2 if ev_ebitda < 8 else 0))
        val_steps.append(f"EV/EBITDA: {ev_ebitda:.1f}x → {'+' if adj_eb >= 0 else ''}{adj_eb} (>25x→-2, >15x→-1, <8x→+2)")
    else:
        val_steps.append("EV/EBITDA: not available")
    val_steps.append(f"Result: {valuation_burden}/10")
    rationale_val = "\n".join(val_steps)

    # 7. Size Feasibility
    sz_steps = ["Base: 8"]
    if size_ratio is not None:
        adj_s = -3 if size_ratio > 0.8 else (-2 if size_ratio > 0.5 else (-1 if size_ratio > 0.3 else (1 if size_ratio < 0.05 else 0)))
        if strategy_mode == "merger_of_equals" and size_ratio > 0.8:
            adj_s = 0
        sz_steps.append(f"Size ratio (target EV ${target_ev:.0f}M / buyer EV ${buyer_ev:.0f}M) = {size_ratio:.2f}x: "
                        f"{'+' if adj_s >= 0 else ''}{adj_s} (>0.8x→-3, >0.5x→-2, >0.3x→-1, <0.05x→+1)")
    if cash_cov is not None:
        adj_cc = 1 if cash_cov >= 0.5 else (-1 if cash_cov < 0.1 else 0)
        sz_steps.append(f"Cash coverage (buyer cash ${buyer_cash:.0f}M / target EV ${target_ev:.0f}M) = {cash_cov:.2f}x: "
                        f"{'+' if adj_cc >= 0 else ''}{adj_cc} (≥0.5x can self-fund, <0.1x heavy debt)")
    if strategy_mode == "merger_of_equals":
        sz_steps.append("Merger of equals: +2 bonus")
    sz_steps.append(f"Result: {size_feasibility}/10")
    rationale_sz = "\n".join(sz_steps)

    # 8. Process Momentum
    mom_steps = [
        f"Signals: strategic_review={sr_sig}/5, advisor_hiring={adv_sig}/5, activist={act_sig}/5, "
        f"divestiture={div_sig}/5, management_commentary={mgmt_sig}/5",
        f"Formula: (sr + adv + act + div + mgmt×0.5) × 0.35 + deterministic_flags",
    ]
    if strategic_review:
        mom_steps.append("Deterministic: strategic_review_flag=True → +2")
    if activist:
        mom_steps.append("Deterministic: activist_flag=True → +1")
    mom_steps.append(f"Result: {process_momentum}/4")
    rationale_mom = "\n".join(mom_steps)

    # 9. Scarcity
    niche_sectors = {"semiconductor", "defense", "aerospace", "biotech", "rare"}
    is_niche = any(n in (target_sector or "").lower() for n in niche_sectors)
    pe_old = features.get("target_pe_backed") and (pe_vintage or 9999) < 2020
    sc_steps = ["Base: 1"]
    if is_niche:
        sc_steps.append(f"Niche sector ({target_sector}): → 2 (irreplaceable asset premium)")
    if pe_old:
        sc_steps.append(f"PE-backed vintage <2020 (age >{2024 - (pe_vintage or 2020)}yr): → 2 (auction likely)")
    sc_steps.append(f"Result: {scarcity}/2")
    rationale_sc = "\n".join(sc_steps)

    return {
        "strategic_alpha": rationale_sa,
        "dealability_ownership": rationale_deal,
        "financial_health": rationale_fin,
        "execution_complexity": rationale_exec,
        "regulatory_path": rationale_reg,
        "valuation_premium_burden": rationale_val,
        "size_funding_feasibility": rationale_sz,
        "process_momentum": rationale_mom,
        "scarcity_auction_pressure": rationale_sc,
    }


# ---------------------------------------------------------------------------
# Main buy-side scoring entry point
# ---------------------------------------------------------------------------

def score_buy_side_pair(features: dict, strategy_mode: str) -> dict:
    """Score a buyer-target pair. Returns full scoring result dict."""
    hard_gate = check_hard_gates(features, strategy_mode)

    if hard_gate:
        return {
            "deal_score": 0,
            "confidence_score": 0,
            "tier": "Excluded",
            "tier_label": "EXCLUDED",
            "excluded": True,
            "hard_gates_triggered": [hard_gate],
            "dealability_verdict": "AVOID",
            "acquisition_route": "unclear",
            "score_breakdown": {},
            "rationale_hook": "",
        }

    strategic_alpha = score_strategic_alpha(features)
    dealability = score_dealability(features)
    financial_health = score_financial_health(features, features.get("target_sector") or "")
    execution_complexity = score_execution_complexity(features)
    regulatory_path = score_regulatory_path(features)
    valuation_burden = score_valuation_burden(features)
    size_feasibility = score_size_feasibility(features, strategy_mode)
    process_momentum = score_process_momentum(features)
    scarcity = score_scarcity(features)

    deal_score = min(100, (
        strategic_alpha + dealability + financial_health
        + execution_complexity + regulatory_path + valuation_burden
        + size_feasibility + process_momentum + scarcity
    ))

    confidence_score = _compute_buy_side_confidence(features)
    tier = assign_tier(deal_score, confidence_score, None)
    tier_label = f"TIER {tier.split()[-1]} MATCH" if "Tier" in tier else "EXCLUDED"
    verdict = compute_dealability_verdict(dealability, regulatory_path)
    route = compute_acquisition_route(features)

    score_rationale = _build_score_rationale(
        features, strategy_mode,
        strategic_alpha, dealability, financial_health,
        execution_complexity, regulatory_path, valuation_burden,
        size_feasibility, process_momentum, scarcity,
    )

    return {
        "deal_score": deal_score,
        "confidence_score": confidence_score,
        "tier": tier,
        "tier_label": tier_label,
        "excluded": False,
        "hard_gates_triggered": [],
        "dealability_verdict": verdict,
        "acquisition_route": route,
        "score_breakdown": {
            "strategic_alpha": strategic_alpha,
            "dealability_ownership": dealability,
            "financial_health": financial_health,
            "execution_complexity": execution_complexity,
            "regulatory_path": regulatory_path,
            "valuation_premium_burden": valuation_burden,
            "size_funding_feasibility": size_feasibility,
            "process_momentum": process_momentum,
            "scarcity_auction_pressure": scarcity,
        },
        "score_rationale": score_rationale,
        "ib_metrics": compute_ib_metrics(features),
        "rationale_hook": features.get("rationale_hook", ""),
    }


# ---------------------------------------------------------------------------
# Confidence scoring
# ---------------------------------------------------------------------------

def _compute_buy_side_confidence(features: dict) -> float:
    score = 0.0

    # Data completeness (5 pts each of 8 fields)
    completeness_checks = [
        features.get("target_ebitda_margin_pct"),
        features.get("target_revenue_growth_pct"),
        features.get("target_net_debt_usd_m"),
        features.get("target_market_cap_usd_m") or features.get("target_ev_usd_m"),
        features.get("target_ownership_structure"),
        features.get("target_sector"),
        features.get("buyer_ev_usd_m") or features.get("buyer_market_cap_usd_m"),
        features.get("target_jurisdiction"),
    ]
    score += sum(5 for f in completeness_checks if f is not None)

    # GPT signal quality (3 pts per non-zero AI signal, max 10 signals)
    gpt_signals = [
        "product_overlap", "customer_overlap", "channel_fit",
        "capability_gap_fill", "geographic_logic", "defensive_value",
        "strategic_review_signal", "advisor_hiring_signal",
        "activist_pressure_signal", "divestiture_signal",
    ]
    score += sum(3 for s in gpt_signals if (features.get(s) or 0) > 0)

    # GPT self-reported signal quality
    sq = features.get("strategic_signal_quality") or 0
    score += (sq / 100) * 20

    # Deterministic baseline bonuses — ensure well-matched pairs aren't penalised
    # purely because GPT signals happen to be sparse
    buyer_sector = (features.get("buyer_sector") or "").lower()
    target_sector = (features.get("target_sector") or "").lower()
    buyer_j = (features.get("buyer_jurisdiction") or "").upper()
    target_j = (features.get("target_jurisdiction") or "").upper()

    if buyer_sector and target_sector and buyer_sector == target_sector:
        score += 10  # Same-sector pairs get baseline confidence
    elif buyer_sector and target_sector and (
        buyer_sector in target_sector or target_sector in buyer_sector
    ):
        score += 5   # Adjacent sector

    if buyer_j and target_j and buyer_j == target_j:
        score += 5   # Same jurisdiction

    # Any financial data on the target is a positive signal
    if features.get("target_ev_usd_m") or features.get("target_revenue_usd_m"):
        score += 5

    return round(min(100.0, score), 1)


def _compute_sell_side_confidence(features: dict) -> float:
    score = 0.0

    completeness_checks = [
        features.get("target_ev_usd_m"),
        features.get("buyer_ev_usd_m"),
        features.get("target_ownership_structure"),
        features.get("target_sector"),
        features.get("target_jurisdiction"),
        features.get("buyer_jurisdiction"),
    ]
    score += sum(8 for f in completeness_checks if f is not None)

    sq = features.get("sell_side_signal_quality") or 0
    score += (sq / 100) * 52

    return round(min(100.0, score), 1)
