from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from loguru import logger
from fastapi.responses import HTMLResponse

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

app = FastAPI(
    title=f"{settings.APP_NAME} - Task A",
    description="DSN X BCT LLM Agent Challenge - Task A: User Modeling",
    version="1.0.0",
    docs_url="/docs",
    redoc_url=None,
    lifespan=lifespan,
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

# Register API Routers
app.include_router(reviews_router, prefix="/api/v1/reviews", tags=["Reviews"])