import React from "react";

export function CompanyHeader({ company = {} }) {
  const { legal_name, display_name, ticker, isin, exchange, jurisdiction } = company;
  return (
    <div style={{ borderBottom: "1px solid var(--dl-border)", paddingBottom: 16, marginBottom: 16 }}>
      <h1 style={{ fontSize: 24, fontWeight: 700, color: "var(--dl-text-primary)" }}>
        {legal_name || display_name || "—"}
      </h1>
      <div style={{ display: "flex", gap: 16, marginTop: 8, color: "var(--dl-text-secondary)", fontSize: 13 }}>
        {ticker && <span className="mono" style={{ color: "var(--dl-gold)" }}>{ticker}</span>}
        {isin && <span className="mono">{isin}</span>}
        {exchange && <span>{exchange}</span>}
        {jurisdiction && (
          <span style={{
            background: "var(--dl-bg-tertiary)",
            border: "1px solid var(--dl-border)",
            borderRadius: 4,
            padding: "1px 8px",
            fontSize: 11,
            fontWeight: 600,
            letterSpacing: 1,
          }}>
            {jurisdiction}
          </span>
        )}
      </div>
    </div>
  );
}
