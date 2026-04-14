import React from "react";

const ROLE_COLOR = {
  must_contact_strategic: "var(--dl-teal)",
  price_anchor: "var(--dl-gold)",
  certainty_anchor: "var(--dl-green)",
  tension_creator: "var(--dl-purple)",
  sponsor_floor: "var(--dl-blue)",
};

export function ProcessRoleBadge({ role, label }) {
  const color = ROLE_COLOR[role] || "var(--dl-text-muted)";
  return (
    <span style={{
      fontSize: 10,
      fontWeight: 700,
      letterSpacing: 0.8,
      color,
      border: `1px solid ${color}`,
      borderRadius: 4,
      padding: "2px 8px",
      fontFamily: "var(--dl-font-mono)",
    }}>
      {label || role?.replace(/_/g, " ").toUpperCase()}
    </span>
  );
}
