from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from sqlalchemy import select, func
from core.database import AsyncSessionLocal, engine, Base
from models.database_models import Company, MarketNewsItem
import os

# Import all routers
from routers.v1 import (
    entity,
    company,
    discovery,
    regulatory,
    drafts,
    market_intelligence,
    shortlists
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Cleanup on shutdown
    await engine.dispose()

app = FastAPI(
    title="DealLens AI",
    version="1.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(entity.router, prefix="/v1", tags=["Entity Resolution"])
app.include_router(company.router, prefix="/v1", tags=["Company Profile"])
app.include_router(discovery.router, prefix="/v1", tags=["Discovery"])
app.include_router(regulatory.router, prefix="/v1", tags=["Regulatory"])
app.include_router(drafts.router, prefix="/v1", tags=["Drafts"])
app.include_router(market_intelligence.router, prefix="/v1", tags=["Market Intelligence"])
app.include_router(shortlists.router, prefix="/v1", tags=["Shortlists"])

@app.get("/v1/health")
async def health_check():
    """System health check."""
    db_status = "healthy"
    companies_count = 0
    last_news_fetch = None
    
    try:
        async with AsyncSessionLocal() as db:
            # Test connection
            result = await db.execute(select(func.count()).select_from(Company))
            companies_count = result.scalar() or 0
            
            # Get last news fetch
            news_result = await db.execute(
                select(MarketNewsItem.fetched_at)
                .order_by(MarketNewsItem.fetched_at.desc())
                .limit(1)
            )
            row = news_result.scalar_one_or_none()
            if row:
                last_news_fetch = row.isoformat()
    except Exception as e:
        print(f"Database health check failed: {e}")
        db_status = "unhealthy"
    
    return {
        "status": "ok",
        "version": "1.0",
        "product": "DealLens AI",
        "services": {
            "database": db_status,
            "openai": "healthy" if os.getenv("OPENAI_API_KEY") else "unhealthy",
            "news_fetcher": "healthy",
            "enrichment_worker": "healthy"
        },
        "last_news_fetch": last_news_fetch,
        "companies_in_database": companies_count,
        "generated_at": __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()
    }

@app.get("/")
async def root():
    return {"message": "DealLens AI API", "docs": "/docs"}
