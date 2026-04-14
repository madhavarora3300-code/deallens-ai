# DealLens AI — Project Memory

## What this is
DealLens AI is a live M&A intelligence portal for investment bankers.
Built from scratch. Fresh codebase. No legacy code.

## Location
/mnt/c/Users/maddy/Desktop/deallens

## Start command
cd /mnt/c/Users/maddy/Desktop/deallens
sudo docker compose up -d

## URLs
Frontend: http://localhost:3001
Backend:  http://localhost:8001
API docs: http://localhost:8001/docs

## API version
All endpoints under /v1

## Golden rules
1. AI extracts features. Python scores. Never reversed.
2. Every response has sources[], confidence_score, freshness_status.
3. Missing data = null. Never fabricated.
4. Hard gates before scoring. Always.
5. Confidence separate from deal score. Never blend.
6. GPT-4o for research. GPT-4o-mini for extraction and narration.
7. No hardcoded company lists.

## Scoring weights (buy-side)
strategic_alpha: 24, dealability: 16, financial_health: 14,
execution_complexity: 10, regulatory_path: 10,
valuation_burden: 10, size_feasibility: 10,
process_momentum: 4, scarcity: 2

## Scoring weights (sell-side)
strategic_need: 22, ability_to_pay: 16, certainty_of_close: 16,
regulatory_path: 12, valuation_tension: 12, process_credibility: 8,
execution_compatibility: 6, sponsor_positioning: 4, momentum: 4

## Hard gates (exclude before scoring)
SANCTIONED_JURISDICTION: RU, IR, KP, SY, CU, BY
TARGET_TOO_LARGE: target_ev > 1.2x buyer_ev (except merger_of_equals)
SAME_ENTITY: buyer and target are same company
FDI_PROHIBITED: specific sector/jurisdiction combos
NO_MINIMUM_DATA: cannot resolve company at all

## Tier logic
Tier 1: deal_score >= 65 AND confidence_score >= 60 AND no hard gate
Tier 2: deal_score >= 45 OR confidence_score >= 50 AND no hard gate
Tier 3: everything else with no hard gate
Excluded: any hard gate triggered

## Tech stack
Backend:  Python 3.11 + FastAPI (internal port 8000, host port 8001)
Database: PostgreSQL 15 + SQLAlchemy async + Alembic
Cache:    Redis 7
Queue:    Celery 5 + Redis
Frontend: React 18 + Vite (internal port 3000, host port 3001)
Fonts:    Inter + JetBrains Mono (Google Fonts CDN)
AI:       OpenAI (gpt-4o for research, gpt-4o-mini for extraction)
Container: Docker Compose

## Port mapping note
Ports 8000/3000/5432/6379 are occupied by an existing prism project on this machine.
DealLens host ports: backend=8001, frontend=3001.
Internal Docker network still uses 8000/3000 — vite proxy target = http://backend:8000.

## Phase 0 test results (2026-03-29) — ALL PASS
GET  /v1/health                         → 200 {"status":"ok","product":"DealLens AI"}
POST /v1/entity/resolve                 → 200 (stub)
GET  /v1/company/{id}                   → 200 (stub)
GET  /v1/company/{id}/enrichment-status → 200 (stub)
GET  /v1/company/{id}/discovery-eligibility → 200 (stub)
POST /v1/discovery/buy-side             → 200 (stub)
POST /v1/discovery/sell-side            → 200 (stub)
POST /v1/regulatory/predict             → 200 (stub)
POST /v1/drafts/generate                → 200 (stub)
GET  /v1/market-intelligence/feed       → 200 (stub)
GET  /v1/market-intelligence/company/{id}/news → 200 (stub)
POST /v1/shortlists                     → 200 (stub)
GET  /v1/shortlists                     → 200 (stub)
GET  /docs                              → 200 (all 7 router groups visible)
GET  http://localhost:3001              → 200 (React app)
Scoring engine: hard gate SANCTIONED_JURISDICTION → Excluded ✓
Scoring engine: hard gate SAME_ENTITY detected ✓
Celery worker: ready, no errors ✓

## Phase 1 test results (2026-03-29) — ALL PASS
Alembic autogenerate migration: deallens_initial_schema ✓
alembic upgrade head: applied clean ✓
PostgreSQL tables created (11): companies (19 cols), enrichment_profiles (44 cols),
  entity_aliases (5 cols), discovery_runs (9 cols), discovery_results (14 cols),
  regulatory_predictions (14 cols), drafts (12 cols), market_news_items (16 cols),
  market_digest (8 cols), shortlists (7 cols), shortlist_entries (8 cols) ✓
Migration file: alembic/versions/758f33e133a9_deallens_initial_schema.py

## Phase 2 notes
All AI calls use gpt-4o-mini (not gpt-4o). Applies to all phases.
Entity resolver: DB lookup (ticker/isin/lei exact → alias → name fuzzy) then GPT-4o-mini fallback.
docker compose restart is NOT enough to reload .env — use --force-recreate.

## Phase 2 test results (2026-03-29) — ALL PASS
POST /v1/entity/resolve (empty query)              → 400 ✓
POST /v1/entity/resolve (ticker AAPL, DB cache)    → resolved, confidence 95 ✓
POST /v1/entity/resolve (ISIN, DB cache)           → resolved, confidence 95 ✓
POST /v1/entity/resolve (name fuzzy, DB cache)     → resolved, confidence 80 ✓
POST /v1/entity/resolve ("Microsoft", GPT live)    → resolved, written to DB ✓
POST /v1/entity/resolve ("MSFT", DB cache hit)     → resolved, source=database_cache ✓
POST /v1/entity/resolve ("Reliance Industries IN") → resolved, ISIN INE002A01018 ✓
POST /v1/entity/resolve ("Standard Bank")          → ambiguous, 2 candidates ✓
POST /v1/entity/resolve ("zxqwerty12345nonsense")  → not_found ✓
GET  /v1/company/{id}                              → full profile from DB ✓
GET  /v1/company/{id}/enrichment-status            → depth/freshness/sections_ready ✓
GET  /v1/company/{id}/discovery-eligibility        → missing fields list ✓
GET  /v1/company/does_not_exist                    → 404 ✓

## Phase 3 test results (2026-03-29) — ALL PASS
POST /v1/company/{id}/enrich         → queued immediately, background pipeline runs ✓
GET  /v1/company/{id}/enrichment-status (after 20s) → coverage_depth DEEP, confidence 77.5 ✓
GET  /v1/company/{id}                → full financials + ownership + strategic_features ✓
GET  /v1/company/{id}/discovery-eligibility → buy_side_eligible true, sell_side_eligible true ✓
POST /v1/company/{id}/enrich (fresh) → already_fresh, no re-enrichment ✓
Enrichment pipeline: Pass1 (basic) → Pass2 (deep), both GPT-4o-mini ✓

## Phase 4 test results (2026-03-29) — ALL PASS
POST /v1/discovery/buy-side (MSFT buying)    → 2 scanned, 1 gated (Apple too large), 1 scored Tier 2 ✓
POST /v1/discovery/sell-side (Reliance sell) → 2 scanned, 0 gated, 2 scored Tier 2 ✓
Hard gate TARGET_TOO_LARGE triggered correctly ✓
score_breakdown all 9 components populated ✓
GPT-4o-mini narration generated for top results ✓
process_architecture roles assigned (tension_creator for both buyers) ✓
All AI calls use gpt-4o-mini only ✓

## Phase 5 test results (2026-03-29) — ALL PASS
POST /v1/regulatory/predict (MSFT+Reliance $50B) → MEDIUM risk, 70% clearance, 12mo timeline, 3 precedents ✓
POST /v1/drafts/generate (investment_thesis)      → full IC thesis, 5 bullets, risks, why-now, 535 words ✓
POST /v1/shortlists (add)                         → creates list + adds company ✓
POST /v1/shortlists (add second)                  → same list, 2 companies ✓
GET  /v1/shortlists                               → list with company_count ✓
GET  /v1/shortlists/{id}                          → full detail with enrichment data ✓
DELETE /v1/shortlists/{id}/company/{id}           → removed: true ✓
Drafts persisted to DB with token counts ✓
Regulatory prediction persisted to DB ✓
Supported draft types: investment_thesis, teaser, cim_outline, loi_points, board_memo_bullets, synergy_analysis

## Phase 6 test results (2026-03-29) — ALL PASS
POST /v1/market-intelligence/fetch          → pipeline started in background ✓
Fetch pipeline: 176 raw items from 7 sources (Reuters blocked in container, 6 others OK) ✓
Classify pipeline: 176 raw → 45 relevant via GPT-4o-mini ✓
GET  /v1/market-intelligence/feed           → 5 items, last_updated set, real deal headlines ✓
GET  /v1/market-intelligence/feed?category=deal_activity → filtered correctly ✓
GET  /v1/market-intelligence/company/{id}/news → 0 items (no MSFT in today's feed, correct) ✓
Daily digest generated via GPT-4o-mini ✓
Celery beat task wired → runs every 6h automatically ✓
Deduplication by URL works (44 dupes skipped on second run) ✓

## Phase 7 test results (2026-03-29) — ALL PASS
GET  http://localhost:3001                   → 200 React app ✓
SearchHome: entity resolve → disambiguation modal → company page navigation ✓
CompanyPage: flat API fields mapped to identity/financials/ownership shapes ✓
CompanyPage: financials in raw USD → converted to $B for display ✓
CompanyPage: description (not business.business_description) ✓
CompanyPage: triggerEnrichment + startStream wired ✓
BuySideDiscovery: target_* prefixed fields normalized → TargetCard renders ✓
BuySideDiscovery: tier counts tier_1_count/tier_2_count/tier_3_count ✓
BuySideDiscovery: excluded_targets normalized ✓
SellSideDiscovery: buyer_* prefixed fields normalized → BuyerCard renders ✓
RegulatoryLens: expected_timeline_months (not p50_close_months) ✓
RegulatoryLens: rationale (not risk_description) ✓
Drafts: DRAFT_TYPES = investment_thesis/teaser/cim_outline/loi_points/board_memo_bullets/synergy_analysis ✓
Drafts: thesis_bullets are plain strings (not {text,confidence} objects) ✓
Drafts: executive_summary/why_now/why_not_now_risks mapped ✓
MarketIntelligence: feed items render, period/category filters work ✓
All 6 draft types → HTTP 200 ✓

## Phase 8 changes (2026-03-30)
WebSocket enrichment: enrichment_ws.py streams real step_complete/section_ready/enrichment_complete messages
Health endpoint: returns real DB company count + last news fetch timestamp
RegulatoryLens: added critical_status_indicators (colored dots), risk_rationale_chips, sanctions_alerts,
  fdi_concerns, ownership_control_analysis table, precedent_deals, source_rationale, footer metadata
TargetCard: score breakdown bars now normalize per component max (24/16/14/10/10/10/10/4/2),
  bar color = teal/amber/red based on % of max, shows val/max label
TargetCard + BuyerCard: fetch and display per-company recent news (sentiment-colored chips)
BuyerCard: added why_not_now risks, flag_chips rendering

## Phase 9 changes (2026-03-31)
Drafts screen: replaced raw company ID text input with SearchBar + useCompanySearch + DisambiguationModal;
  optional counterparty search shown for synergy_analysis, loi_points, investment_thesis draft types;
  selected companies shown as chips with × to clear; payload includes counterparty_id when set
CompanyPage: added strategic_features 3-column grid — key products (gray chips) + geographic markets (teal mono chips),
  top competitors (›) + strategic priorities (✓), M&A signals (boolean flags as amber ⚑ chips) + recent acquisitions
SellSideDiscovery: added seller context strip (seller name, EV, valuation range, buyer count) + process architecture
  panel with 6 color-coded role buckets (must_contact → teal, price_anchors → gold, certainty → green,
  tension → amber, sponsor_floor → blue, do_not_approach → red)
Shortlists screen (/shortlists): full CRUD UI — 280px sidebar listing all shortlists with type badge + count,
  detail panel with company table (EV/Revenue/Score/Tier/Coverage/Remove), notes section, navigate to company page
discovery.py: sell-side response now includes seller_name + seller_context (EV, valuation range, process_stage)

## Phase 9 test results (2026-03-31) — ALL PASS
POST /v1/discovery/sell-side → seller_name populated, seller_context returned ✓
POST /v1/drafts/generate (synergy_analysis, counterparty_id set) → draft generated, counterparty_id in response ✓
GET  /v1/shortlists → 2 lists, company_count correct ✓
GET  /v1/shortlists/{id} → full detail with companies array ✓
GET  /v1/company/{id} → strategic_features keys verified (14 keys, key_products populated) ✓
Frontend: Shortlists screen accessible at /shortlists ✓
Frontend: App.jsx nav includes Shortlists tab ✓
Frontend: Drafts screen has SearchBar + counterparty wiring ✓
Frontend: CompanyPage has strategic_features 3-column section ✓
Frontend: SellSideDiscovery has process_architecture panel + seller context strip ✓

## Sessions completed
Phase 0: Project scaffold — COMPLETE AND VERIFIED (2026-03-29)
Phase 1: Database schema — COMPLETE AND VERIFIED (2026-03-29)
Phase 2: Entity resolver — COMPLETE AND VERIFIED (2026-03-29)
Phase 3: Company researcher + enrichment service — COMPLETE AND VERIFIED (2026-03-29)
Phase 4: Feature extraction + scoring engine — COMPLETE AND VERIFIED (2026-03-29)
Phase 5: Regulatory lens + drafts + shortlists — COMPLETE AND VERIFIED (2026-03-29)
Phase 6: Market intelligence (RSS + GPT-4o-mini classification) — COMPLETE AND VERIFIED (2026-03-29)
Phase 7: Frontend integration — COMPLETE AND VERIFIED (2026-03-29)
Phase 8: UI enrichment + WebSocket streaming — COMPLETE (2026-03-30)
Phase 9: UI gaps + nice-to-haves — COMPLETE AND VERIFIED (2026-03-31)

## Bug fixes (2026-03-31) — post Phase 9

### Vite HMR not detecting file changes on WSL2-mounted Windows filesystem
Root cause: inotify (Linux file watcher) does not work for /mnt/c/ paths in Docker on WSL2.
Fix: added `watch: { usePolling: true, interval: 300 }` to vite.config.js server config.
Impact: frontend changes now hot-reload correctly without requiring container restart.

### CompanyPage not refreshing after enrichment completes
Root cause: profile state was fetched once on mount and never re-fetched after the enrichment
  WebSocket stream fired enrichment_complete. New companies showed NONE/NEVER_ENRICHED permanently.
Fix: added second useEffect in CompanyPage.jsx watching the `complete` flag — re-fetches profile
  and eligibility when enrichment stream finishes.

### EnrichmentPipeline shown at bottom of page (not visible during loading)
Fix: moved EnrichmentPipeline component to render immediately after badges row (top of page).

### OwnershipCard showing blank
Root cause: component destructured wrong field names (ownership_controller, controller_type,
  promoter_holding_pct, free_float_pct) — API returns different keys (ownership_structure,
  controlling_shareholder, controlling_stake_pct, pe_sponsor, pe_vintage_year).
Fix: updated OwnershipCard.jsx to use correct API field names.

### Financial data disclaimer
All financials come from GPT-4o-mini training knowledge (not live). Added disclaimer line
  below metric cards showing fiscal year and noting figures are not real-time market prices.
Prompt updated to request `financials_as_of_year` field; enrichment_service stores it as revenue_year.

### Ambiguous candidates missing company_id → "Company not found" after selection
Root cause: GPT ambiguous resolution returned candidates without saving them to DB, so
  company_id was undefined; frontend navigated to /company/undefined → 404.
Fix: in entity_resolver.py, when GPT returns ambiguous candidates, each is now saved via
  _create_canonical_record() before returning, so every candidate has a real company_id.

### HTTP 500 on non-US company searches (e.g. Siemens AG)
Root cause: GPT returned full country name ("Germany") for hq_country field, but DB column
  is VARCHAR(2) expecting ISO-2 code ("DE") → StringDataRightTruncationError.
Fix: added _to_iso2() helper in entity_resolver.py that converts country names to ISO-2 codes
  before DB insert. Covers 50 common countries; falls back to first 2 chars for unknowns.
  Applied to both `jurisdiction` and `hq_country` fields in _create_canonical_record().

### ISIN hallucination — wrong company returned for ISIN searches
Root cause: GPT hallucinated ISINs when resolving ISIN queries (e.g. returned FR0000121014
  for Société Générale when that is actually LVMH's ISIN). DB record stored with wrong ISIN,
  causing subsequent ISIN lookups to return the wrong company.
Fix 1: direct DB correction of Société Générale record to FR0000130809 (its correct ISIN).
Fix 2: added _looks_like_isin() detection in entity_resolver.py; when query is ISIN format,
  the searched ISIN is forced onto the GPT result regardless of what GPT returned.

### Buy-side / Sell-side discovery only showing previously-searched companies
Root cause: discovery engine scanned only DB-resident enriched companies (discovery_eligible=True).
  New users with few searched companies saw minimal/irrelevant results.
Fix: added _seed_candidates() in discovery.py — before each discovery run, asks GPT for
  10-25 relevant targets (buy-side) or buyers (sell-side), resolves + enriches each, then
  they flow into the existing scoring pipeline. Companies already in DB are skipped.

## GPT model upgrade note
All AI calls use gpt-4o-mini. To upgrade: change model= parameter in company_researcher.py
  (_call_gpt) and entity_resolver.py (_gpt_resolve). Upgrading model improves accuracy and
  reduces hallucinations but does NOT provide live financial data — that requires a paid
  financial data feed (Bloomberg API, Refinitiv, etc.).

## Phase 10 changes (2026-03-31) — Buy-side discovery overhaul

### Issue 1+3 — Tier 1 now achievable (scoring fixes)
scoring_engine.py — assign_tier(): Tier 1 threshold recalibrated to confidence>=45 (was 60).
scoring_engine.py — _compute_buy_side_confidence(): deterministic bonuses added:
  same sector → +10pts, adjacent sector → +5pts, same jurisdiction → +5pts, any financials → +5pts.
  These prevent confidence from collapsing entirely when GPT signal is weak.

### Issue 2 — Better AI prompts for feature extraction
feature_extractor.py — _extract_strategic_features(): rewritten with _profile_brief() helper
  that injects full buyer+target context (sector, EV, revenue, EBITDA margin, ownership structure,
  key products, strategic priorities, description) into GPT prompt.
  Deterministic fallback: when GPT returns all zeros, compute product_overlap=5/capability_gap_fill=4
  from sector match, geographic_logic=4 from cross-border, =3 from same jurisdiction.

### Issue 4 — Professional M&A filter panel
Backend: DiscoveryFilters Pydantic model expanded with: ev_min/max_usd_b, employee_count_min/max,
  regions (north_america/europe/asia_pacific/latam/middle_east/india/global), ownership_types
  (public/private/pe_backed/family_founder/state_owned), listing_statuses, sector_focus
  (same/adjacent/any), deal_structures (friendly_only/hostile_acceptable/minority_stake/full_acquisition),
  min_revenue_growth_pct, min_ebitda_margin_pct, max_net_debt_ebitda.
  _load_all_enriched_profiles() applies all new filters post-query with REGION_JURISDICTIONS mapping.
Frontend: BuySideDiscovery.jsx — collapsible "Discovery Parameters" panel with:
  2-column grid for numeric inputs (EV range, Revenue range, growth floor, margin floor, leverage),
  chip toggles for Geography, Ownership Type, Deal Structure, Sector Focus.
  Active filter count shown on the ⊕ Filters button; "Clear all" button when any active.

### Issue 5 — Removed "Excluded" tab
BuySideDiscovery.jsx: removed "Excluded" from tiers array + removed the excluded summary card.
  Excluded companies are still scored/gated internally but not shown in the UI.

### Issue 6 — Prominent view toggle
BuySideDiscovery.jsx: view toggle moved from corner to centered pill switcher with
  filled teal/muted styling. Tier tabs now sit below as a separate row (only when in tier view).

### Issue 7 — Score breakdown reasoning
TargetCard.jsx: added getScoreReason(key, val, max, target) function returning a one-line
  explanation for each score component based on value percentage, ownership string, listing status,
  and jurisdiction. Reason sentence shown in italic below each bar row.

### Issue 8 — Deep Analysis screen
DeepAnalysis.jsx (new screen at /deep-analysis?buyer={id}&target={id}&ds={score}&tier={tier}&sb={json}):
  Side-by-side buyer/target profile panels (financials, key products, strategic priorities).
  Central ScoreDial showing deal score.
  Full score breakdown with wider bars.
  Regulatory assessment card with "Run Regulatory Prediction" button (calls /v1/regulatory/predict).
  "Generate Draft" and "Full Target Profile" action buttons.
TargetCard.jsx: Deep Analysis button now wires onClick → navigate to /deep-analysis with all params.
App.jsx: added /deep-analysis route + DeepAnalysis import.

### Discovery global seeding (prior session — now active)
discovery.py — _seed_candidates(): asks GPT for 10-25 relevant targets per buyer/seller globally.
  Returns list of seeded company_ids; resolves + enriches in parallel (asyncio.Semaphore(6)).
  _STRATEGY_CONTEXT dict: 7 strategy-specific paragraphs injected into seeding prompt so results
  differ meaningfully by strategy mode (capability_bolt_on vs geographic_expansion etc.).
  _load_all_enriched_profiles(): accepts company_ids whitelist for scoped runs (seeded companies only).

### Loading screen (prior session — now active)
DiscoveryLoadingScreen.jsx: 3-phase animated loading (sources → enrichment → scoring).
  Shows sector-appropriate candidate names, enrichment counter, animated score bars.
  Used in both BuySideDiscovery and SellSideDiscovery.

## Phase 10 — Sessions completed
Phase 10: Buy-side discovery overhaul (8 issues) — COMPLETE (2026-03-31)

## Phase 11 changes (2026-04-01)

### Issue 1+2 — Non-obvious matches + live M&A signal context in seeding
discovery.py _seed_candidates(): added _LIVE_SIGNALS_CONTEXT block (PE dry powder, AI gap, ESG,
  near-shoring, sector convergence, rate cycle) injected into GPT system prompt.
Added rule 9 (NON-OBVIOUS MATCHES): 2-3 cross-sector candidates with is_non_obvious + non_obvious_bridge.
Added rule 10 (PRECEDENT DEALS): each candidate cites 1 real comparable transaction.
_seeded_meta now stores: is_non_obvious, non_obvious_bridge, precedent_deals per company.
Both buy-side and sell-side result injection updated to pass new fields to API response.
TargetCard.jsx: "NON-OBVIOUS MATCH" gold badge, amber-bordered bridge explanation box,
  ESTIMATED SYNERGIES metric row in teal monospace, PRECEDENT TRANSACTION chip in italic.
BuySideDiscovery.jsx normalizeTarget: added is_non_obvious, non_obvious_bridge,
  estimated_synergy_value_usd_m, precedent_deals, ib_metrics fields.

### Issue 4 — Market Intel Daily tab fix
market_intelligence.py: daily period now filters by fetched_at (when we received the article)
  instead of published_at (editorial timestamp). Weekly/Monthly still use published_at.
  Fixes empty Daily tab when feed hasn't run in >24h.
MarketIntelligence.jsx: added "↻ Refresh Feed" button that calls POST /market-intelligence/fetch,
  shows amber status message, auto-refreshes feed after 45s.
deallens.js: added triggerMarketFetch() API helper.

### Issue 5 — Contact page
Contact.jsx (new screen at /contact): professional M&A advisory-style contact page with
  name "Madhav Arora | M&A Technology & Advisory", about section, capabilities chips,
  4 contact cards (email mailto, phone tel, WhatsApp wa.me, Location).
  All links open correct platform on click. DealLens dark theme with teal/gold accents.
App.jsx: added /contact route + "Contact" tab in NAV_ITEMS.

### Issue 6 — Sell-side BuyerCard parity
scoring_engine.py: added _build_sell_side_score_rationale() (9 components, parallel to buy-side).
  score_sell_side_pair() now returns score_rationale alongside score_breakdown.
SellSideDiscovery.jsx: normalizeBuyer now maps deal_score, score_breakdown, score_rationale, ib_metrics.
  Passes sellerCompanyId prop to BuyerCard.
BuyerCard.jsx: full rewrite — added TierBadge, score breakdown expand section with formula rows
  (same expandable pattern as TargetCard), "Deep Analysis →" button navigating to
  /deep-analysis?role=seller&seller={id}&buyer={id}&ds={score}&tier={tier}&sb={json}.
  score_rationale stored to sessionStorage for DeepAnalysis consumption.
DeepAnalysis.jsx: supports role=seller URL param — swaps panel labels to "Seller"/"Potential Acquirer",
  loads profiles correctly, reads score_rationale + ib_metrics from sessionStorage for correct company.
  Added sell-side SCORE_MAX values to the existing map.

### Issue 7 — IB Valuation Metrics
scoring_engine.py: new compute_ib_metrics() function — additive, no scoring weights changed.
  Computes from existing features: FCF Yield (EBITDA×0.65/EV), Leverage Headroom (EBITDA×5.5−net_debt),
  Implied Control Premium (sector median×1.30 vs current EV/Rev), EV/EBITDA context label,
  Accretion/Dilution signal (margin comparison + synergy yield), Deal Size Classification.
  score_buy_side_pair() returns ib_metrics alongside score_breakdown.
DeepAnalysis.jsx: "IB VALUATION METRICS" card with 6 metric tiles (Accretion/Dilution,
  FCF Yield, Leverage Headroom, Control Premium, EV/EBITDA Context, Deal Sizing).
  Each tile shows colored left-border + formula note. Disclaimer footer added.
TargetCard.jsx: ib_metrics stored to sessionStorage on Deep Analysis click.

### Score formulas (prior session, Phase 10) — now fully wired
scoring_engine.py: _build_score_rationale() added (9 buy-side components, formula strings with
  actual input values). score_buy_side_pair() calls it, returns score_rationale.
DeepAnalysis.jsx: clickable formula rows — each score bar row expands to show formula + inputs.
  "Scoring Methodology" accordion at bottom explains all 9 components.
TargetCard.jsx: non-obvious badge, why_now line, score_rationale stored to sessionStorage.
BuySideDiscovery.jsx normalizeTarget: score_rationale + rationale_category + why_now mapped.

## Phase 11 — Session completed
Phase 11: Wow factor + sell-side parity + IB metrics + contact page — COMPLETE (2026-04-01)
Issues resolved: 1 (non-obvious matches), 2 (synergy/precedent deals), 4 (daily tab fix),
  5 (contact page), 6 (sell-side Deep Analysis), 7 (IB valuation metrics)
Issue 3 (live internet research via OpenAI Responses API) — DEFERRED to future phase.
