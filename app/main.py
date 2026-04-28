from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.config import get_settings
from app.core.database import db
from app.api import notes, search, review, deep_review

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    # Startup
    await db.connect()
    await db.init_indexes()
    print("Connected to Neo4j")
    yield
    # Shutdown
    await db.close()
    print("Disconnected from Neo4j")


app = FastAPI(
    title="Knowledge Graph RAG + Review",
    description="GraphRAG-based knowledge management with FSRS review",
    version="0.1.0",
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
app.include_router(notes.router)
app.include_router(search.router)
app.include_router(review.router)
app.include_router(deep_review.router)


@app.get("/")
async def root():
    return {
        "status": "running",
        "endpoints": {
            "notes": "/notes",
            "search": "/search",
            "review": "/review",
            "deep-review": "/deep-review"
        }
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.get("/visualize")
async def visualize():
    """Serve the visualization dashboard"""
    return FileResponse("app/templates/index.html")


@app.get("/db/query")
async def db_query(query: str, limit: int = 100):
    """Execute a raw Cypher query for debugging"""
    try:
        results = await db.execute_query(query, {"limit": limit}) or []
        return {"results": results}
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=True
    )
