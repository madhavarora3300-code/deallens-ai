import React from "react";
import { Routes, Route, NavLink, useNavigate } from "react-router-dom";
import { SearchHome } from "./screens/SearchHome.jsx";
import { CompanyPage } from "./screens/CompanyPage.jsx";
import { BuySideDiscovery } from "./screens/BuySideDiscovery.jsx";
import { SellSideDiscovery } from "./screens/SellSideDiscovery.jsx";
import { RegulatoryLens } from "./screens/RegulatoryLens.jsx";
import { Drafts } from "./screens/Drafts.jsx";
import { MarketIntelligence } from "./screens/MarketIntelligence.jsx";
import { Shortlists } from "./screens/Shortlists.jsx";
import { DeepAnalysis } from "./screens/DeepAnalysis.jsx";
import { StatusBar } from "./components/StatusBar.jsx";
import { SearchBar } from "./components/SearchBar.jsx";
import { useCompanySearch } from "./hooks/useCompanySearch.js";
import { DisambiguationModal } from "./components/DisambiguationModal.jsx";

const NAV_ITEMS = [
  { to: "/", label: "Company", sublabel: "Intelligence profile", end: true },
  { to: "/buy-side", label: "Buy Side", sublabel: "Target discovery" },
  { to: "/sell-side", label: "Sell Side", sublabel: "Buyer universe" },
  { to: "/regulatory", label: "Regulatory", sublabel: "Clearance lens" },
  { to: "/drafts", label: "Drafts", sublabel: "AI workbench" },
  { to: "/market-intel", label: "Market Intel", sublabel: "Live signals" },
  { to: "/shortlists",   label: "Shortlists",   sublabel: "Saved companies" },
];

function GlobalSearch() {
  const navigate = useNavigate();
  const { result, loading, search, reset } = useCompanySearch();
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

  return (
    <>
      <div style={{ width: 320 }}>
        <SearchBar onSearch={handleSearch} loading={loading} placeholder="⌘K  Search any company..." />
      </div>
      {showDisambig && (
        <DisambiguationModal
          candidates={result?.candidates || []}
          onSelect={(c) => { setShowDisambig(false); reset(); navigate(`/company/${c.company_id}`); }}
          onClose={() => { setShowDisambig(false); reset(); }}
        />
      )}
    </>
  );
}

export default function App() {
  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", minHeight: "100vh" }}>
      {/* Top nav */}
      <header style={{
        display: "flex",
        alignItems: "center",
        gap: 24,
        padding: "0 20px",
        height: 56,
        background: "var(--dl-bg-secondary)",
        borderBottom: "1px solid var(--dl-border)",
        flexShrink: 0,
      }}>
        {/* Wordmark */}
        <div style={{ fontSize: 16, fontWeight: 800, whiteSpace: "nowrap", letterSpacing: -0.5 }}>
          <span style={{ color: "var(--dl-gold)" }}>Deal</span>
          <span style={{ color: "var(--dl-teal)" }}>Lens</span>
        </div>

        {/* Nav links */}
        <nav style={{ display: "flex", gap: 4 }}>
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              style={({ isActive }) => ({
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                padding: "4px 12px",
                borderRadius: 6,
                textDecoration: "none",
                background: isActive ? "var(--dl-bg-elevated)" : "transparent",
                borderBottom: isActive ? "2px solid var(--dl-teal)" : "2px solid transparent",
              })}
            >
              {({ isActive }) => (
                <>
                  <span style={{ fontSize: 12, fontWeight: 600, color: isActive ? "var(--dl-text-primary)" : "var(--dl-text-muted)" }}>
                    {item.label}
                  </span>
                  <span style={{ fontSize: 9, color: "var(--dl-text-muted)", letterSpacing: 0.5 }}>
                    {item.sublabel}
                  </span>
                </>
              )}
            </NavLink>
          ))}
        </nav>

        <div style={{ flex: 1 }} />
        <GlobalSearch />
      </header>

      {/* Page content */}
      <div style={{ flex: 1, overflowY: "auto" }}>
        <Routes>
          <Route path="/" element={<SearchHome />} />
          <Route path="/company/:companyId" element={<CompanyPage />} />
          <Route path="/buy-side" element={<BuySideDiscovery />} />
          <Route path="/sell-side" element={<SellSideDiscovery />} />
          <Route path="/regulatory" element={<RegulatoryLens />} />
          <Route path="/drafts" element={<Drafts />} />
          <Route path="/market-intel" element={<MarketIntelligence />} />
          <Route path="/shortlists" element={<Shortlists />} />
          <Route path="/deep-analysis" element={<DeepAnalysis />} />
        </Routes>
      </div>

      {/* Status bar — always visible */}
      <StatusBar systemStatus="NOMINAL" />
    </div>
  );
}
