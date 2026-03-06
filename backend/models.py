from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean
from datetime import datetime, timezone
from backend.database import Base


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    url = Column(Text, nullable=False)
    enabled = Column(Boolean, default=True)
    node_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))


class Node(Base):
    __tablename__ = "nodes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    subscription_id = Column(Integer, nullable=False)
    name = Column(String(255), nullable=False)
    type = Column(String(50), nullable=False)
    server = Column(String(255), nullable=False)
    port = Column(Integer, nullable=False)
    listener_port = Column(Integer, nullable=True)
    raw_config = Column(Text, nullable=False)
    enabled = Column(Boolean, default=True)
