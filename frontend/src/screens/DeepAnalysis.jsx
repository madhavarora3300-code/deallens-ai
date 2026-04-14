import React, { useState, useEffect } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { getCompanyProfile, predictRegulatory } from "../api/deallens.js";
import { ScoreDial } from "../components/ScoreDial.jsx";
import { TierBadge } from "../components/TierBadge.jsx";
import { JurisdictionBadge } from "../components/JurisdictionBadge.jsx";

const SCORE_MAX = {
  // Buy-side
  strategic_alpha: 24, dealability_ownership: 16, financial_health: 14,
  execution_complexity: 10, regulatory_path: 10, valuation_premium_burden: 10,
  size_funding_feasibility: 10, process_momentum: 4, scarcity_auction_pressure: 2,
  // Sell-side
  strategic_need_buyer_urgency: 22, ability_to_pay: 16, certainty_of_close: 16,
  valuation_tension_potential: 12, process_credibility: 8, execution_compatibility: 6,
  sponsor_strategic_positioning: 4, momentum_market_signaling: 4,
};

function ProfilePanel({ profile, role }) {
  if (!profile) return (
    <div className="card" style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", minHeight: 200 }}>
      <span style={{ color: "var(--dl-text-muted)", fontSize: 13 }}>Loading {role} profile…</span>
    </div>
  );

  const fin = profile.financials || {};
  const own = profile.ownership || {};
  const sf  = profile.strategic_features || {};

  return (
    <div className="card" style={{ flex: 1, display: "flex", flexDirection: "column", gap: 14 }}>
      <div style={{ fontSize: 10, color: "var(--dl-text-muted)", fontWeight: 700, letterSpacing: 1 }}>{role.toUpperCase()}</div>
      <div>
        <div style={{ fontWeight: 700, fontSize: 16 }}>{profile.legal_name}</div>
        <div style={{ display: "flex", gap: 8, marginTop: 4, alignItems: "center", flexWrap: "wrap" }}>
          {profile.ticker && <span style={{ fontFamily: "var(--dl-font-mono)", fontSize: 11, color: "var(--dl-gold)" }}>{profile.ticker}</span>}
          <JurisdictionBadge jurisdiction={profile.jurisdiction} />
          {profile.sector && <span style={{ fontSize: 10, color: "var(--dl-text-muted)" }}>{profile.sector}</span>}
        </div>
      </div>

      {/* Key metrics */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
        {fin.enterprise_value_usd_b != null && (
          <div>
            <div style={{ fontSize: 10, color: "var(--dl-text-muted)", marginBottom: 2 }}>ENTERPRISE VALUE</div>
            <div style={{ fontFamily: "var(--dl-font-mono)", fontSize: 14, fontWeight: 700, color: "var(--dl-gold)" }}>${fin.enterprise_value_usd_b}B</div>
          </div>
        )}
        {fin.revenue_usd_m != null && (
          <div>
            <div style={{ fontSize: 10, color: "var(--dl-text-muted)", marginBottom: 2 }}>REVENUE</div>
            <div style={{ fontFamily: "var(--dl-font-mono)", fontSize: 14, fontWeight: 700 }}>
              {fin.revenue_usd_m >= 1000 ? `$${(fin.revenue_usd_m / 1000).toFixed(1)}B` : `$${fin.revenue_usd_m}M`}
            </div>
          </div>
        )}
        {fin.ebitda_margin_pct != null && (
          <div>
            <div style={{ fontSize: 10, color: "var(--dl-text-muted)", marginBottom: 2 }}>EBITDA MARGIN</div>
            <div style={{ fontFamily: "var(--dl-font-mono)", fontSize: 14, fontWeight: 700, color: "var(--dl-teal)" }}>{fin.ebitda_margin_pct}%</div>
          </div>
        )}
        {own.ownership_structure && (
          <div>
            <div style={{ fontSize: 10, color: "var(--dl-text-muted)", marginBottom: 2 }}>OWNERSHIP</div>
            <div style={{ fontSize: 12, fontWeight: 600 }}>{own.ownership_structure}</div>
          </div>
        )}
      </div>

      {/* Key products */}
      {sf.key_products?.length > 0 && (
        <div>
          <div style={{ fontSize: 10, color: "var(--dl-text-muted)", fontWeight: 600, letterSpacing: 0.8, marginBottom: 6 }}>KEY PRODUCTS</div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
            {sf.key_products.slice(0, 6).map((p, i) => (
              <span key={i} style={{ fontSize: 10, padding: "2px 8px", borderRadius: 4, background: "var(--dl-bg-tertiary)", border: "1px solid var(--dl-border)", color: "var(--dl-text-secondary)" }}>{p}</span>
            ))}
          </div>
        </div>
      )}

      {/* Strategic priorities */}
      {sf.strategic_priorities?.length > 0 && (
        <div>
          <div style={{ fontSize: 10, color: "var(--dl-text-muted)", fontWeight: 600, letterSpacing: 0.8, marginBottom: 6 }}>STRATEGIC PRIORITIES</div>
          {sf.strategic_priorities.slice(0, 3).map((p, i) => (
            <div key={i} style={{ fontSize: 11, color: "var(--dl-text-secondary)", display: "flex", gap: 6, marginBottom: 2 }}>
              <span style={{ color: "var(--dl-green)", flexShrink: 0 }}>✓</span>{p}
            </div>
          ))}
        </div>
      )}

      {profile.description && (
        <div style={{ fontSize: 11, color: "var(--dl-text-muted)", lineHeight: 1.5, borderTop: "1px solid var(--dl-border)", paddingTop: 10 }}>
          {profile.description.slice(0, 280)}{profile.description.length > 280 ? "…" : ""}
        </div>
      )}
    </div>
  );
}

export function DeepAnalysis() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  // role=seller means sell-side mode: seller param = seller, buyer param = potential acquirer
  const role     = searchParams.get("role") || "buyer";
  const isSellSide = role === "seller";
  const buyerId  = isSellSide ? searchParams.get("buyer") || "" : searchParams.get("buyer") || "";
  const targetId = isSellSide ? searchParams.get("seller") || "" : searchParams.get("target") || "";

  const [buyerProfile,  setBuyerProfile]  = useState(null);
  const [targetProfile, setTargetProfile] = useState(null);
  const [regulatory,    setRegulatory]    = useState(null);
  const [regLoading,    setRegLoading]    = useState(false);
  const [expandedRows, setExpandedRows]   = useState({});
  const [showMethodology, setShowMethodology] = useState(false);
  const [scoreBreakdown, setScoreBreakdown] = useState(
    JSON.parse(searchParams.get("sb") || "null")
  );
  // For sell-side: score_rationale/ib_metrics stored under buyer company id
  const rationale_id = isSellSide ? buyerId : targetId;
  const [scoreRationale] = useState(() => {
    if (!rationale_id) return null;
    try {
      const stored = sessionStorage.getItem(`dl_score_rationale_${rationale_id}`);
      return stored ? JSON.parse(stored) : null;
    } catch { return null; }
  });
  const [ibMetrics] = useState(() => {
    if (!rationale_id) return null;
    try {
      const stored = sessionStorage.getItem(`dl_ib_metrics_${rationale_id}`);
      return stored ? JSON.parse(stored) : null;
    } catch { return null; }
  });
  const dealScore = parseInt(searchParams.get("ds") || "0", 10);
  const tier      = searchParams.get("tier") || "";
  const verdict   = searchParams.get("verdict") || "";

  // Panel labels vary by role
  const leftLabel  = isSellSide ? "Seller" : "Buyer";
  const rightLabel = isSellSide ? "Potential Acquirer" : "Target";

  useEffect(() => {
    if (targetId) getCompanyProfile(targetId).then(d => setTargetProfile(d)).catch(() => {});
    if (buyerId)  getCompanyProfile(buyerId).then(d  => setBuyerProfile(d)).catch(() => {});
  }, [buyerId, targetId]);

  const runRegulatory = async () => {
    if (!buyerId || !targetId) return;
    setRegLoading(true);
    try {
      const data = await predictRegulatory({
        buyer_company_id: buyerId,
        target_company_id: targetId,
        deal_value_usd_b: targetProfile?.financials?.enterprise_value_usd_b || 1,
      });
      setRegulatory(data);
    } catch {
      // ignore
    } finally {
      setRegLoading(false);
    }
  };

  const VERDICT_COLOR = { APPROACHABLE: "var(--dl-teal)", "NEEDS STRUCTURING": "var(--dl-amber)", COMPLEX: "var(--dl-red)", AVOID: "var(--dl-red)" };

  return (
    <main style={{ padding: 24, display: "flex", flexDirection: "column", gap: 20, maxWidth: 1400, margin: "0 auto", width: "100%" }}>

      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <button onClick={() => navigate(-1)}
          style={{ background: "none", border: "none", color: "var(--dl-text-muted)", cursor: "pointer", fontSize: 13, padding: "4px 8px" }}>
          ← Back
        </button>
        <h2 style={{ fontSize: 20, fontWeight: 700 }}>Deep Analysis</h2>
        {tier && <TierBadge tier={tier} />}
        {verdict && (
          <span style={{ fontSize: 11, fontWeight: 700, color: VERDICT_COLOR[verdict] || "var(--dl-text-muted)", fontFamily: "var(--dl-font-mono)" }}>
            {verdict}
          </span>
        )}
      </div>

      {/* Side-by-side profiles */}
      <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
        <ProfilePanel profile={isSellSide ? targetProfile : buyerProfile}  role={leftLabel} />
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 8, flexShrink: 0 }}>
          <ScoreDial score={dealScore} label="DEAL SCORE" size={80} />
        </div>
        <ProfilePanel profile={isSellSide ? buyerProfile : targetProfile} role={rightLabel} />
      </div>

      {/* Full score breakdown */}
      {scoreBreakdown && (
        <div className="card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
            <div style={{ fontSize: 11, color: "var(--dl-text-muted)", fontWeight: 700, letterSpacing: 1 }}>SCORE BREAKDOWN</div>
            {scoreRationale && (
              <span style={{ fontSize: 10, color: "var(--dl-text-muted)", fontStyle: "italic" }}>Click any row to expand formula</span>
            )}
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {Object.entries(scoreBreakdown).map(([key, val]) => {
              const max = SCORE_MAX[key] || 10;
              const pct = Math.min((val / max) * 100, 100);
              const barColor = pct >= 80 ? "var(--dl-teal)" : pct >= 50 ? "var(--dl-amber)" : "var(--dl-red)";
              const rationale = scoreRationale?.[key];
              const isExpanded = expandedRows[key];
              return (
                <div key={key} style={{ borderBottom: "1px solid var(--dl-border)", paddingBottom: 10 }}>
                  <div
                    style={{ display: "flex", alignItems: "center", gap: 12, cursor: rationale ? "pointer" : "default" }}
                    onClick={() => rationale && setExpandedRows(r => ({ ...r, [key]: !r[key] }))}
                  >
                    <span style={{ fontSize: 11, color: "var(--dl-text-secondary)", width: 220, flexShrink: 0, textTransform: "capitalize" }}>
                      {key.replace(/_/g, " ")}
                    </span>
                    <div style={{ flex: 1, height: 7, background: "var(--dl-border)", borderRadius: 3 }}>
                      <div style={{ height: "100%", width: `${pct}%`, background: barColor, borderRadius: 3, transition: "width 0.4s ease" }} />
                    </div>
                    <span style={{ fontSize: 12, fontFamily: "var(--dl-font-mono)", color: barColor, width: 50, textAlign: "right", flexShrink: 0, fontWeight: 700 }}>
                      {val}/{max}
                    </span>
                    {rationale && (
                      <span style={{ fontSize: 11, color: "var(--dl-text-muted)", flexShrink: 0, width: 16 }}>
                        {isExpanded ? "▲" : "▼"}
                      </span>
                    )}
                  </div>
                  {rationale && isExpanded && (
                    <div style={{
                      marginTop: 10,
                      padding: "10px 14px",
                      background: "var(--dl-bg-tertiary)",
                      borderRadius: 6,
                      borderLeft: `3px solid ${barColor}`,
                    }}>
                      <div style={{ fontSize: 10, color: "var(--dl-text-muted)", fontWeight: 700, letterSpacing: 0.8, marginBottom: 6 }}>
                        SCORING FORMULA & INPUTS
                      </div>
                      {rationale.split("\n").map((line, i) => (
                        <div key={i} style={{
                          fontSize: 11,
                          fontFamily: line.startsWith("Formula:") || line.startsWith("Inputs:") || line.startsWith("= ") ? "var(--dl-font-mono)" : "inherit",
                          color: line.startsWith("Result:") ? barColor : line.startsWith("Formula:") ? "var(--dl-text-primary)" : "var(--dl-text-secondary)",
                          fontWeight: line.startsWith("Result:") ? 700 : 400,
                          marginBottom: 3,
                          lineHeight: 1.5,
                        }}>
                          {line}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {/* Scoring Methodology accordion */}
          <div style={{ marginTop: 16, borderTop: "1px solid var(--dl-border)", paddingTop: 12 }}>
            <button
              onClick={() => setShowMethodology(m => !m)}
              style={{ background: "none", border: "none", cursor: "pointer", color: "var(--dl-text-muted)", fontSize: 11, fontWeight: 600, padding: 0, display: "flex", alignItems: "center", gap: 6 }}
            >
              Scoring Methodology {showMethodology ? "▲" : "▼"}
            </button>
            {showMethodology && (
              <div style={{ marginTop: 10, fontSize: 11, color: "var(--dl-text-secondary)", lineHeight: 1.8 }}>
                <div style={{ fontWeight: 700, color: "var(--dl-text-primary)", marginBottom: 8 }}>DealLens 9-Component M&A Scoring Model (max 100)</div>
                {[
                  ["Strategic Alpha", 24, "Product/capability/geographic synergies via AI feature extraction (GPT-4o-mini). Formula: weighted sum of product_overlap, capability_gap_fill, customer_overlap, channel_fit, geographic_logic, defensive_value."],
                  ["Dealability / Ownership", 16, "Ownership structure, exit mandate, promoter holding. Base 10 for public; adjustments for SOE (floor 3), family-owned (-3), PE-backed with exit vintage (+4), promoter >75% (-5), strategic review (+2), activist (+1)."],
                  ["Financial Health", 14, "EBITDA margin, revenue growth YoY, Net Debt/EBITDA leverage. Base 7; additive adjustments per threshold. Penalises distressed financials; rewards strong growth/low leverage."],
                  ["Execution Complexity", 10, "Inverted score (10 = simplest). Penalties: cross-border (-2), SOE target (-4), large size ratio >0.5x (-2). Private target bonus (+1)."],
                  ["Regulatory Path", 10, "Jurisdiction risk (CN+US: -5, CN: -3, IN cross-border: -1, DE non-EU: -1), cross-border penalty (-1), same-sector horizontal antitrust (-2)."],
                  ["Valuation Premium Burden", 10, "EV/Revenue vs sector median (8 sector benchmarks). Premium ratio ≤0.8x→+3, ≤1.2x→+1, ≤2.0x→-2, >2.0x→-4. EV/EBITDA >25x→-2, >15x→-1, <8x→+2."],
                  ["Size & Funding Feasibility", 10, "Target EV / Buyer EV size ratio (>0.8x→-3, >0.5x→-2, >0.3x→-1, <0.05x→+1). Cash coverage ratio ≥0.5x→+1 (can self-fund), <0.1x→-1 (heavy debt burden)."],
                  ["Process Momentum", 4, "AI signals: strategic_review + advisor_hiring + activist_pressure + divestiture + management_commentary (×0.5), scaled ×0.35. Deterministic flags: strategic_review→+2, activist→+1."],
                  ["Scarcity & Auction Pressure", 2, "Niche sector (semiconductor/defense/aerospace/biotech): max score 2. PE-backed vintage <2020 (exit pressure): max score 2. Base: 1."],
                ].map(([name, max, desc]) => (
                  <div key={name} style={{ marginBottom: 10, paddingLeft: 12, borderLeft: "2px solid var(--dl-border)" }}>
                    <span style={{ fontWeight: 700, color: "var(--dl-text-primary)" }}>{name}</span>
                    <span style={{ color: "var(--dl-text-muted)", fontFamily: "var(--dl-font-mono)", fontSize: 10 }}> (/{max}) </span>
                    <span style={{ color: "var(--dl-text-secondary)" }}>{desc}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Regulatory assessment */}
      <div className="card">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
          <div style={{ fontSize: 11, color: "var(--dl-text-muted)", fontWeight: 700, letterSpacing: 1 }}>REGULATORY ASSESSMENT</div>
          {!regulatory && (
            <button onClick={runRegulatory} disabled={regLoading}
              style={{ padding: "5px 14px", fontSize: 11, fontWeight: 700, background: "var(--dl-teal)", border: "none", color: "#000", borderRadius: 6, cursor: regLoading ? "not-allowed" : "pointer" }}>
              {regLoading ? "Predicting…" : "Run Regulatory Prediction →"}
            </button>
          )}
        </div>
        {regulatory ? (
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
              <div>
                <div style={{ fontSize: 10, color: "var(--dl-text-muted)", marginBottom: 2 }}>OVERALL RISK</div>
                <div style={{ fontWeight: 700, fontSize: 14, color: regulatory.overall_risk_level === "LOW" ? "var(--dl-teal)" : regulatory.overall_risk_level === "MEDIUM" ? "var(--dl-amber)" : "var(--dl-red)" }}>
                  {regulatory.overall_risk_level}
                </div>
              </div>
              <div>
                <div style={{ fontSize: 10, color: "var(--dl-text-muted)", marginBottom: 2 }}>CLEARANCE PROBABILITY</div>
                <div style={{ fontFamily: "var(--dl-font-mono)", fontWeight: 700, fontSize: 14, color: "var(--dl-teal)" }}>
                  {regulatory.clearance_probability_pct}%
                </div>
              </div>
              <div>
                <div style={{ fontSize: 10, color: "var(--dl-text-muted)", marginBottom: 2 }}>EXPECTED TIMELINE</div>
                <div style={{ fontFamily: "var(--dl-font-mono)", fontWeight: 700, fontSize: 14 }}>
                  {regulatory.expected_timeline_months}mo
                </div>
              </div>
            </div>
            {regulatory.rationale && (
              <div style={{ fontSize: 12, color: "var(--dl-text-secondary)", lineHeight: 1.6, borderTop: "1px solid var(--dl-border)", paddingTop: 10 }}>
                {regulatory.rationale}
              </div>
            )}
          </div>
        ) : (
          <div style={{ fontSize: 12, color: "var(--dl-text-muted)" }}>
            Run regulatory prediction to see jurisdictional risk, clearance probability, and expected timeline.
          </div>
        )}
      </div>

      {/* IB Valuation Metrics */}
      {ibMetrics && Object.keys(ibMetrics).length > 0 && (
        <div className="card">
          <div style={{ fontSize: 11, color: "var(--dl-text-muted)", fontWeight: 700, letterSpacing: 1, marginBottom: 14 }}>
            IB VALUATION METRICS
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))", gap: 16 }}>

            {ibMetrics.accretion_dilution && (
              <div style={{ padding: "12px 14px", background: "var(--dl-bg-tertiary)", borderRadius: 8,
                borderLeft: `3px solid ${ibMetrics.accretion_dilution === "ACCRETIVE" ? "var(--dl-green)" : ibMetrics.accretion_dilution === "POTENTIALLY ACCRETIVE" ? "var(--dl-amber)" : "var(--dl-red)"}` }}>
                <div style={{ fontSize: 10, color: "var(--dl-text-muted)", fontWeight: 700, letterSpacing: 0.8, marginBottom: 4 }}>ACCRETION / DILUTION</div>
                <div style={{ fontSize: 13, fontWeight: 700, color: ibMetrics.accretion_dilution === "ACCRETIVE" ? "var(--dl-green)" : ibMetrics.accretion_dilution === "POTENTIALLY ACCRETIVE" ? "var(--dl-amber)" : "var(--dl-red)" }}>
                  {ibMetrics.accretion_dilution}
                </div>
                {ibMetrics.accretion_note && (
                  <div style={{ fontSize: 10, color: "var(--dl-text-muted)", marginTop: 4, lineHeight: 1.4 }}>{ibMetrics.accretion_note}</div>
                )}
              </div>
            )}

            {ibMetrics.fcf_yield_pct != null && (
              <div style={{ padding: "12px 14px", background: "var(--dl-bg-tertiary)", borderRadius: 8, borderLeft: "3px solid var(--dl-teal)" }}>
                <div style={{ fontSize: 10, color: "var(--dl-text-muted)", fontWeight: 700, letterSpacing: 0.8, marginBottom: 4 }}>FCF YIELD</div>
                <div style={{ fontSize: 20, fontWeight: 700, fontFamily: "var(--dl-font-mono)", color: "var(--dl-teal)" }}>{ibMetrics.fcf_yield_pct}%</div>
                {ibMetrics.fcf_yield_note && (
                  <div style={{ fontSize: 10, color: "var(--dl-text-muted)", marginTop: 4, lineHeight: 1.4 }}>{ibMetrics.fcf_yield_note}</div>
                )}
              </div>
            )}

            {ibMetrics.additional_debt_capacity_usd_m != null && (
              <div style={{ padding: "12px 14px", background: "var(--dl-bg-tertiary)", borderRadius: 8, borderLeft: "3px solid var(--dl-blue)" }}>
                <div style={{ fontSize: 10, color: "var(--dl-text-muted)", fontWeight: 700, letterSpacing: 0.8, marginBottom: 4 }}>LEVERAGE HEADROOM</div>
                <div style={{ fontSize: 18, fontWeight: 700, fontFamily: "var(--dl-font-mono)", color: "var(--dl-blue)" }}>
                  ${ibMetrics.additional_debt_capacity_usd_m >= 1000
                    ? (ibMetrics.additional_debt_capacity_usd_m / 1000).toFixed(1) + "B"
                    : ibMetrics.additional_debt_capacity_usd_m.toFixed(0) + "M"}
                </div>
                {ibMetrics.debt_capacity_note && (
                  <div style={{ fontSize: 10, color: "var(--dl-text-muted)", marginTop: 4, lineHeight: 1.4 }}>{ibMetrics.debt_capacity_note}</div>
                )}
              </div>
            )}

            {ibMetrics.implied_control_premium_pct != null && (
              <div style={{ padding: "12px 14px", background: "var(--dl-bg-tertiary)", borderRadius: 8, borderLeft: "3px solid var(--dl-gold)" }}>
                <div style={{ fontSize: 10, color: "var(--dl-text-muted)", fontWeight: 700, letterSpacing: 0.8, marginBottom: 4 }}>IMPLIED CONTROL PREMIUM</div>
                <div style={{ fontSize: 20, fontWeight: 700, fontFamily: "var(--dl-font-mono)", color: "var(--dl-gold)" }}>
                  {ibMetrics.implied_control_premium_pct > 0 ? `+${ibMetrics.implied_control_premium_pct}%` : `${ibMetrics.implied_control_premium_pct}%`}
                </div>
                {ibMetrics.control_premium_note && (
                  <div style={{ fontSize: 10, color: "var(--dl-text-muted)", marginTop: 4, lineHeight: 1.4 }}>{ibMetrics.control_premium_note}</div>
                )}
              </div>
            )}

            {ibMetrics.ev_ebitda_context && (
              <div style={{ padding: "12px 14px", background: "var(--dl-bg-tertiary)", borderRadius: 8, borderLeft: "3px solid var(--dl-purple)" }}>
                <div style={{ fontSize: 10, color: "var(--dl-text-muted)", fontWeight: 700, letterSpacing: 0.8, marginBottom: 4 }}>EV/EBITDA CONTEXT</div>
                <div style={{ fontSize: 11, color: "var(--dl-text-secondary)", lineHeight: 1.5 }}>{ibMetrics.ev_ebitda_context}</div>
              </div>
            )}

            {ibMetrics.deal_size_classification && (
              <div style={{ padding: "12px 14px", background: "var(--dl-bg-tertiary)", borderRadius: 8, borderLeft: "3px solid var(--dl-text-muted)" }}>
                <div style={{ fontSize: 10, color: "var(--dl-text-muted)", fontWeight: 700, letterSpacing: 0.8, marginBottom: 4 }}>DEAL SIZING</div>
                <div style={{ fontSize: 11, color: "var(--dl-text-secondary)", lineHeight: 1.5 }}>{ibMetrics.deal_size_classification}</div>
              </div>
            )}
          </div>
          <div style={{ marginTop: 10, fontSize: 10, color: "var(--dl-text-muted)", fontStyle: "italic" }}>
            IB metrics are estimates based on available financial data. FCF yield uses EBITDA×0.65 approximation. Control premium assumes 30% sector standard. Not financial advice.
          </div>
        </div>
      )}

      {/* Actions */}
      <div style={{ display: "flex", gap: 10 }}>
        {targetId && !isSellSide && (
          <button onClick={() => navigate(`/drafts?company=${targetId}`)}
            style={{ padding: "10px 20px", fontWeight: 700, fontSize: 13, background: "var(--dl-gold)", border: "none", color: "#000", borderRadius: 8, cursor: "pointer" }}>
            Generate Draft →
          </button>
        )}
        {targetId && !isSellSide && (
          <button onClick={() => navigate(`/company/${targetId}`)}
            style={{ padding: "10px 20px", fontWeight: 600, fontSize: 13, background: "var(--dl-bg-elevated)", border: "1px solid var(--dl-border)", color: "var(--dl-text-primary)", borderRadius: 8, cursor: "pointer" }}>
            Full Target Profile
          </button>
        )}
        {isSellSide && buyerId && (
          <button onClick={() => navigate(`/company/${buyerId}`)}
            style={{ padding: "10px 20px", fontWeight: 600, fontSize: 13, background: "var(--dl-bg-elevated)", border: "1px solid var(--dl-border)", color: "var(--dl-text-primary)", borderRadius: 8, cursor: "pointer" }}>
            Full Acquirer Profile
          </button>
        )}
        {isSellSide && targetId && (
          <button onClick={() => navigate(`/company/${targetId}`)}
            style={{ padding: "10px 20px", fontWeight: 600, fontSize: 13, background: "var(--dl-bg-elevated)", border: "1px solid var(--dl-border)", color: "var(--dl-text-primary)", borderRadius: 8, cursor: "pointer" }}>
            Full Seller Profile
          </button>
        )}
      </div>
    </main>
  );
}
