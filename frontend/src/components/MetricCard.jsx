import React from "react";

export function MetricCard({ label, value, unit = "", trend = null }) {
  const trendColor = trend > 0 ? "var(--dl-green)" : trend < 0 ? "var(--dl-red)" : "var(--dl-text-muted)";
  return (
    <div className="card" style={{ minWidth: 120, flex: 1 }}>
      <div style={{ fontSize: 10, color: "var(--dl-text-muted)", letterSpacing: 1, fontWeight: 600, marginBottom: 8 }}>
        {label}
      </div>
      <div style={{ fontSize: 20, fontWeight: 700, fontFamily: "var(--dl-font-mono)", color: "var(--dl-text-primary)" }}>
        {value != null ? `${value}${unit}` : "—"}
      </div>
      {trend != null && (
        <div style={{ fontSize: 11, color: trendColor, marginTop: 4 }}>
          {trend > 0 ? "▲" : "▼"} {Math.abs(trend)}%
        </div>
      )}
    </div>
  );
}
