from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.db import engine, Base
import app.models  # ensure models are imported for metadata
from app.api.v1.api import api_router

from sqlalchemy import text

# Create tables and execute lightweight column migrations if missing
try:
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS password_changed_at TIMESTAMP WITH TIME ZONE;"))
        conn.commit()
    Base.metadata.create_all(bind=engine)
except Exception as e:
    print(f"Database initialization warning: {e}")


app = FastAPI(

    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# Set up CORS middleware
# Filter out wildcard origin '*' to ensure secure credential handling
cors_origins = [o for o in settings.BACKEND_CORS_ORIGINS if o != "*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Set up Security Headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "no-referrer-when-downgrade"
    return response

app.include_router(api_router, prefix=settings.API_V1_STR)

import os
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Check for frontend/dist relative to the root folder (development or bundled layout)
current_dir = os.path.dirname(os.path.abspath(__file__))
frontend_dist_path = None
possible_paths = [
    os.path.abspath(os.path.join(current_dir, "..", "..", "..", "frontend", "dist")),
    os.path.abspath(os.path.join(current_dir, "..", "..", "frontend", "dist")),
    os.path.abspath(os.path.join(current_dir, "..", "frontend", "dist")),
    os.path.abspath(os.path.join(current_dir, "frontend", "dist")),
]
import sys
if hasattr(sys, '_MEIPASS'):
    possible_paths.append(os.path.join(sys._MEIPASS, "frontend", "dist"))
if getattr(sys, 'frozen', False):
    possible_paths.append(os.path.abspath(os.path.join(os.path.dirname(sys.executable), "frontend", "dist")))

for p in possible_paths:
    if os.path.exists(p) and os.path.exists(os.path.join(p, "index.html")):
        frontend_dist_path = p
        break

if frontend_dist_path:
    # Mount assets folder
    assets_path = os.path.join(frontend_dist_path, "assets")
    if os.path.exists(assets_path):
        app.mount("/assets", StaticFiles(directory=assets_path), name="static_assets")

    # Serve index.html for root "/"
    @app.get("/")
    async def read_root():
        return FileResponse(os.path.join(frontend_dist_path, "index.html"))

    # Catch-all for React routing (SPA routing)
    @app.get("/{catchall:path}")
    async def serve_spa(request: Request, catchall: str):
        if catchall.startswith("api/") or catchall.startswith("docs") or catchall.startswith("redoc") or catchall.startswith("openapi.json"):
            # Let standard router handle it or raise 404 if it doesn't match anything
            return None
        index_file = os.path.join(frontend_dist_path, "index.html")
        if os.path.exists(index_file):
            return FileResponse(index_file)
        return {"detail": "Not Found"}
else:
    @app.get("/")
    def read_root():
        return {
            "status": "online",
            "service": settings.PROJECT_NAME,
            "version": settings.VERSION,
            "docs_url": "/docs"
        }
