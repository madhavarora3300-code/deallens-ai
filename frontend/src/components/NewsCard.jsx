import React from "react";

const CATEGORY_COLOR = {
  deal_activity: "var(--dl-teal)",
  capital_markets: "var(--dl-blue)",
  institutional: "var(--dl-purple)",
  macro_geopolitical: "var(--dl-amber)",
};

const SENTIMENT_COLOR = {
  positive: "var(--dl-green)",
  negative: "var(--dl-red)",
  neutral: "var(--dl-text-muted)",
};

export function NewsCard({ item = {} }) {
  const catColor = CATEGORY_COLOR[item.category] || "var(--dl-text-muted)";
  const sentColor = SENTIMENT_COLOR[item.sentiment] || "var(--dl-text-muted)";

  return (
    <div className="card" style={{ borderLeft: `3px solid ${catColor}` }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 8 }}>
        <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: 0.8, color: catColor, fontFamily: "var(--dl-font-mono)" }}>
          {(item.category || "").replace(/_/g, " ").toUpperCase()}
        </span>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <span style={{ width: 6, height: 6, borderRadius: "50%", background: sentColor, display: "inline-block" }} />
          <span style={{ fontSize: 11, color: "var(--dl-text-muted)" }}>{item.time_ago || ""}</span>
        </div>
      </div>
      <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 6, lineHeight: 1.4 }}>
        {item.source_url ? (
          <a href={item.source_url} target="_blank" rel="noopener noreferrer" style={{ color: "var(--dl-text-primary)" }}>
            {item.headline}
          </a>
        ) : item.headline}
      </div>
      {item.ai_summary && (
        <div style={{ fontSize: 12, color: "var(--dl-text-secondary)", lineHeight: 1.5 }}>
          {item.ai_summary}
        </div>
      )}
      {item.source_name && (
        <div style={{ marginTop: 8, fontSize: 11, color: "var(--dl-text-muted)" }}>
          {item.source_name}
          {item.deal_type && (
            <span style={{ marginLeft: 8, color: "var(--dl-text-muted)", border: "1px solid var(--dl-border)", borderRadius: 3, padding: "0 4px", fontSize: 10, fontFamily: "var(--dl-font-mono)" }}>
              {item.deal_type}
            </span>
          )}
        </div>
      )}
    </div>
  );
}
