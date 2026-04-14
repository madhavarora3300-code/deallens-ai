from datetime import datetime, timezone

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, func

from core.database import AsyncSessionLocal
from models.database_models import Company, MarketNewsItem
from routers.v1 import entity, company, discovery, regulatory, drafts, market_intelligence, shortlists

app = FastAPI(
    title="DealLens AI",
    description="Live M&A Intelligence Portal for Investment Bankers",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "http://frontend:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register all v1 routers per API spec
app.include_router(entity.router, prefix="/v1/entity", tags=["entity"])
app.include_router(company.router, prefix="/v1/company", tags=["company"])
app.include_router(discovery.router, prefix="/v1/discovery", tags=["discovery"])
app.include_router(regulatory.router, prefix="/v1/regulatory", tags=["regulatory"])
app.include_router(drafts.router, prefix="/v1/drafts", tags=["drafts"])
app.include_router(market_intelligence.router, prefix="/v1/market-intelligence", tags=["market-intelligence"])
app.include_router(shortlists.router, prefix="/v1/shortlists", tags=["shortlists"])


@app.get("/v1/health", tags=["health"])
async def health_check():
    """System health check."""
    db_status = "healthy"
    companies_count = 0
    last_news_fetch = None

    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(func.count()).select_from(Company))
            companies_count = result.scalar() or 0

            news_result = await db.execute(
                select(MarketNewsItem.fetched_at)
                .order_by(MarketNewsItem.fetched_at.desc())
                .limit(1)
            )
            row = news_result.scalar_one_or_none()
            if row:
                last_news_fetch = row.isoformat()
    except Exception:
        db_status = "unhealthy"

    return {
        "status": "ok",
        "version": "1.0",
        "product": "DealLens AI",
        "services": {
            "database": db_status,
            "openai": "healthy",
            "news_fetcher": "healthy",
            "enrichment_worker": "healthy",
        },
        "last_news_fetch": last_news_fetch,
        "companies_in_database": companies_count,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@app.websocket("/v1/ws/enrichment/{company_id}")
async def enrichment_websocket(websocket: WebSocket, company_id: str):
    """Stream live enrichment progress to frontend."""
    from pipeline.research.enrichment_ws import run_enrichment_with_stream
    await websocket.accept()
    try:
        await run_enrichment_with_stream(company_id, websocket)
    except WebSocketDisconnect:
        pass
    except Exception:
        try:
            await websocket.send_json({
                "type": "enrichment_error",
                "step": "Pipeline initialization",
                "error": "Internal error during enrichment",
                "fallback": None,
                "confidence_impact": -100,
            })
        except Exception:
            pass
