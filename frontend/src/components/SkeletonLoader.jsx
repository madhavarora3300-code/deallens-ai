import React from "react";

export function SkeletonLoader({ width = "100%", height = 16, borderRadius = 4, style = {} }) {
  return (
    <div style={{
      width,
      height,
      borderRadius,
      background: "linear-gradient(90deg, var(--dl-bg-elevated) 25%, var(--dl-bg-tertiary) 50%, var(--dl-bg-elevated) 75%)",
      backgroundSize: "200% 100%",
      animation: "shimmer 1.5s infinite",
      ...style,
    }} />
  );
}

// Inject shimmer keyframe once
if (typeof document !== "undefined" && !document.getElementById("dl-shimmer")) {
  const style = document.createElement("style");
  style.id = "dl-shimmer";
  style.textContent = `@keyframes shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }`;
  document.head.appendChild(style);
}
