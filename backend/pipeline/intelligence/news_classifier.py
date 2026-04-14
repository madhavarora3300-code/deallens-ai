"""
News Classifier — GPT-4o-mini batch classification of M&A news items.

Runs items in concurrent batches of 10 to stay within token limits.
Items classified as not_relevant are filtered out before DB write.
"""
import asyncio
import json

from openai import AsyncOpenAI

from core.config import settings

_client: AsyncOpenAI | None = None
_BATCH_SIZE = 10
_CLASSIFY_CONCURRENCY = 4


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _client


_SYSTEM_PROMPT = """You are filtering news for investment bankers. Classify this M&A/finance news headline.

Return ONLY valid JSON. No markdown.

{
  "relevant": true or false,
  "category": "deal_activity" | "capital_markets" | "institutional" | "macro_geopolitical" | "not_relevant",
  "sentiment": "positive" | "negative" | "neutral",
  "urgency": "high" | "medium" | "low",
  "companies_mentioned": ["Company Name", ...],
  "tickers_mentioned": ["TICK", ...],
  "deal_type": "acquisition" | "merger" | "ipo" | "fundraise" | "divestiture" | "activist" | "regulatory" | "macro" | "other" | null,
  "deal_size_usd": number in USD (not millions/billions) or null,
  "summary": "one sentence — key fact only, no editorialising",
  "relevance_score": 0-100,
  "classification_confidence": 0-100
}

Mark relevant=true for: M&A deals, IPOs, PE fundraises, activist campaigns,
regulatory changes affecting investment, geopolitical events moving markets,
central bank decisions, major corporate restructurings, earnings surprises.

Mark relevant=false for: sports, entertainment, product launches unrelated to M&A,
general politics without market impact, HR/employment news, weather."""


async def classify_item(item: dict) -> dict:
    """Classify a single news item. Returns item with classification fields merged in."""
    user_msg = (
        f"Headline: {item.get('headline', '')}\n"
        f"Source: {item.get('source_name', '')}\n"
        f"Summary: {item.get('summary', '')[:200]}"
    )
    try:
        resp = await _get_client().chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.0,
            max_tokens=300,
            response_format={"type": "json_object"},
        )
        cls = json.loads(resp.choices[0].message.content)
    except Exception:
        cls = {
            "relevant": False,
            "category": "not_relevant",
            "sentiment": "neutral",
            "urgency": "low",
            "companies_mentioned": [],
            "tickers_mentioned": [],
            "deal_type": None,
            "deal_size_usd": None,
            "summary": item.get("summary", ""),
            "relevance_score": 0,
            "classification_confidence": 0,
        }

    return {
        **item,
        "relevant": cls.get("relevant", False),
        "category": cls.get("category", item.get("raw_category", "not_relevant")),
        "sentiment": cls.get("sentiment", "neutral"),
        "urgency": cls.get("urgency", "low"),
        "companies_mentioned": cls.get("companies_mentioned", []),
        "tickers_mentioned": cls.get("tickers_mentioned", []),
        "deal_type": cls.get("deal_type"),
        "deal_size_usd": cls.get("deal_size_usd"),
        "summary": cls.get("summary") or item.get("summary", ""),
        "relevance_score": cls.get("relevance_score", 0),
        "classification_raw": cls,
    }


async def classify_batch(items: list[dict]) -> list[dict]:
    """
    Classify a batch of news items concurrently.
    Returns only items where relevant=True, sorted by relevance_score desc.
    """
    if not items:
        return []

    semaphore = asyncio.Semaphore(_CLASSIFY_CONCURRENCY)

    async def _classify_one(item: dict) -> dict:
        async with semaphore:
            return await classify_item(item)

    # Process in chunks to avoid overwhelming the API
    results = []
    for i in range(0, len(items), _BATCH_SIZE * _CLASSIFY_CONCURRENCY):
        chunk = items[i:i + _BATCH_SIZE * _CLASSIFY_CONCURRENCY]
        chunk_results = await asyncio.gather(*[_classify_one(item) for item in chunk])
        results.extend(chunk_results)

    # Filter to relevant only and sort by relevance_score
    relevant = [r for r in results if r.get("relevant", False)]
    relevant.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
    return relevant
