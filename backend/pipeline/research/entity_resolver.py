"""
Entity Resolver — resolves any company identifier to a canonical record.

Flow:
1. Search companies table by ticker, isin, lei (exact match)
2. Search entity_aliases table
3. Fuzzy search by legal_name / display_name
4. If no match: call GPT-4o-mini to identify the company
5. If GPT resolves: create canonical record + aliases in DB
6. Return resolution result with confidence and sources

Resolution statuses:
  resolved   — single unambiguous match
  ambiguous  — 2–5 candidates returned to frontend for user selection
  not_found  — GPT could not identify the company
"""
import re
from datetime import datetime, timezone
from uuid import uuid4

from openai import AsyncOpenAI
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from models.database_models import Company, EntityAlias, EnrichmentProfile

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _client


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def resolve_entity(
    query: str,
    query_type: str = "auto",
    jurisdiction_hint: str | None = None,
    db: AsyncSession | None = None,
) -> dict:
    """
    Main entry point. Returns resolution result dict.

    Returns:
        {
          resolution_status: "resolved" | "ambiguous" | "not_found",
          resolved: {company_id, legal_name, ticker, jurisdiction, ...} | None,
          candidates: [...] | [],
          confidence: 0-100,
          sources: [...],
          generated_at: ISO string,
        }
    """
    generated_at = datetime.now(timezone.utc).isoformat()

    if not query or not query.strip():
        return _not_found(generated_at)

    query = query.strip()

    # 1. Try database first (zero cost, fast)
    if db is not None:
        db_result = await _search_database(db, query, query_type)
        if db_result:
            return db_result

    # 2. GPT-4o-mini resolution
    gpt_result = await _gpt_resolve(query, jurisdiction_hint)

    if gpt_result is None:
        return _not_found(generated_at)

    # If the query looks like an ISIN, force it onto the GPT result regardless of
    # what ISIN GPT returned — GPT frequently hallucinates ISIN values.
    if _looks_like_isin(query):
        if not gpt_result.get("ambiguous"):
            gpt_result["isin"] = query.upper()

    if gpt_result.get("ambiguous"):
        raw_candidates = gpt_result.get("candidates", [])
        # Save each candidate to DB so they have a company_id the frontend can navigate to
        if db is not None:
            saved = []
            for c in raw_candidates:
                company_id = await _create_canonical_record(db, c)
                saved.append({**c, "company_id": company_id})
            raw_candidates = saved
        return {
            "resolution_status": "ambiguous",
            "resolved": None,
            "candidates": raw_candidates,
            "confidence": gpt_result.get("confidence", 30),
            "sources": [],
            "generated_at": generated_at,
        }

    # 3. Single resolution — persist to DB and return
    if db is not None:
        company_id = await _create_canonical_record(db, gpt_result)
        gpt_result["company_id"] = company_id

    return {
        "resolution_status": "resolved",
        "resolved": {
            "company_id": gpt_result.get("company_id", ""),
            "legal_name": gpt_result.get("legal_name", query),
            "display_name": gpt_result.get("display_name") or gpt_result.get("legal_name", query),
            "ticker": gpt_result.get("ticker"),
            "isin": gpt_result.get("isin"),
            "jurisdiction": gpt_result.get("jurisdiction"),
            "listing_status": gpt_result.get("listing_status", "unknown"),
            "sector": gpt_result.get("sector"),
            "industry": gpt_result.get("industry"),
            "hq_country": gpt_result.get("hq_country"),
            "website": gpt_result.get("website"),
        },
        "candidates": [],
        "confidence": gpt_result.get("confidence", 70),
        "sources": gpt_result.get("sources", []),
        "generated_at": generated_at,
    }


# ---------------------------------------------------------------------------
# Database search
# ---------------------------------------------------------------------------

async def _search_database(db: AsyncSession, query: str, query_type: str) -> dict | None:
    """Search existing canonical records. Returns resolution dict or None."""
    generated_at = datetime.now(timezone.utc).isoformat()
    query_upper = query.upper()
    query_lower = query.lower()

    # 1. Exact match on ticker / isin / lei
    stmt = select(Company).where(
        or_(
            Company.ticker == query_upper,
            Company.isin == query_upper,
            Company.lei == query_upper,
        )
    )
    result = await db.execute(stmt)
    company = result.scalar_one_or_none()

    if company:
        return _format_db_result(company, confidence=95, generated_at=generated_at)

    # 2. Alias lookup
    alias_stmt = select(EntityAlias).where(
        EntityAlias.alias == query_lower
    )
    alias_result = await db.execute(alias_stmt)
    alias = alias_result.scalar_one_or_none()

    if alias:
        company_stmt = select(Company).where(Company.company_id == alias.company_id)
        company_result = await db.execute(company_stmt)
        company = company_result.scalar_one_or_none()
        if company:
            return _format_db_result(company, confidence=90, generated_at=generated_at)

    # 3. Case-insensitive name match
    name_stmt = select(Company).where(
        or_(
            Company.legal_name.ilike(f"%{query}%"),
            Company.display_name.ilike(f"%{query}%"),
        )
    ).limit(5)
    name_result = await db.execute(name_stmt)
    companies = name_result.scalars().all()

    if len(companies) == 1:
        return _format_db_result(companies[0], confidence=80, generated_at=generated_at)

    if len(companies) > 1:
        return {
            "resolution_status": "ambiguous",
            "resolved": None,
            "candidates": [_company_to_candidate(c) for c in companies],
            "confidence": 50,
            "sources": [],
            "generated_at": generated_at,
        }

    return None


def _format_db_result(company: Company, confidence: int, generated_at: str) -> dict:
    return {
        "resolution_status": "resolved",
        "resolved": {
            "company_id": company.company_id,
            "legal_name": company.legal_name,
            "display_name": company.display_name or company.legal_name,
            "ticker": company.ticker,
            "isin": company.isin,
            "jurisdiction": company.jurisdiction,
            "listing_status": company.listing_status,
            "sector": company.sector,
            "industry": company.industry,
            "hq_country": company.hq_country,
            "website": company.website,
        },
        "candidates": [],
        "confidence": confidence,
        "sources": ["database_cache"],
        "generated_at": generated_at,
    }


def _company_to_candidate(company: Company) -> dict:
    return {
        "company_id": company.company_id,
        "legal_name": company.legal_name,
        "display_name": company.display_name or company.legal_name,
        "ticker": company.ticker,
        "jurisdiction": company.jurisdiction,
        "listing_status": company.listing_status,
        "sector": company.sector,
    }


# ---------------------------------------------------------------------------
# GPT-4o-mini resolution
# ---------------------------------------------------------------------------

_RESOLVE_PROMPT = """You are a corporate identity resolver for an M&A intelligence platform.

Given a company query, identify the company and return a JSON object.

Rules:
- Return ONLY valid JSON. No markdown, no explanation.
- If the query unambiguously identifies one company, return a single resolved object.
- If 2–5 plausible companies match, return an ambiguous result with candidates array.
- If you cannot identify any real company, return not_found.
- jurisdiction: ISO 3166-1 alpha-2 country code (US, GB, IN, DE, etc.)
- listing_status: one of public | private | subsidiary | spac | defunct
- confidence: 0-100 integer
- Never fabricate tickers, ISINs, or financial data.

Response format for RESOLVED (single company):
{
  "resolution_type": "resolved",
  "legal_name": "Full Legal Name Inc.",
  "display_name": "Short Name",
  "ticker": "TICK",
  "isin": "US1234567890",
  "lei": null,
  "jurisdiction": "US",
  "listing_status": "public",
  "sector": "Technology",
  "industry": "Software",
  "sic_code": null,
  "hq_city": "San Francisco",
  "hq_country": "US",
  "website": "https://example.com",
  "description": "One sentence description.",
  "aliases": ["Alt Name", "Abbreviation"],
  "confidence": 92,
  "sources": ["openai_knowledge"]
}

Response format for AMBIGUOUS (multiple matches):
{
  "resolution_type": "ambiguous",
  "candidates": [
    {"legal_name": "...", "display_name": "...", "ticker": "...", "jurisdiction": "...", "listing_status": "...", "sector": "..."},
    ...
  ],
  "confidence": 30
}

Response format for NOT FOUND:
{
  "resolution_type": "not_found"
}"""


async def _gpt_resolve(query: str, jurisdiction_hint: str | None) -> dict | None:
    """
    Resolve company using gpt-4o-mini-search-preview with live web search.
    Falls back to plain gpt-4o-mini on error.
    Returns parsed dict or None.
    """
    import json
    hint = f" (jurisdiction hint: {jurisdiction_hint})" if jurisdiction_hint else ""
    user_message = f"Resolve this company query: \"{query}\"{hint}"
    full_prompt = f"{_RESOLVE_PROMPT}\n\n{user_message}"

    try:
        response = await _get_client().responses.create(
            model="gpt-4o-mini-search-preview",
            tools=[{"type": "web_search_preview"}],
            input=full_prompt,
        )
        raw = ""
        for block in response.output:
            if hasattr(block, "content"):
                for chunk in block.content:
                    if hasattr(chunk, "text"):
                        raw += chunk.text
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()
        data = json.loads(raw)
    except Exception:
        # Fallback to plain chat completion
        try:
            fb = await _get_client().chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": _RESOLVE_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.1,
                max_tokens=600,
                response_format={"type": "json_object"},
            )
            data = json.loads(fb.choices[0].message.content)
        except Exception:
            return None

    resolution_type = data.get("resolution_type", "not_found")

    if resolution_type == "not_found":
        return None

    if resolution_type == "ambiguous":
        return {
            "ambiguous": True,
            "candidates": data.get("candidates", []),
            "confidence": data.get("confidence", 30),
        }

    if resolution_type == "resolved":
        return data

    return None


# ---------------------------------------------------------------------------
# Canonical record creation
# ---------------------------------------------------------------------------

async def _create_canonical_record(db: AsyncSession, resolved_data: dict) -> str:
    """
    Upsert company record in database. Returns company_id.
    If ticker/isin already exists (race condition), returns existing id.
    """
    # Check if company already exists by ticker or isin
    ticker = resolved_data.get("ticker")
    isin = resolved_data.get("isin")

    if ticker or isin:
        filters = []
        if ticker:
            filters.append(Company.ticker == ticker.upper())
        if isin:
            filters.append(Company.isin == isin.upper())

        stmt = select(Company).where(or_(*filters))
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            return existing.company_id

    # Generate new company_id
    legal_name = resolved_data.get("legal_name", "unknown")
    jurisdiction = _to_iso2(resolved_data.get("jurisdiction", "xx"))
    company_id = _generate_company_id(legal_name, jurisdiction)

    company = Company(
        company_id=company_id,
        legal_name=legal_name,
        display_name=resolved_data.get("display_name") or legal_name,
        ticker=resolved_data.get("ticker"),
        isin=resolved_data.get("isin"),
        lei=resolved_data.get("lei"),
        jurisdiction=jurisdiction,
        listing_status=resolved_data.get("listing_status", "unknown"),
        sector=resolved_data.get("sector"),
        industry=resolved_data.get("industry"),
        sic_code=resolved_data.get("sic_code"),
        hq_city=resolved_data.get("hq_city"),
        hq_country=_to_iso2(resolved_data.get("hq_country")),
        website=resolved_data.get("website"),
        description=resolved_data.get("description"),
    )
    db.add(company)

    # Create stub enrichment profile
    profile = EnrichmentProfile(
        profile_id=f"enr_{uuid4().hex[:12]}",
        company_id=company_id,
        coverage_depth="NONE",
        confidence_score=0.0,
        discovery_eligible=False,
        missing_fields=_compute_missing_fields(resolved_data),
        sources=resolved_data.get("sources", []),
    )
    db.add(profile)

    # Store aliases
    aliases_to_add = resolved_data.get("aliases", [])
    seen_aliases = set()

    # Always store ticker and legal name as aliases for future lookups
    for alias_val, alias_type in [
        (resolved_data.get("ticker"), "ticker"),
        (resolved_data.get("isin"), "isin"),
        (resolved_data.get("lei"), "lei"),
        (legal_name.lower(), "former_name"),
    ] + [(a.lower(), "trading_name") for a in aliases_to_add]:
        if alias_val and alias_val.lower() not in seen_aliases:
            seen_aliases.add(alias_val.lower())
            db.add(EntityAlias(
                company_id=company_id,
                alias=alias_val.lower(),
                alias_type=alias_type,
            ))

    await db.commit()
    return company_id


def _compute_missing_fields(data: dict) -> list[str]:
    """Identify which key fields are missing from resolution data."""
    missing = []
    for field in ["revenue_usd", "ebitda_usd", "enterprise_value_usd", "market_cap_usd",
                  "ownership_structure", "employee_count", "founded_year",
                  "key_products", "geographic_markets", "strategic_priorities"]:
        if not data.get(field):
            missing.append(field)
    return missing


_COUNTRY_TO_ISO2 = {
    "united states": "US", "usa": "US", "u.s.": "US", "u.s.a.": "US",
    "united kingdom": "GB", "uk": "GB", "britain": "GB",
    "germany": "DE", "deutschland": "DE",
    "france": "FR",
    "india": "IN",
    "china": "CN",
    "japan": "JP",
    "south korea": "KR", "korea": "KR",
    "taiwan": "TW",
    "australia": "AU",
    "canada": "CA",
    "brazil": "BR",
    "netherlands": "NL",
    "switzerland": "CH",
    "sweden": "SE",
    "norway": "NO",
    "denmark": "DK",
    "finland": "FI",
    "italy": "IT",
    "spain": "ES",
    "singapore": "SG",
    "hong kong": "HK",
    "israel": "IL",
    "ireland": "IE",
    "austria": "AT",
    "belgium": "BE",
    "mexico": "MX",
    "indonesia": "ID",
    "saudi arabia": "SA",
    "uae": "AE", "united arab emirates": "AE",
    "south africa": "ZA",
    "russia": "RU",
    "turkey": "TR",
    "poland": "PL",
    "portugal": "PT",
    "greece": "GR",
    "czech republic": "CZ",
    "new zealand": "NZ",
    "malaysia": "MY",
    "thailand": "TH",
    "philippines": "PH",
    "vietnam": "VN",
    "pakistan": "PK",
    "bangladesh": "BD",
    "egypt": "EG",
    "nigeria": "NG",
    "kenya": "KE",
    "argentina": "AR",
    "chile": "CL",
    "colombia": "CO",
    "peru": "PE",
}


def _looks_like_isin(query: str) -> bool:
    """Returns True if query matches ISIN format: 2 letters + 10 alphanumeric chars."""
    return bool(re.match(r'^[A-Za-z]{2}[A-Za-z0-9]{10}$', query.strip()))


def _to_iso2(value: str | None) -> str | None:
    """Convert a country name or ISO-2 code to a valid 2-char ISO-2 code.
    Returns None if input is None. Returns first 2 chars uppercased as fallback."""
    if not value:
        return None
    v = value.strip()
    if len(v) == 2:
        return v.upper()
    iso = _COUNTRY_TO_ISO2.get(v.lower())
    if iso:
        return iso
    # Last resort: take first 2 chars uppercased so we never exceed VARCHAR(2)
    return v[:2].upper()


def _generate_company_id(legal_name: str, jurisdiction: str) -> str:
    """Generate deterministic-ish company_id."""
    clean = re.sub(r"[^a-z0-9]", "_", legal_name.lower())[:20]
    clean = re.sub(r"_+", "_", clean).strip("_")
    return f"cmp_{clean}_{jurisdiction.lower()}_{uuid4().hex[:6]}"


def _not_found(generated_at: str) -> dict:
    return {
        "resolution_status": "not_found",
        "resolved": None,
        "candidates": [],
        "confidence": 0,
        "sources": [],
        "generated_at": generated_at,
    }
