import React, { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
  listShortlists,
  getShortlist,
  removeFromShortlist,
} from "../api/deallens.js";

const TIER_COLOR = {
  "Tier 1": "var(--dl-teal)",
  "Tier 2": "var(--dl-amber)",
  "Tier 3": "var(--dl-text-muted)",
};

const TYPE_COLOR = {
  buy_side:  { label: "BUY SIDE",  color: "var(--dl-teal)" },
  sell_side: { label: "SELL SIDE", color: "var(--dl-gold)" },
  watchlist: { label: "WATCHLIST", color: "var(--dl-blue)" },
};

function fmtUSD(v) {
  if (v == null) return "—";
  if (v >= 1e9) return `$${(v / 1e9).toFixed(1)}B`;
  if (v >= 1e6) return `$${(v / 1e6).toFixed(0)}M`;
  return `$${v.toLocaleString()}`;
}

export function Shortlists() {
  const navigate = useNavigate();
  const [lists, setLists] = useState([]);
  const [activeId, setActiveId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [loadingLists, setLoadingLists] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [removing, setRemoving] = useState(null); // company_id being removed

  // Load all shortlists on mount
  const fetchLists = useCallback(async () => {
    setLoadingLists(true);
    try {
      const data = await listShortlists();
      setLists(Array.isArray(data) ? data : []);
    } catch {
      setLists([]);
    } finally {
      setLoadingLists(false);
    }
  }, []);

  useEffect(() => { fetchLists(); }, [fetchLists]);

  // Load detail when activeId changes
  useEffect(() => {
    if (!activeId) { setDetail(null); return; }
    setLoadingDetail(true);
    getShortlist(activeId)
      .then(setDetail)
      .catch(() => setDetail(null))
      .finally(() => setLoadingDetail(false));
  }, [activeId]);

  const handleRemove = async (shortlistId, companyId) => {
    setRemoving(companyId);
    try {
      await removeFromShortlist(shortlistId, companyId);
      // Refresh detail
      const updated = await getShortlist(shortlistId);
      setDetail(updated);
      // Update count in list
      setLists(prev => prev.map(l =>
        l.shortlist_id === shortlistId
          ? { ...l, company_count: (l.company_count || 1) - 1 }
          : l
      ));
    } catch {
      // ignore — entry may already be gone
    } finally {
      setRemoving(null);
    }
  };

  const activeList = lists.find(l => l.shortlist_id === activeId);

  return (
    <main style={{ padding: 24, display: "flex", flexDirection: "column", gap: 20, maxWidth: 1300, margin: "0 auto", width: "100%" }}>
      <h2 style={{ fontSize: 20, fontWeight: 700 }}>Shortlists</h2>

      <div style={{ display: "grid", gridTemplateColumns: "280px 1fr", gap: 20, alignItems: "start" }}>

        {/* Left sidebar — list of shortlists */}
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <div style={{ fontSize: 11, color: "var(--dl-text-muted)", fontWeight: 600, letterSpacing: 1, marginBottom: 4 }}>
            YOUR SHORTLISTS
          </div>

          {loadingLists && (
            [1, 2, 3].map(i => (
              <div key={i} style={{ height: 64, background: "var(--dl-bg-elevated)", borderRadius: 8, border: "1px solid var(--dl-border)" }} />
            ))
          )}

          {!loadingLists && lists.length === 0 && (
            <div style={{ fontSize: 13, color: "var(--dl-text-muted)", padding: "16px 0" }}>
              No shortlists yet. Add companies from the Buy-Side or Sell-Side discovery screens.
            </div>
          )}

          {lists.map(sl => {
            const typeInfo = TYPE_COLOR[sl.list_type] || TYPE_COLOR.watchlist;
            const isActive = sl.shortlist_id === activeId;
            return (
              <button
                key={sl.shortlist_id}
                onClick={() => setActiveId(isActive ? null : sl.shortlist_id)}
                style={{
                  textAlign: "left", padding: "12px 14px",
                  background: isActive ? "var(--dl-bg-elevated)" : "var(--dl-bg-secondary)",
                  border: isActive ? `1px solid ${typeInfo.color}` : "1px solid var(--dl-border)",
                  borderRadius: 8, cursor: "pointer", color: "var(--dl-text-primary)",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                  <div style={{ fontWeight: 600, fontSize: 13, lineHeight: 1.3, flex: 1, paddingRight: 8 }}>
                    {sl.name}
                  </div>
                  <span style={{
                    fontSize: 9, fontWeight: 700, padding: "2px 5px",
                    color: typeInfo.color, border: `1px solid ${typeInfo.color}`,
                    borderRadius: 3, whiteSpace: "nowrap", flexShrink: 0,
                  }}>
                    {typeInfo.label}
                  </span>
                </div>
                <div style={{ fontSize: 11, color: "var(--dl-text-muted)", marginTop: 5 }}>
                  {sl.company_count} {sl.company_count === 1 ? "company" : "companies"}
                  {sl.updated_at && (
                    <span> · {new Date(sl.updated_at).toLocaleDateString()}</span>
                  )}
                </div>
              </button>
            );
          })}
        </div>

        {/* Right panel — shortlist detail */}
        <div>
          {!activeId && (
            <div style={{
              height: 300, display: "flex", alignItems: "center", justifyContent: "center",
              color: "var(--dl-text-muted)", fontSize: 14, textAlign: "center",
              border: "1px dashed var(--dl-border)", borderRadius: 10,
            }}>
              <div>
                <div style={{ fontSize: 28, marginBottom: 12 }}>☰</div>
                Select a shortlist to view its companies
              </div>
            </div>
          )}

          {activeId && loadingDetail && (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {[1, 2, 3].map(i => (
                <div key={i} style={{ height: 52, background: "var(--dl-bg-elevated)", borderRadius: 8, border: "1px solid var(--dl-border)" }} />
              ))}
            </div>
          )}

          {activeId && !loadingDetail && detail && (
            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              {/* Detail header */}
              <div style={{ display: "flex", gap: 16, alignItems: "flex-start", justifyContent: "space-between" }}>
                <div>
                  <div style={{ fontWeight: 700, fontSize: 17 }}>{detail.name}</div>
                  {detail.description && (
                    <div style={{ fontSize: 12, color: "var(--dl-text-muted)", marginTop: 4 }}>{detail.description}</div>
                  )}
                  {detail.anchor_company_id && (
                    <div style={{ fontSize: 11, color: "var(--dl-text-muted)", marginTop: 4 }}>
                      Anchor: <span style={{ color: "var(--dl-teal)" }}>{detail.anchor_company_id}</span>
                    </div>
                  )}
                </div>
                <div style={{ fontSize: 11, color: "var(--dl-text-muted)", textAlign: "right", flexShrink: 0 }}>
                  <div>{detail.company_count} companies</div>
                  {detail.created_at && <div>Created {new Date(detail.created_at).toLocaleDateString()}</div>}
                </div>
              </div>

              {/* Company table */}
              {detail.companies?.length > 0 ? (
                <div className="card" style={{ padding: 0, overflow: "hidden" }}>
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                    <thead>
                      <tr style={{ background: "var(--dl-bg-tertiary)", fontSize: 10, color: "var(--dl-text-muted)", letterSpacing: 1 }}>
                        <th style={{ textAlign: "left", padding: "10px 14px", fontWeight: 600 }}>COMPANY</th>
                        <th style={{ textAlign: "left", padding: "10px 10px", fontWeight: 600 }}>SECTOR</th>
                        <th style={{ textAlign: "right", padding: "10px 10px", fontWeight: 600 }}>EV</th>
                        <th style={{ textAlign: "right", padding: "10px 10px", fontWeight: 600 }}>REVENUE</th>
                        <th style={{ textAlign: "center", padding: "10px 10px", fontWeight: 600 }}>SCORE</th>
                        <th style={{ textAlign: "center", padding: "10px 10px", fontWeight: 600 }}>TIER</th>
                        <th style={{ textAlign: "center", padding: "10px 10px", fontWeight: 600 }}>COVERAGE</th>
                        <th style={{ padding: "10px 14px" }} />
                      </tr>
                    </thead>
                    <tbody>
                      {detail.companies.map((co) => (
                        <tr
                          key={co.company_id}
                          style={{ borderTop: "1px solid var(--dl-border)", cursor: "pointer" }}
                          onClick={() => navigate(`/company/${co.company_id}`)}
                        >
                          <td style={{ padding: "12px 14px" }}>
                            <div style={{ fontWeight: 600 }}>{co.display_name || co.legal_name}</div>
                            <div style={{ fontSize: 11, color: "var(--dl-text-muted)", fontFamily: "var(--dl-font-mono)" }}>
                              {[co.ticker, co.jurisdiction].filter(Boolean).join(" · ")}
                            </div>
                          </td>
                          <td style={{ padding: "12px 10px", color: "var(--dl-text-secondary)", fontSize: 12 }}>
                            {co.sector || "—"}
                          </td>
                          <td style={{ padding: "12px 10px", textAlign: "right", fontFamily: "var(--dl-font-mono)", fontSize: 12 }}>
                            {fmtUSD(co.enterprise_value_usd)}
                          </td>
                          <td style={{ padding: "12px 10px", textAlign: "right", fontFamily: "var(--dl-font-mono)", fontSize: 12 }}>
                            {fmtUSD(co.revenue_usd)}
                          </td>
                          <td style={{ padding: "12px 10px", textAlign: "center", fontFamily: "var(--dl-font-mono)", fontWeight: 700 }}>
                            {co.deal_score != null
                              ? <span style={{ color: co.deal_score >= 65 ? "var(--dl-teal)" : co.deal_score >= 45 ? "var(--dl-amber)" : "var(--dl-text-muted)" }}>
                                  {Math.round(co.deal_score)}
                                </span>
                              : <span style={{ color: "var(--dl-text-muted)" }}>—</span>
                            }
                          </td>
                          <td style={{ padding: "12px 10px", textAlign: "center" }}>
                            {co.tier
                              ? <span style={{ fontSize: 10, fontWeight: 700, color: TIER_COLOR[co.tier] || "var(--dl-text-muted)" }}>
                                  {co.tier.toUpperCase()}
                                </span>
                              : <span style={{ color: "var(--dl-text-muted)" }}>—</span>
                            }
                          </td>
                          <td style={{ padding: "12px 10px", textAlign: "center" }}>
                            {co.coverage_depth
                              ? <span style={{ fontSize: 10, fontWeight: 600, color: co.coverage_depth === "DEEP" ? "var(--dl-teal)" : "var(--dl-text-muted)" }}>
                                  {co.coverage_depth}
                                </span>
                              : <span style={{ color: "var(--dl-text-muted)" }}>—</span>
                            }
                          </td>
                          <td style={{ padding: "12px 14px", textAlign: "right" }} onClick={e => e.stopPropagation()}>
                            <button
                              onClick={() => handleRemove(detail.shortlist_id, co.company_id)}
                              disabled={removing === co.company_id}
                              style={{
                                background: "none", border: "1px solid var(--dl-border)", borderRadius: 4,
                                color: removing === co.company_id ? "var(--dl-text-muted)" : "var(--dl-red)",
                                cursor: removing === co.company_id ? "not-allowed" : "pointer",
                                fontSize: 11, padding: "3px 8px",
                              }}
                            >
                              {removing === co.company_id ? "..." : "Remove"}
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div style={{
                  padding: 40, textAlign: "center", color: "var(--dl-text-muted)", fontSize: 13,
                  border: "1px dashed var(--dl-border)", borderRadius: 8,
                }}>
                  This shortlist is empty. Add companies from discovery results.
                </div>
              )}

              {/* Notes column if any company has notes */}
              {detail.companies?.some(c => c.notes) && (
                <div className="card">
                  <div style={{ fontSize: 11, color: "var(--dl-text-muted)", letterSpacing: 1, fontWeight: 600, marginBottom: 12 }}>NOTES</div>
                  {detail.companies.filter(c => c.notes).map(c => (
                    <div key={c.company_id} style={{ marginBottom: 10 }}>
                      <div style={{ fontSize: 12, fontWeight: 600, color: "var(--dl-text-primary)" }}>{c.display_name || c.legal_name}</div>
                      <div style={{ fontSize: 12, color: "var(--dl-text-secondary)", marginTop: 2, lineHeight: 1.5 }}>{c.notes}</div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
