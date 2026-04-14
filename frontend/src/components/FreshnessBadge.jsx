import React from "react";

const STATUS_COLOR = {
  LIVE: "var(--dl-teal)",
  RECENT: "var(--dl-green)",
  STALE: "var(--dl-amber)",
};

export function FreshnessBadge({ status = "STALE" }) {
  const color = STATUS_COLOR[status] || "var(--dl-text-muted)";
  return (
    <span style={{
      display: "inline-flex",
      alignItems: "center",
      gap: 6,
      fontSize: 11,
      fontWeight: 700,
      letterSpacing: 1,
      color,
      fontFamily: "var(--dl-font-mono)",
    }}>
      <span style={{
        width: 7,
        height: 7,
        borderRadius: "50%",
        background: color,
        display: "inline-block",
        ...(status === "LIVE" ? { boxShadow: `0 0 6px ${color}` } : {}),
      }} />
      {status}
    </span>
  );
}
