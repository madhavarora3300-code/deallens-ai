import React from "react";

const STEPS = [
  "Resolving company identity",
  "Pulling latest public disclosures",
  "Reading annual report and filings",
  "Extracting ownership and control signals",
  "Scoring strategic fit and dealability",
  "Ranking candidates and validating confidence",
  "Building M&A-ready intelligence summary",
];

export function EnrichmentPipeline({ progress = 0, steps = [], log = [] }) {
  const completedSteps = steps.filter((s) => s.status === "complete").map((s) => s.step);

  return (
    <div className="card" style={{ marginTop: 16 }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 12 }}>
        <span style={{ fontSize: 11, color: "var(--dl-teal)", fontWeight: 700, letterSpacing: 1 }}>
          ANALYSIS PIPELINE
        </span>
        <span style={{ fontSize: 11, color: "var(--dl-text-muted)", fontFamily: "var(--dl-font-mono)" }}>
          {progress}%
        </span>
      </div>

      {/* Progress bar */}
      <div style={{ height: 3, background: "var(--dl-border)", borderRadius: 2, marginBottom: 16 }}>
        <div style={{
          height: "100%",
          width: `${progress}%`,
          background: "var(--dl-teal)",
          borderRadius: 2,
          transition: "width 0.4s ease",
        }} />
      </div>

      {/* Step checklist */}
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {STEPS.map((step, i) => {
          const done = completedSteps.includes(step);
          const inProgress = !done && progress > (i / STEPS.length) * 100;
          return (
            <div key={i} style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 12 }}>
              <span style={{
                width: 16, height: 16, borderRadius: "50%", flexShrink: 0,
                background: done ? "var(--dl-teal)" : inProgress ? "var(--dl-amber)" : "var(--dl-border)",
                display: "flex", alignItems: "center", justifyContent: "center",
                fontSize: 9, color: "#000", fontWeight: 700,
              }}>
                {done ? "✓" : ""}
              </span>
              <span style={{ color: done ? "var(--dl-text-primary)" : "var(--dl-text-muted)" }}>
                {step}
              </span>
            </div>
          );
        })}
      </div>

      {/* Live log */}
      {log.length > 0 && (
        <div style={{
          marginTop: 16,
          padding: 10,
          background: "var(--dl-bg-primary)",
          borderRadius: 6,
          fontFamily: "var(--dl-font-mono)",
          fontSize: 11,
          color: "var(--dl-text-muted)",
          maxHeight: 100,
          overflowY: "auto",
        }}>
          {log.map((line, i) => (
            <div key={i} style={{ marginBottom: 2 }}>{line}</div>
          ))}
        </div>
      )}
    </div>
  );
}
