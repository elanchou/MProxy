from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.generator import generate_config
from backend.mihomo_manager import mihomo

router = APIRouter(prefix="/api/proxy", tags=["proxy"])


@router.get("/status")
def proxy_status():
    return mihomo.status()


@router.post("/start")
def proxy_start(db: Session = Depends(get_db)):
    generate_config(db)
    ok = mihomo.start()
    return {"success": ok, **mihomo.status()}


@router.post("/stop")
def proxy_stop():
    mihomo.stop()
    return {"success": True, **mihomo.status()}


@router.post("/restart")
def proxy_restart(db: Session = Depends(get_db)):
    generate_config(db)
    ok = mihomo.restart()
    return {"success": ok, **mihomo.status()}


@router.post("/generate")
def regenerate_config(db: Session = Depends(get_db)):
    config = generate_config(db)
    return {"proxies": len(config.get("proxies", [])), "listeners": len(config.get("listeners", []))}
