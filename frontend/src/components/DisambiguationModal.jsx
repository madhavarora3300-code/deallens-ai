import React from "react";

export function DisambiguationModal({ candidates = [], onSelect, onClose }) {
  if (!candidates.length) return null;
  return (
    <div style={{
      position: "fixed", inset: 0, background: "rgba(0,0,0,0.7)",
      display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000,
    }}>
      <div className="card" style={{ width: 480, maxWidth: "90vw" }}>
        <div style={{ fontSize: 11, color: "var(--dl-amber)", fontWeight: 700, letterSpacing: 1, marginBottom: 16 }}>
          MULTIPLE MATCHES FOUND
        </div>
        <div style={{ fontSize: 13, color: "var(--dl-text-secondary)", marginBottom: 16 }}>
          Select the company you're looking for:
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {candidates.map((c) => (
            <button
              key={c.company_id}
              onClick={() => onSelect?.(c)}
              style={{
                background: "var(--dl-bg-tertiary)",
                border: "1px solid var(--dl-border)",
                borderRadius: 6,
                padding: "12px 14px",
                textAlign: "left",
                cursor: "pointer",
                color: "var(--dl-text-primary)",
              }}
            >
              <div style={{ fontWeight: 600 }}>{c.legal_name}</div>
              <div style={{ fontSize: 11, color: "var(--dl-text-muted)", marginTop: 4, fontFamily: "var(--dl-font-mono)" }}>
                {[c.ticker, c.isin, c.jurisdiction, c.exchange].filter(Boolean).join(" · ")}
              </div>
            </button>
          ))}
        </div>
        <button
          onClick={onClose}
          style={{
            marginTop: 12, width: "100%", padding: "8px", background: "none",
            border: "1px solid var(--dl-border)", borderRadius: 6, color: "var(--dl-text-muted)",
            cursor: "pointer", fontSize: 12,
          }}
        >
          Cancel
        </button>
      </div>
    </div>
  );
}
