import React from "react";

const DEPTH_COLOR = {
  FULL: "var(--dl-teal)",
  DEEP: "var(--dl-green)",
  STANDARD: "var(--dl-blue)",
  BASIC: "var(--dl-text-muted)",
};

export function CoverageBadge({ depth = "BASIC" }) {
  const color = DEPTH_COLOR[depth] || "var(--dl-text-muted)";
  return (
    <span style={{
      fontSize: 11,
      fontWeight: 700,
      letterSpacing: 1,
      color,
      border: `1px solid ${color}`,
      borderRadius: 4,
      padding: "2px 8px",
      fontFamily: "var(--dl-font-mono)",
    }}>
      {depth} COVERAGE
    </span>
  );
}
