import React from "react";

export function ConfidenceBadge({ score = 0 }) {
  const color = score >= 80 ? "var(--dl-teal)" : score >= 50 ? "var(--dl-amber)" : "var(--dl-red)";
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
      <span style={{ fontSize: 36, fontWeight: 700, color, fontFamily: "var(--dl-font-mono)" }}>
        {score}
      </span>
      <span style={{ fontSize: 10, color: "var(--dl-text-muted)", letterSpacing: 1, fontWeight: 600 }}>
        CONFIDENCE
      </span>
    </div>
  );
}
