import React, { useEffect, useRef, useState } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { startBuySideDiscovery, getDiscoveryJobStatus } from "../api/deallens.js";
import { TargetCard } from "../components/TargetCard.jsx";
import { SkeletonLoader } from "../components/SkeletonLoader.jsx";
import { DiscoveryLoadingScreen } from "../components/DiscoveryLoadingScreen.jsx";

const STRATEGY_MODES = [
  { value: "capability_bolt_on",     label: "Capability Bolt-On" },
  { value: "geographic_expansion",   label: "Geographic Expansion" },
  { value: "scale_consolidation",    label: "Scale Consolidation" },
  { value: "distressed_opportunity", label: "Distressed Opportunity" },
  { value: "merger_of_equals",       label: "Merger of Equals" },
  { value: "platform_build",         label: "Platform Build" },
  { value: "minority_to_control",    label: "Minority to Control" },
];

// Derive deal category from score_breakdown + jurisdiction comparison
function getDealCategory(target, buyerJurisdiction) {
  const sb = target.score_breakdown || {};
  const strategicAlpha = sb.strategic_alpha || 0;
  const processSignal  = sb.process_momentum || 0;
  const financialHealth = sb.financial_health || 0;
  const scarcity       = sb.scarcity_auction_pressure || 0;
  const targetJx = target.target_jurisdiction || target.jurisdiction || "";

  if (strategicAlpha >= 16) return "Strategic Fit";
  if (buyerJurisdiction && targetJx && targetJx !== buyerJurisdiction) return "Geographic Expansion";
  if (financialHealth <= 5 && processSignal >= 2) return "Distressed Opportunity";
  if (scarcity >= 1) return "Defensive Play";
  return "Financial";
}

const CATEGORY_ORDER = ["Strategic Fit", "Geographic Expansion", "Defensive Play", "Distressed Opportunity", "Financial"];
const CATEGORY_COLOR = {
  "Strategic Fit":        "var(--dl-teal)",
  "Geographic Expansion": "var(--dl-blue)",
  "Defensive Play":       "var(--dl-amber)",
  "Distressed Opportunity": "var(--dl-red)",
  "Financial":            "var(--dl-text-muted)",
};

// ---------- sessionStorage helpers ----------
const SS_KEY = (buyerId) => `dl_buyside_${buyerId}`;

function saveToCache(buyerId, data) {
  try {
    sessionStorage.setItem(SS_KEY(buyerId), JSON.stringify(data));
  } catch (_) {}
}

function loadFromCache(buyerId) {
  try {
    const raw = sessionStorage.getItem(SS_KEY(buyerId));
    return raw ? JSON.parse(raw) : null;
  } catch (_) { return null; }
}
// --------------------------------------------

export function BuySideDiscovery() {
  const [searchParams] = useSearchParams();
  const buyerCompanyId = searchParams.get("buyer") || "";

  // Restore from cache on first render
  const cached = buyerCompanyId ? loadFromCache(buyerCompanyId) : null;

  const [results, setResults]   = useState(cached?.results || null);
  const [loading, setLoading]   = useState(false);
  const [loadingPhase, setLoadingPhase] = useState(""); // "queued" | "running" | "scoring"
  const [error, setError]       = useState(null);
  const pollRef = useRef(null);
  const [activeTier, setActiveTier] = useState("Tier 1");
  const [viewMode, setViewMode] = useState("tier"); // "tier" | "rationale"
  const [strategyMode, setStrategyMode] = useState(cached?.strategyMode || "capability_bolt_on");
  const [buyerJurisdiction, setBuyerJurisdiction] = useState(cached?.buyerJurisdiction || "");
  const [buyerName, setBuyerName] = useState(cached?.buyerName || "");
  const [buyerSector, setBuyerSector] = useState(cached?.buyerSector || "");
  const [filtersOpen, setFiltersOpen] = useState(false);

  // Filter state
  const [fRegions, setFRegions] = useState([]);
  const [fOwnershipTypes, setFOwnershipTypes] = useState([]);
  const [fListingStatuses, setFListingStatuses] = useState([]);
  const [fEvMin, setFEvMin] = useState("");
  const [fEvMax, setFEvMax] = useState("");
  const [fRevMin, setFRevMin] = useState("");
  const [fRevMax, setFRevMax] = useState("");
  const [fMinRevenueGrowth, setFMinRevenueGrowth] = useState("");
  const [fMinEbitdaMargin, setFMinEbitdaMargin] = useState("");
  const [fMaxLeverage, setFMaxLeverage] = useState("");
  const [fDealStructures, setFDealStructures] = useState([]);
  const [fSectorFocus, setFSectorFocus] = useState("any");

  const toggleArr = (arr, setArr, val) =>
    setArr(arr.includes(val) ? arr.filter(x => x !== val) : [...arr, val]);

  const buildFilters = () => {
    const f = {};
    if (fRegions.length)          f.regions = fRegions;
    if (fOwnershipTypes.length)   f.ownership_types = fOwnershipTypes;
    if (fListingStatuses.length)  f.listing_statuses = fListingStatuses;
    if (fEvMin)                   f.ev_min_usd_b = parseFloat(fEvMin);
    if (fEvMax)                   f.ev_max_usd_b = parseFloat(fEvMax);
    if (fRevMin)                  f.revenue_min_usd_m = parseFloat(fRevMin);
    if (fRevMax)                  f.revenue_max_usd_m = parseFloat(fRevMax);
    if (fMinRevenueGrowth)        f.min_revenue_growth_pct = parseFloat(fMinRevenueGrowth);
    if (fMinEbitdaMargin)         f.min_ebitda_margin_pct = parseFloat(fMinEbitdaMargin);
    if (fMaxLeverage)             f.max_net_debt_ebitda = parseFloat(fMaxLeverage);
    if (fDealStructures.length)   f.deal_structures = fDealStructures;
    if (fSectorFocus !== "any")   f.sector_focus = fSectorFocus;
    return f;
  };

  const activeFilterCount = [
    fRegions.length, fOwnershipTypes.length, fListingStatuses.length,
    fEvMin, fEvMax, fRevMin, fRevMax, fMinRevenueGrowth, fMinEbitdaMargin,
    fMaxLeverage, fDealStructures.length, fSectorFocus !== "any" ? 1 : 0,
  ].filter(Boolean).length;

  const stopPoll = () => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
  };

  // Clean up poll on unmount
  useEffect(() => () => stopPoll(), []);

  const runDiscovery = async () => {
    if (!buyerCompanyId) return;
    stopPoll();
    setLoading(true);
    setLoadingPhase("queued");
    setError(null);
    setResults(null);
    try {
      // Step 1: queue the job — returns immediately with job_id
      const { job_id } = await startBuySideDiscovery({
        buyer_company_id: buyerCompanyId,
        strategy_mode: strategyMode,
        filters: buildFilters(),
        limit: 50,
      });

      // Step 2: poll every 3s until complete
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
            const first = data?.targets?.[0];
            const jx   = first?.buyer_jurisdiction || "";
            const name  = first?.buyer_display_name || first?.buyer_legal_name || "";
            const sector = first?.buyer_sector || "";
            if (jx) setBuyerJurisdiction(jx);
            if (name) setBuyerName(name);
            if (sector) setBuyerSector(sector);
            saveToCache(buyerCompanyId, { results: data, strategyMode, buyerJurisdiction: jx, buyerName: name, buyerSector: sector });
          } else if (status.status === "failed") {
            stopPoll();
            setError(status.error || "Discovery failed");
            setLoading(false);
            setLoadingPhase("");
          } else if (status.status === "running") {
            setLoadingPhase("scoring");
          }
          // "queued" → keep polling
        } catch (pollErr) {
          // Network blip — keep polling, don't abort
        }
      }, 3000);
    } catch (e) {
      stopPoll();
      setError(e.message);
      setLoading(false);
      setLoadingPhase("");
    }
  };

  const tiers = ["Tier 1", "Tier 2", "Tier 3"];
  const tierCounts = results?.summary || {};

  // Normalise target fields (scoring engine returns target_* prefixed fields)
  const normalizeTarget = (t, index) => ({
    ...t,
    company_id:  t.company_id  || t.target_company_id,
    legal_name:  t.legal_name  || t.target_legal_name  || t.target_display_name,
    ticker:      t.ticker      || t.target_ticker,
    jurisdiction: t.jurisdiction || t.target_jurisdiction,
    sector:      t.sector      || t.target_sector,
    enterprise_value_usd_b: t.enterprise_value_usd_b
      || (t.target_ev_usd_m ? (t.target_ev_usd_m / 1000).toFixed(1) : null),
    revenue_usd_m: t.revenue_usd_m || t.target_revenue_usd_m,
    investment_thesis: t.investment_thesis || (t.rationale ? [t.rationale] : []),
    deal_score: t.deal_score ?? t.target_deal_score ?? 0,
    score_rationale: t.score_rationale || null,
    ib_metrics: t.ib_metrics || null,
    rationale_category: t.rationale_category || null,
    why_now: t.why_now || null,
    is_non_obvious: t.is_non_obvious || false,
    non_obvious_bridge: t.non_obvious_bridge || null,
    estimated_synergy_value_usd_m: t.estimated_synergy_value_usd_m || null,
    precedent_deals: t.precedent_deals || null,
    _rank: index + 1,
  });

  const allTargets       = (results?.targets || []).map(normalizeTarget);
  const tierTargets      = allTargets.filter((t) => t.tier === activeTier);
  const excludedTargets  = (results?.excluded_targets || []).map((t, i) =>
    normalizeTarget(t, allTargets.length + i)
  );

  // Group by deal category for "By Rationale" view
  const targetsByCategory = {};
  for (const cat of CATEGORY_ORDER) {
    const group = allTargets.filter(t => getDealCategory(t, buyerJurisdiction) === cat);
    if (group.length > 0) targetsByCategory[cat] = group;
  }

  const strategyLabel = STRATEGY_MODES.find(m => m.value === strategyMode)?.label || strategyMode;

  return (
    <main style={{ padding: 24, display: "flex", flexDirection: "column", gap: 20, maxWidth: 1400, margin: "0 auto", width: "100%" }}>

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h2 style={{ fontSize: 20, fontWeight: 700 }}>Buy-Side Discovery</h2>
      </div>

      {/* Controls */}
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
        <select
          value={strategyMode}
          onChange={(e) => setStrategyMode(e.target.value)}
          style={{
            padding: "8px 12px", background: "var(--dl-bg-elevated)", border: "1px solid var(--dl-border)",
            borderRadius: 6, color: "var(--dl-text-primary)", fontSize: 12, fontFamily: "var(--dl-font-sans)",
          }}
        >
          {STRATEGY_MODES.map((m) => (
            <option key={m.value} value={m.value}>{m.label}</option>
          ))}
        </select>
        <button
          onClick={() => setFiltersOpen(o => !o)}
          style={{
            padding: "8px 14px", fontWeight: 600, fontSize: 12,
            background: filtersOpen || activeFilterCount > 0 ? "var(--dl-bg-elevated)" : "none",
            color: activeFilterCount > 0 ? "var(--dl-teal)" : "var(--dl-text-muted)",
            border: `1px solid ${activeFilterCount > 0 ? "var(--dl-teal)" : "var(--dl-border)"}`,
            borderRadius: 7, cursor: "pointer", fontFamily: "var(--dl-font-sans)",
          }}
        >
          ⊕ Filters{activeFilterCount > 0 ? ` (${activeFilterCount})` : ""}
        </button>
        <button
          onClick={runDiscovery}
          disabled={loading || !buyerCompanyId}
          style={{
            padding: "8px 20px", fontWeight: 700, fontSize: 13,
            background: loading ? "var(--dl-bg-elevated)" : "var(--dl-teal)",
            color: loading ? "var(--dl-text-muted)" : "#000",
            border: "none", borderRadius: 8, cursor: loading ? "not-allowed" : "pointer",
          }}
        >
          {loading ? "Analysing..." : "Run Discovery →"}
        </button>
        {!buyerCompanyId && (
          <span style={{ fontSize: 12, color: "var(--dl-amber)" }}>
            Search a company first to set as buyer
          </span>
        )}
      </div>

      {/* M&A Filter Panel */}
      {filtersOpen && (
        <div className="card" style={{ display: "flex", flexDirection: "column", gap: 18 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontSize: 11, fontWeight: 700, color: "var(--dl-text-muted)", letterSpacing: 1 }}>DISCOVERY PARAMETERS</span>
            {activeFilterCount > 0 && (
              <button
                onClick={() => { setFRegions([]); setFOwnershipTypes([]); setFListingStatuses([]); setFEvMin(""); setFEvMax(""); setFRevMin(""); setFRevMax(""); setFMinRevenueGrowth(""); setFMinEbitdaMargin(""); setFMaxLeverage(""); setFDealStructures([]); setFSectorFocus("any"); }}
                style={{ fontSize: 11, color: "var(--dl-red)", background: "none", border: "none", cursor: "pointer" }}
              >
                Clear all
              </button>
            )}
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 18 }}>

            {/* Target EV Range */}
            <div>
              <div style={{ fontSize: 10, color: "var(--dl-text-muted)", fontWeight: 600, letterSpacing: 0.8, marginBottom: 6 }}>TARGET EV RANGE ($B)</div>
              <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                <input type="number" placeholder="Min" value={fEvMin} onChange={e => setFEvMin(e.target.value)}
                  style={{ width: 80, padding: "5px 8px", background: "var(--dl-bg-tertiary)", border: "1px solid var(--dl-border)", borderRadius: 5, color: "var(--dl-text-primary)", fontSize: 12, fontFamily: "var(--dl-font-mono)" }} />
                <span style={{ color: "var(--dl-text-muted)", fontSize: 11 }}>—</span>
                <input type="number" placeholder="Max" value={fEvMax} onChange={e => setFEvMax(e.target.value)}
                  style={{ width: 80, padding: "5px 8px", background: "var(--dl-bg-tertiary)", border: "1px solid var(--dl-border)", borderRadius: 5, color: "var(--dl-text-primary)", fontSize: 12, fontFamily: "var(--dl-font-mono)" }} />
              </div>
            </div>

            {/* Revenue Range */}
            <div>
              <div style={{ fontSize: 10, color: "var(--dl-text-muted)", fontWeight: 600, letterSpacing: 0.8, marginBottom: 6 }}>REVENUE RANGE ($M)</div>
              <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                <input type="number" placeholder="Min" value={fRevMin} onChange={e => setFRevMin(e.target.value)}
                  style={{ width: 80, padding: "5px 8px", background: "var(--dl-bg-tertiary)", border: "1px solid var(--dl-border)", borderRadius: 5, color: "var(--dl-text-primary)", fontSize: 12, fontFamily: "var(--dl-font-mono)" }} />
                <span style={{ color: "var(--dl-text-muted)", fontSize: 11 }}>—</span>
                <input type="number" placeholder="Max" value={fRevMax} onChange={e => setFRevMax(e.target.value)}
                  style={{ width: 80, padding: "5px 8px", background: "var(--dl-bg-tertiary)", border: "1px solid var(--dl-border)", borderRadius: 5, color: "var(--dl-text-primary)", fontSize: 12, fontFamily: "var(--dl-font-mono)" }} />
              </div>
            </div>

            {/* Revenue Growth Floor */}
            <div>
              <div style={{ fontSize: 10, color: "var(--dl-text-muted)", fontWeight: 600, letterSpacing: 0.8, marginBottom: 6 }}>MIN REVENUE GROWTH (%)</div>
              <input type="number" placeholder="e.g. 10" value={fMinRevenueGrowth} onChange={e => setFMinRevenueGrowth(e.target.value)}
                style={{ width: 100, padding: "5px 8px", background: "var(--dl-bg-tertiary)", border: "1px solid var(--dl-border)", borderRadius: 5, color: "var(--dl-text-primary)", fontSize: 12, fontFamily: "var(--dl-font-mono)" }} />
            </div>

            {/* EBITDA Margin Floor */}
            <div>
              <div style={{ fontSize: 10, color: "var(--dl-text-muted)", fontWeight: 600, letterSpacing: 0.8, marginBottom: 6 }}>MIN EBITDA MARGIN (%)</div>
              <input type="number" placeholder="e.g. 15" value={fMinEbitdaMargin} onChange={e => setFMinEbitdaMargin(e.target.value)}
                style={{ width: 100, padding: "5px 8px", background: "var(--dl-bg-tertiary)", border: "1px solid var(--dl-border)", borderRadius: 5, color: "var(--dl-text-primary)", fontSize: 12, fontFamily: "var(--dl-font-mono)" }} />
            </div>

            {/* Max Leverage */}
            <div>
              <div style={{ fontSize: 10, color: "var(--dl-text-muted)", fontWeight: 600, letterSpacing: 0.8, marginBottom: 6 }}>MAX NET DEBT / EBITDA</div>
              <input type="number" placeholder="e.g. 4.0" value={fMaxLeverage} onChange={e => setFMaxLeverage(e.target.value)}
                style={{ width: 100, padding: "5px 8px", background: "var(--dl-bg-tertiary)", border: "1px solid var(--dl-border)", borderRadius: 5, color: "var(--dl-text-primary)", fontSize: 12, fontFamily: "var(--dl-font-mono)" }} />
            </div>

            {/* Sector Focus */}
            <div>
              <div style={{ fontSize: 10, color: "var(--dl-text-muted)", fontWeight: 600, letterSpacing: 0.8, marginBottom: 6 }}>SECTOR FOCUS</div>
              <div style={{ display: "flex", gap: 6 }}>
                {[{ v: "same", l: "Same Sector" }, { v: "adjacent", l: "Adjacent" }, { v: "any", l: "Any" }].map(({ v, l }) => (
                  <button key={v} onClick={() => setFSectorFocus(v)}
                    style={{ padding: "4px 10px", fontSize: 11, fontWeight: 600, borderRadius: 5, cursor: "pointer", fontFamily: "var(--dl-font-sans)", border: `1px solid ${fSectorFocus === v ? "var(--dl-teal)" : "var(--dl-border)"}`, background: fSectorFocus === v ? "rgba(0,212,170,0.12)" : "none", color: fSectorFocus === v ? "var(--dl-teal)" : "var(--dl-text-muted)" }}>
                    {l}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Geography */}
          <div>
            <div style={{ fontSize: 10, color: "var(--dl-text-muted)", fontWeight: 600, letterSpacing: 0.8, marginBottom: 8 }}>GEOGRAPHY</div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              {[
                { v: "north_america", l: "North America" }, { v: "europe", l: "Europe" },
                { v: "asia_pacific", l: "Asia-Pacific" }, { v: "india", l: "India" },
                { v: "middle_east", l: "Middle East" }, { v: "latam", l: "LatAm" },
                { v: "global", l: "Global" },
              ].map(({ v, l }) => {
                const active = fRegions.includes(v);
                return (
                  <button key={v} onClick={() => toggleArr(fRegions, setFRegions, v)}
                    style={{ padding: "4px 12px", fontSize: 11, fontWeight: 600, borderRadius: 5, cursor: "pointer", fontFamily: "var(--dl-font-sans)", border: `1px solid ${active ? "var(--dl-blue)" : "var(--dl-border)"}`, background: active ? "rgba(59,130,246,0.12)" : "none", color: active ? "var(--dl-blue)" : "var(--dl-text-muted)" }}>
                    {l}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Ownership Type */}
          <div>
            <div style={{ fontSize: 10, color: "var(--dl-text-muted)", fontWeight: 600, letterSpacing: 0.8, marginBottom: 8 }}>OWNERSHIP TYPE</div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              {[
                { v: "public", l: "Public" }, { v: "private", l: "Private" },
                { v: "pe_backed", l: "PE-Backed" }, { v: "family_founder", l: "Family/Founder" },
                { v: "state_owned", l: "State-Owned" },
              ].map(({ v, l }) => {
                const active = fOwnershipTypes.includes(v);
                return (
                  <button key={v} onClick={() => toggleArr(fOwnershipTypes, setFOwnershipTypes, v)}
                    style={{ padding: "4px 12px", fontSize: 11, fontWeight: 600, borderRadius: 5, cursor: "pointer", fontFamily: "var(--dl-font-sans)", border: `1px solid ${active ? "var(--dl-gold)" : "var(--dl-border)"}`, background: active ? "rgba(245,158,11,0.12)" : "none", color: active ? "var(--dl-gold)" : "var(--dl-text-muted)" }}>
                    {l}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Deal Structure */}
          <div>
            <div style={{ fontSize: 10, color: "var(--dl-text-muted)", fontWeight: 600, letterSpacing: 0.8, marginBottom: 8 }}>DEAL STRUCTURE</div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              {[
                { v: "friendly_only", l: "Friendly Only" }, { v: "hostile_acceptable", l: "Hostile Acceptable" },
                { v: "minority_stake", l: "Minority Stake" }, { v: "full_acquisition", l: "Full Acquisition" },
              ].map(({ v, l }) => {
                const active = fDealStructures.includes(v);
                return (
                  <button key={v} onClick={() => toggleArr(fDealStructures, setFDealStructures, v)}
                    style={{ padding: "4px 12px", fontSize: 11, fontWeight: 600, borderRadius: 5, cursor: "pointer", fontFamily: "var(--dl-font-sans)", border: `1px solid ${active ? "var(--dl-teal)" : "var(--dl-border)"}`, background: active ? "rgba(0,212,170,0.12)" : "none", color: active ? "var(--dl-teal)" : "var(--dl-text-muted)" }}>
                    {l}
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {error && <div style={{ color: "var(--dl-red)", fontSize: 13 }}>{error}</div>}

      {/* Animated loading screen */}
      {loading && (
        <DiscoveryLoadingScreen
          mode="buy_side"
          anchorName={buyerName}
          strategyHint={strategyMode}
          anchorSector={buyerSector}
          statusPhase={loadingPhase}
        />
      )}

      {/* Results */}
      {results && !loading && (
        <>
          {/* Summary strip (mirrors sell-side) */}
          <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
            <div className="card" style={{ flex: 2, minWidth: 200 }}>
              <div style={{ fontSize: 11, color: "var(--dl-text-muted)", marginBottom: 4 }}>BUYER</div>
              <div style={{ fontWeight: 700, fontSize: 15 }}>
                {results.targets?.[0]?.buyer_display_name
                  || results.targets?.[0]?.buyer_legal_name
                  || buyerCompanyId}
              </div>
              <div style={{ fontSize: 11, color: "var(--dl-text-muted)", marginTop: 2 }}>
                Strategy: <span style={{ color: "var(--dl-teal)" }}>{strategyLabel}</span>
              </div>
            </div>
            <div className="card" style={{ flex: 1, minWidth: 130 }}>
              <div style={{ fontSize: 11, color: "var(--dl-text-muted)", marginBottom: 4 }}>TARGETS RANKED</div>
              <div style={{ fontFamily: "var(--dl-font-mono)", fontWeight: 700, fontSize: 24 }}>
                {allTargets.length}
              </div>
            </div>
            <div className="card" style={{ flex: 1, minWidth: 100 }}>
              <div style={{ fontSize: 11, color: "var(--dl-text-muted)", marginBottom: 4 }}>TIER 1</div>
              <div style={{ fontFamily: "var(--dl-font-mono)", fontWeight: 700, fontSize: 24, color: "var(--dl-teal)" }}>
                {tierCounts.tier_1_count || 0}
              </div>
            </div>
            <div className="card" style={{ flex: 1, minWidth: 100 }}>
              <div style={{ fontSize: 11, color: "var(--dl-text-muted)", marginBottom: 4 }}>TIER 2</div>
              <div style={{ fontFamily: "var(--dl-font-mono)", fontWeight: 700, fontSize: 24, color: "var(--dl-blue)" }}>
                {tierCounts.tier_2_count || 0}
              </div>
            </div>
          </div>

          {/* Prominent view mode toggle — centered pill switcher */}
          <div style={{ display: "flex", justifyContent: "center" }}>
            <div style={{
              display: "inline-flex", gap: 0, background: "var(--dl-bg-elevated)",
              border: "1px solid var(--dl-border)", borderRadius: 10, padding: 3,
            }}>
              {[{ id: "tier", label: "⊟  By Tier" }, { id: "rationale", label: "◈  By Rationale" }].map(({ id, label }) => (
                <button
                  key={id}
                  onClick={() => setViewMode(id)}
                  style={{
                    padding: "8px 24px", fontSize: 13, fontWeight: 700,
                    background: viewMode === id ? "var(--dl-teal)" : "none",
                    border: "none",
                    color: viewMode === id ? "#000" : "var(--dl-text-muted)",
                    borderRadius: 7, cursor: "pointer", fontFamily: "var(--dl-font-sans)",
                    transition: "all 0.15s ease",
                  }}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          {/* Tier tabs (only in tier view) */}
          {viewMode === "tier" && (
            <div style={{ display: "flex", gap: 4, borderBottom: "1px solid var(--dl-border)" }}>
              {tiers.map((t) => {
                const countKey = `${t.toLowerCase().replace(" ", "_")}_count`;
                const count = tierCounts[countKey] || 0;
                return (
                  <button
                    key={t}
                    onClick={() => setActiveTier(t)}
                    style={{
                      padding: "8px 16px", background: "none",
                      border: "none", borderBottom: activeTier === t ? "2px solid var(--dl-teal)" : "2px solid transparent",
                      color: activeTier === t ? "var(--dl-teal)" : "var(--dl-text-muted)",
                      fontWeight: 600, fontSize: 12, cursor: "pointer", fontFamily: "var(--dl-font-sans)",
                    }}
                  >
                    {t} ({count})
                  </button>
                );
              })}
            </div>
          )}
          {viewMode === "rationale" && (
            <div style={{ fontSize: 12, color: "var(--dl-text-muted)", padding: "4px 0" }}>
              {allTargets.length} targets across {Object.keys(targetsByCategory).length} categories
            </div>
          )}

          {/* BY TIER view */}
          {viewMode === "tier" && (
            <>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(420px, 1fr))", gap: 16 }}>
                {tierTargets.map((t, i) => (
                  <TargetCard
                    key={t.company_id || i}
                    target={t}
                    rank={t._rank}
                    dealCategory={getDealCategory(t, buyerJurisdiction)}
                    buyerCompanyId={buyerCompanyId}
                  />
                ))}
              </div>
              {tierTargets.length === 0 && (
                <div style={{ textAlign: "center", color: "var(--dl-text-muted)", padding: 40 }}>
                  No {activeTier} targets found
                </div>
              )}
            </>
          )}

          {/* BY RATIONALE view */}
          {viewMode === "rationale" && (
            <div style={{ display: "flex", flexDirection: "column", gap: 28 }}>
              {Object.entries(targetsByCategory).map(([cat, targets]) => (
                <div key={cat}>
                  {/* Category header */}
                  <div style={{
                    display: "flex", alignItems: "center", gap: 10,
                    marginBottom: 14, paddingBottom: 8,
                    borderBottom: `1px solid ${CATEGORY_COLOR[cat]}44`,
                  }}>
                    <span style={{
                      fontSize: 11, fontWeight: 700, letterSpacing: 1,
                      color: CATEGORY_COLOR[cat], fontFamily: "var(--dl-font-mono)",
                    }}>
                      {cat.toUpperCase()}
                    </span>
                    <span style={{ fontSize: 11, color: "var(--dl-text-muted)" }}>
                      {targets.length} target{targets.length !== 1 ? "s" : ""}
                    </span>
                    <div style={{ flex: 1, height: 1, background: `${CATEGORY_COLOR[cat]}33` }} />
                  </div>
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(420px, 1fr))", gap: 16 }}>
                    {targets.map((t, i) => (
                      <TargetCard
                        key={t.company_id || i}
                        target={t}
                        rank={t._rank}
                        dealCategory={cat}
                        buyerCompanyId={buyerCompanyId}
                      />
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {!results && !loading && (
        <div style={{
          flex: 1, display: "flex", alignItems: "center", justifyContent: "center",
          color: "var(--dl-text-muted)", fontSize: 14, textAlign: "center", padding: 60,
        }}>
          <div>
            <div style={{ fontSize: 32, marginBottom: 16 }}>◎</div>
            Select a buyer company and run discovery to see ranked acquisition targets
          </div>
        </div>
      )}
    </main>
  );
}
