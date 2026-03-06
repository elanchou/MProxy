from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from backend.database import get_db
from backend.models import Node

router = APIRouter(prefix="/api/nodes", tags=["nodes"])


@router.get("")
def list_nodes(subscription_id: int | None = None, db: Session = Depends(get_db)):
    q = db.query(Node)
    if subscription_id is not None:
        q = q.filter(Node.subscription_id == subscription_id)
    return q.all()


class NodeToggle(BaseModel):
    enabled: bool


@router.patch("/{node_id}")
def toggle_node(node_id: int, body: NodeToggle, db: Session = Depends(get_db)):
    node = db.query(Node).get(node_id)
    if node:
        node.enabled = body.enabled
        db.commit()
        db.refresh(node)
    return node
