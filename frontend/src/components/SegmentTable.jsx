import React from "react";

const RISK_COLOR = {
  LOW: "var(--dl-green)",
  MODERATE: "var(--dl-amber)",
  HIGH: "var(--dl-red)",
};

export function SegmentTable({ segments = [] }) {
  if (!segments.length) return null;
  return (
    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
      <thead>
        <tr style={{ color: "var(--dl-text-muted)", fontSize: 11, letterSpacing: 1 }}>
          <th style={{ textAlign: "left", padding: "6px 8px", fontWeight: 600 }}>SEGMENT</th>
          <th style={{ textAlign: "right", padding: "6px 8px", fontWeight: 600 }}>REV %</th>
          <th style={{ textAlign: "right", padding: "6px 8px", fontWeight: 600 }}>EBITDA %</th>
          <th style={{ textAlign: "right", padding: "6px 8px", fontWeight: 600 }}>YoY</th>
          <th style={{ textAlign: "center", padding: "6px 8px", fontWeight: 600 }}>RISK</th>
        </tr>
      </thead>
      <tbody>
        {segments.map((s, i) => (
          <tr key={i} style={{ borderTop: "1px solid var(--dl-border)" }}>
            <td style={{ padding: "8px 8px", color: "var(--dl-text-primary)" }}>{s.segment}</td>
            <td style={{ padding: "8px 8px", textAlign: "right", fontFamily: "var(--dl-font-mono)" }}>
              {s.revenue_contribution_pct ?? "—"}%
            </td>
            <td style={{ padding: "8px 8px", textAlign: "right", fontFamily: "var(--dl-font-mono)" }}>
              {s.ebitda_margin_pct ?? "—"}%
            </td>
            <td style={{ padding: "8px 8px", textAlign: "right", fontFamily: "var(--dl-font-mono)",
              color: (s.yoy_growth_pct || 0) >= 0 ? "var(--dl-green)" : "var(--dl-red)" }}>
              {s.yoy_growth_pct != null ? `${s.yoy_growth_pct > 0 ? "+" : ""}${s.yoy_growth_pct}%` : "—"}
            </td>
            <td style={{ padding: "8px 8px", textAlign: "center" }}>
              <span style={{ color: RISK_COLOR[s.risk_exposure] || "var(--dl-text-muted)", fontSize: 11, fontWeight: 700 }}>
                {s.risk_exposure || "—"}
              </span>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
