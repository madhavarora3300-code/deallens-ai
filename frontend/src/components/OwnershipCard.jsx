import React from "react";

export function OwnershipCard({ ownership = {} }) {
  const { ownership_structure, controlling_shareholder, controlling_stake_pct, pe_sponsor, pe_vintage_year } = ownership;
  return (
    <div className="card">
      <div style={{ fontSize: 11, color: "var(--dl-text-muted)", letterSpacing: 1, fontWeight: 600, marginBottom: 12 }}>
        OWNERSHIP & CONTROL
      </div>
      {ownership_structure && (
        <div style={{ marginBottom: 10 }}>
          <div style={{ fontSize: 11, color: "var(--dl-text-muted)" }}>Structure</div>
          <div style={{ fontWeight: 600, textTransform: "capitalize" }}>{ownership_structure.replace(/_/g, " ")}</div>
        </div>
      )}
      {controlling_shareholder && (
        <div style={{ marginBottom: 10 }}>
          <div style={{ fontSize: 11, color: "var(--dl-text-muted)" }}>Controlling Shareholder</div>
          <div style={{ fontWeight: 600 }}>{controlling_shareholder}</div>
          {controlling_stake_pct != null && (
            <div style={{ fontFamily: "var(--dl-font-mono)", fontSize: 13, color: "var(--dl-gold)", fontWeight: 700 }}>
              {controlling_stake_pct}%
            </div>
          )}
        </div>
      )}
      {pe_sponsor && (
        <div style={{ marginBottom: 10 }}>
          <div style={{ fontSize: 11, color: "var(--dl-text-muted)" }}>PE Sponsor</div>
          <div style={{ fontWeight: 600 }}>{pe_sponsor}</div>
          {pe_vintage_year && (
            <div style={{ fontSize: 11, color: "var(--dl-text-secondary)" }}>Vintage {pe_vintage_year}</div>
          )}
        </div>
      )}
      {!controlling_shareholder && !pe_sponsor && ownership_structure && (
        <div style={{ fontSize: 12, color: "var(--dl-text-muted)", marginTop: 4 }}>
          Widely held public company — no controlling shareholder
        </div>
      )}
    </div>
  );
}
