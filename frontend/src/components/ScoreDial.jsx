import React from "react";

export function ScoreDial({ score = 0, label = "SCORE", size = 80 }) {
  const color = score >= 65 ? "var(--dl-teal)" : score >= 45 ? "var(--dl-amber)" : "var(--dl-red)";
  const radius = (size / 2) - 6;
  const circumference = 2 * Math.PI * radius;
  const dash = (score / 100) * circumference;

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 4 }}>
      <svg width={size} height={size} style={{ transform: "rotate(-90deg)" }}>
        <circle cx={size / 2} cy={size / 2} r={radius}
          fill="none" stroke="var(--dl-border)" strokeWidth={5} />
        <circle cx={size / 2} cy={size / 2} r={radius}
          fill="none" stroke={color} strokeWidth={5}
          strokeDasharray={`${dash} ${circumference}`}
          strokeLinecap="round" />
        <text x="50%" y="50%" textAnchor="middle" dominantBaseline="middle"
          style={{ transform: `rotate(90deg) translateX(0)`, fill: color, fontSize: size * 0.25, fontWeight: 700, fontFamily: "var(--dl-font-mono)" }}>
          {score}
        </text>
      </svg>
      <span style={{ fontSize: 10, color: "var(--dl-text-muted)", fontWeight: 600, letterSpacing: 1 }}>{label}</span>
    </div>
  );
}
