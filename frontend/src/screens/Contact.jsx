import React from "react";

const CONTACT_INFO = {
  name: "Madhav Arora",
  title: "M&A Technology & Advisory",
  tagline: "Founder of DealLens AI — an intelligent M&A discovery and deal analysis platform built for investment bankers, advisors, and corporate development teams.",
  about: [
    "DealLens AI combines institutional-grade M&A intelligence with modern AI to surface strategic acquisition targets, score deal feasibility, and generate investment-ready deal documentation — in seconds.",
    "Built for practitioners who demand precision: every score is traceable to formula, every recommendation backed by strategic rationale.",
  ],
  contacts: [
    {
      icon: "✉",
      label: "Email",
      value: "amadhav91@gmail.com",
      href: "mailto:amadhav91@gmail.com",
      color: "var(--dl-teal)",
    },
    {
      icon: "📞",
      label: "Phone",
      value: "+91 88603 74768",
      href: "tel:+918860374768",
      color: "var(--dl-gold)",
    },
    {
      icon: "💬",
      label: "WhatsApp",
      value: "+91 88603 74768",
      href: "https://wa.me/918860374768",
      color: "var(--dl-green)",
    },
    {
      icon: "📍",
      label: "Location",
      value: "India",
      href: null,
      color: "var(--dl-text-secondary)",
    },
  ],
};

function ContactCard({ icon, label, value, href, color }) {
  const inner = (
    <div style={{
      display: "flex",
      alignItems: "center",
      gap: 14,
      padding: "16px 20px",
      background: "var(--dl-bg-elevated)",
      border: "1px solid var(--dl-border)",
      borderRadius: 10,
      transition: "border-color 0.2s, background 0.2s",
      cursor: href ? "pointer" : "default",
      textDecoration: "none",
    }}
    onMouseEnter={e => { if (href) { e.currentTarget.style.borderColor = color; e.currentTarget.style.background = "var(--dl-bg-tertiary)"; } }}
    onMouseLeave={e => { e.currentTarget.style.borderColor = "var(--dl-border)"; e.currentTarget.style.background = "var(--dl-bg-elevated)"; }}
    >
      <div style={{
        width: 42, height: 42, borderRadius: 10,
        background: `color-mix(in srgb, ${color} 12%, var(--dl-bg-primary))`,
        border: `1px solid color-mix(in srgb, ${color} 30%, transparent)`,
        display: "flex", alignItems: "center", justifyContent: "center",
        fontSize: 18, flexShrink: 0,
      }}>
        {icon}
      </div>
      <div>
        <div style={{ fontSize: 10, color: "var(--dl-text-muted)", fontWeight: 700, letterSpacing: 0.8, marginBottom: 3 }}>
          {label.toUpperCase()}
        </div>
        <div style={{ fontSize: 13, fontWeight: 600, color: href ? color : "var(--dl-text-secondary)" }}>
          {value}
        </div>
        {href && (
          <div style={{ fontSize: 10, color: "var(--dl-text-muted)", marginTop: 2 }}>
            Click to open →
          </div>
        )}
      </div>
    </div>
  );

  if (href) {
    return (
      <a href={href} target={href.startsWith("http") ? "_blank" : "_self"} rel="noopener noreferrer"
        style={{ textDecoration: "none", display: "block" }}>
        {inner}
      </a>
    );
  }
  return <div>{inner}</div>;
}

export function Contact() {
  return (
    <main style={{ padding: "40px 24px", maxWidth: 900, margin: "0 auto", width: "100%" }}>

      {/* Hero section */}
      <div style={{
        padding: "40px 48px",
        background: "linear-gradient(135deg, var(--dl-bg-elevated) 0%, var(--dl-bg-tertiary) 100%)",
        border: "1px solid var(--dl-border)",
        borderRadius: 16,
        marginBottom: 32,
        position: "relative",
        overflow: "hidden",
      }}>
        {/* Decorative accent */}
        <div style={{
          position: "absolute", top: 0, right: 0,
          width: 200, height: 200,
          background: "radial-gradient(circle, rgba(0,212,170,0.06) 0%, transparent 70%)",
          pointerEvents: "none",
        }} />

        {/* DealLens wordmark */}
        <div style={{ fontSize: 13, fontWeight: 800, letterSpacing: -0.5, marginBottom: 24 }}>
          <span style={{ color: "var(--dl-gold)" }}>Deal</span>
          <span style={{ color: "var(--dl-teal)" }}>Lens</span>
          <span style={{ fontSize: 9, color: "var(--dl-text-muted)", fontWeight: 400, letterSpacing: 1, marginLeft: 8 }}>AI</span>
        </div>

        {/* Name & title */}
        <h1 style={{ fontSize: 32, fontWeight: 800, margin: "0 0 6px", letterSpacing: -0.5 }}>
          {CONTACT_INFO.name}
        </h1>
        <div style={{ fontSize: 14, color: "var(--dl-teal)", fontWeight: 600, marginBottom: 20, letterSpacing: 0.3 }}>
          {CONTACT_INFO.title}
        </div>

        {/* Tagline */}
        <p style={{ fontSize: 14, color: "var(--dl-text-secondary)", lineHeight: 1.7, maxWidth: 600, margin: 0 }}>
          {CONTACT_INFO.tagline}
        </p>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24, alignItems: "start" }}>
        {/* Left: About */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div style={{ fontSize: 10, color: "var(--dl-text-muted)", fontWeight: 700, letterSpacing: 1 }}>
            ABOUT THE PLATFORM
          </div>
          {CONTACT_INFO.about.map((para, i) => (
            <p key={i} style={{ fontSize: 13, color: "var(--dl-text-secondary)", lineHeight: 1.7, margin: 0 }}>
              {para}
            </p>
          ))}

          {/* Feature chips */}
          <div style={{ marginTop: 8 }}>
            <div style={{ fontSize: 10, color: "var(--dl-text-muted)", fontWeight: 700, letterSpacing: 1, marginBottom: 10 }}>
              CAPABILITIES
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              {[
                "AI Target Discovery", "Sell-Side Mandates", "Deal Scoring",
                "Regulatory Lens", "IC Draft Generation", "Market Intelligence",
                "Score Formula Transparency", "Non-Obvious Match Engine",
              ].map((cap) => (
                <span key={cap} style={{
                  fontSize: 10, fontWeight: 600, padding: "3px 10px", borderRadius: 4,
                  background: "var(--dl-bg-tertiary)", border: "1px solid var(--dl-border)",
                  color: "var(--dl-text-secondary)",
                }}>
                  {cap}
                </span>
              ))}
            </div>
          </div>
        </div>

        {/* Right: Contact cards */}
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <div style={{ fontSize: 10, color: "var(--dl-text-muted)", fontWeight: 700, letterSpacing: 1, marginBottom: 4 }}>
            GET IN TOUCH
          </div>
          {CONTACT_INFO.contacts.map((c) => (
            <ContactCard key={c.label} {...c} />
          ))}

          {/* Availability note */}
          <div style={{
            marginTop: 8, padding: "12px 16px",
            background: "rgba(0,212,170,0.06)",
            border: "1px solid rgba(0,212,170,0.2)",
            borderRadius: 8,
            fontSize: 11, color: "var(--dl-text-muted)", lineHeight: 1.5,
          }}>
            <span style={{ color: "var(--dl-teal)", fontWeight: 700 }}>Open to:</span> Advisory mandates, product feedback, partnership discussions, and investor conversations.
          </div>
        </div>
      </div>

      {/* Footer */}
      <div style={{
        marginTop: 48, paddingTop: 20,
        borderTop: "1px solid var(--dl-border)",
        display: "flex", justifyContent: "space-between", alignItems: "center",
        flexWrap: "wrap", gap: 8,
      }}>
        <div style={{ fontSize: 11, color: "var(--dl-text-muted)" }}>
          <span style={{ color: "var(--dl-gold)" }}>Deal</span>
          <span style={{ color: "var(--dl-teal)" }}>Lens</span>
          <span style={{ marginLeft: 6 }}>AI v1.0 — M&A Intelligence Platform</span>
        </div>
        <div style={{ fontSize: 11, color: "var(--dl-text-muted)" }}>
          Built for investment bankers. Powered by AI.
        </div>
      </div>
    </main>
  );
}
