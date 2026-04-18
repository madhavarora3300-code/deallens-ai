import React, { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { startSellSideDiscovery, getDiscoveryJobStatus } from "../api/deallens.js";
import { BuyerCard } from "../components/BuyerCard.jsx";
import { SkeletonLoader } from "../components/SkeletonLoader.jsx";
import { DiscoveryLoadingScreen } from "../components/DiscoveryLoadingScreen.jsx";

const OBJECTIVES = [
  "maximize_price", "maximize_close_certainty", "balanced_auction",
  "strategic_only", "sponsor_backstop", "cross_border_expansion_sale",
];

const ARCH_ROLES = [
  { key: "must_contact_strategic", label: "Must Contact",      color: "var(--dl-teal)" },
  { key: "price_anchors",          label: "Price Anchors",     color: "var(--dl-gold)" },
  { key: "certainty_anchors",      label: "Certainty Anchors", color: "var(--dl-green)" },
  { key: "tension_creators",       label: "Tension Creators",  color: "var(--dl-amber)" },
  { key: "sponsor_floor",          label: "Sponsor Floor",     color: "var(--dl-blue)" },
  { key: "do_not_approach",        label: "Do Not Approach",   color: "var(--dl-red)" },
];

// ---------- sessionStorage helpers ----------
const SS_KEY_SELL = (sellerId) => `dl_sellside_${sellerId}`;

function saveSellCache(sellerId, data) {
  try { sessionStorage.setItem(SS_KEY_SELL(sellerId), JSON.stringify(data)); } catch (_) {}
}

function loadSellCache(sellerId) {
  try {
    const raw = sessionStorage.getItem(SS_KEY_SELL(sellerId));
    return raw ? JSON.parse(raw) : null;
  } catch (_) { return null; }
}
// --------------------------------------------

export function SellSideDiscovery() {
  const [searchParams] = useSearchParams();
  const sellerCompanyId = searchParams.get("seller") || "";

  const cached = sellerCompanyId ? loadSellCache(sellerCompanyId) : null;

  const [results, setResults] = useState(cached?.results || null);
  const [loading, setLoading] = useState(false);
  const [loadingPhase, setLoadingPhase] = useState("");
  const [error, setError] = useState(null);
  const [objective, setObjective] = useState(cached?.objective || "maximize_price");
  const [sellerName, setSellerName] = useState(cached?.sellerName || "");
  const [sellerSector, setSellerSector] = useState("");
  const pollRef = useRef(null);

  const stopPoll = () => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
  };

  useEffect(() => () => stopPoll(), []);

  const runDiscovery = async () => {
    if (!sellerCompanyId) return;
    stopPoll();
    setLoading(true);
    setLoadingPhase("queued");
    setError(null);
    setResults(null);
    try {
      const { job_id } = await startSellSideDiscovery({
        seller_company_id: sellerCompanyId,
        process_objective: objective,
        filters: {},
        limit: 25,
      });

      setLoadingPhase("running");
      pollRef.current = setInterval(async () => {
        try {
          const status = await getDiscoveryJobStatus(job_id);
          if (status.status === "complete") {
            stopPoll();
            const data = status.result;
            setResults(data);
            setLoading(false);
            setLoadingPhase("");
            const name = data?.seller_name || "";
            if (name) setSellerName(name);
            saveSellCache(sellerCompanyId, { results: data, objective, sellerName: name });
          } else if (status.status === "failed") {
            stopPoll();
            setError(status.error || "Discovery failed");
            setLoading(false);
            setLoadingPhase("");
          } else if (status.status === "running") {
            setLoadingPhase("scoring");
          }
        } catch (_) {
          // Network blip — keep polling
        }
      }, 3000);
    } catch (e) {
      stopPoll();
      setError(e.message);
      setLoading(false);
      setLoadingPhase("");
    }
  };

  return (
    <main style={{ padding: 24, display: "flex", flexDirection: "column", gap: 20, maxWidth: 1400, margin: "0 auto", width: "100%" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h2 style={{ fontSize: 20, fontWeight: 700 }}>Sell-Side Discovery</h2>
      </div>

      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
        <select
          value={objective}
          onChange={(e) => setObjective(e.target.value)}
          style={{
            padding: "8px 12px", background: "var(--dl-bg-elevated)", border: "1px solid var(--dl-border)",
            borderRadius: 6, color: "var(--dl-text-primary)", fontSize: 12, fontFamily: "var(--dl-font-sans)",
          }}
        >
          {OBJECTIVES.map((o) => (
            <option key={o} value={o}>{o.replace(/_/g, " ")}</option>
          ))}
        </select>
        <button
          onClick={runDiscovery}
          disabled={loading || !sellerCompanyId}
          style={{
            padding: "8px 20px", fontWeight: 700, fontSize: 13,
            background: loading ? "var(--dl-bg-elevated)" : "var(--dl-gold)",
            color: loading ? "var(--dl-text-muted)" : "#000",
            border: "none", borderRadius: 8, cursor: loading ? "not-allowed" : "pointer",
          }}
        >
          {loading ? "Analysing..." : "Find Buyers →"}
        </button>
        {!sellerCompanyId && (
          <span style={{ fontSize: 12, color: "var(--dl-amber)" }}>
            Search a company first to set as seller
          </span>
        )}
      </div>

      {error && <div style={{ color: "var(--dl-red)", fontSize: 13 }}>{error}</div>}

      {/* Animated loading screen */}
      {loading && (
        <DiscoveryLoadingScreen
          mode="sell_side"
          anchorName={sellerName}
          strategyHint={objective}
          anchorSector={sellerSector}
          statusPhase={loadingPhase}
        />
      )}

      {results && !loading && (
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>

          {/* Seller context strip */}
          {(results.seller_name || results.seller_context) && (
            <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
              <div className="card" style={{ flex: 1, minWidth: 200 }}>
                <div style={{ fontSize: 11, color: "var(--dl-text-muted)", marginBottom: 4 }}>SELLER</div>
                <div style={{ fontWeight: 700, fontSize: 15 }}>{results.seller_name}</div>
                {results.seller_context?.enterprise_value_usd_b && (
                  <div style={{ fontSize: 12, color: "var(--dl-text-secondary)", marginTop: 4 }}>
                    EV: <span style={{ fontFamily: "var(--dl-font-mono)", color: "var(--dl-gold)" }}>
                      ${results.seller_context.enterprise_value_usd_b}B
                    </span>
                  </div>
                )}
                {results.seller_context?.process_stage && (
                  <div style={{ fontSize: 11, color: "var(--dl-text-muted)", marginTop: 2 }}>
                    {results.seller_context.process_stage}
                  </div>
                )}
              </div>
              {results.seller_context?.target_valuation_range_low_b && (
                <div className="card" style={{ flex: 1, minWidth: 220 }}>
                  <div style={{ fontSize: 11, color: "var(--dl-text-muted)", marginBottom: 4 }}>TARGET VALUATION RANGE</div>
                  <div style={{ fontFamily: "var(--dl-font-mono)", fontWeight: 700, fontSize: 20, color: "var(--dl-teal)" }}>
                    ${results.seller_context.target_valuation_range_low_b}B – ${results.seller_context.target_valuation_range_high_b}B
                  </div>
                </div>
              )}
              {results.buyers?.length > 0 && (
                <div className="card" style={{ flex: 1, minWidth: 140 }}>
                  <div style={{ fontSize: 11, color: "var(--dl-text-muted)", marginBottom: 4 }}>BUYERS RANKED</div>
                  <div style={{ fontFamily: "var(--dl-font-mono)", fontWeight: 700, fontSize: 24, color: "var(--dl-text-primary)" }}>
                    {results.buyers.length}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Process architecture */}
          {results.process_architecture && ARCH_ROLES.some(r => results.process_architecture[r.key]?.length > 0) && (
            <div className="card">
              <div style={{ fontSize: 11, color: "var(--dl-text-muted)", letterSpacing: 1, fontWeight: 600, marginBottom: 14 }}>
                PROCESS ARCHITECTURE
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(190px, 1fr))", gap: 10 }}>
                {ARCH_ROLES.map(({ key, label, color }) => {
                  const names = results.process_architecture[key];
                  if (!names?.length) return null;
                  return (
                    <div key={key} style={{
                      padding: "10px 12px", background: "var(--dl-bg-tertiary)",
                      borderRadius: 8, border: `1px solid ${color}33`,
                    }}>
                      <div style={{ fontSize: 10, fontWeight: 700, color, letterSpacing: 1, marginBottom: 8 }}>
                        {label.toUpperCase()}
                      </div>
                      {names.map((name, i) => (
                        <div key={i} style={{ fontSize: 12, color: "var(--dl-text-secondary)", marginBottom: 3, display: "flex", gap: 6 }}>
                          <span style={{ color, flexShrink: 0 }}>›</span>
                          <span>{name}</span>
                        </div>
                      ))}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Buyer cards */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(380px, 1fr))", gap: 16 }}>
            {loading
              ? [1, 2, 3].map(i => <SkeletonLoader key={i} height={280} borderRadius={10} />)
              : (results.buyers || []).map((b, i) => {
                  const sb = b.score_breakdown || {};
                  const snScore = sb.strategic_need_buyer_urgency ?? 0;
                  const atpScore = sb.ability_to_pay ?? 0;
                  const vtScore = sb.valuation_tension_potential ?? 0;
                  const cocScore = sb.certainty_of_close ?? 0;

                  const normalized = {
                    ...b,
                    company_id: b.company_id || b.buyer_company_id,
                    legal_name: b.legal_name || b.buyer_legal_name || b.buyer_display_name,
                    ticker: b.ticker || b.buyer_ticker,
                    jurisdiction: b.jurisdiction || b.buyer_jurisdiction,
                    rank: i + 1,
                    deal_score: b.deal_score ?? b.buyer_deal_score ?? 0,
                    score_breakdown: sb,
                    score_rationale: b.score_rationale || null,
                    ib_metrics: b.ib_metrics || null,
                    investment_thesis: b.investment_thesis || (b.rationale ? [b.rationale] : []),
                    // Derived display fields for BuyerCard summary row
                    strategic_need: snScore >= 16 ? "Strong Strategic Pull"
                      : snScore >= 10 ? "Moderate Strategic Pull"
                      : snScore > 0 ? "Weak Strategic Pull"
                      : null,
                    ability_to_pay: atpScore > 0 ? {
                      label: atpScore >= 12 ? "Strong Balance Sheet"
                        : atpScore >= 8 ? "Moderate Capacity"
                        : "Limited Capacity",
                    } : null,
                    valuation_tension: vtScore > 0 ? {
                      level: vtScore >= 9 ? "High Potential"
                        : vtScore >= 6 ? "Moderate"
                        : "Low",
                    } : null,
                    close_certainty_pct: cocScore > 0
                      ? Math.round((cocScore / 16) * 100)
                      : null,
                  };
                  return <BuyerCard key={normalized.company_id || i} buyer={normalized} sellerCompanyId={sellerCompanyId} />;
                })
            }
          </div>
        </div>
      )}

      {!results && !loading && (
        <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", color: "var(--dl-text-muted)", fontSize: 14, textAlign: "center", padding: 60 }}>
          <div>
            <div style={{ fontSize: 32, marginBottom: 16 }}>◎</div>
            Select a target company and run discovery to see the buyer universe
          </div>
        </div>
      )}
    </main>
  );
}
