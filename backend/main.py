from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

app = FastAPI(title="MProxy", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

from backend.database import engine, Base
from backend.routers import subscriptions, nodes, proxy
from backend.mihomo_manager import mihomo

Base.metadata.create_all(bind=engine)
app.include_router(subscriptions.router)
app.include_router(nodes.router)
app.include_router(proxy.router)


@app.on_event("startup")
def startup():
    from backend.database import SessionLocal
    from backend.models import Node
    db = SessionLocal()
    try:
        if db.query(Node).filter(Node.enabled == True).count() > 0:
            from backend.generator import generate_config
            generate_config(db)
    finally:
        db.close()


@app.on_event("shutdown")
def shutdown():
    mihomo.stop()


@app.get("/api/health")
async def health():
    return {"status": "ok"}


dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if dist.exists():
    app.mount("/assets", StaticFiles(directory=str(dist / "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(request: Request, full_path: str):
        file_path = dist / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(dist / "index.html")
