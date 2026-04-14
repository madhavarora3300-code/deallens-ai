import asyncio

from workers.celery_app import celery_app


@celery_app.task(name="workers.tasks.health_check")
def health_check() -> dict:
    return {"status": "ok"}


@celery_app.task(name="workers.tasks.fetch_and_classify_news", bind=True, max_retries=2)
def fetch_and_classify_news(self) -> dict:
    """
    Fetch all RSS feeds and classify with GPT-4o-mini.
    Runs every 6 hours via Celery beat.
    """
    async def _run():
        from routers.v1.market_intelligence import _run_fetch_pipeline
        return await _run_fetch_pipeline()

    try:
        result = asyncio.run(_run())
        return result
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(name="workers.tasks.run_enrichment", bind=True, max_retries=2)
def run_enrichment(self, company_id: str) -> dict:
    """
    Trigger full enrichment pipeline for a company.
    Runs the async pipeline in a synchronous Celery context.
    """
    async def _run():
        from core.database import AsyncSessionLocal
        from pipeline.research.enrichment_service import run_enrichment_pipeline
        async with AsyncSessionLocal() as db:
            return await run_enrichment_pipeline(company_id, db)

    try:
        result = asyncio.run(_run())
        return {"company_id": company_id, "status": "complete", **result}
    except Exception as exc:
        raise self.retry(exc=exc, countdown=30)
