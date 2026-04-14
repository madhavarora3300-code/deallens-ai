import React from "react";
import { useNavigate } from "react-router-dom";
import { SearchBar } from "../components/SearchBar.jsx";
import { DisambiguationModal } from "../components/DisambiguationModal.jsx";
import { useCompanySearch } from "../hooks/useCompanySearch.js";

function SiteFooter() {
  return (
    <footer style={{
      width: "100vw",
      marginLeft: "calc(-50vw + 50%)",
      borderTop: "1px solid var(--dl-border)",
      background: "var(--dl-bg-secondary)",
      marginTop: 80,
    }}>
      {/* Main footer columns */}
      <div style={{
        maxWidth: 1100,
        margin: "0 auto",
        padding: "48px 40px 40px",
        display: "grid",
        gridTemplateColumns: "1.6fr 1fr 1fr 1fr",
        gap: 48,
      }}>

        {/* Col 1 — Brand + about */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div style={{ fontSize: 18, fontWeight: 800, letterSpacing: -0.5 }}>
            <span style={{ color: "var(--dl-gold)" }}>Deal</span>
            <span style={{ color: "var(--dl-teal)" }}>Lens</span>
            <span style={{ fontSize: 10, color: "var(--dl-text-muted)", fontWeight: 400, letterSpacing: 1, marginLeft: 8 }}>AI</span>
          </div>
          <p style={{ fontSize: 13, color: "var(--dl-text-muted)", lineHeight: 1.7, margin: 0, maxWidth: 280 }}>
            Institutional-grade M&A intelligence for investment bankers, advisors, and corporate development teams. Every score traceable to formula.
          </p>
          <div style={{ fontSize: 11, color: "var(--dl-text-muted)", marginTop: 4 }}>
            Built by{" "}
            <span style={{ color: "var(--dl-text-secondary)", fontWeight: 600 }}>Madhav Arora</span>
            {" "}· M&A Technology &amp; Advisory · India
          </div>
        </div>

        {/* Col 2 — Platform */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: 1, color: "var(--dl-text-secondary)" }}>
            PLATFORM
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {[
              "Company Intelligence",
              "Buy-Side Discovery",
              "Sell-Side Mandates",
              "Regulatory Lens",
              "IC Draft Generation",
              "Market Intelligence",
            ].map(item => (
              <span key={item} style={{ fontSize: 13, color: "var(--dl-text-muted)", lineHeight: 1 }}>
                {item}
              </span>
            ))}
          </div>
        </div>

        {/* Col 3 — Intelligence */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: 1, color: "var(--dl-text-secondary)" }}>
            INTELLIGENCE
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {[
              "Deal Scoring Engine",
              "Score Formula View",
              "Non-Obvious Matches",
              "IB Valuation Metrics",
              "Process Architecture",
              "Deep Analysis",
            ].map(item => (
              <span key={item} style={{ fontSize: 13, color: "var(--dl-text-muted)", lineHeight: 1 }}>
                {item}
              </span>
            ))}
          </div>
        </div>

        {/* Col 4 — Contact */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: 1, color: "var(--dl-text-secondary)" }}>
            CONTACT
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <div>
              <div style={{ fontSize: 10, color: "var(--dl-text-muted)", marginBottom: 3 }}>EMAIL</div>
              <a href="mailto:amadhav91@gmail.com" style={{
                fontSize: 13, color: "var(--dl-teal)", textDecoration: "none",
                fontFamily: "var(--dl-font-mono)",
              }}>
                amadhav91@gmail.com
              </a>
            </div>
            <div>
              <div style={{ fontSize: 10, color: "var(--dl-text-muted)", marginBottom: 3 }}>PHONE</div>
              <a href="tel:+918860374768" style={{
                fontSize: 13, color: "var(--dl-text-secondary)", textDecoration: "none",
              }}>
                +91 88603 74768
              </a>
            </div>
            <div>
              <div style={{ fontSize: 10, color: "var(--dl-text-muted)", marginBottom: 6 }}>WHATSAPP</div>
              <a href="https://wa.me/918860374768" target="_blank" rel="noopener noreferrer" style={{
                display: "inline-block",
                fontSize: 12, fontWeight: 600, padding: "6px 16px", borderRadius: 4,
                background: "rgba(0,212,170,0.08)", border: "1px solid rgba(0,212,170,0.25)",
                color: "var(--dl-teal)", textDecoration: "none",
              }}>
                Message on WhatsApp →
              </a>
            </div>
            <div style={{ marginTop: 4 }}>
              <div style={{ fontSize: 10, color: "var(--dl-text-muted)", marginBottom: 3 }}>OPEN TO</div>
              <div style={{ fontSize: 12, color: "var(--dl-text-muted)", lineHeight: 1.6 }}>
                Advisory mandates · Partnerships · Investor conversations
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Bottom copyright bar */}
      <div style={{
        borderTop: "1px solid var(--dl-border)",
        padding: "14px 40px",
        display: "flex", justifyContent: "space-between", alignItems: "center",
        flexWrap: "wrap", gap: 8,
        maxWidth: 1100, margin: "0 auto",
      }}>
        <div style={{ fontSize: 11, color: "var(--dl-text-muted)" }}>
          © 2026 DealLens AI · M&A Intelligence Platform · All rights reserved
        </div>
        <div style={{ fontSize: 11, color: "var(--dl-text-muted)" }}>
          Built for investment bankers. Powered by AI.
        </div>
      </div>
    </footer>
  );
}

export function SearchHome() {
  const navigate = useNavigate();
  const { result, loading, error, search, reset } = useCompanySearch();
  const [showDisambig, setShowDisambig] = React.useState(false);

  const handleSearch = async (query) => {
    const data = await search(query);
    if (!data) return;
    if (data.resolution_status === "ambiguous") {
      setShowDisambig(true);
    } else if (data.resolved?.company_id) {
      navigate(`/company/${data.resolved.company_id}`);
    }
  };

  const handleSelect = (candidate) => {
    setShowDisambig(false);
    navigate(`/company/${candidate.company_id}`);
  };

  return (
    <main style={{
      flex: 1, display: "flex", flexDirection: "column",
      alignItems: "center", justifyContent: "flex-start",
      padding: "80px 20px 0", gap: 32,
    }}>
      {/* Logo / Title */}
      <div style={{ textAlign: "center" }}>
        <h1 style={{ fontSize: 36, fontWeight: 800, letterSpacing: -1 }}>
          <span style={{ color: "var(--dl-gold)" }}>Deal</span>
          <span style={{ color: "var(--dl-teal)" }}>Lens</span>
          <span style={{ color: "var(--dl-text-secondary)", fontWeight: 400 }}> AI</span>
        </h1>
        <p style={{ color: "var(--dl-text-muted)", marginTop: 8, fontSize: 14 }}>
          Live M&A Intelligence — Resolve any public company globally
        </p>
      </div>

      {/* Search bar */}
      <div style={{ width: "100%", maxWidth: 600 }}>
        <SearchBar onSearch={handleSearch} loading={loading} />
        {error && <p style={{ color: "var(--dl-red)", fontSize: 12, marginTop: 8 }}>{error}</p>}
      </div>

      {/* Search mode hints */}
      <div style={{ display: "flex", gap: 12 }}>
        {["BY TICKER", "BY ISIN", "BY NAME"].map((mode) => (
          <div key={mode} style={{
            padding: "8px 16px",
            background: "var(--dl-bg-elevated)",
            border: "1px solid var(--dl-border)",
            borderRadius: 6,
            fontSize: 11,
            fontWeight: 700,
            letterSpacing: 1,
            color: "var(--dl-text-muted)",
            fontFamily: "var(--dl-font-mono)",
          }}>
            {mode}
          </div>
        ))}
      </div>

      {/* Deep Intelligence layer card */}
      <div className="card" style={{ maxWidth: 600, width: "100%", borderColor: "var(--dl-border-bright)" }}>
        <div style={{ fontSize: 11, color: "var(--dl-teal)", fontWeight: 700, letterSpacing: 1, marginBottom: 8 }}>
          DEEP INTELLIGENCE LAYER
        </div>
        <p style={{ fontSize: 13, color: "var(--dl-text-secondary)", lineHeight: 1.6 }}>
          DealLens resolves any company globally, builds a live M&A intelligence profile,
          runs buy-side and sell-side target discovery, predicts regulatory clearance,
          and generates AI-drafted deal documents.
        </p>
      </div>

      {/* Full-width site footer */}
      <SiteFooter />

      {showDisambig && (
        <DisambiguationModal
          candidates={result?.candidates || []}
          onSelect={handleSelect}
          onClose={() => { setShowDisambig(false); reset(); }}
        />
      )}
    </main>
  );
}
