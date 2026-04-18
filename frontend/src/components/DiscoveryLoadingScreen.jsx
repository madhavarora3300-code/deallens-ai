import React, { useState, useEffect, useRef } from "react";

const SOURCES = [
  "SEC Filings", "Bloomberg Terminal", "Reuters M&A", "Private Equity DB",
  "Crunchbase", "PitchBook", "Dealogic", "Refinitiv Eikon", "S&P Capital IQ",
  "Mergermarket", "FactSet", "CB Insights",
];

const LOG_TEMPLATES_BUYABLE = [
  (n) => `Resolving identity for ${n}...`,
  (n) => `Fetching financials for ${n}`,
  (n) => `Extracting ownership structure: ${n}`,
  (n) => `Scoring strategic fit: ${n}`,
  (n) => `Applying hard gates: ${n}`,
  (n) => `Computing deal score: ${n}`,
];

const SAMPLE_NAMES_BY_SECTOR = {
  Technology: ["Snowflake Inc.", "UiPath SA", "Celonis SE", "SUSE S.A.", "Mimecast Ltd.", "Bazaarvoice Inc.", "Medallia Inc.", "Qualtrics International"],
  "Financial Services": ["Finastra Group", "nCino Inc.", "Temenos AG", "Mambu GmbH", "Thought Machine", "Marqeta Inc.", "Blend Labs", "Solarisbank AG"],
  Industrials: ["Roper Technologies", "Watts Water Technologies", "Hexcel Corp.", "Zurn Elkay Water", "Chart Industries", "Watts Industries", "Colfax Corp."],
  Healthcare: ["Veeva Systems", "Invacare Corp.", "Natus Medical", "Meridian Bioscience", "Luminex Corp.", "Haemonetics Corp.", "NovaBay Pharma"],
  "Consumer Discretionary": ["Sonder Holdings", "Rover Group", "Rent the Runway", "Poshmark Inc.", "Kidoz Inc.", "Marley Spoon AG"],
  Energy: ["Archaea Energy", "Carbon Clean Solutions", "Bloom Energy", "Stem Inc.", "Eos Energy Enterprises", "Electriq Power"],
  default: ["ABBYY Group", "Boomi Inc.", "Citrix Systems", "Compuware Corp.", "Epicor Software", "Infor Inc.", "IDERA Inc.", "Ivanti Software"],
};

function getNames(sector) {
  return SAMPLE_NAMES_BY_SECTOR[sector] || SAMPLE_NAMES_BY_SECTOR.default;
}

const PHASES = [
  { id: "scan",   label: "Scanning Global Landscape",   pct: 0,  endPct: 20 },
  { id: "enrich", label: "Enriching Candidate Profiles", pct: 20, endPct: 70 },
  { id: "score",  label: "Scoring & Ranking",            pct: 70, endPct: 98 },
];

// statusPhase: "queued" | "running" | "scoring" — from the backend job status poll
const STATUS_PHASE_LABEL = {
  queued:  "Job queued — waiting for worker...",
  running: "AI seeding candidates from global M&A landscape...",
  scoring: "Scoring & ranking candidates...",
};

export function DiscoveryLoadingScreen({ mode = "buy_side", anchorName = "", strategyHint = "", anchorSector = "", statusPhase = "" }) {
  const [progress, setProgress] = useState(0);
  const [phase, setPhase] = useState(0);       // 0,1,2
  const [logLines, setLogLines] = useState([]);
  const [activeSources, setActiveSources] = useState([]);
  const [candidateNames, setCandidateNames] = useState([]);
  const [enrichCount, setEnrichCount] = useState(0);
  const enrichTotal = 20;
  const logRef = useRef(null);
  const names = getNames(anchorSector);

  // Smooth progress increment
  useEffect(() => {
    const phaseObj = PHASES[phase];
    if (!phaseObj) return;
    const range = phaseObj.endPct - phaseObj.pct;
    // Each phase advances over its allotted "time slice"
    // Total ~90s: phase 0 = 15s, phase 1 = 50s, phase 2 = 25s
    const durations = [15000, 50000, 25000];
    const interval = durations[phase] / range;
    const timer = setInterval(() => {
      setProgress(prev => {
        const next = prev + 1;
        if (next >= phaseObj.endPct) {
          clearInterval(timer);
          if (phase < PHASES.length - 1) setPhase(p => p + 1);
        }
        return Math.min(next, 98);
      });
    }, interval);
    return () => clearInterval(timer);
  }, [phase]);

  // Phase 0: animate sources and candidate names appearing
  useEffect(() => {
    if (phase !== 0) return;
    let sourceIdx = 0;
    const srcTimer = setInterval(() => {
      if (sourceIdx < SOURCES.length) {
        setActiveSources(prev => [...prev, SOURCES[sourceIdx++]]);
      } else {
        clearInterval(srcTimer);
      }
    }, 1200);

    let nameIdx = 0;
    const nameTimer = setInterval(() => {
      if (nameIdx < Math.min(8, names.length)) {
        setCandidateNames(prev => [...prev, names[nameIdx++]]);
      } else {
        clearInterval(nameTimer);
      }
    }, 1600);

    return () => { clearInterval(srcTimer); clearInterval(nameTimer); };
  }, [phase]);

  // Phase 1: increment enrichment counter and show log lines
  useEffect(() => {
    if (phase !== 1) return;
    let count = 0;
    const logTimer = setInterval(() => {
      if (count >= enrichTotal) { clearInterval(logTimer); return; }
      const n = names[count % names.length];
      const template = LOG_TEMPLATES_BUYABLE[count % LOG_TEMPLATES_BUYABLE.length];
      setLogLines(prev => [...prev.slice(-12), template(n)]);
      setEnrichCount(c => Math.min(c + 1, enrichTotal));
      count++;
    }, 2500);
    return () => clearInterval(logTimer);
  }, [phase]);

  // Phase 2: scoring log lines
  useEffect(() => {
    if (phase !== 2) return;
    const msgs = [
      "Applying hard gates (sanctions, size, same-entity)...",
      "Computing strategic alpha scores...",
      "Evaluating dealability & ownership...",
      "Assessing regulatory path...",
      "Calculating valuation burden...",
      "Ranking by deal score...",
      "Generating AI rationale for top results...",
    ];
    let i = 0;
    const timer = setInterval(() => {
      if (i < msgs.length) setLogLines(prev => [...prev.slice(-12), msgs[i++]]);
      else clearInterval(timer);
    }, 3200);
    return () => clearInterval(timer);
  }, [phase]);

  // Auto-scroll log
  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [logLines]);

  const strategyLabel = strategyHint.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
  const modeLabel = mode === "buy_side" ? "Acquisition Targets" : "Potential Acquirers";

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24, padding: "8px 0" }}>

      {/* Header */}
      <div>
        <div style={{ fontSize: 11, color: "var(--dl-text-muted)", letterSpacing: 1, fontWeight: 600, marginBottom: 6 }}>
          AI DISCOVERY ENGINE
        </div>
        <div style={{ fontSize: 15, fontWeight: 600, color: "var(--dl-text-primary)" }}>
          Scanning global landscape for{" "}
          <span style={{ color: "var(--dl-teal)" }}>{strategyLabel || "strategic"}</span>{" "}
          {modeLabel}
          {anchorName ? <span style={{ color: "var(--dl-gold)" }}> · {anchorName}</span> : ""}
        </div>
      </div>

      {/* Progress bar */}
      <div>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
          <span style={{ fontSize: 11, fontWeight: 700, color: PHASES[phase]?.id === "score" ? "var(--dl-gold)" : "var(--dl-teal)", letterSpacing: 1 }}>
            {PHASES[phase]?.label?.toUpperCase()}
          </span>
          <span style={{ fontSize: 11, fontFamily: "var(--dl-font-mono)", color: "var(--dl-text-muted)" }}>
            {progress}%
          </span>
        </div>
        <div style={{ height: 4, background: "var(--dl-bg-elevated)", borderRadius: 2, overflow: "hidden" }}>
          <div style={{
            height: "100%",
            width: `${progress}%`,
            background: `linear-gradient(90deg, var(--dl-teal), var(--dl-gold))`,
            borderRadius: 2,
            transition: "width 0.8s ease",
          }} />
        </div>
        {/* Phase steps */}
        <div style={{ display: "flex", gap: 0, marginTop: 10 }}>
          {PHASES.map((p, i) => (
            <div key={p.id} style={{ flex: 1, display: "flex", alignItems: "center", gap: 6 }}>
              <div style={{
                width: 20, height: 20, borderRadius: "50%", flexShrink: 0,
                display: "flex", alignItems: "center", justifyContent: "center",
                background: i < phase ? "var(--dl-teal)" : i === phase ? "var(--dl-gold)" : "var(--dl-bg-elevated)",
                border: `1px solid ${i < phase ? "var(--dl-teal)" : i === phase ? "var(--dl-gold)" : "var(--dl-border)"}`,
                fontSize: 9, fontWeight: 700, color: i <= phase ? "#000" : "var(--dl-text-muted)",
                fontFamily: "var(--dl-font-mono)",
              }}>
                {i < phase ? "✓" : i + 1}
              </div>
              <span style={{ fontSize: 10, color: i === phase ? "var(--dl-text-primary)" : "var(--dl-text-muted)", fontWeight: i === phase ? 600 : 400 }}>
                {p.label}
              </span>
              {i < PHASES.length - 1 && (
                <div style={{ flex: 1, height: 1, background: i < phase ? "var(--dl-teal)" : "var(--dl-border)", margin: "0 8px" }} />
              )}
            </div>
          ))}
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>

        {/* Left: Sources / Candidates */}
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {phase === 0 && (
            <>
              <div>
                <div style={{ fontSize: 10, color: "var(--dl-text-muted)", fontWeight: 600, letterSpacing: 1, marginBottom: 8 }}>
                  DATA SOURCES ACTIVE
                </div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                  {activeSources.map((s, i) => (
                    <span key={i} style={{
                      fontSize: 10, padding: "3px 8px", borderRadius: 4,
                      background: "var(--dl-bg-elevated)",
                      border: "1px solid var(--dl-teal)",
                      color: "var(--dl-teal)",
                      fontFamily: "var(--dl-font-mono)",
                      animation: "fadeIn 0.4s ease",
                    }}>
                      {s}
                    </span>
                  ))}
                </div>
              </div>
              {candidateNames.length > 0 && (
                <div>
                  <div style={{ fontSize: 10, color: "var(--dl-text-muted)", fontWeight: 600, letterSpacing: 1, marginBottom: 8 }}>
                    CANDIDATES IDENTIFIED
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
                    {candidateNames.map((n, i) => (
                      <div key={i} style={{
                        fontSize: 12, color: "var(--dl-text-secondary)",
                        display: "flex", alignItems: "center", gap: 8,
                        animation: "fadeIn 0.4s ease",
                      }}>
                        <span style={{ color: "var(--dl-gold)", fontSize: 10 }}>◆</span>
                        {n}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}

          {phase === 1 && (
            <div>
              <div style={{ fontSize: 10, color: "var(--dl-text-muted)", fontWeight: 600, letterSpacing: 1, marginBottom: 10 }}>
                PROFILE ENRICHMENT
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12 }}>
                <div style={{ fontFamily: "var(--dl-font-mono)", fontSize: 28, fontWeight: 700, color: "var(--dl-teal)" }}>
                  {enrichCount}
                </div>
                <div>
                  <div style={{ fontSize: 11, color: "var(--dl-text-secondary)" }}>of {enrichTotal} candidates enriched</div>
                  <div style={{ height: 3, width: 140, background: "var(--dl-bg-elevated)", borderRadius: 2, marginTop: 4 }}>
                    <div style={{
                      height: "100%", width: `${(enrichCount / enrichTotal) * 100}%`,
                      background: "var(--dl-teal)", borderRadius: 2, transition: "width 0.5s ease",
                    }} />
                  </div>
                </div>
              </div>
              <div style={{ fontSize: 10, color: "var(--dl-text-muted)", fontWeight: 600, letterSpacing: 1, marginBottom: 8 }}>
                ENRICHMENT PASSES
              </div>
              {["Pass 1: Identity + Financials", "Pass 2: Ownership + Strategy"].map((pass, i) => (
                <div key={i} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
                  <div style={{
                    width: 6, height: 6, borderRadius: "50%",
                    background: enrichCount > (i === 0 ? 0 : enrichTotal / 2) ? "var(--dl-teal)" : "var(--dl-border)",
                  }} />
                  <span style={{ fontSize: 11, color: enrichCount > (i === 0 ? 0 : enrichTotal / 2) ? "var(--dl-text-secondary)" : "var(--dl-text-muted)" }}>
                    {pass}
                  </span>
                </div>
              ))}
            </div>
          )}

          {phase === 2 && (
            <div>
              <div style={{ fontSize: 10, color: "var(--dl-text-muted)", fontWeight: 600, letterSpacing: 1, marginBottom: 10 }}>
                SCORING ENGINE
              </div>
              {[
                { label: "Strategic Alpha", max: 24, color: "var(--dl-teal)" },
                { label: "Dealability", max: 16, color: "var(--dl-gold)" },
                { label: "Financial Health", max: 14, color: "var(--dl-green)" },
                { label: "Regulatory Path", max: 10, color: "var(--dl-blue)" },
              ].map(({ label, max, color }, i) => (
                <div key={i} style={{ marginBottom: 8 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 3 }}>
                    <span style={{ fontSize: 10, color: "var(--dl-text-muted)" }}>{label}</span>
                    <span style={{ fontSize: 10, fontFamily: "var(--dl-font-mono)", color }}>/{max}</span>
                  </div>
                  <div style={{ height: 3, background: "var(--dl-bg-elevated)", borderRadius: 2 }}>
                    <div style={{
                      height: "100%", borderRadius: 2,
                      width: progress >= 80 ? "75%" : progress >= 75 ? "50%" : "20%",
                      background: color, transition: "width 1s ease",
                    }} />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Right: Live log */}
        <div>
          <div style={{ fontSize: 10, color: "var(--dl-text-muted)", fontWeight: 600, letterSpacing: 1, marginBottom: 8 }}>
            LIVE ACTIVITY
          </div>
          <div
            ref={logRef}
            style={{
              height: 220, overflowY: "auto",
              background: "var(--dl-bg-elevated)",
              borderRadius: 6, padding: "10px 12px",
              border: "1px solid var(--dl-border)",
              display: "flex", flexDirection: "column", gap: 5,
            }}
          >
            {logLines.length === 0 ? (
              <span style={{ fontSize: 11, color: "var(--dl-text-muted)" }}>Initialising discovery engine...</span>
            ) : (
              logLines.map((line, i) => (
                <div key={i} style={{ display: "flex", gap: 8, fontSize: 11, color: "var(--dl-text-secondary)", alignItems: "flex-start" }}>
                  <span style={{ color: "var(--dl-teal)", flexShrink: 0, marginTop: 1 }}>›</span>
                  {line}
                </div>
              ))
            )}
            {/* Blinking cursor */}
            <div style={{ display: "flex", gap: 8, fontSize: 11, color: "var(--dl-text-muted)", alignItems: "center" }}>
              <span style={{ color: "var(--dl-teal)" }}>›</span>
              <span style={{ animation: "blink 1s step-end infinite" }}>_</span>
            </div>
          </div>
        </div>

      </div>

      {/* Footer note */}
      <div style={{ fontSize: 11, color: "var(--dl-text-muted)", borderTop: "1px solid var(--dl-border)", paddingTop: 12, display: "flex", flexDirection: "column", gap: 4 }}>
        {statusPhase && STATUS_PHASE_LABEL[statusPhase] && (
          <div style={{ display: "flex", alignItems: "center", gap: 6, color: "var(--dl-teal)", fontFamily: "var(--dl-font-mono)", fontWeight: 600 }}>
            <span style={{ display: "inline-block", width: 6, height: 6, borderRadius: "50%",
              background: "var(--dl-teal)", animation: "pulse 1.2s infinite" }} />
            {STATUS_PHASE_LABEL[statusPhase]}
          </div>
        )}
        <div>
          AI is analysing global M&A landscape using GPT-4o-mini knowledge base. Results are strategy-specific and scored by the DealLens scoring engine.
          This typically takes 60–120 seconds for a full discovery run.
        </div>
      </div>

      <style>{`
        @keyframes fadeIn { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: translateY(0); } }
        @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0; } }
      `}</style>
    </div>
  );
}
