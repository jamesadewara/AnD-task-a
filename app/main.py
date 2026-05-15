from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.gzip import GZipMiddleware
from loguru import logger
from fastapi.responses import HTMLResponse, JSONResponse
from slowapi.errors import RateLimitExceeded
from app.core.ratelimit import limiter

from app.core.config import settings
from app.core.logging import setup_logging

# Initialize logging as soon as possible
setup_logging()

# Import Routers
from app.api.v1.endpoints.reviews import router as reviews_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──
    logger.info(f"🚀 [Lifespan] Starting up {settings.APP_NAME}")
    
    try:
        logger.info("✨ [Lifespan] Server ready to handle requests.")
        yield
        
    except Exception as e:
        logger.error(f"❌ [Lifespan] CRITICAL ERROR during startup: {e}")
        raise
    
    finally:
        # ── Shutdown ──
        logger.info(f"🛑 [Lifespan] Shutting down {settings.APP_NAME}...")
        logger.info("🏁 [Lifespan] Cleanup complete.")

from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

app = FastAPI(
    title=f"{settings.APP_NAME} - Task A",
    description="DSN X BCT LLM Agent Challenge - Task A: User Modeling",
    version="1.0.0",
    docs_url="/docs",
    redoc_url=None,
    lifespan=lifespan,
)

# Attach limiter to state
app.state.limiter = limiter

@app.exception_handler(RateLimitExceeded)
async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    """Custom Nigerian-voice 429 response."""
    return JSONResponse(
        status_code=429,
        content={
            "detail": "Omo calm down abeg, you dey too fast. \nTry again in a moment."
        }
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,
)

app.add_middleware(GZipMiddleware, minimum_size=1000)


@app.get("/redoc", include_in_schema=False)
async def redoc_html():
    # Serves ReDoc using unpkg CDN instead of jsdelivr.net
    # jsdelivr is blocked by Edge/Safari tracking prevention
    return HTMLResponse(f"""
<!DOCTYPE html>
<html>
  <head>
    <title>{settings.APP_NAME} - API Docs</title>
    <meta charset="utf-8"/>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>body {{ margin: 0; padding: 0; }}</style>
  </head>
  <body>
    <redoc spec-url="/openapi.json"></redoc>
    <script src="https://unpkg.com/redoc@latest/bundles/redoc.standalone.js"></script>
  </body>
</html>
""")


# ── Routes ─────────────────────────────────────────────────────────────────────
@app.get("/", include_in_schema=False)
async def root():
    return {"message": "Task A service is running", "version": "1.0.0"}

@app.get("/api/v1/health")
async def health():
    return {"status": "ok"}

@app.get("/api/v1/health/stream")
async def health_stream():
    from fastapi.responses import StreamingResponse
    import json
    import asyncio
    
    async def heartbeat():
        try:
            while True:
                yield f"data: {json.dumps({'status': 'ok', 'service': 'task-a'})}\n\n"
                await asyncio.sleep(15)
        except asyncio.CancelledError:
            logger.info("Health stream for Task A closed.")
            
    return StreamingResponse(heartbeat(), media_type="text/event-stream")
    
# Register API Routers
app.include_router(reviews_router, prefix="/api/v1/reviews", tags=["Reviews"])