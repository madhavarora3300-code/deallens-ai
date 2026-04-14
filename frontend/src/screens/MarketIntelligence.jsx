import React, { useEffect, useState } from "react";
import { getMarketFeed, triggerMarketFetch } from "../api/deallens.js";
import { NewsCard } from "../components/NewsCard.jsx";
import { SkeletonLoader } from "../components/SkeletonLoader.jsx";

const CATEGORIES = ["all", "deal_activity", "capital_markets", "institutional", "macro_geopolitical"];

export function MarketIntelligence() {
  const [feed, setFeed] = useState(null);
  const [loading, setLoading] = useState(true);
  const [period, setPeriod] = useState("daily");
  const [category, setCategory] = useState("all");
  const [refreshing, setRefreshing] = useState(false);
  const [refreshMsg, setRefreshMsg] = useState(null);

  // Auto-fetch on first mount if feed has no items or last_updated is stale (>6h)
  useEffect(() => {
    getMarketFeed("daily", "all", 1).then((data) => {
      const lastUpdated = data?.last_updated ? new Date(data.last_updated) : null;
      const ageHours = lastUpdated ? (Date.now() - lastUpdated.getTime()) / 36e5 : Infinity;
      if (!data?.items?.length || ageHours > 6) {
        triggerMarketFetch().catch(() => {});
        setRefreshMsg("Feed is stale — fetching latest data in the background. Reloading in ~45s.");
        setTimeout(() => {
          setRefreshMsg(null);
          getMarketFeed(period, category, 50).then(setFeed).catch(console.error);
        }, 45000);
      }
    }).catch(() => {});
  }, []); // run once on mount

  useEffect(() => {
    setLoading(true);
    getMarketFeed(period, category, 50)
      .then(setFeed)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [period, category]);

  const items = feed?.items || [];

  const handleRefresh = async () => {
    setRefreshing(true);
    setRefreshMsg(null);
    try {
      await triggerMarketFetch();
      setRefreshMsg("Feed refresh started. New items will appear in 30–60 seconds.");
      setTimeout(() => {
        setLoading(true);
        getMarketFeed(period, category, 50).then(setFeed).catch(console.error).finally(() => setLoading(false));
        setRefreshMsg(null);
      }, 45000);
    } catch {
      setRefreshMsg("Refresh failed. Try again.");
    } finally {
      setRefreshing(false);
    }
  };

  return (
    <main style={{ padding: 24, display: "flex", flexDirection: "column", gap: 20, maxWidth: 1200, margin: "0 auto", width: "100%" }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12 }}>
        <h2 style={{ fontSize: 20, fontWeight: 700 }}>Market Intelligence</h2>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          {feed?.last_updated && (
            <span style={{ fontSize: 11, color: "var(--dl-text-muted)", fontFamily: "var(--dl-font-mono)" }}>
              Updated: {new Date(feed.last_updated).toLocaleString()}
            </span>
          )}
          <button
            onClick={handleRefresh}
            disabled={refreshing}
            style={{
              padding: "6px 14px", fontSize: 11, fontWeight: 700,
              background: refreshing ? "var(--dl-bg-elevated)" : "var(--dl-teal)",
              color: refreshing ? "var(--dl-text-muted)" : "#000",
              border: "none", borderRadius: 6, cursor: refreshing ? "not-allowed" : "pointer",
            }}
          >
            {refreshing ? "Refreshing…" : "↻ Refresh Feed"}
          </button>
        </div>
      </div>
      {refreshMsg && (
        <div style={{ fontSize: 11, color: "var(--dl-amber)", padding: "8px 12px", background: "rgba(245,158,11,0.08)", borderRadius: 6, border: "1px solid var(--dl-amber)" }}>
          {refreshMsg}
        </div>
      )}

      {/* Controls */}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        {["daily", "weekly", "monthly"].map((p) => (
          <button
            key={p}
            onClick={() => setPeriod(p)}
            style={{
              padding: "6px 14px", fontSize: 12, fontWeight: 600, borderRadius: 6,
              background: period === p ? "var(--dl-teal)" : "var(--dl-bg-elevated)",
              color: period === p ? "#000" : "var(--dl-text-muted)",
              border: period === p ? "none" : "1px solid var(--dl-border)",
              cursor: "pointer",
            }}
          >
            {p.charAt(0).toUpperCase() + p.slice(1)}
          </button>
        ))}
        <div style={{ width: 1, background: "var(--dl-border)", margin: "0 4px" }} />
        {CATEGORIES.map((c) => (
          <button
            key={c}
            onClick={() => setCategory(c)}
            style={{
              padding: "6px 12px", fontSize: 11, fontWeight: 600, borderRadius: 6,
              background: category === c ? "var(--dl-bg-tertiary)" : "none",
              color: category === c ? "var(--dl-text-primary)" : "var(--dl-text-muted)",
              border: "1px solid " + (category === c ? "var(--dl-border-bright)" : "transparent"),
              cursor: "pointer",
            }}
          >
            {c.replace(/_/g, " ")}
          </button>
        ))}
      </div>

      {/* Feed */}
      <div style={{ display: "grid", gridTemplateColumns: "3fr 2fr", gap: 20, alignItems: "start" }}>
        {/* Main feed */}
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {loading
            ? [1,2,3,4,5].map(i => <SkeletonLoader key={i} height={120} borderRadius={10} />)
            : items.length > 0
              ? items.map((item) => <NewsCard key={item.item_id} item={item} />)
              : (
                <div style={{ padding: 40, textAlign: "center", color: "var(--dl-text-muted)" }}>
                  No news items found. The feed updates every 6 hours.
                </div>
              )
          }
        </div>

        {/* Monthly digest */}
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {feed?.monthly_digest && (
            <div className="card" style={{ borderColor: "var(--dl-gold)" }}>
              <div style={{ fontSize: 11, color: "var(--dl-gold)", letterSpacing: 1, fontWeight: 700, marginBottom: 10 }}>
                MONTHLY DIGEST
              </div>
              <p style={{ fontSize: 12, color: "var(--dl-text-secondary)", lineHeight: 1.6, marginBottom: 12 }}>
                {feed.monthly_digest.summary}
              </p>
              {feed.monthly_digest.key_themes?.length > 0 && (
                <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                  {feed.monthly_digest.key_themes.map((t, i) => (
                    <span key={i} style={{
                      fontSize: 10, fontWeight: 600, color: "var(--dl-text-secondary)",
                      border: "1px solid var(--dl-border)", borderRadius: 4, padding: "2px 8px",
                    }}>{t}</span>
                  ))}
                </div>
              )}
              {feed.monthly_digest.total_deals_tracked && (
                <div style={{ marginTop: 10, fontSize: 11, color: "var(--dl-text-muted)" }}>
                  {feed.monthly_digest.total_deals_tracked} deals tracked
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
