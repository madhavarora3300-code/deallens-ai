import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { TierBadge } from "./TierBadge.jsx";
import { ScoreDial } from "./ScoreDial.jsx";
import { JurisdictionBadge } from "./JurisdictionBadge.jsx";
import { getCompanyNews } from "../api/deallens.js";

// Max points per buy-side scoring component (per spec)
const SCORE_MAX = {
  strategic_alpha: 24,
  dealability_ownership: 16,
  financial_health: 14,
  execution_complexity: 10,
  regulatory_path: 10,
  valuation_premium_burden: 10,
  size_funding_feasibility: 10,
  process_momentum: 4,
  scarcity_auction_pressure: 2,
};

const VERDICT_COLOR = {
  APPROACHABLE: "var(--dl-teal)",
  "NEEDS STRUCTURING": "var(--dl-amber)",
  COMPLEX: "var(--dl-red)",
  AVOID: "var(--dl-red)",
};

const ROUTE_COLOR = {
  friendly_approach: "var(--dl-teal)",
  negotiated_deal: "var(--dl-blue)",
  hostile_or_complex: "var(--dl-red)",
  unclear: "var(--dl-text-muted)",
};

function strategicFitLabel(score) {
  if (score == null) return { label: "—", color: "var(--dl-text-muted)" };
  if (score >= 18) return { label: "High", color: "var(--dl-teal)" };
  if (score >= 12) return { label: "Medium", color: "var(--dl-amber)" };
  return { label: "Low", color: "var(--dl-red)" };
}

function complexityLabel(score) {
  if (score == null) return { label: "—", color: "var(--dl-text-muted)" };
  if (score >= 8) return { label: "Simple", color: "var(--dl-teal)" };
  if (score >= 5) return { label: "Moderate", color: "var(--dl-amber)" };
  return { label: "Complex", color: "var(--dl-red)" };
}

function regulatoryLabel(score) {
  if (score == null) return { label: "—", color: "var(--dl-text-muted)" };
  if (score >= 8) return { label: "Clean", color: "var(--dl-teal)" };
  if (score >= 5) return { label: "Watch", color: "var(--dl-amber)" };
  return { label: "Flagged", color: "var(--dl-red)" };
}

function getScoreReason(key, val, max, target) {
  const pct = max > 0 ? val / max : 0;
  const jx = target.jurisdiction || target.target_jurisdiction || "";
  const ownership = (target.ownership_structure || "").toLowerCase();
  const listing = (target.listing_status || "").toLowerCase();

  switch (key) {
    case "strategic_alpha":
      if (pct >= 0.75) return "Strong sector alignment and product overlap detected";
      if (pct >= 0.5)  return "Partial sector alignment; some capability overlap";
      if (pct >= 0.25) return "Limited overlap — adjacent market or early-stage fit";
      return "No direct sector alignment identified";

    case "dealability_ownership":
      if (ownership.includes("pe") || ownership.includes("private equity")) return "PE-backed — active exit mandate likely";
      if (ownership.includes("public") || listing === "public") return "Public company — standard tender/negotiation path";
      if (ownership.includes("family") || ownership.includes("founder")) return "Family/founder-owned — dealability depends on succession intent";
      if (pct >= 0.7) return "Ownership structure favourable for approach";
      if (pct >= 0.4) return "Moderate dealability — ownership may require structuring";
      return "Complex ownership — low dealability signal";

    case "financial_health":
      if (pct >= 0.8) return "Strong financials: healthy revenue growth and margins";
      if (pct >= 0.5) return "Adequate financial health; some metrics below sector norms";
      if (pct >= 0.25) return "Weak financials — distressed or declining metrics";
      return "Insufficient financial data available";

    case "execution_complexity":
      if (pct >= 0.8) return "Straightforward execution — public entity, standard process";
      if (pct >= 0.5) return "Moderate complexity — some structural or operational hurdles";
      return "High complexity — regulatory, structural, or operational barriers";

    case "regulatory_path":
      if (pct >= 0.8) return "Clean regulatory path — same jurisdiction, no known flags";
      if (pct >= 0.5) return `Cross-border or sector scrutiny likely (${jx || "foreign"})`;
      return "Significant regulatory risk — FDI screening or antitrust concerns";

    case "valuation_premium_burden":
      if (pct >= 0.8) return "Valuation attractive — low premium burden for acquirer";
      if (pct >= 0.5) return "Moderate valuation; premium justified by strategic fit";
      return "High valuation burden — premium may compress deal returns";

    case "size_funding_feasibility":
      if (pct >= 0.8) return "Deal size well within buyer's balance sheet capacity";
      if (pct >= 0.5) return "Feasible with debt financing or equity raise";
      return "Stretches buyer's capacity — consortium or partial stake likely needed";

    case "process_momentum":
      if (val >= 3) return "Active deal process signals detected (advisors, data room)";
      if (val >= 2) return "Early-stage process signals — management/board activity";
      return "No active process signal detected";

    case "scarcity_auction_pressure":
      if (val >= 2) return "Competitive auction dynamics — multiple bidders likely";
      if (val >= 1) return "Some competing interest; moderate auction pressure";
      return "No competing bid pressure identified";

    default:
      return null;
  }
}

export function TargetCard({ target = {}, rank, dealCategory, onOpenProfile, buyerCompanyId }) {
  const [expanded, setExpanded] = useState(false);
  const [news, setNews] = useState([]);
  const navigate = useNavigate();
  const verdict = target.dealability_verdict || "COMPLEX";
  const verdictColor = VERDICT_COLOR[verdict] || "var(--dl-text-muted)";
  const sb = target.score_breakdown || {};

  const strategicFit = strategicFitLabel(sb.strategic_alpha);
  const complexity = complexityLabel(sb.execution_complexity);
  const regulatory = regulatoryLabel(sb.regulatory_path);

  const routeLabel = (target.acquisition_route || "unclear").replace(/_/g, " ");
  const routeColor = ROUTE_COLOR[target.acquisition_route] || "var(--dl-text-muted)";

  useEffect(() => {
    if (!target.company_id) return;
    getCompanyNews(target.company_id).then(d => {
      if (d?.items?.length) setNews(d.items.slice(0, 2));
    }).catch(() => {});
  }, [target.company_id]);

  return (
    <div className="card" style={{ display: "flex", flexDirection: "column", gap: 12 }}>

      {/* Header: rank + company + score dial (mirrors BuyerCard layout) */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          {/* Rank number */}
          <div style={{ fontFamily: "var(--dl-font-mono)", fontSize: 28, fontWeight: 700, color: "var(--dl-gold)", lineHeight: 1 }}>
            {rank != null ? `#${String(rank).padStart(2, "0")}` : ""}
          </div>
          {/* Name + identifiers */}
          <div style={{ fontWeight: 600, fontSize: 14, marginTop: rank != null ? 6 : 0 }}>
            {target.legal_name}
          </div>
          <div style={{ display: "flex", gap: 8, marginTop: 4, alignItems: "center" }}>
            {target.ticker && (
              <span style={{ fontFamily: "var(--dl-font-mono)", fontSize: 11, color: "var(--dl-gold)" }}>
                {target.ticker}
              </span>
            )}
            <JurisdictionBadge jurisdiction={target.jurisdiction} />
            {target.sector && (
              <span style={{ fontSize: 10, color: "var(--dl-text-muted)" }}>{target.sector}</span>
            )}
          </div>
          {/* Tier + route badges */}
          <div style={{ display: "flex", gap: 6, marginTop: 8, flexWrap: "wrap" }}>
            <TierBadge tier={target.tier} />
            {target.acquisition_route && target.acquisition_route !== "unclear" && (
              <span style={{
                fontSize: 10, fontWeight: 700, letterSpacing: 0.8,
                color: routeColor, border: `1px solid ${routeColor}`,
                borderRadius: 4, padding: "2px 8px", fontFamily: "var(--dl-font-mono)",
              }}>
                {routeLabel.toUpperCase()}
              </span>
            )}
            {dealCategory && (
              <span style={{
                fontSize: 10, fontWeight: 700, letterSpacing: 0.8,
                color: "var(--dl-purple)", border: "1px solid var(--dl-purple)",
                borderRadius: 4, padding: "2px 8px", fontFamily: "var(--dl-font-mono)",
              }}>
                {dealCategory.toUpperCase()}
              </span>
            )}
            {target.rationale_category && (
              <span style={{
                fontSize: 10, fontWeight: 700, letterSpacing: 0.6,
                color: "var(--dl-teal)", border: "1px solid var(--dl-teal)",
                borderRadius: 4, padding: "2px 8px", fontFamily: "var(--dl-font-mono)",
                background: "rgba(0,212,170,0.08)",
              }}>
                {target.rationale_category.replace(/_/g, " ")}
              </span>
            )}
          </div>
          {/* Non-obvious match badge */}
          {target.is_non_obvious && (
            <div style={{
              marginTop: 6,
              display: "inline-flex", alignItems: "center", gap: 5,
              fontSize: 9, fontWeight: 800, letterSpacing: 0.8,
              color: "#000", background: "var(--dl-gold)",
              borderRadius: 4, padding: "2px 8px",
              fontFamily: "var(--dl-font-mono)",
            }}>
              ◈ NON-OBVIOUS MATCH
            </div>
          )}
          {/* Why-now signal */}
          {target.why_now && (
            <div style={{ fontSize: 11, color: "var(--dl-text-muted)", fontStyle: "italic", marginTop: 4 }}>
              ⚡ {target.why_now}
            </div>
          )}
        </div>
        <ScoreDial score={target.deal_score || 0} label="DEAL SCORE" size={72} />
      </div>

      {/* Verdict row */}
      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <span style={{ fontSize: 11, fontWeight: 700, color: verdictColor, fontFamily: "var(--dl-font-mono)" }}>
          {verdict}
        </span>
      </div>

      {/* M&A context grid (mirrors sell-side BuyerCard 2x2 grid) */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
        <div>
          <div style={{ fontSize: 10, color: "var(--dl-text-muted)", marginBottom: 2 }}>STRATEGIC FIT</div>
          <div style={{ fontSize: 12, fontWeight: 600, color: strategicFit.color }}>{strategicFit.label}</div>
        </div>
        <div>
          <div style={{ fontSize: 10, color: "var(--dl-text-muted)", marginBottom: 2 }}>DEAL SIZE</div>
          <div style={{ fontSize: 12, fontFamily: "var(--dl-font-mono)", color: "var(--dl-teal)" }}>
            {target.enterprise_value_usd_b ? `$${target.enterprise_value_usd_b}B` : target.revenue_usd_m ? `$${target.revenue_usd_m}M Rev` : "Undisclosed"}
          </div>
        </div>
        <div>
          <div style={{ fontSize: 10, color: "var(--dl-text-muted)", marginBottom: 2 }}>DEAL COMPLEXITY</div>
          <div style={{ fontSize: 12, fontWeight: 600, color: complexity.color }}>{complexity.label}</div>
        </div>
        <div>
          <div style={{ fontSize: 10, color: "var(--dl-text-muted)", marginBottom: 2 }}>REGULATORY PATH</div>
          <div style={{ fontSize: 12, fontWeight: 600, color: regulatory.color }}>{regulatory.label}</div>
        </div>
      </div>

      {/* Non-obvious bridge explanation */}
      {target.is_non_obvious && target.non_obvious_bridge && (
        <div style={{
          padding: "10px 12px",
          background: "rgba(245,200,66,0.06)",
          border: "1px solid rgba(245,200,66,0.25)",
          borderRadius: 6,
          fontSize: 11, color: "var(--dl-text-secondary)", lineHeight: 1.5,
        }}>
          <span style={{ color: "var(--dl-gold)", fontWeight: 700 }}>Strategic Bridge: </span>
          {target.non_obvious_bridge}
        </div>
      )}

      {/* Synergy estimate */}
      {target.estimated_synergy_value_usd_m && (
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <div>
            <div style={{ fontSize: 10, color: "var(--dl-text-muted)", marginBottom: 1 }}>ESTIMATED SYNERGIES</div>
            <div style={{ fontFamily: "var(--dl-font-mono)", fontSize: 13, fontWeight: 700, color: "var(--dl-teal)" }}>
              ${target.estimated_synergy_value_usd_m >= 1000
                ? (target.estimated_synergy_value_usd_m / 1000).toFixed(1) + "B"
                : target.estimated_synergy_value_usd_m + "M"} est.
            </div>
          </div>
        </div>
      )}

      {/* Thesis bullets */}
      {target.investment_thesis?.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          {target.investment_thesis.map((t, i) => (
            <div key={i} style={{ fontSize: 12, color: "var(--dl-text-secondary)", display: "flex", gap: 6 }}>
              <span style={{ color: "var(--dl-green)", flexShrink: 0 }}>✓</span>
              {t}
            </div>
          ))}
        </div>
      )}

      {/* Risk vectors */}
      {target.risk_vectors?.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          {target.risk_vectors.map((r, i) => (
            <div key={i} style={{ fontSize: 12, color: "var(--dl-text-secondary)", display: "flex", gap: 6 }}>
              <span style={{ color: "var(--dl-amber)", flexShrink: 0 }}>⚠</span>
              {r}
            </div>
          ))}
        </div>
      )}

      {/* Flag chips */}
      {target.flag_chips?.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
          {target.flag_chips.map((chip, i) => (
            <span key={i} style={{
              fontSize: 10, fontWeight: 700, letterSpacing: 0.5,
              color: "var(--dl-amber)", border: "1px solid var(--dl-amber)",
              borderRadius: 4, padding: "1px 6px", fontFamily: "var(--dl-font-mono)",
            }}>
              {chip}
            </span>
          ))}
        </div>
      )}

      {/* Precedent deals */}
      {target.precedent_deals && (
        <div style={{ borderTop: "1px solid var(--dl-border)", paddingTop: 10 }}>
          <div style={{ fontSize: 10, color: "var(--dl-text-muted)", fontWeight: 600, letterSpacing: 1, marginBottom: 4 }}>PRECEDENT TRANSACTION</div>
          <div style={{ fontSize: 11, color: "var(--dl-text-secondary)", fontStyle: "italic" }}>
            📎 {target.precedent_deals}
          </div>
        </div>
      )}

      {/* Score breakdown toggle */}
      {target.score_breakdown && Object.keys(target.score_breakdown).length > 0 && (
        <div>
          <button
            onClick={() => setExpanded(!expanded)}
            style={{ background: "none", border: "none", color: "var(--dl-text-muted)", cursor: "pointer", fontSize: 11, padding: 0 }}
          >
            Score Breakdown {expanded ? "▲" : "▼"}
          </button>
          {expanded && (
            <div style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 10 }}>
              {Object.entries(target.score_breakdown).map(([key, val]) => {
                const max = SCORE_MAX[key] || 10;
                const pct = Math.min((val / max) * 100, 100);
                const barColor = pct >= 80 ? "var(--dl-teal)" : pct >= 50 ? "var(--dl-amber)" : "var(--dl-red)";
                const reason = getScoreReason(key, val, max, target);
                return (
                  <div key={key}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <span style={{ fontSize: 10, color: "var(--dl-text-muted)", width: 160, flexShrink: 0, textTransform: "capitalize" }}>
                        {key.replace(/_/g, " ")}
                      </span>
                      <div style={{ flex: 1, height: 4, background: "var(--dl-border)", borderRadius: 2 }}>
                        <div style={{ height: "100%", width: `${pct}%`, background: barColor, borderRadius: 2, transition: "width 0.3s ease" }} />
                      </div>
                      <span style={{ fontSize: 10, fontFamily: "var(--dl-font-mono)", color: barColor, width: 36, textAlign: "right", flexShrink: 0 }}>
                        {val}/{max}
                      </span>
                    </div>
                    {reason && (
                      <div style={{ fontSize: 10, color: "var(--dl-text-muted)", marginTop: 2, paddingLeft: 168, fontStyle: "italic" }}>
                        {reason}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Recent news */}
      {news.length > 0 && (
        <div style={{ borderTop: "1px solid var(--dl-border)", paddingTop: 10 }}>
          <div style={{ fontSize: 10, color: "var(--dl-text-muted)", fontWeight: 600, letterSpacing: 1, marginBottom: 6 }}>RECENT NEWS</div>
          {news.map((item, i) => (
            <div key={i} style={{ fontSize: 11, color: "var(--dl-text-secondary)", marginBottom: 4, display: "flex", gap: 6 }}>
              <span style={{
                fontSize: 9, fontWeight: 700, padding: "1px 5px", borderRadius: 3,
                background: item.sentiment === "positive" ? "rgba(0,212,170,0.15)" : item.sentiment === "negative" ? "rgba(239,68,68,0.15)" : "var(--dl-bg-tertiary)",
                color: item.sentiment === "positive" ? "var(--dl-teal)" : item.sentiment === "negative" ? "var(--dl-red)" : "var(--dl-text-muted)",
                flexShrink: 0, alignSelf: "flex-start", marginTop: 1,
              }}>
                {item.sentiment?.toUpperCase() || "—"}
              </span>
              <span>{item.headline}</span>
            </div>
          ))}
        </div>
      )}

      {/* Actions */}
      <div style={{ display: "flex", gap: 8, marginTop: 4 }}>
        <button
          onClick={() => navigate(`/company/${target.company_id}`)}
          style={{
            flex: 1, padding: "7px 12px", fontSize: 12, fontWeight: 600,
            background: "var(--dl-bg-tertiary)", border: "1px solid var(--dl-border)",
            color: "var(--dl-text-primary)", borderRadius: 6, cursor: "pointer",
          }}
        >
          Open Profile
        </button>
        <button
          onClick={() => {
            const params = new URLSearchParams();
            if (buyerCompanyId) params.set("buyer", buyerCompanyId);
            params.set("target", target.company_id);
            params.set("ds", String(target.deal_score || 0));
            if (target.tier) params.set("tier", target.tier);
            if (target.dealability_verdict) params.set("verdict", target.dealability_verdict);
            if (target.score_breakdown) params.set("sb", JSON.stringify(target.score_breakdown));
            // Store score_rationale + ib_metrics in sessionStorage (too large for URL params)
            if (target.score_rationale) {
              sessionStorage.setItem(
                `dl_score_rationale_${target.company_id}`,
                JSON.stringify(target.score_rationale)
              );
            }
            if (target.ib_metrics) {
              sessionStorage.setItem(
                `dl_ib_metrics_${target.company_id}`,
                JSON.stringify(target.ib_metrics)
              );
            }
            navigate(`/deep-analysis?${params.toString()}`);
          }}
          style={{
            flex: 1, padding: "7px 12px", fontSize: 12, fontWeight: 600,
            background: "var(--dl-teal)", border: "none",
            color: "#000", borderRadius: 6, cursor: "pointer",
          }}
        >
          Deep Analysis →
        </button>
      </div>
    </div>
  );
}
