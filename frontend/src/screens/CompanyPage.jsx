import React, { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { getCompanyProfile, checkDiscoveryEligibility, triggerEnrichment } from "../api/deallens.js";
import { CompanyHeader } from "../components/CompanyHeader.jsx";
import { CoverageBadge } from "../components/CoverageBadge.jsx";
import { FreshnessBadge } from "../components/FreshnessBadge.jsx";
import { ConfidenceBadge } from "../components/ConfidenceBadge.jsx";
import { SourcePanel } from "../components/SourcePanel.jsx";
import { MetricCard } from "../components/MetricCard.jsx";
import { SegmentTable } from "../components/SegmentTable.jsx";
import { OwnershipCard } from "../components/OwnershipCard.jsx";
import { AIStrategicLens } from "../components/AIStrategicLens.jsx";
import { EnrichmentPipeline } from "../components/EnrichmentPipeline.jsx";
import { SkeletonLoader } from "../components/SkeletonLoader.jsx";
import { useEnrichmentStream } from "../hooks/useEnrichmentStream.js";

const CP_SS_KEY = (id) => `dl_company_${id}`;

function saveCpCache(id, profile, eligibility) {
  try { sessionStorage.setItem(CP_SS_KEY(id), JSON.stringify({ profile, eligibility })); } catch (_) {}
}

function loadCpCache(id) {
  try {
    const raw = sessionStorage.getItem(CP_SS_KEY(id));
    return raw ? JSON.parse(raw) : null;
  } catch (_) { return null; }
}

export function CompanyPage() {
  const { companyId } = useParams();
  const navigate = useNavigate();

  const cpCached = companyId ? loadCpCache(companyId) : null;
  const [profile, setProfile] = useState(cpCached?.profile || null);
  const [eligibility, setEligibility] = useState(cpCached?.eligibility || null);
  const [loading, setLoading] = useState(!cpCached); // skip loading flash if we have cache
  const { progress, steps, log, streaming, complete, startStream } = useEnrichmentStream();

  useEffect(() => {
    // Always re-fetch in background to get fresh data; show cached immediately
    if (!cpCached) setLoading(true);
    Promise.all([
      getCompanyProfile(companyId),
      checkDiscoveryEligibility(companyId),
    ]).then(([p, e]) => {
      setProfile(p);
      setEligibility(e);
      saveCpCache(companyId, p, e);
      if (p?.portal_state?.enrichment_status !== "COMPLETE") {
        startStream(companyId);
        triggerEnrichment(companyId).catch(() => {}); // fire and forget
      }
    }).catch(console.error)
      .finally(() => setLoading(false));
  }, [companyId]);

  // Re-fetch profile after enrichment stream completes so UI shows fresh data
  useEffect(() => {
    if (!complete) return;
    Promise.all([
      getCompanyProfile(companyId),
      checkDiscoveryEligibility(companyId),
    ]).then(([p, e]) => {
      setProfile(p);
      setEligibility(e);
      saveCpCache(companyId, p, e);
    }).catch(() => {});
  }, [complete, companyId]);

  if (loading) return (
    <main style={{ padding: 24, display: "flex", flexDirection: "column", gap: 16 }}>
      <SkeletonLoader height={40} />
      <SkeletonLoader height={20} width="60%" />
      <div style={{ display: "flex", gap: 16 }}>
        {[1,2,3,4,5,6].map(i => <SkeletonLoader key={i} height={80} style={{ flex: 1 }} />)}
      </div>
    </main>
  );

  if (!profile) return <div style={{ padding: 24, color: "var(--dl-red)" }}>Company not found.</div>;

  // API returns flat fields — map to shapes expected by components
  const identity = {
    legal_name: profile.legal_name,
    display_name: profile.display_name,
    ticker: profile.ticker,
    isin: profile.isin,
    jurisdiction: profile.jurisdiction,
  };
  const financials = profile.financials || {};
  const ownership = profile.ownership || {};
  const { portal_state = {}, sources = [], description, strategic_features } = profile;
  const ai_strategic_lens = strategic_features?.m_and_a_appetite
    ? { insight: strategic_features.m_and_a_appetite, confidence: portal_state.confidence_score }
    : null;

  // financials values are raw USD — convert to billions for display
  const fmtB = (v) => v ? `$${(v / 1e9).toFixed(1)}B` : null;

  return (
    <main style={{ padding: 24, display: "flex", flexDirection: "column", gap: 20, maxWidth: 1200, margin: "0 auto", width: "100%" }}>
      <CompanyHeader company={identity} />

      {/* Badges row */}
      <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
        <CoverageBadge depth={portal_state.coverage_depth} />
        <FreshnessBadge status={portal_state.freshness_status} />
        <ConfidenceBadge score={portal_state.confidence_score || 0} />
      </div>

      {/* Enrichment pipeline — shown at top when in progress */}
      {!complete && (streaming || portal_state.enrichment_status !== "COMPLETE") && (
        <EnrichmentPipeline progress={progress} steps={steps} log={log} />
      )}

      {/* Source transparency */}
      <SourcePanel sources={sources} />

      {/* Action buttons */}
      <div style={{ display: "flex", gap: 12 }}>
        <button
          disabled={!eligibility?.buy_side_eligible}
          onClick={() => navigate(`/buy-side?buyer=${companyId}`)}
          style={{
            padding: "10px 20px", fontWeight: 700, fontSize: 13,
            background: eligibility?.buy_side_eligible ? "var(--dl-teal)" : "var(--dl-bg-elevated)",
            color: eligibility?.buy_side_eligible ? "#000" : "var(--dl-text-muted)",
            border: eligibility?.buy_side_eligible ? "none" : "1px solid var(--dl-border)",
            borderRadius: 8, cursor: eligibility?.buy_side_eligible ? "pointer" : "not-allowed",
          }}
        >
          RUN BUY-SIDE DISCOVERY
        </button>
        <button
          disabled={!eligibility?.sell_side_eligible}
          onClick={() => navigate(`/sell-side?seller=${companyId}`)}
          style={{
            padding: "10px 20px", fontWeight: 700, fontSize: 13,
            background: eligibility?.sell_side_eligible ? "var(--dl-gold)" : "var(--dl-bg-elevated)",
            color: eligibility?.sell_side_eligible ? "#000" : "var(--dl-text-muted)",
            border: eligibility?.sell_side_eligible ? "none" : "1px solid var(--dl-border)",
            borderRadius: 8, cursor: eligibility?.sell_side_eligible ? "pointer" : "not-allowed",
          }}
        >
          RUN SELL-SIDE BUYER DISCOVERY
        </button>
      </div>

      {/* Two-column: business + ownership */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {description && (
            <div className="card">
              <div style={{ fontSize: 11, color: "var(--dl-text-muted)", letterSpacing: 1, fontWeight: 600, marginBottom: 8 }}>BUSINESS</div>
              <p style={{ fontSize: 13, color: "var(--dl-text-secondary)", lineHeight: 1.6 }}>
                {description}
              </p>
            </div>
          )}
          <AIStrategicLens lens={ai_strategic_lens} />
        </div>
        <OwnershipCard ownership={ownership} />
      </div>

      {/* Financial metrics row */}
      <div>
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
          <MetricCard label="MARKET CAP" value={fmtB(financials.market_cap_usd)} />
          <MetricCard label="EV" value={fmtB(financials.enterprise_value_usd)} />
          <MetricCard label="REVENUE" value={fmtB(financials.revenue_usd)} />
          <MetricCard label="EBITDA" value={fmtB(financials.ebitda_usd)} trend={financials.ebitda_margin} />
          <MetricCard label="CASH" value={fmtB(financials.cash_usd)} />
          <MetricCard label="NET DEBT" value={financials.total_debt_usd && financials.cash_usd ? fmtB(financials.total_debt_usd - financials.cash_usd) : null} />
        </div>
        <div style={{ fontSize: 11, color: "var(--dl-text-muted)", marginTop: 8 }}>
          ⚠ Financials sourced from AI knowledge base{financials.revenue_year ? ` (FY${financials.revenue_year})` : ""}. Market cap &amp; EV are not live — figures may differ from current market prices.
        </div>
      </div>

      {/* Segment table */}
      {financials.segment_breakdown?.length > 0 && (
        <div className="card">
          <div style={{ fontSize: 11, color: "var(--dl-text-muted)", letterSpacing: 1, fontWeight: 600, marginBottom: 12 }}>SEGMENT BREAKDOWN</div>
          <SegmentTable segments={financials.segment_breakdown} />
        </div>
      )}

      {/* Strategic features — products, markets, competitors, acquisitions, M&A signals */}
      {strategic_features && Object.values(strategic_features).some(v => v != null && v !== false && !(Array.isArray(v) && v.length === 0)) && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16 }}>

          {/* Key products */}
          {strategic_features.key_products?.length > 0 && (
            <div className="card">
              <div style={{ fontSize: 11, color: "var(--dl-text-muted)", letterSpacing: 1, fontWeight: 600, marginBottom: 10 }}>KEY PRODUCTS</div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                {strategic_features.key_products.map((p, i) => (
                  <span key={i} style={{
                    fontSize: 11, padding: "3px 8px", borderRadius: 4,
                    background: "var(--dl-bg-tertiary)", border: "1px solid var(--dl-border)",
                    color: "var(--dl-text-secondary)",
                  }}>{p}</span>
                ))}
              </div>
              {strategic_features.geographic_markets?.length > 0 && (
                <>
                  <div style={{ fontSize: 11, color: "var(--dl-text-muted)", letterSpacing: 1, fontWeight: 600, marginBottom: 8, marginTop: 14 }}>MARKETS</div>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                    {strategic_features.geographic_markets.map((m, i) => (
                      <span key={i} style={{
                        fontSize: 11, padding: "3px 8px", borderRadius: 4,
                        background: "var(--dl-bg-tertiary)", border: "1px solid var(--dl-border)",
                        color: "var(--dl-teal)", fontFamily: "var(--dl-font-mono)",
                      }}>{m}</span>
                    ))}
                  </div>
                </>
              )}
            </div>
          )}

          {/* Competitors + strategic priorities */}
          {(strategic_features.top_competitors?.length > 0 || strategic_features.strategic_priorities?.length > 0) && (
            <div className="card">
              {strategic_features.top_competitors?.length > 0 && (
                <>
                  <div style={{ fontSize: 11, color: "var(--dl-text-muted)", letterSpacing: 1, fontWeight: 600, marginBottom: 10 }}>TOP COMPETITORS</div>
                  {strategic_features.top_competitors.map((c, i) => (
                    <div key={i} style={{ fontSize: 12, color: "var(--dl-text-secondary)", marginBottom: 4, display: "flex", gap: 6 }}>
                      <span style={{ color: "var(--dl-text-muted)" }}>›</span>{c}
                    </div>
                  ))}
                </>
              )}
              {strategic_features.strategic_priorities?.length > 0 && (
                <>
                  <div style={{ fontSize: 11, color: "var(--dl-text-muted)", letterSpacing: 1, fontWeight: 600, marginBottom: 10, marginTop: strategic_features.top_competitors?.length > 0 ? 14 : 0 }}>STRATEGIC PRIORITIES</div>
                  {strategic_features.strategic_priorities.map((p, i) => (
                    <div key={i} style={{ fontSize: 12, color: "var(--dl-text-secondary)", marginBottom: 4, display: "flex", gap: 6 }}>
                      <span style={{ color: "var(--dl-teal)" }}>✓</span>{p}
                    </div>
                  ))}
                </>
              )}
            </div>
          )}

          {/* M&A signals + acquisitions */}
          <div className="card">
            <div style={{ fontSize: 11, color: "var(--dl-text-muted)", letterSpacing: 1, fontWeight: 600, marginBottom: 10 }}>M&A SIGNALS</div>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {strategic_features.m_and_a_appetite && (
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12 }}>
                  <span style={{ color: "var(--dl-text-muted)" }}>Appetite</span>
                  <span style={{ color: "var(--dl-gold)", fontWeight: 600 }}>
                    {strategic_features.m_and_a_appetite.replace(/_/g, " ")}
                  </span>
                </div>
              )}
              {[
                { key: "rumored_target", label: "Rumored Target" },
                { key: "rumored_seller", label: "Rumored Seller" },
                { key: "activist_present", label: "Activist Present" },
                { key: "management_change_recent", label: "Mgmt Change" },
                { key: "strategic_review_underway", label: "Strategic Review" },
              ].map(({ key, label }) => strategic_features[key] === true && (
                <div key={key} style={{
                  display: "flex", alignItems: "center", gap: 8, padding: "4px 8px",
                  background: "rgba(245,200,66,0.08)", borderRadius: 6,
                  border: "1px solid rgba(245,200,66,0.2)",
                }}>
                  <span style={{ color: "var(--dl-amber)", fontSize: 11 }}>⚑</span>
                  <span style={{ fontSize: 11, fontWeight: 600, color: "var(--dl-amber)" }}>{label}</span>
                </div>
              ))}
            </div>

            {strategic_features.recent_acquisitions?.length > 0 && (
              <>
                <div style={{ fontSize: 11, color: "var(--dl-text-muted)", letterSpacing: 1, fontWeight: 600, marginBottom: 8, marginTop: 14 }}>RECENT ACQUISITIONS</div>
                {strategic_features.recent_acquisitions.map((a, i) => (
                  <div key={i} style={{ fontSize: 12, color: "var(--dl-text-secondary)", marginBottom: 4, display: "flex", justifyContent: "space-between" }}>
                    <span>{a.name}</span>
                    <span style={{ fontFamily: "var(--dl-font-mono)", color: "var(--dl-text-muted)" }}>{a.year}</span>
                  </div>
                ))}
              </>
            )}
          </div>
        </div>
      )}

    </main>
  );
}
