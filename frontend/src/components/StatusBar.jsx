import React from "react";

export function StatusBar({ systemStatus = "NOMINAL" }) {
  const isOk = systemStatus === "NOMINAL";
  return (
    <div style={{
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      padding: "6px 20px",
      background: "var(--dl-bg-secondary)",
      borderTop: "1px solid var(--dl-border)",
      fontSize: 11,
      fontFamily: "var(--dl-font-mono)",
      color: "var(--dl-text-muted)",
      flexShrink: 0,
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span style={{
          width: 6, height: 6, borderRadius: "50%",
          background: isOk ? "var(--dl-teal)" : "var(--dl-red)",
          boxShadow: isOk ? "0 0 6px var(--dl-teal)" : "none",
          display: "inline-block",
        }} />
        <span style={{ color: isOk ? "var(--dl-teal)" : "var(--dl-red)", fontWeight: 600 }}>
          SYSTEMS {systemStatus}
        </span>
      </div>
      <div style={{ display: "flex", gap: 20 }}>
        <span>DealLens AI v1.0</span>
        <span style={{ color: "var(--dl-border-bright)" }}>|</span>
        <span>M&A Intelligence Portal</span>
      </div>
    </div>
  );
}
