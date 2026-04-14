import React, { useState } from "react";
import { predictRegulatory } from "../api/deallens.js";
import { RegulatoryDial } from "../components/RegulatoryDial.jsx";
import { SearchBar } from "../components/SearchBar.jsx";
import { SkeletonLoader } from "../components/SkeletonLoader.jsx";
import { useCompanySearch } from "../hooks/useCompanySearch.js";

const STATUS_COLOR = { green: "var(--dl-green)", amber: "var(--dl-amber)", red: "var(--dl-red)" };
const FLAG_COLOR = {
  "INDIRECT HOLDING": "var(--dl-amber)",
  "TAX HAVEN FLAG": "var(--dl-red)",
  CLEAN: "var(--dl-green)",
};
const OUTCOME_COLOR = {
  APPROVED: "var(--dl-green)",
  CLEARED: "var(--dl-green)",
  INITIALLY_BLOCKED_THEN_REMEDIED: "var(--dl-amber)",
  ABANDONED: "var(--dl-red)",
  BLOCKED: "var(--dl-red)",
};

export function RegulatoryLens() {
  const [companyA, setCompanyA] = useState(null);
  const [companyB, setCompanyB] = useState(null);
  const [dealSize, setDealSize] = useState("");
  const [dealType, setDealType] = useState("acquisition");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const searchA = useCompanySearch();
  const searchB = useCompanySearch();

  const handleSearchA = async (q) => {
    const d = await searchA.search(q);
    if (d?.resolved) setCompanyA(d.resolved);
  };

  const handleSearchB = async (q) => {
    const d = await searchB.search(q);
    if (d?.resolved) setCompanyB(d.resolved);
  };

  const handlePredict = async () => {
    if (!companyA || !companyB) return;
    setLoading(true);
    setError(null);
    try {
      const data = await predictRegulatory({
        company_a_id: companyA.company_id,
        company_b_id: companyB.company_id,
        deal_size_usd_b: parseFloat(dealSize) || 0,
        deal_type: dealType,
      });
      setResult(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <main style={{ padding: 24, display: "flex", flexDirection: "column", gap: 24, maxWidth: 1200, margin: "0 auto", width: "100%" }}>
      <h2 style={{ fontSize: 20, fontWeight: 700 }}>Regulatory Lens</h2>

      {/* Input row */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr auto auto auto", gap: 12, alignItems: "start" }}>
        <div>
          <div style={{ fontSize: 11, color: "var(--dl-text-muted)", marginBottom: 6 }}>COMPANY A</div>
          <SearchBar onSearch={handleSearchA} loading={searchA.loading} placeholder="Buyer / Company A..." />
          {companyA && <div style={{ fontSize: 11, color: "var(--dl-teal)", marginTop: 4 }}>✓ {companyA.legal_name}</div>}
        </div>
        <div>
          <div style={{ fontSize: 11, color: "var(--dl-text-muted)", marginBottom: 6 }}>COMPANY B</div>
          <SearchBar onSearch={handleSearchB} loading={searchB.loading} placeholder="Target / Company B..." />
          {companyB && <div style={{ fontSize: 11, color: "var(--dl-teal)", marginTop: 4 }}>✓ {companyB.legal_name}</div>}
        </div>
        <div>
          <div style={{ fontSize: 11, color: "var(--dl-text-muted)", marginBottom: 6 }}>DEAL SIZE ($B)</div>
          <input
            type="number"
            value={dealSize}
            onChange={(e) => setDealSize(e.target.value)}
            placeholder="25"
            style={{
              padding: "12px", background: "var(--dl-bg-elevated)", border: "1px solid var(--dl-border-bright)",
              borderRadius: 8, color: "var(--dl-text-primary)", fontSize: 14, width: 100, outline: "none",
            }}
          />
        </div>
        <div>
          <div style={{ fontSize: 11, color: "var(--dl-text-muted)", marginBottom: 6 }}>TYPE</div>
          <select
            value={dealType}
            onChange={(e) => setDealType(e.target.value)}
            style={{
              padding: "12px", background: "var(--dl-bg-elevated)", border: "1px solid var(--dl-border)",
              borderRadius: 8, color: "var(--dl-text-primary)", fontSize: 13, fontFamily: "var(--dl-font-sans)",
            }}
          >
            <option value="acquisition">Acquisition</option>
            <option value="merger">Merger</option>
            <option value="minority_stake">Minority Stake</option>
          </select>
        </div>
        <div style={{ paddingTop: 22 }}>
          <button
            onClick={handlePredict}
            disabled={loading || !companyA || !companyB}
            style={{
              padding: "12px 20px", fontWeight: 700, fontSize: 13,
              background: (!companyA || !companyB) ? "var(--dl-bg-elevated)" : "var(--dl-teal)",
              color: (!companyA || !companyB) ? "var(--dl-text-muted)" : "#000",
              border: "none", borderRadius: 8, cursor: (!companyA || !companyB) ? "not-allowed" : "pointer",
              whiteSpace: "nowrap",
            }}
          >
            {loading ? "Analysing..." : "Predict →"}
          </button>
        </div>
      </div>

      {error && <div style={{ color: "var(--dl-red)", fontSize: 13 }}>{error}</div>}

      {loading && (
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {[1, 2, 3].map(i => <SkeletonLoader key={i} height={60} />)}
        </div>
      )}

      {result && !loading && (
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>

          {/* Risk dial + summary + critical status indicators */}
          <div className="card" style={{ display: "flex", gap: 24, alignItems: "flex-start" }}>
            <RegulatoryDial score={result.jurisdictional_risk_score} />
            <div style={{ flex: 1 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 4 }}>
                <div style={{ fontWeight: 700, fontSize: 16 }}>{result.risk_label}</div>
                {result.processing_depth && (
                  <span style={{ fontSize: 10, color: "var(--dl-text-muted)", fontFamily: "var(--dl-font-mono)" }}>
                    {result.processing_depth}
                  </span>
                )}
              </div>
              <div style={{ color: "var(--dl-text-secondary)", fontSize: 13, marginBottom: 12 }}>
                {result.rationale || result.risk_description}
              </div>
              <div style={{ display: "flex", gap: 20, fontSize: 12, fontFamily: "var(--dl-font-mono)", marginBottom: 14 }}>
                <span>Clearance: <strong style={{ color: "var(--dl-teal)" }}>{result.overall_clearance_probability_pct}%</strong></span>
                <span>P50 close: <strong>{result.expected_timeline_months || result.p50_close_months} mo</strong></span>
                {result.p80_close_months && (
                  <span>P80 close: <strong>{result.p80_close_months} mo</strong></span>
                )}
                {result.critical_path_authority && (
                  <span>Critical path: <strong style={{ color: "var(--dl-amber)" }}>{result.critical_path_authority}</strong></span>
                )}
              </div>

              {/* Critical status indicators */}
              {result.critical_status_indicators && (
                <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
                  {Object.entries(result.critical_status_indicators).map(([key, ind]) => (
                    <div key={key} style={{
                      display: "flex", alignItems: "center", gap: 6, padding: "5px 10px",
                      background: "var(--dl-bg-tertiary)", borderRadius: 6,
                      border: `1px solid ${STATUS_COLOR[ind.color] || "var(--dl-border)"}22`,
                    }}>
                      <div style={{
                        width: 8, height: 8, borderRadius: "50%",
                        background: STATUS_COLOR[ind.color] || "var(--dl-text-muted)",
                        flexShrink: 0,
                      }} />
                      <div>
                        <div style={{ fontSize: 10, color: "var(--dl-text-muted)", fontWeight: 600 }}>
                          {key.replace(/_/g, " ").toUpperCase()}
                        </div>
                        <div style={{ fontSize: 11, color: "var(--dl-text-primary)" }}>{ind.detail}</div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Risk rationale chips */}
            {result.risk_rationale_chips?.length > 0 && (
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                <div style={{ fontSize: 10, color: "var(--dl-text-muted)", fontWeight: 600, letterSpacing: 1 }}>RISK SIGNALS</div>
                {result.risk_rationale_chips.map((chip, i) => (
                  <span key={i} style={{
                    fontSize: 10, fontWeight: 700, color: "var(--dl-amber)",
                    border: "1px solid var(--dl-amber)", borderRadius: 4,
                    padding: "2px 8px", fontFamily: "var(--dl-font-mono)", whiteSpace: "nowrap",
                  }}>
                    {chip}
                  </span>
                ))}
              </div>
            )}
          </div>

          {/* Sanctions alerts */}
          {result.sanctions_alerts?.length > 0 && (
            <div style={{
              border: "1px solid var(--dl-red)", borderRadius: 10, padding: 16,
              background: "rgba(239,68,68,0.06)",
            }}>
              <div style={{ fontSize: 11, color: "var(--dl-red)", letterSpacing: 1, fontWeight: 700, marginBottom: 10 }}>
                ⚠ SANCTIONS ALERTS
              </div>
              {result.sanctions_alerts.map((alert, i) => (
                <div key={i} style={{ display: "flex", gap: 10, marginBottom: i < result.sanctions_alerts.length - 1 ? 10 : 0 }}>
                  <span style={{
                    fontSize: 10, fontWeight: 700, padding: "2px 6px",
                    background: alert.severity === "HIGH" ? "var(--dl-red)" : "var(--dl-amber)",
                    color: "#000", borderRadius: 4, flexShrink: 0, alignSelf: "flex-start",
                  }}>
                    {alert.severity}
                  </span>
                  <span style={{ fontSize: 12, color: "var(--dl-text-secondary)" }}>{alert.message}</span>
                </div>
              ))}
            </div>
          )}

          {/* FDI concerns */}
          {result.fdi_concerns?.length > 0 && (
            <div className="card">
              <div style={{ fontSize: 11, color: "var(--dl-text-muted)", letterSpacing: 1, fontWeight: 600, marginBottom: 10 }}>FDI CONCERNS</div>
              {result.fdi_concerns.map((concern, i) => (
                <div key={i} style={{ display: "flex", gap: 8, marginBottom: 6, fontSize: 13 }}>
                  <span style={{ color: "var(--dl-amber)", flexShrink: 0 }}>›</span>
                  <span style={{ color: "var(--dl-text-secondary)" }}>{concern}</span>
                </div>
              ))}
            </div>
          )}

          {/* Two-column: Authority table + Ownership control */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>

            {/* Authority table */}
            {result.authorities?.length > 0 && (
              <div className="card">
                <div style={{ fontSize: 11, color: "var(--dl-text-muted)", letterSpacing: 1, fontWeight: 600, marginBottom: 12 }}>REGULATORY AUTHORITIES</div>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                  <thead>
                    <tr style={{ color: "var(--dl-text-muted)", fontSize: 10, letterSpacing: 1 }}>
                      <th style={{ textAlign: "left", padding: "4px 8px" }}>AUTHORITY</th>
                      <th style={{ textAlign: "center", padding: "4px 8px" }}>TYPE</th>
                      <th style={{ textAlign: "right", padding: "4px 8px" }}>P1 WKS</th>
                      <th style={{ textAlign: "right", padding: "4px 8px" }}>CLEARANCE</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.authorities.map((a, i) => (
                      <tr key={i} style={{ borderTop: "1px solid var(--dl-border)" }}>
                        <td style={{ padding: "8px 8px" }}>
                          <div>{a.name}</div>
                          {a.key_concerns?.length > 0 && (
                            <div style={{ fontSize: 10, color: "var(--dl-text-muted)", marginTop: 2 }}>
                              {a.key_concerns.slice(0, 2).join(" · ")}
                            </div>
                          )}
                        </td>
                        <td style={{ padding: "8px 8px", textAlign: "center" }}>
                          <span style={{ fontSize: 10, color: a.type === "MANDATORY" ? "var(--dl-red)" : "var(--dl-text-muted)", fontWeight: 700 }}>
                            {a.type}
                          </span>
                        </td>
                        <td style={{ padding: "8px 8px", textAlign: "right", fontFamily: "var(--dl-font-mono)" }}>{a.phase1_weeks}</td>
                        <td style={{ padding: "8px 8px", textAlign: "right", fontFamily: "var(--dl-font-mono)" }}>
                          <span style={{ color: a.clearance_probability_pct >= 70 ? "var(--dl-teal)" : a.clearance_probability_pct >= 50 ? "var(--dl-amber)" : "var(--dl-red)" }}>
                            {a.clearance_probability_pct}%
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* Ownership control analysis */}
            {result.ownership_control_analysis?.length > 0 && (
              <div className="card">
                <div style={{ fontSize: 11, color: "var(--dl-text-muted)", letterSpacing: 1, fontWeight: 600, marginBottom: 12 }}>OWNERSHIP CONTROL ANALYSIS</div>
                <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                  {result.ownership_control_analysis.map((entity, i) => (
                    <div key={i} style={{
                      padding: "10px 12px", background: "var(--dl-bg-tertiary)",
                      borderRadius: 8, border: "1px solid var(--dl-border)",
                    }}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 4 }}>
                        <div style={{ fontWeight: 600, fontSize: 13 }}>{entity.holding_entity}</div>
                        <span style={{
                          fontSize: 10, fontWeight: 700, fontFamily: "var(--dl-font-mono)",
                          color: FLAG_COLOR[entity.flag] || "var(--dl-text-muted)",
                          border: `1px solid ${FLAG_COLOR[entity.flag] || "var(--dl-border)"}`,
                          borderRadius: 4, padding: "1px 6px",
                        }}>
                          {entity.flag}
                        </span>
                      </div>
                      <div style={{ fontSize: 11, color: "var(--dl-text-muted)", marginBottom: 4 }}>{entity.structure}</div>
                      <div style={{ display: "flex", gap: 16, fontSize: 11, fontFamily: "var(--dl-font-mono)" }}>
                        <span style={{ color: "var(--dl-gold)" }}>{entity.stake_pct}%</span>
                        <span style={{ color: "var(--dl-text-secondary)" }}>{entity.control_rights}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Precedent deals */}
          {result.precedent_deals?.length > 0 && (
            <div className="card">
              <div style={{ fontSize: 11, color: "var(--dl-text-muted)", letterSpacing: 1, fontWeight: 600, marginBottom: 12 }}>PRECEDENT DEALS</div>
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                {result.precedent_deals.map((deal, i) => (
                  <div key={i} style={{
                    display: "grid", gridTemplateColumns: "auto 1fr auto",
                    gap: 12, alignItems: "center", padding: "10px 0",
                    borderTop: i === 0 ? "none" : "1px solid var(--dl-border)",
                  }}>
                    <div style={{ fontFamily: "var(--dl-font-mono)", color: "var(--dl-text-muted)", fontSize: 12 }}>{deal.year}</div>
                    <div>
                      <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 2 }}>
                        {deal.buyer} → {deal.target}
                      </div>
                      <div style={{ fontSize: 11, color: "var(--dl-text-muted)" }}>{deal.similarity_reason}</div>
                    </div>
                    <span style={{
                      fontSize: 10, fontWeight: 700, padding: "2px 8px",
                      color: OUTCOME_COLOR[deal.outcome] || "var(--dl-text-muted)",
                      border: `1px solid ${OUTCOME_COLOR[deal.outcome] || "var(--dl-border)"}`,
                      borderRadius: 4, fontFamily: "var(--dl-font-mono)", whiteSpace: "nowrap",
                    }}>
                      {deal.outcome?.replace(/_/g, " ")}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Recommended actions */}
          {result.recommended_actions?.length > 0 && (
            <div className="card">
              <div style={{ fontSize: 11, color: "var(--dl-text-muted)", letterSpacing: 1, fontWeight: 600, marginBottom: 12 }}>RECOMMENDED ACTIONS</div>
              {result.recommended_actions.map((action, i) => (
                <div key={i} style={{ display: "flex", gap: 12, marginBottom: 8, fontSize: 13 }}>
                  <span style={{ color: "var(--dl-teal)", fontFamily: "var(--dl-font-mono)", fontWeight: 700, width: 20 }}>{i + 1}.</span>
                  <span style={{ color: "var(--dl-text-secondary)" }}>{action}</span>
                </div>
              ))}
            </div>
          )}

          {/* Source rationale */}
          {result.source_rationale?.length > 0 && (
            <div className="card">
              <div style={{ fontSize: 11, color: "var(--dl-text-muted)", letterSpacing: 1, fontWeight: 600, marginBottom: 10 }}>SOURCE RATIONALE</div>
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {result.source_rationale.map((src, i) => (
                  <div key={i} style={{ display: "flex", gap: 12, fontSize: 12 }}>
                    <span style={{ color: "var(--dl-text-muted)", width: 120, flexShrink: 0 }}>{src.source_name}</span>
                    <span style={{ color: "var(--dl-text-secondary)" }}>{src.detail}</span>
                    {src.date && <span style={{ color: "var(--dl-text-muted)", fontFamily: "var(--dl-font-mono)", fontSize: 10 }}>{src.date}</span>}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Footer metadata */}
          <div style={{ display: "flex", gap: 20, fontSize: 11, color: "var(--dl-text-muted)", fontFamily: "var(--dl-font-mono)", paddingTop: 4 }}>
            {result.legal_confidence && <span>Legal confidence: {result.legal_confidence}</span>}
            {result.coverage_alpha_pct && <span>Coverage α: {result.coverage_alpha_pct}%</span>}
            {result.entity_type && <span>Entity type: {result.entity_type}</span>}
            {result.jurisdiction_pair && <span>{result.jurisdiction_pair}</span>}
          </div>

        </div>
      )}
    </main>
  );
}
