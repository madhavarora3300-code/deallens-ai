import React from "react";

const SOURCE_TYPE_LABEL = {
  regulator_exchange: "REGULATOR/EXCHANGE",
  annual_report: "ANNUAL REPORT",
  regulatory_filing: "FILING",
  ir_document: "IR PAGE",
  news: "NEWS",
};

export function SourcePanel({ sources = [] }) {
  if (!sources.length) return null;
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 8, margin: "12px 0" }}>
      {sources.map((s, i) => (
        <a
          key={i}
          href={s.source_url || "#"}
          target="_blank"
          rel="noopener noreferrer"
          style={{
            fontSize: 10,
            fontWeight: 700,
            letterSpacing: 0.8,
            color: "var(--dl-text-secondary)",
            border: "1px solid var(--dl-border)",
            borderRadius: 4,
            padding: "3px 10px",
            textDecoration: "none",
            fontFamily: "var(--dl-font-mono)",
            transition: "border-color 0.15s",
          }}
        >
          {SOURCE_TYPE_LABEL[s.source_type] || s.source_name || "SOURCE"}
        </a>
      ))}
    </div>
  );
}
