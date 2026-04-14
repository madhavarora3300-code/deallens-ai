"""
News Fetcher — async RSS ingestion from free public sources.

Fetches all feeds concurrently with a timeout per source.
Deduplicates by URL before returning.
Each raw item shape:
  {headline, summary, url, source_name, published_at (ISO str), raw_category}
"""
import asyncio
import hashlib
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import feedparser
import httpx

FREE_RSS_SOURCES = [
    {"name": "Reuters Business", "url": "https://feeds.reuters.com/reuters/businessNews", "category": "capital_markets"},
    {"name": "Economic Times M&A", "url": "https://economictimes.indiatimes.com/markets/mergers-n-acquisitions/rssfeeds/2143429.cms", "category": "deal_activity"},
    {"name": "Yahoo Finance", "url": "https://finance.yahoo.com/rss/topstories", "category": "capital_markets"},
    {"name": "CNBC Top News", "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114", "category": "macro_geopolitical"},
    {"name": "Business Standard", "url": "https://www.business-standard.com/rss/home_page_top_stories.rss", "category": "deal_activity"},
    {"name": "Seeking Alpha", "url": "https://seekingalpha.com/feed.xml", "category": "institutional"},
    {"name": "Reddit r/mergers", "url": "https://www.reddit.com/r/mergers.rss", "category": "deal_activity"},
    {"name": "Reddit r/privateequity", "url": "https://www.reddit.com/r/privateequity.rss", "category": "institutional"},
    {"name": "Reddit r/investing", "url": "https://www.reddit.com/r/investing.rss", "category": "institutional"},
    {"name": "Moneycontrol", "url": "https://www.moneycontrol.com/rss/latestnews.xml", "category": "deal_activity"},
]

_FETCH_TIMEOUT = 10  # seconds per source
_CONCURRENT_SOURCES = 6


async def fetch_all_feeds() -> list[dict]:
    """
    Fetch all RSS sources concurrently. Returns deduplicated list of raw items.
    Sources that fail or timeout are silently skipped.
    """
    semaphore = asyncio.Semaphore(_CONCURRENT_SOURCES)

    async def _fetch_one(source: dict) -> list[dict]:
        async with semaphore:
            return await fetch_feed(source)

    results = await asyncio.gather(*[_fetch_one(s) for s in FREE_RSS_SOURCES])

    # Flatten and deduplicate by URL
    seen_urls: set[str] = set()
    items: list[dict] = []
    for batch in results:
        for item in batch:
            url = item.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                items.append(item)

    return items


async def fetch_feed(source: dict) -> list[dict]:
    """
    Fetch a single RSS source via httpx + feedparser.
    Returns list of raw item dicts. Returns [] on any error.
    """
    try:
        async with httpx.AsyncClient(
            timeout=_FETCH_TIMEOUT,
            headers={"User-Agent": "DealLens AI/1.0 (RSS reader)"},
            follow_redirects=True,
        ) as client:
            resp = await client.get(source["url"])
            resp.raise_for_status()
            content = resp.text
    except Exception:
        return []

    try:
        feed = feedparser.parse(content)
    except Exception:
        return []

    items = []
    for entry in feed.entries[:30]:  # cap per source
        headline = entry.get("title", "").strip()
        if not headline:
            continue

        url = entry.get("link", "").strip()
        summary = _clean_summary(entry.get("summary") or entry.get("description") or "")

        published_at = _parse_date(entry)

        # Generate stable item_id from URL hash
        item_id = "news_" + hashlib.md5(url.encode()).hexdigest()[:16] if url else \
                  "news_" + hashlib.md5(headline.encode()).hexdigest()[:16]

        items.append({
            "item_id": item_id,
            "headline": headline,
            "summary": summary,
            "url": url,
            "source_name": source["name"],
            "published_at": published_at,
            "raw_category": source["category"],
            "raw_content": summary,
        })

    return items


def _parse_date(entry) -> str:
    """Parse RSS entry date to ISO UTC string. Falls back to now."""
    for field in ("published", "updated", "created"):
        val = entry.get(field)
        if val:
            try:
                dt = parsedate_to_datetime(val)
                return dt.astimezone(timezone.utc).isoformat()
            except Exception:
                pass
    # Try feedparser's parsed_struct
    for field in ("published_parsed", "updated_parsed"):
        val = entry.get(field)
        if val:
            try:
                import time
                ts = time.mktime(val)
                return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
            except Exception:
                pass
    return datetime.now(timezone.utc).isoformat()


def _clean_summary(text: str) -> str:
    """Strip HTML tags and truncate."""
    import re
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:500]
