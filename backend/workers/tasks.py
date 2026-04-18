import asyncio
import logging
import sys
import os

# Ensure /app is on sys.path for forked prefork workers (needed for lazy imports inside asyncio.run)
_app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _app_dir not in sys.path:
    sys.path.insert(0, _app_dir)

from workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="workers.tasks.health_check")
def health_check() -> dict:
    return {"status": "ok"}


@celery_app.task(name="workers.tasks.fetch_and_classify_news", bind=True, max_retries=2)
def fetch_and_classify_news(self) -> dict:
    """
    Fetch all RSS feeds and classify with GPT-4o-mini.
    Runs every 6 hours via Celery beat.
    Market intelligence pipeline has no DB writes inside asyncio.run(), safe as-is.
    """
    async def _run():
        from routers.v1.market_intelligence import _run_fetch_pipeline
        return await _run_fetch_pipeline()

    try:
        result = asyncio.run(_run())
        return result
    except Exception as exc:
        logger.error("CELERY fetch_and_classify_news failed: %s", exc, exc_info=True)
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(name="workers.tasks.run_enrichment", bind=True, max_retries=2)
def run_enrichment(self, company_id: str) -> dict:
    """
    Trigger full enrichment pipeline for a company.
    Uses NullPool engine so asyncio.run() never reuses an asyncpg connection
    from a previous (destroyed) event loop.
    """
    from core.database import make_task_session_factory
    from pipeline.research.enrichment_service import run_enrichment_pipeline

    async def _run():
        SessionFactory = make_task_session_factory()
        async with SessionFactory() as db:
            return await run_enrichment_pipeline(company_id, db)

    try:
        logger.info("CELERY run_enrichment: starting for company_id=%s", company_id)
        result = asyncio.run(_run())
        logger.info("CELERY run_enrichment: complete for company_id=%s", company_id)
        return {"company_id": company_id, "status": "complete", **result}
    except Exception as exc:
        logger.error("CELERY run_enrichment failed for %s: %s", company_id, exc, exc_info=True)
        raise self.retry(exc=exc, countdown=30)


@celery_app.task(name="workers.tasks.run_buy_side_discovery", bind=True, max_retries=1, time_limit=600)
def run_buy_side_discovery(self, payload: dict) -> dict:
    """
    Full buy-side discovery pipeline: seed candidates via GPT, enrich, score, tier.

    Uses NullPool engine (created fresh inside asyncio.run()) to prevent asyncpg
    connection reuse across destroyed event loops — the root cause of 'random companies'
    being returned when the real pipeline silently failed.
    """
    # Import at the function level (not inside the coroutine) so prefork child processes
    # can resolve module paths correctly.
    from core.database import make_task_session_factory
    from routers.v1.discovery import _run_buy_side_pipeline

    buyer_id = payload.get("buyer_company_id", "unknown")

    async def _run():
        session_factory = make_task_session_factory()
        return await _run_buy_side_pipeline(payload, session_factory=session_factory)

    try:
        logger.info("CELERY run_buy_side_discovery: starting for buyer=%s strategy=%s",
                    buyer_id, payload.get("strategy_mode"))
        result = asyncio.run(_run())
        n_targets = len(result.get("targets", [])) if isinstance(result, dict) else 0
        logger.info("CELERY run_buy_side_discovery: complete for buyer=%s, %d targets returned",
                    buyer_id, n_targets)
        return result
    except Exception as exc:
        logger.error("CELERY run_buy_side_discovery failed for buyer=%s: %s", buyer_id, exc, exc_info=True)
        raise self.retry(exc=exc, countdown=5)


@celery_app.task(name="workers.tasks.run_sell_side_discovery", bind=True, max_retries=1, time_limit=600)
def run_sell_side_discovery(self, payload: dict) -> dict:
    """
    Full sell-side discovery pipeline: seed buyers via GPT, enrich, score, tier.
    Uses NullPool engine for the same reason as buy-side.
    """
    from core.database import make_task_session_factory
    from routers.v1.discovery import _run_sell_side_pipeline

    seller_id = payload.get("seller_company_id", "unknown")

    async def _run():
        session_factory = make_task_session_factory()
        return await _run_sell_side_pipeline(payload, session_factory=session_factory)

    try:
        logger.info("CELERY run_sell_side_discovery: starting for seller=%s objective=%s",
                    seller_id, payload.get("process_objective"))
        result = asyncio.run(_run())
        n_buyers = len(result.get("buyers", [])) if isinstance(result, dict) else 0
        logger.info("CELERY run_sell_side_discovery: complete for seller=%s, %d buyers returned",
                    seller_id, n_buyers)
        return result
    except Exception as exc:
        logger.error("CELERY run_sell_side_discovery failed for seller=%s: %s", seller_id, exc, exc_info=True)
        raise self.retry(exc=exc, countdown=5)
