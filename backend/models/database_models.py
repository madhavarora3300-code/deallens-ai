"""
Database models — Phase 1 full schema.
11 tables: companies, enrichment_profiles, entity_aliases, discovery_runs,
discovery_results, regulatory_predictions, drafts, market_news_items,
market_digest, shortlists, shortlist_entries
"""
from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey,
    Integer, JSON, String, Text, UniqueConstraint
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from core.database import Base


class Company(Base):
    __tablename__ = "companies"

    company_id = Column(String, primary_key=True)
    legal_name = Column(String, nullable=False)
    display_name = Column(String)
    ticker = Column(String, index=True)
    isin = Column(String, index=True)
    lei = Column(String, index=True)
    jurisdiction = Column(String(2), index=True)
    listing_status = Column(String, default="public")  # public | private | subsidiary | spac | defunct
    sector = Column(String)
    industry = Column(String)
    sic_code = Column(String)
    employee_count = Column(Integer)
    founded_year = Column(Integer)
    hq_city = Column(String)
    hq_country = Column(String(2))
    website = Column(String)
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    enrichment_profile = relationship("EnrichmentProfile", back_populates="company", uselist=False)
    aliases = relationship("EntityAlias", back_populates="company")


class EnrichmentProfile(Base):
    __tablename__ = "enrichment_profiles"

    profile_id = Column(String, primary_key=True)
    company_id = Column(String, ForeignKey("companies.company_id", ondelete="CASCADE"), unique=True, nullable=False, index=True)

    # Financial metrics
    revenue_usd = Column(Float)
    revenue_year = Column(Integer)
    ebitda_usd = Column(Float)
    ebitda_margin = Column(Float)
    net_income_usd = Column(Float)
    total_assets_usd = Column(Float)
    total_debt_usd = Column(Float)
    cash_usd = Column(Float)
    enterprise_value_usd = Column(Float)
    market_cap_usd = Column(Float)
    ev_revenue_multiple = Column(Float)
    ev_ebitda_multiple = Column(Float)
    revenue_growth_yoy = Column(Float)

    # M&A context
    ownership_structure = Column(String)       # public | pe_backed | family | state_owned | founder_led
    controlling_shareholder = Column(String)
    controlling_stake_pct = Column(Float)
    pe_sponsor = Column(String)
    pe_vintage_year = Column(Integer)
    strategic_priorities = Column(JSON)        # list[str]
    recent_acquisitions = Column(JSON)         # list[{name, year, value_usd}]
    recent_divestitures = Column(JSON)

    # Products & markets
    key_products = Column(JSON)               # list[str]
    geographic_markets = Column(JSON)         # list[str country codes]
    customer_concentration = Column(Float)    # 0-1
    top_customers = Column(JSON)
    top_competitors = Column(JSON)

    # Signals
    m_and_a_appetite = Column(String)         # active_acquirer | selective | defensive | unknown
    rumored_target = Column(Boolean, default=False)
    rumored_seller = Column(Boolean, default=False)
    activist_present = Column(Boolean, default=False)
    management_change_recent = Column(Boolean, default=False)
    strategic_review_underway = Column(Boolean, default=False)

    # Enrichment metadata
    coverage_depth = Column(String, default="NONE")  # NONE | BASIC | STANDARD | DEEP
    confidence_score = Column(Float, default=0.0)
    discovery_eligible = Column(Boolean, default=False)
    missing_fields = Column(JSON, default=list)
    sources = Column(JSON, default=list)       # list[{url, title, retrieved_at}]
    gpt_research_raw = Column(Text)
    last_enriched_at = Column(DateTime(timezone=True))
    enrichment_version = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    company = relationship("Company", back_populates="enrichment_profile")


class EntityAlias(Base):
    __tablename__ = "entity_aliases"

    alias_id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(String, ForeignKey("companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    alias = Column(String, nullable=False, index=True)
    alias_type = Column(String)   # trading_name | former_name | abbreviation | ticker | isin | lei
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("company_id", "alias", name="uq_entity_alias"),)

    company = relationship("Company", back_populates="aliases")


class DiscoveryRun(Base):
    __tablename__ = "discovery_runs"

    run_id = Column(String, primary_key=True)
    run_type = Column(String, nullable=False)        # buy_side | sell_side
    input_company_id = Column(String, ForeignKey("companies.company_id"), nullable=False, index=True)
    strategy_mode = Column(String)                    # FULL_ACQUISITION | MINORITY_STAKE | MERGER_OF_EQUALS | STRATEGIC_PARTNERSHIP
    status = Column(String, default="pending")        # pending | running | complete | failed
    result_count = Column(Integer, default=0)
    error_message = Column(Text)
    requested_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True))

    results = relationship("DiscoveryResult", back_populates="run")


class DiscoveryResult(Base):
    __tablename__ = "discovery_results"

    result_id = Column(String, primary_key=True)
    run_id = Column(String, ForeignKey("discovery_runs.run_id", ondelete="CASCADE"), nullable=False, index=True)
    candidate_company_id = Column(String, ForeignKey("companies.company_id"), nullable=False, index=True)

    # Scores
    deal_score = Column(Float)
    confidence_score = Column(Float)
    tier = Column(String)                             # Tier 1 | Tier 2 | Tier 3 | Excluded
    hard_gate = Column(String)                        # gate name if excluded, else null
    dealability_verdict = Column(String)
    acquisition_route = Column(String)

    # Component scores (stored for transparency)
    component_scores = Column(JSON)                   # {strategic_alpha: x, dealability: y, ...}
    feature_snapshot = Column(JSON)                   # features at time of scoring
    rationale = Column(Text)                          # GPT-4o-mini narration
    sources = Column(JSON, default=list)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    run = relationship("DiscoveryRun", back_populates="results")


class RegulatoryPrediction(Base):
    __tablename__ = "regulatory_predictions"

    prediction_id = Column(String, primary_key=True)
    buyer_company_id = Column(String, ForeignKey("companies.company_id"), nullable=False, index=True)
    target_company_id = Column(String, ForeignKey("companies.company_id"), nullable=False, index=True)

    # Prediction output
    overall_risk = Column(String)            # LOW | MEDIUM | HIGH | VERY_HIGH
    combined_market_share = Column(Float)
    hhi_delta = Column(Float)
    jurisdictions_flagged = Column(JSON)     # list[str]
    likely_remedies = Column(JSON)           # list[str]
    expected_timeline_months = Column(Integer)
    clearance_probability = Column(Float)    # 0-1
    rationale = Column(Text)
    sources = Column(JSON, default=list)
    confidence_score = Column(Float)

    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Draft(Base):
    __tablename__ = "drafts"

    draft_id = Column(String, primary_key=True)
    company_id = Column(String, ForeignKey("companies.company_id"), nullable=False, index=True)
    document_type = Column(String, nullable=False)   # teaser | cim | loi | board_memo | synergy_analysis
    title = Column(String)
    content_markdown = Column(Text)
    word_count = Column(Integer)
    model_used = Column(String)
    prompt_tokens = Column(Integer)
    completion_tokens = Column(Integer)
    generation_params = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class MarketNewsItem(Base):
    __tablename__ = "market_news_items"

    item_id = Column(String, primary_key=True)
    headline = Column(String, nullable=False)
    summary = Column(Text)
    url = Column(String)
    source_name = Column(String)
    published_at = Column(DateTime(timezone=True), index=True)

    # Classification
    category = Column(String, index=True)    # deal_activity | capital_markets | institutional | macro_geopolitical
    relevance_score = Column(Float)          # 0-1
    sentiment = Column(String)               # positive | neutral | negative
    companies_mentioned = Column(JSON)       # list[str] company_ids
    tickers_mentioned = Column(JSON)         # list[str]
    deal_size_usd = Column(Float)
    deal_type = Column(String)               # acquisition | merger | ipo | fundraise | divestiture

    # Ingestion metadata
    raw_content = Column(Text)
    classification_raw = Column(JSON)
    fetched_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("url", name="uq_news_url"),)


class MarketDigest(Base):
    __tablename__ = "market_digest"

    digest_id = Column(String, primary_key=True)
    period = Column(String, nullable=False)          # daily | weekly | monthly
    period_label = Column(String)                    # e.g. "2026-03-29" or "2026-W13"
    summary = Column(Text)
    key_themes = Column(JSON)                        # list[str]
    total_deals_tracked = Column(Integer)
    total_items = Column(Integer)
    generated_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("period", "period_label", name="uq_digest_period"),)


class Shortlist(Base):
    __tablename__ = "shortlists"

    shortlist_id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(Text)
    list_type = Column(String)                       # buy_side | sell_side | watchlist
    anchor_company_id = Column(String, ForeignKey("companies.company_id"), index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    entries = relationship("ShortlistEntry", back_populates="shortlist", cascade="all, delete-orphan")


class ShortlistEntry(Base):
    __tablename__ = "shortlist_entries"

    entry_id = Column(String, primary_key=True)
    shortlist_id = Column(String, ForeignKey("shortlists.shortlist_id", ondelete="CASCADE"), nullable=False, index=True)
    company_id = Column(String, ForeignKey("companies.company_id"), nullable=False, index=True)
    deal_score = Column(Float)
    confidence_score = Column(Float)
    tier = Column(String)
    notes = Column(Text)
    added_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("shortlist_id", "company_id", name="uq_shortlist_entry"),)

    shortlist = relationship("Shortlist", back_populates="entries")
