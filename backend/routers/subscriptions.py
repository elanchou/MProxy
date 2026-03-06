from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from backend.database import get_db
from backend.models import Subscription, Node

router = APIRouter(prefix="/api/subscriptions", tags=["subscriptions"])


class SubCreate(BaseModel):
    name: str
    url: str


class SubUpdate(BaseModel):
    name: str | None = None
    url: str | None = None
    enabled: bool | None = None


@router.get("")
def list_subs(db: Session = Depends(get_db)):
    return db.query(Subscription).all()


@router.post("", status_code=201)
def create_sub(body: SubCreate, db: Session = Depends(get_db)):
    sub = Subscription(name=body.name, url=body.url)
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return sub


@router.put("/{sub_id}")
def update_sub(sub_id: int, body: SubUpdate, db: Session = Depends(get_db)):
    sub = db.query(Subscription).get(sub_id)
    if not sub:
        raise HTTPException(404, "Subscription not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(sub, k, v)
    db.commit()
    db.refresh(sub)
    return sub


@router.delete("/{sub_id}", status_code=204)
def delete_sub(sub_id: int, db: Session = Depends(get_db)):
    sub = db.query(Subscription).get(sub_id)
    if not sub:
        raise HTTPException(404, "Subscription not found")
    db.query(Node).filter(Node.subscription_id == sub_id).delete()
    db.delete(sub)
    db.commit()
