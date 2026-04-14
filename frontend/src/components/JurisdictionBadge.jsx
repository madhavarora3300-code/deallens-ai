import React from "react";

export function JurisdictionBadge({ jurisdiction }) {
  if (!jurisdiction) return null;
  return (
    <span style={{
      fontSize: 10,
      fontWeight: 700,
      letterSpacing: 1,
      color: "var(--dl-text-secondary)",
      border: "1px solid var(--dl-border)",
      borderRadius: 4,
      padding: "1px 6px",
      fontFamily: "var(--dl-font-mono)",
    }}>
      {jurisdiction}
    </span>
  );
}
