import React from "react";

const TIER_STYLE = {
  "Tier 1": { color: "var(--dl-teal)", border: "var(--dl-teal)", label: "TIER 1 MATCH" },
  "Tier 2": { color: "var(--dl-blue)", border: "var(--dl-blue)", label: "TIER 2 MATCH" },
  "Tier 3": { color: "var(--dl-text-muted)", border: "var(--dl-border)", label: "TIER 3" },
  "Excluded": { color: "var(--dl-red)", border: "var(--dl-red)", label: "EXCLUDED" },
};

export function TierBadge({ tier = "Tier 3" }) {
  const style = TIER_STYLE[tier] || TIER_STYLE["Tier 3"];
  return (
    <span style={{
      fontSize: 10,
      fontWeight: 700,
      letterSpacing: 1,
      color: style.color,
      border: `1px solid ${style.border}`,
      borderRadius: 4,
      padding: "2px 8px",
      fontFamily: "var(--dl-font-mono)",
    }}>
      {style.label}
    </span>
  );
}
