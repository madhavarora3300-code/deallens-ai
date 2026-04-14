import React, { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { generateDraft } from "../api/deallens.js";
import { SearchBar } from "../components/SearchBar.jsx";
import { DisambiguationModal } from "../components/DisambiguationModal.jsx";
import { SkeletonLoader } from "../components/SkeletonLoader.jsx";
import { useCompanySearch } from "../hooks/useCompanySearch.js";

const DRAFT_TYPES = [
  "investment_thesis",
  "teaser",
  "cim_outline",
  "loi_points",
  "board_memo_bullets",
  "synergy_analysis",
];

const DRAFT_LABELS = {
  investment_thesis:    "Investment Thesis",
  teaser:               "Teaser",
  cim_outline:          "CIM Outline",
  loi_points:           "LOI Points",
  board_memo_bullets:   "Board Memo Bullets",
  synergy_analysis:     "Synergy Analysis",
};

// draft types that benefit from a counterparty (two-company context)
const COUNTERPARTY_TYPES = new Set(["synergy_analysis", "loi_points", "investment_thesis"]);

export function Drafts() {
  const [searchParams] = useSearchParams();

  // Primary company — pre-seed from URL ?company=id
  const [company, setCompany] = useState(
    searchParams.get("company") ? { company_id: searchParams.get("company"), legal_name: searchParams.get("company") } : null
  );
  const [showDisambigA, setShowDisambigA] = useState(false);
  const searchA = useCompanySearch();

  // Counterparty (optional)
  const [counterparty, setCounterparty] = useState(null);
  const [showDisambigB, setShowDisambigB] = useState(false);
  const searchB = useCompanySearch();

  const [projectName, setProjectName] = useState("");
  const [draftType, setDraftType] = useState("investment_thesis");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSearchA = async (q) => {
    const data = await searchA.search(q);
    if (!data) return;
    if (data.resolution_status === "ambiguous") {
      setShowDisambigA(true);
    } else if (data.resolved) {
      setCompany(data.resolved);
    }
  };

  const handleSearchB = async (q) => {
    const data = await searchB.search(q);
    if (!data) return;
    if (data.resolution_status === "ambiguous") {
      setShowDisambigB(true);
    } else if (data.resolved) {
      setCounterparty(data.resolved);
    }
  };

  const handleGenerate = async () => {
    if (!company?.company_id) return;
    setLoading(true);
    setError(null);
    try {
      const payload = {
        company_id: company.company_id,
        draft_type: draftType,
        project_name: projectName || undefined,
      };
      if (counterparty?.company_id) {
        payload.counterparty_id = counterparty.company_id;
      }
      const data = await generateDraft(payload);
      setResult(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const needsCounterparty = COUNTERPARTY_TYPES.has(draftType);

  return (
    <main style={{ padding: 24, display: "flex", flexDirection: "column", gap: 20, maxWidth: 1200, margin: "0 auto", width: "100%" }}>
      <h2 style={{ fontSize: 20, fontWeight: 700 }}>AI Drafts Workbench</h2>

      {/* Company search row */}
      <div style={{ display: "grid", gridTemplateColumns: needsCounterparty ? "1fr 1fr" : "1fr", gap: 16 }}>
        {/* Primary company */}
        <div>
          <div style={{ fontSize: 11, color: "var(--dl-text-muted)", fontWeight: 600, letterSpacing: 1, marginBottom: 6 }}>
            COMPANY
          </div>
          {company ? (
            <div style={{
              display: "flex", alignItems: "center", justifyContent: "space-between",
              padding: "10px 14px", background: "var(--dl-bg-elevated)",
              border: "1px solid var(--dl-teal)", borderRadius: 8,
            }}>
              <div>
                <div style={{ fontWeight: 600, fontSize: 13 }}>{company.legal_name || company.display_name}</div>
                {company.ticker && <div style={{ fontSize: 11, color: "var(--dl-gold)", fontFamily: "var(--dl-font-mono)" }}>{company.ticker}</div>}
              </div>
              <button
                onClick={() => { setCompany(null); searchA.reset(); }}
                style={{ background: "none", border: "none", color: "var(--dl-text-muted)", cursor: "pointer", fontSize: 16, padding: "0 4px" }}
              >
                ×
              </button>
            </div>
          ) : (
            <SearchBar
              onSearch={handleSearchA}
              loading={searchA.loading}
              placeholder="Search company..."
            />
          )}
        </div>

        {/* Counterparty — only shown for relevant draft types */}
        {needsCounterparty && (
          <div>
            <div style={{ fontSize: 11, color: "var(--dl-text-muted)", fontWeight: 600, letterSpacing: 1, marginBottom: 6 }}>
              COUNTERPARTY <span style={{ color: "var(--dl-text-muted)", fontWeight: 400 }}>(optional)</span>
            </div>
            {counterparty ? (
              <div style={{
                display: "flex", alignItems: "center", justifyContent: "space-between",
                padding: "10px 14px", background: "var(--dl-bg-elevated)",
                border: "1px solid var(--dl-gold)", borderRadius: 8,
              }}>
                <div>
                  <div style={{ fontWeight: 600, fontSize: 13 }}>{counterparty.legal_name || counterparty.display_name}</div>
                  {counterparty.ticker && <div style={{ fontSize: 11, color: "var(--dl-gold)", fontFamily: "var(--dl-font-mono)" }}>{counterparty.ticker}</div>}
                </div>
                <button
                  onClick={() => { setCounterparty(null); searchB.reset(); }}
                  style={{ background: "none", border: "none", color: "var(--dl-text-muted)", cursor: "pointer", fontSize: 16, padding: "0 4px" }}
                >
                  ×
                </button>
              </div>
            ) : (
              <SearchBar
                onSearch={handleSearchB}
                loading={searchB.loading}
                placeholder="Search counterparty..."
              />
            )}
          </div>
        )}
      </div>

      {/* Controls row */}
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "flex-end" }}>
        <div style={{ flex: 1, minWidth: 200 }}>
          <div style={{ fontSize: 11, color: "var(--dl-text-muted)", fontWeight: 600, letterSpacing: 1, marginBottom: 6 }}>PROJECT NAME</div>
          <input
            value={projectName}
            onChange={(e) => setProjectName(e.target.value)}
            placeholder="e.g. Project Obsidian — Q3 Acquisitions"
            style={{
              width: "100%", padding: "10px 12px", background: "var(--dl-bg-elevated)",
              border: "1px solid var(--dl-border)", borderRadius: 8,
              color: "var(--dl-text-primary)", fontSize: 13, outline: "none",
            }}
          />
        </div>
        <div>
          <div style={{ fontSize: 11, color: "var(--dl-text-muted)", fontWeight: 600, letterSpacing: 1, marginBottom: 6 }}>DRAFT TYPE</div>
          <select
            value={draftType}
            onChange={(e) => setDraftType(e.target.value)}
            style={{
              padding: "10px 12px", background: "var(--dl-bg-elevated)", border: "1px solid var(--dl-border)",
              borderRadius: 8, color: "var(--dl-text-primary)", fontSize: 13, fontFamily: "var(--dl-font-sans)",
            }}
          >
            {DRAFT_TYPES.map((t) => (
              <option key={t} value={t}>{DRAFT_LABELS[t]}</option>
            ))}
          </select>
        </div>
        <button
          onClick={handleGenerate}
          disabled={loading || !company?.company_id}
          style={{
            padding: "10px 24px", fontWeight: 700, fontSize: 13,
            background: (!company?.company_id || loading) ? "var(--dl-bg-elevated)" : "var(--dl-purple)",
            color: (!company?.company_id || loading) ? "var(--dl-text-muted)" : "#fff",
            border: (!company?.company_id || loading) ? "1px solid var(--dl-border)" : "none",
            borderRadius: 8, cursor: (!company?.company_id || loading) ? "not-allowed" : "pointer",
            whiteSpace: "nowrap",
          }}
        >
          {loading ? "Generating..." : `Generate ${DRAFT_LABELS[draftType]} →`}
        </button>
      </div>

      {error && <div style={{ color: "var(--dl-red)", fontSize: 13 }}>{error}</div>}

      {loading && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16 }}>
          {[1, 2, 3].map(i => <SkeletonLoader key={i} height={300} borderRadius={10} />)}
        </div>
      )}

      {result && !loading && (
        <>
          {/* Draft header */}
          {(result.project_name || result.draft_id) && (
            <div style={{ display: "flex", gap: 16, alignItems: "center" }}>
              {result.project_name && (
                <div style={{ fontWeight: 700, fontSize: 15 }}>{result.project_name}</div>
              )}
              {result.draft_id && (
                <span style={{ fontSize: 11, fontFamily: "var(--dl-font-mono)", color: "var(--dl-text-muted)" }}>
                  {result.draft_id}
                </span>
              )}
              {result.word_count && (
                <span style={{ fontSize: 11, color: "var(--dl-text-muted)" }}>{result.word_count} words</span>
              )}
              {result.confidence_score && (
                <span style={{ fontSize: 11, color: "var(--dl-teal)" }}>
                  Confidence: {result.confidence_score}%
                </span>
              )}
            </div>
          )}

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16 }}>
            {/* Thesis bullets */}
            <div className="card">
              <div style={{ fontSize: 11, color: "var(--dl-text-muted)", letterSpacing: 1, fontWeight: 600, marginBottom: 12 }}>THESIS BULLETS</div>
              {result.thesis_bullets?.length > 0
                ? result.thesis_bullets.map((b, i) => (
                    <div key={i} style={{ marginBottom: 10, display: "flex", gap: 8, fontSize: 13, color: "var(--dl-text-secondary)", lineHeight: 1.5 }}>
                      <span style={{ color: "var(--dl-green)", flexShrink: 0 }}>✓</span>
                      <span>{typeof b === "string" ? b : b.text}</span>
                    </div>
                  ))
                : <div style={{ color: "var(--dl-text-muted)", fontSize: 12 }}>No thesis bullets in this draft type.</div>
              }
            </div>

            {/* Executive summary / strategic rationale / situation overview */}
            <div className="card">
              <div style={{ fontSize: 11, color: "var(--dl-text-muted)", letterSpacing: 1, fontWeight: 600, marginBottom: 12 }}>
                {result.executive_summary ? "EXECUTIVE SUMMARY"
                  : result.strategic_rationale ? "STRATEGIC RATIONALE"
                  : result.situation_overview ? "SITUATION OVERVIEW"
                  : "SUMMARY"}
              </div>
              <p style={{ fontSize: 13, color: "var(--dl-text-secondary)", lineHeight: 1.7 }}>
                {result.executive_summary
                  || result.strategic_rationale
                  || result.situation_overview
                  || result.recommendation
                  || result.strategic_summary
                  || "—"}
              </p>
            </div>

            {/* Risks + Why Now */}
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              {(result.why_not_now_risks?.length > 0 || result.key_risks?.length > 0 || result.risk_factors?.length > 0) && (
                <div className="card">
                  <div style={{ fontSize: 11, color: "var(--dl-text-muted)", letterSpacing: 1, fontWeight: 600, marginBottom: 12 }}>KEY RISKS</div>
                  {(result.why_not_now_risks || result.key_risks || result.risk_factors || []).map((r, i) => (
                    <div key={i} style={{ fontSize: 12, color: "var(--dl-text-secondary)", marginBottom: 6, display: "flex", gap: 6 }}>
                      <span style={{ color: "var(--dl-amber)", flexShrink: 0 }}>{i + 1}.</span>
                      <span>{r}</span>
                    </div>
                  ))}
                </div>
              )}
              {result.why_now && (
                <div className="card" style={{ borderColor: "var(--dl-teal)" }}>
                  <div style={{ fontSize: 11, color: "var(--dl-teal)", letterSpacing: 1, fontWeight: 600, marginBottom: 8 }}>WHY NOW</div>
                  <p style={{ fontSize: 12, color: "var(--dl-text-secondary)" }}>{result.why_now}</p>
                </div>
              )}
              {result.risk_assessment && (
                <div className="card" style={{ borderColor: "var(--dl-amber)" }}>
                  <div style={{ fontSize: 11, color: "var(--dl-amber)", letterSpacing: 1, fontWeight: 600, marginBottom: 8 }}>RISK ASSESSMENT</div>
                  <p style={{ fontSize: 12, color: "var(--dl-text-secondary)" }}>{result.risk_assessment}</p>
                </div>
              )}
            </div>
          </div>
        </>
      )}

      {/* Disambiguation modals */}
      {showDisambigA && (
        <DisambiguationModal
          candidates={searchA.result?.candidates || []}
          onSelect={(c) => { setShowDisambigA(false); setCompany(c); searchA.reset(); }}
          onClose={() => { setShowDisambigA(false); searchA.reset(); }}
        />
      )}
      {showDisambigB && (
        <DisambiguationModal
          candidates={searchB.result?.candidates || []}
          onSelect={(c) => { setShowDisambigB(false); setCounterparty(c); searchB.reset(); }}
          onClose={() => { setShowDisambigB(false); searchB.reset(); }}
        />
      )}
    </main>
  );
}
