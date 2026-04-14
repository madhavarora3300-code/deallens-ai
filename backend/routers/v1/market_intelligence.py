"""
Market Intelligence router — AI-filtered M&A news feed.

GET /feed         — paginated feed with period/category filters, includes monthly digest
GET /company/{id}/news — news mentioning a specific company (by name matching)
POST /fetch       — manually trigger a feed fetch + classify cycle (dev/admin)
"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import AsyncSessionLocal, get_db
from models.database_models import Company, MarketDigest, MarketNewsItem

router = APIRouter(tags=["market-intelligence"])


# ---------------------------------------------------------------------------
# Feed endpoint
# ---------------------------------------------------------------------------

@router.get("/feed")
async def get_feed(
    period: str = Query(default="daily", pattern="^(daily|weekly|monthly)$"),
    category: str = Query(default="all"),
    limit: int = Query(default=50, le=200),
    db: AsyncSession = Depends(get_db),
):
    """
    AI-filtered M&A news feed from free RSS sources.
    Updated every 6 hours via Celery beat.
    """
    # Time window for period
    # Daily: filter by fetched_at (shows everything received in the last 24h regardless of pub date)
    # Weekly/Monthly: filter by published_at (editorial recency)
    now = datetime.now(timezone.utc)
    if period == "daily":
        time_field = MarketNewsItem.fetched_at
        period_start = now - timedelta(days=1)
    elif period == "weekly":
        time_field = MarketNewsItem.published_at
        period_start = now - timedelta(days=7)
    else:
        time_field = MarketNewsItem.published_at
        period_start = now - timedelta(days=30)

    # Build query
    stmt = select(MarketNewsItem).where(
        time_field >= period_start
    )
    if category != "all":
        stmt = stmt.where(MarketNewsItem.category == category)

    stmt = stmt.order_by(
        MarketNewsItem.relevance_score.desc().nullslast(),
        MarketNewsItem.published_at.desc(),
    ).limit(limit)

    result = await db.execute(stmt)
    items = result.scalars().all()

    # Most recent fetch time
    latest_stmt = select(MarketNewsItem.fetched_at).order_by(
        MarketNewsItem.fetched_at.desc()
    ).limit(1)
    latest_r = await db.execute(latest_stmt)
    last_fetched = latest_r.scalar_one_or_none()

    # Monthly digest (most recent)
    digest = None
    if period == "monthly":
        digest_stmt = select(MarketDigest).where(
            MarketDigest.period == "monthly"
        ).order_by(MarketDigest.generated_at.desc()).limit(1)
        digest_r = await db.execute(digest_stmt)
        digest_obj = digest_r.scalar_one_or_none()
        if digest_obj:
            digest = {
                "summary": digest_obj.summary,
                "key_themes": digest_obj.key_themes,
                "total_deals_tracked": digest_obj.total_deals_tracked,
                "period_label": digest_obj.period_label,
                "generated_at": digest_obj.generated_at.isoformat() if digest_obj.generated_at else None,
            }

    serialized = [_serialize_item(item) for item in items]

    return {
        "period": period,
        "category": category,
        "last_updated": last_fetched.isoformat() if last_fetched else None,
        "total_items": len(serialized),
        "sources_scanned": len({i["source_name"] for i in serialized}),
        "items": serialized,
        "monthly_digest": digest,
    }


# ---------------------------------------------------------------------------
# Company news endpoint
# ---------------------------------------------------------------------------

@router.get("/company/{company_id}/news")
async def get_company_news(
    company_id: str,
    days: int = Query(default=7, le=30),
    limit: int = Query(default=20, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Recent news mentioning a specific company by name."""
    # Load company name for matching
    r = await db.execute(select(Company).where(Company.company_id == company_id))
    company = r.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail=f"Company '{company_id}' not found")

    since = datetime.now(timezone.utc) - timedelta(days=days)

    # Search by company_id in the JSON array OR by name in headline
    # Use JSON containment check + headline ILIKE for broad matching
    name_variants = [
        company.legal_name,
        company.display_name or "",
        company.ticker or "",
    ]
    name_variants = [n for n in name_variants if n]

    # Build OR conditions for headline matching
    headline_conditions = [
        MarketNewsItem.headline.ilike(f"%{name}%")
        for name in name_variants
    ]

    stmt = select(MarketNewsItem).where(
        and_(
            MarketNewsItem.published_at >= since,
            or_(*headline_conditions),
        )
    ).order_by(
        MarketNewsItem.published_at.desc()
    ).limit(limit)

    result = await db.execute(stmt)
    items = result.scalars().all()

    return {
        "company_id": company_id,
        "company_name": company.display_name or company.legal_name,
        "news_count_7d": len(items),
        "items": [_serialize_item(item) for item in items],
    }


# ---------------------------------------------------------------------------
# Manual trigger (dev/admin)
# ---------------------------------------------------------------------------

@router.post("/fetch")
async def trigger_fetch(background_tasks: BackgroundTasks):
    """
    Manually trigger a full RSS fetch + classify cycle.
    Returns immediately; runs in background.
    """
    background_tasks.add_task(_run_fetch_pipeline)
    return {
        "status": "fetch_started",
        "message": "Fetching and classifying news in background. Check /feed in ~60s.",
    }


async def _run_fetch_pipeline() -> dict:
    """Full ingestion pipeline: fetch → classify → deduplicate → persist → digest."""
    from pipeline.intelligence.news_fetcher import fetch_all_feeds
    from pipeline.intelligence.news_classifier import classify_batch

    # 1. Fetch all RSS sources
    raw_items = await fetch_all_feeds()
    if not raw_items:
        return {"status": "no_items_fetched"}

    # 2. Classify with GPT-4o-mini (returns only relevant items)
    classified = await classify_batch(raw_items)
    if not classified:
        return {"status": "no_relevant_items"}

    # 3. Persist to DB — skip duplicates by URL
    async with AsyncSessionLocal() as db:
        inserted = 0
        for item in classified:
            # Check for duplicate URL
            url = item.get("url", "")
            if url:
                existing = await db.execute(
                    select(MarketNewsItem).where(MarketNewsItem.url == url)
                )
                if existing.scalar_one_or_none():
                    continue

            # Parse published_at
            pub_at = None
            pub_str = item.get("published_at")
            if pub_str:
                try:
                    pub_at = datetime.fromisoformat(pub_str)
                except Exception:
                    pub_at = datetime.now(timezone.utc)

            news_item = MarketNewsItem(
                item_id=item["item_id"],
                headline=item.get("headline", ""),
                summary=item.get("summary", ""),
                url=url or None,
                source_name=item.get("source_name", ""),
                published_at=pub_at,
                category=item.get("category", "not_relevant"),
                relevance_score=item.get("relevance_score", 0) / 100,
                sentiment=item.get("sentiment", "neutral"),
                companies_mentioned=item.get("companies_mentioned", []),
                tickers_mentioned=item.get("tickers_mentioned", []),
                deal_size_usd=item.get("deal_size_usd"),
                deal_type=item.get("deal_type"),
                raw_content=item.get("raw_content", ""),
                classification_raw=item.get("classification_raw"),
            )
            db.add(news_item)
            inserted += 1

        await db.commit()

        # 4. Generate/update daily digest
        await _upsert_digest(db, "daily", classified)

    return {"status": "complete", "fetched": len(raw_items), "relevant": len(classified), "inserted": inserted}


async def _upsert_digest(db: AsyncSession, period: str, items: list[dict]) -> None:
    """Generate a brief digest summary for the period."""
    from openai import AsyncOpenAI
    from core.config import settings
    import json

    if not items:
        return

    today_label = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Check if digest for today already exists
    existing = await db.execute(
        select(MarketDigest).where(
            MarketDigest.period == period,
            MarketDigest.period_label == today_label,
        )
    )
    if existing.scalar_one_or_none():
        return

    # Build digest prompt from top 20 headlines
    headlines = "\n".join(
        f"- {item['headline']}" for item in items[:20]
    )

    try:
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are an M&A market analyst writing a brief daily digest for investment bankers. Return ONLY valid JSON: {\"summary\": \"2-3 sentence paragraph\", \"key_themes\": [\"theme1\", \"theme2\", \"theme3\"], \"total_deals_tracked\": integer}",
                },
                {
                    "role": "user",
                    "content": f"Today's M&A headlines:\n{headlines}\n\nWrite the daily digest.",
                },
            ],
            temperature=0.2,
            max_tokens=300,
            response_format={"type": "json_object"},
        )
        digest_data = json.loads(resp.choices[0].message.content)
    except Exception:
        digest_data = {
            "summary": f"{len(items)} relevant M&A and market items ingested.",
            "key_themes": [],
            "total_deals_tracked": len([i for i in items if i.get("deal_type") == "acquisition"]),
        }

    digest = MarketDigest(
        digest_id=f"dgst_{datetime.now(timezone.utc).strftime('%Y%m%d')}_{period}",
        period=period,
        period_label=today_label,
        summary=digest_data.get("summary", ""),
        key_themes=digest_data.get("key_themes", []),
        total_deals_tracked=digest_data.get("total_deals_tracked", 0),
        total_items=len(items),
    )
    db.add(digest)
    await db.commit()


# ---------------------------------------------------------------------------
# Serialiser
# ---------------------------------------------------------------------------

def _serialize_item(item: MarketNewsItem) -> dict:
    return {
        "item_id": item.item_id,
        "headline": item.headline,
        "summary": item.summary,
        "url": item.url,
        "source_name": item.source_name,
        "published_at": item.published_at.isoformat() if item.published_at else None,
        "category": item.category,
        "relevance_score": item.relevance_score,
        "sentiment": item.sentiment,
        "companies_mentioned": item.companies_mentioned or [],
        "tickers_mentioned": item.tickers_mentioned or [],
        "deal_type": item.deal_type,
        "deal_size_usd": item.deal_size_usd,
        "fetched_at": item.fetched_at.isoformat() if item.fetched_at else None,
    }
