import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { ProcessRoleBadge } from "./ProcessRoleBadge.jsx";
import { ScoreDial } from "./ScoreDial.jsx";
import { TierBadge } from "./TierBadge.jsx";
import { getCompanyNews } from "../api/deallens.js";

const SELL_SIDE_MAX = {
  strategic_need_buyer_urgency: 22,
  ability_to_pay: 16,
  certainty_of_close: 16,
  regulatory_path: 12,
  valuation_tension_potential: 12,
  process_credibility: 8,
  execution_compatibility: 6,
  sponsor_strategic_positioning: 4,
  momentum_market_signaling: 4,
};

export function BuyerCard({ buyer = {}, sellerCompanyId }) {
  const [news, setNews] = useState([]);
  const [expanded, setExpanded] = useState(false);
  const [expandedRows, setExpandedRows] = useState({});
  const navigate = useNavigate();

  useEffect(() => {
    if (!buyer.company_id) return;
    getCompanyNews(buyer.company_id).then(d => {
      if (d?.items?.length) setNews(d.items.slice(0, 2));
    }).catch(() => {});
  }, [buyer.company_id]);

  const sb = buyer.score_breakdown || {};
  const sr = buyer.score_rationale || null;

  const handleDeepAnalysis = () => {
    const params = new URLSearchParams();
    params.set("role", "seller");
    if (sellerCompanyId) params.set("seller", sellerCompanyId);
    params.set("buyer", buyer.company_id);
    params.set("ds", String(buyer.deal_score || 0));
    if (buyer.tier) params.set("tier", buyer.tier);
    if (buyer.dealability_verdict) params.set("verdict", buyer.dealability_verdict);
    if (sb) params.set("sb", JSON.stringify(sb));
    if (sr) {
      sessionStorage.setItem(`dl_score_rationale_${buyer.company_id}`, JSON.stringify(sr));
    }
    if (buyer.ib_metrics) {
      sessionStorage.setItem(`dl_ib_metrics_${buyer.company_id}`, JSON.stringify(buyer.ib_metrics));
    }
    navigate(`/deep-analysis?${params.toString()}`);
  };

  return (
    <div className="card" style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <div style={{ fontFamily: "var(--dl-font-mono)", fontSize: 28, fontWeight: 700, color: "var(--dl-gold)", lineHeight: 1 }}>
            {buyer.discovery_match || `#${String(buyer.rank || 1).padStart(2, "0")}`}
          </div>
          <div style={{ fontWeight: 600, fontSize: 14, marginTop: 6 }}>{buyer.legal_name}</div>
          <div style={{ marginTop: 6, display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
            <ProcessRoleBadge role={buyer.process_role} label={buyer.process_role_label} />
            {buyer.tier && <TierBadge tier={buyer.tier} />}
          </div>
        </div>
        <ScoreDial score={buyer.deal_score || 0} label="SCORE" size={64} />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
        <div>
          <div style={{ fontSize: 10, color: "var(--dl-text-muted)", marginBottom: 2 }}>STRATEGIC NEED</div>
          <div style={{ fontSize: 12, color: "var(--dl-text-secondary)" }}>{buyer.strategic_need || "—"}</div>
        </div>
        <div>
          <div style={{ fontSize: 10, color: "var(--dl-text-muted)", marginBottom: 2 }}>ABILITY TO PAY</div>
          <div style={{ fontSize: 12, fontFamily: "var(--dl-font-mono)", color: "var(--dl-teal)" }}>
            {buyer.ability_to_pay?.label || "—"}
          </div>
        </div>
        <div>
          <div style={{ fontSize: 10, color: "var(--dl-text-muted)", marginBottom: 2 }}>VALUATION TENSION</div>
          <div style={{ fontSize: 12, color: buyer.valuation_tension?.level === "High Potential" ? "var(--dl-green)" : "var(--dl-text-secondary)" }}>
            {buyer.valuation_tension?.level || "—"}
          </div>
        </div>
        <div>
          <div style={{ fontSize: 10, color: "var(--dl-text-muted)", marginBottom: 2 }}>CLOSE CERTAINTY</div>
          <div style={{ fontSize: 12, fontFamily: "var(--dl-font-mono)", color: "var(--dl-text-primary)" }}>
            {buyer.close_certainty_pct != null ? `${buyer.close_certainty_pct}%` : "—"}
          </div>
        </div>
      </div>

      {buyer.regulatory_friction && (
        <div style={{ fontSize: 11, color: "var(--dl-text-muted)", borderTop: "1px solid var(--dl-border)", paddingTop: 10 }}>
          <span style={{ color: "var(--dl-amber)" }}>⚠</span> {buyer.regulatory_friction.reason}
        </div>
      )}

      {buyer.investment_thesis?.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          {buyer.investment_thesis.map((t, i) => (
            <div key={i} style={{ fontSize: 12, color: "var(--dl-text-secondary)", display: "flex", gap: 6 }}>
              <span style={{ color: "var(--dl-green)", flexShrink: 0 }}>✓</span>{t}
            </div>
          ))}
        </div>
      )}

      {buyer.why_not_now?.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          {buyer.why_not_now.map((r, i) => (
            <div key={i} style={{ fontSize: 12, color: "var(--dl-text-secondary)", display: "flex", gap: 6 }}>
              <span style={{ color: "var(--dl-amber)", flexShrink: 0 }}>⚠</span>{r}
            </div>
          ))}
        </div>
      )}

      {buyer.flag_chips?.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
          {buyer.flag_chips.map((chip, i) => (
            <span key={i} style={{
              fontSize: 10, fontWeight: 700, letterSpacing: 0.5,
              color: "var(--dl-teal)", border: "1px solid var(--dl-teal)",
              borderRadius: 4, padding: "1px 6px", fontFamily: "var(--dl-font-mono)",
            }}>
              {chip}
            </span>
          ))}
        </div>
      )}

      {/* Score breakdown toggle */}
      {Object.keys(sb).length > 0 && (
        <div>
          <button
            onClick={() => setExpanded(!expanded)}
            style={{ background: "none", border: "none", color: "var(--dl-text-muted)", cursor: "pointer", fontSize: 11, padding: 0 }}
          >
            Score Breakdown {expanded ? "▲" : "▼"}
          </button>
          {expanded && (
            <div style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 10 }}>
              {sr && <div style={{ fontSize: 10, color: "var(--dl-text-muted)", fontStyle: "italic" }}>Click any row to see formula</div>}
              {Object.entries(sb).map(([key, val]) => {
                const max = SELL_SIDE_MAX[key] || 10;
                const pct = Math.min((val / max) * 100, 100);
                const barColor = pct >= 70 ? "var(--dl-teal)" : pct >= 40 ? "var(--dl-amber)" : "var(--dl-red)";
                const rationale = sr?.[key];
                const isExpanded = expandedRows[key];
                return (
                  <div key={key} style={{ borderBottom: "1px solid var(--dl-border)", paddingBottom: 8 }}>
                    <div
                      style={{ display: "flex", alignItems: "center", gap: 8, cursor: rationale ? "pointer" : "default" }}
                      onClick={() => rationale && setExpandedRows(r => ({ ...r, [key]: !r[key] }))}
                    >
                      <span style={{ fontSize: 10, color: "var(--dl-text-muted)", width: 160, flexShrink: 0, textTransform: "capitalize" }}>
                        {key.replace(/_/g, " ")}
                      </span>
                      <div style={{ flex: 1, height: 4, background: "var(--dl-border)", borderRadius: 2 }}>
                        <div style={{ height: "100%", width: `${pct}%`, background: barColor, borderRadius: 2, transition: "width 0.3s ease" }} />
                      </div>
                      <span style={{ fontSize: 10, fontFamily: "var(--dl-font-mono)", color: barColor, width: 36, textAlign: "right", flexShrink: 0 }}>
                        {val}/{max}
                      </span>
                      {rationale && (
                        <span style={{ fontSize: 10, color: "var(--dl-text-muted)", flexShrink: 0, width: 12 }}>{isExpanded ? "▲" : "▼"}</span>
                      )}
                    </div>
                    {rationale && isExpanded && (
                      <div style={{
                        marginTop: 8, padding: "8px 12px",
                        background: "var(--dl-bg-tertiary)", borderRadius: 6,
                        borderLeft: `3px solid ${barColor}`,
                      }}>
                        {rationale.split("\n").map((line, i) => (
                          <div key={i} style={{
                            fontSize: 10,
                            fontFamily: line.startsWith("Formula:") || line.startsWith("Inputs:") ? "var(--dl-font-mono)" : "inherit",
                            color: line.startsWith("Score ") ? barColor : "var(--dl-text-secondary)",
                            fontWeight: line.startsWith("Score ") ? 700 : 400,
                            marginBottom: 2, lineHeight: 1.5,
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
          )}
        </div>
      )}

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
          onClick={() => navigate(`/company/${buyer.company_id}`)}
          style={{
            flex: 1, padding: "7px 12px", fontSize: 12, fontWeight: 600,
            background: "var(--dl-bg-tertiary)", border: "1px solid var(--dl-border)",
            color: "var(--dl-text-primary)", borderRadius: 6, cursor: "pointer",
          }}
        >
          Open Profile
        </button>
        <button
          onClick={handleDeepAnalysis}
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
