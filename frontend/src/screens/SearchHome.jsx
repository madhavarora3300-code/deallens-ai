import React from "react";
import { useNavigate } from "react-router-dom";
import { SearchBar } from "../components/SearchBar.jsx";
import { DisambiguationModal } from "../components/DisambiguationModal.jsx";
import { useCompanySearch } from "../hooks/useCompanySearch.js";

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
      alignItems: "center", justifyContent: "center",
      padding: "40px 20px", gap: 32,
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
