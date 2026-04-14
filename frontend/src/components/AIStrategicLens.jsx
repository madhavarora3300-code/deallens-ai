import React from "react";

export function AIStrategicLens({ lens = {} }) {
  if (!lens?.insight) return null;
  return (
    <div className="card" style={{ borderColor: "var(--dl-teal)", borderLeftWidth: 3 }}>
      <div style={{ fontSize: 10, color: "var(--dl-teal)", letterSpacing: 1, fontWeight: 700, marginBottom: 8 }}>
        AI STRATEGIC LENS
      </div>
      <p style={{ color: "var(--dl-text-secondary)", lineHeight: 1.6, fontSize: 13 }}>
        {lens.insight}
      </p>
      {lens.confidence && (
        <div style={{ marginTop: 8, fontSize: 11, color: "var(--dl-text-muted)" }}>
          Confidence: {lens.confidence}%
        </div>
      )}
    </div>
  );
}
