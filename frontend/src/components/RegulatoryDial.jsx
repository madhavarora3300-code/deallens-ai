import React from "react";

export function RegulatoryDial({ score = 0, label = "RISK SCORE" }) {
  const color = score >= 70 ? "var(--dl-red)" : score >= 40 ? "var(--dl-amber)" : "var(--dl-green)";
  const size = 120;
  const radius = size / 2 - 8;
  const circumference = 2 * Math.PI * radius;
  const dash = (score / 100) * circumference;

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 8 }}>
      <svg width={size} height={size} style={{ transform: "rotate(-90deg)" }}>
        <circle cx={size / 2} cy={size / 2} r={radius}
          fill="none" stroke="var(--dl-border)" strokeWidth={8} />
        <circle cx={size / 2} cy={size / 2} r={radius}
          fill="none" stroke={color} strokeWidth={8}
          strokeDasharray={`${dash} ${circumference}`}
          strokeLinecap="round" />
        <text x="50%" y="45%" textAnchor="middle" dominantBaseline="middle"
          style={{ fill: color, fontSize: 28, fontWeight: 700, fontFamily: "var(--dl-font-mono)", transform: "rotate(90deg)" }}>
          {score}
        </text>
        <text x="50%" y="63%" textAnchor="middle" dominantBaseline="middle"
          style={{ fill: "var(--dl-text-muted)", fontSize: 9, fontFamily: "var(--dl-font-mono)", transform: "rotate(90deg)", letterSpacing: 1 }}>
          /100
        </text>
      </svg>
      <span style={{ fontSize: 11, color: "var(--dl-text-muted)", fontWeight: 600, letterSpacing: 1 }}>{label}</span>
    </div>
  );
}
