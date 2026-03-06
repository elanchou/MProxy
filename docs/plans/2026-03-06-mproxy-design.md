# MProxy Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a Docker-deployable proxy management application that fetches nodes from subscription URLs, exposes each node as a separate local proxy port via Mihomo, and provides a Web UI for management.

**Architecture:** Python FastAPI backend manages subscriptions, parses nodes, generates Mihomo YAML configs with per-node listeners, and controls the Mihomo process. Vue 3 SPA frontend provides dashboard, subscription management, and node overview. SQLite for persistence. All packaged in a single Docker image.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy + SQLite, Mihomo (Clash.Meta) core, Vue 3 + Vite + TailwindCSS, Docker

---

## Overview

```
┌─────────────────────────────────────────────────┐
│                  Docker Container                │
│                                                  │
│  ┌──────────┐     ┌──────────┐    ┌──────────┐  │
│  │  Vue 3   │────▶│ FastAPI  │───▶│  Mihomo  │  │
│  │  Web UI  │     │ Backend  │    │  Core    │  │
│  │ :3000    │     │ :8080    │    │ :7900+   │  │
│  └──────────┘     └──────────┘    └──────────┘  │
│                        │                         │
│                   ┌────┴────┐                    │
│                   │ SQLite  │                    │
│                   └─────────┘                    │
└─────────────────────────────────────────────────┘
```

**Key Mihomo Config Pattern (per-node listeners):**
```yaml
listeners:
  - name: node-hk-01
    type: mixed
    port: 7901
    listen: 0.0.0.0
    proxy: HK-Node-01
  - name: node-us-01
    type: mixed
    port: 7902
    listen: 0.0.0.0
    proxy: US-Node-01
```

**Port allocation:** Starting at 7901, each node gets a sequential port. The API port is 8080. The base Mihomo control port is 9090 (external-controller).

---

### Task 1: Project Scaffolding

**Files:**
- Create: `backend/__init__.py`
- Create: `backend/main.py`
- Create: `backend/config.py`
- Create: `backend/requirements.txt`
- Create: `frontend/package.json` (via vite init)
- Create: `Dockerfile`
- Create: `docker-compose.yml`
- Create: `.gitignore`

**Step 1: Initialize git repo**

```bash
cd /Users/elanchou/MProxy
git init
```

**Step 2: Create .gitignore**

```gitignore
__pycache__/
*.pyc
.env
node_modules/
dist/
data/
*.db
mihomo
.vite/
```

**Step 3: Create backend scaffolding**

`backend/config.py`:
```python
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

DB_PATH = DATA_DIR / "mproxy.db"
MIHOMO_DIR = DATA_DIR / "mihomo"
MIHOMO_DIR.mkdir(exist_ok=True)
MIHOMO_CONFIG_PATH = MIHOMO_DIR / "config.yaml"
MIHOMO_BINARY = BASE_DIR / "mihomo"

LISTENER_BASE_PORT = 7901
EXTERNAL_CONTROLLER = "0.0.0.0:9090"
API_PORT = 8080
```

`backend/main.py`:
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

app = FastAPI(title="MProxy", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
async def health():
    return {"status": "ok"}

dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if dist.exists():
    app.mount("/", StaticFiles(directory=str(dist), html=True), name="static")
```

`backend/requirements.txt`:
```
fastapi==0.115.6
uvicorn[standard]==0.34.0
sqlalchemy==2.0.36
aiohttp==3.11.11
pyyaml==6.0.2
```

**Step 4: Create Dockerfile**

```dockerfile
FROM node:20-slim AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ .
RUN npm run build

FROM python:3.12-slim
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    wget ca-certificates gunzip \
    && rm -rf /var/lib/apt/lists/*

ARG TARGETARCH
RUN ARCH=$(case ${TARGETARCH} in amd64) echo "amd64";; arm64) echo "arm64";; *) echo "amd64";; esac) && \
    wget -O /tmp/mihomo.gz "https://github.com/MetaCubeX/mihomo/releases/download/v1.19.0/mihomo-linux-${ARCH}-v1.19.0.gz" && \
    gunzip /tmp/mihomo.gz && \
    mv /tmp/mihomo /app/mihomo && \
    chmod +x /app/mihomo

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ backend/
COPY --from=frontend-builder /app/frontend/dist frontend/dist

RUN mkdir -p data/mihomo

EXPOSE 8080 9090
EXPOSE 7901-8100

CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

`docker-compose.yml`:
```yaml
services:
  mproxy:
    build: .
    ports:
      - "8080:8080"
      - "9090:9090"
      - "7901-8100:7901-8100"
    volumes:
      - ./data:/app/data
    restart: unless-stopped
```

**Step 5: Commit**

```bash
git add -A && git commit -m "feat: project scaffolding with FastAPI, Docker, and config"
```

---

### Task 2: Database Models & Subscription CRUD API

**Files:**
- Create: `backend/database.py`
- Create: `backend/models.py`
- Create: `backend/routers/__init__.py`
- Create: `backend/routers/subscriptions.py`
- Modify: `backend/main.py`

**Step 1: Create database module**

`backend/database.py`:
```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from backend.config import DB_PATH

engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

**Step 2: Create models**

`backend/models.py`:
```python
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
    type = Column(String(50), nullable=False)  # ss, vmess, vless, trojan, hysteria2...
    server = Column(String(255), nullable=False)
    port = Column(Integer, nullable=False)
    listener_port = Column(Integer, nullable=True)  # assigned local port
    raw_config = Column(Text, nullable=False)  # JSON of full proxy config
    enabled = Column(Boolean, default=True)
```

**Step 3: Create subscription router**

`backend/routers/subscriptions.py`:
```python
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
```

**Step 4: Wire router into main.py**

Add to `backend/main.py`:
```python
from backend.database import engine, Base
from backend.routers import subscriptions

Base.metadata.create_all(bind=engine)
app.include_router(subscriptions.router)
```

**Step 5: Test manually**

```bash
cd /Users/elanchou/MProxy
pip install -r backend/requirements.txt
python -m uvicorn backend.main:app --port 8080 &
curl -X POST http://localhost:8080/api/subscriptions -H "Content-Type: application/json" -d '{"name":"test","url":"https://example.com/sub"}'
curl http://localhost:8080/api/subscriptions
kill %1
```

**Step 6: Commit**

```bash
git add -A && git commit -m "feat: database models and subscription CRUD API"
```

---

### Task 3: Subscription Fetcher & Node Parser

**Files:**
- Create: `backend/parser.py`
- Create: `backend/routers/nodes.py`
- Modify: `backend/routers/subscriptions.py` (add refresh endpoint)
- Modify: `backend/main.py` (register nodes router)

**Step 1: Create the parser module**

`backend/parser.py`:
```python
import base64
import json
import re
import yaml
from urllib.parse import urlparse, parse_qs, unquote


def fetch_and_parse(content: str) -> list[dict]:
    """Parse subscription content into list of Mihomo proxy dicts."""
    # Try as Clash YAML first
    try:
        data = yaml.safe_load(content)
        if isinstance(data, dict) and "proxies" in data:
            return data["proxies"]
    except yaml.YAMLError:
        pass

    # Try base64 decode
    try:
        decoded = base64.b64decode(content.strip()).decode("utf-8")
        lines = decoded.strip().splitlines()
    except Exception:
        lines = content.strip().splitlines()

    proxies = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        proxy = _parse_uri(line)
        if proxy:
            proxies.append(proxy)
    return proxies


def _parse_uri(uri: str) -> dict | None:
    """Parse a single proxy URI into Mihomo proxy dict format."""
    if uri.startswith("vmess://"):
        return _parse_vmess(uri)
    elif uri.startswith("vless://"):
        return _parse_vless(uri)
    elif uri.startswith("trojan://"):
        return _parse_trojan(uri)
    elif uri.startswith("ss://"):
        return _parse_ss(uri)
    elif uri.startswith("ssr://"):
        return _parse_ssr(uri)
    elif uri.startswith(("hysteria2://", "hy2://")):
        return _parse_hysteria2(uri)
    return None


def _parse_vmess(uri: str) -> dict | None:
    try:
        raw = base64.b64decode(uri[8:]).decode("utf-8")
        j = json.loads(raw)
        proxy = {
            "name": j.get("ps", "vmess-node"),
            "type": "vmess",
            "server": j["add"],
            "port": int(j["port"]),
            "uuid": j["id"],
            "alterId": int(j.get("aid", 0)),
            "cipher": j.get("scy", "auto"),
        }
        net = j.get("net", "tcp")
        if net == "ws":
            proxy["network"] = "ws"
            proxy["ws-opts"] = {
                "path": j.get("path", "/"),
                "headers": {"Host": j.get("host", "")},
            }
        elif net == "grpc":
            proxy["network"] = "grpc"
            proxy["grpc-opts"] = {"grpc-service-name": j.get("path", "")}
        tls = j.get("tls", "")
        if tls == "tls":
            proxy["tls"] = True
            proxy["servername"] = j.get("sni", j.get("host", ""))
        return proxy
    except Exception:
        return None


def _parse_vless(uri: str) -> dict | None:
    try:
        parsed = urlparse(uri)
        params = parse_qs(parsed.query)
        name = unquote(parsed.fragment) or "vless-node"
        proxy = {
            "name": name,
            "type": "vless",
            "server": parsed.hostname,
            "port": parsed.port,
            "uuid": parsed.username,
            "tls": params.get("security", ["none"])[0] in ("tls", "reality"),
            "skip-cert-verify": True,
        }
        flow = params.get("flow", [None])[0]
        if flow:
            proxy["flow"] = flow
        net = params.get("type", ["tcp"])[0]
        if net == "ws":
            proxy["network"] = "ws"
            proxy["ws-opts"] = {
                "path": params.get("path", ["/"])[0],
                "headers": {"Host": params.get("host", [""])[0]},
            }
        elif net == "grpc":
            proxy["network"] = "grpc"
            proxy["grpc-opts"] = {
                "grpc-service-name": params.get("serviceName", [""])[0]
            }
        security = params.get("security", ["none"])[0]
        if security == "reality":
            proxy["reality-opts"] = {
                "public-key": params.get("pbk", [""])[0],
                "short-id": params.get("sid", [""])[0],
            }
            proxy["servername"] = params.get("sni", [""])[0]
        elif security == "tls":
            proxy["servername"] = params.get("sni", [""])[0]
        return proxy
    except Exception:
        return None


def _parse_trojan(uri: str) -> dict | None:
    try:
        parsed = urlparse(uri)
        params = parse_qs(parsed.query)
        name = unquote(parsed.fragment) or "trojan-node"
        proxy = {
            "name": name,
            "type": "trojan",
            "server": parsed.hostname,
            "port": parsed.port,
            "password": unquote(parsed.username),
            "skip-cert-verify": True,
        }
        sni = params.get("sni", [None])[0]
        if sni:
            proxy["sni"] = sni
        net = params.get("type", ["tcp"])[0]
        if net == "ws":
            proxy["network"] = "ws"
            proxy["ws-opts"] = {
                "path": params.get("path", ["/"])[0],
            }
        elif net == "grpc":
            proxy["network"] = "grpc"
            proxy["grpc-opts"] = {
                "grpc-service-name": params.get("serviceName", [""])[0]
            }
        return proxy
    except Exception:
        return None


def _parse_ss(uri: str) -> dict | None:
    try:
        rest = uri[5:]
        if "#" in rest:
            rest, fragment = rest.rsplit("#", 1)
            name = unquote(fragment)
        else:
            name = "ss-node"
        # SIP002 format: method:password@server:port
        # or base64(method:password)@server:port
        if "@" in rest:
            userinfo, hostport = rest.rsplit("@", 1)
            try:
                userinfo = base64.b64decode(userinfo + "==").decode("utf-8")
            except Exception:
                pass
            method, password = userinfo.split(":", 1)
            host, port = hostport.split(":")
        else:
            decoded = base64.b64decode(rest + "==").decode("utf-8")
            method_pass, hostport = decoded.rsplit("@", 1)
            method, password = method_pass.split(":", 1)
            host, port = hostport.split(":")
        return {
            "name": name,
            "type": "ss",
            "server": host,
            "port": int(port),
            "cipher": method,
            "password": password,
        }
    except Exception:
        return None


def _parse_ssr(uri: str) -> dict | None:
    try:
        decoded = base64.b64decode(uri[6:] + "==").decode("utf-8")
        parts = decoded.split(":")
        server = parts[0]
        port = int(parts[1])
        protocol = parts[2]
        method = parts[3]
        obfs = parts[4]
        rest = parts[5]
        password_b64 = rest.split("/")[0]
        password = base64.b64decode(password_b64 + "==").decode("utf-8")
        return {
            "name": f"ssr-{server}:{port}",
            "type": "ssr",
            "server": server,
            "port": port,
            "cipher": method,
            "password": password,
            "protocol": protocol,
            "obfs": obfs,
        }
    except Exception:
        return None


def _parse_hysteria2(uri: str) -> dict | None:
    try:
        parsed = urlparse(uri)
        params = parse_qs(parsed.query)
        name = unquote(parsed.fragment) if parsed.fragment else "hy2-node"
        proxy = {
            "name": name,
            "type": "hysteria2",
            "server": parsed.hostname,
            "port": parsed.port,
            "password": unquote(parsed.username) if parsed.username else "",
            "skip-cert-verify": True,
        }
        sni = params.get("sni", [None])[0]
        if sni:
            proxy["sni"] = sni
        obfs = params.get("obfs", [None])[0]
        if obfs:
            proxy["obfs"] = obfs
            proxy["obfs-password"] = params.get("obfs-password", [""])[0]
        return proxy
    except Exception:
        return None
```

**Step 2: Create subscription refresh endpoint & nodes router**

Add to `backend/routers/subscriptions.py`:
```python
import aiohttp
from backend.parser import fetch_and_parse
import json

@router.post("/{sub_id}/refresh")
async def refresh_sub(sub_id: int, db: Session = Depends(get_db)):
    sub = db.query(Subscription).get(sub_id)
    if not sub:
        raise HTTPException(404, "Subscription not found")

    async with aiohttp.ClientSession() as session:
        async with session.get(sub.url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            if resp.status != 200:
                raise HTTPException(502, f"Failed to fetch subscription: HTTP {resp.status}")
            content = await resp.text()

    proxies = fetch_and_parse(content)

    # Remove old nodes for this subscription
    db.query(Node).filter(Node.subscription_id == sub_id).delete()

    for p in proxies:
        node = Node(
            subscription_id=sub_id,
            name=p.get("name", "unknown"),
            type=p.get("type", "unknown"),
            server=p.get("server", ""),
            port=p.get("port", 0),
            raw_config=json.dumps(p, ensure_ascii=False),
            enabled=True,
        )
        db.add(node)

    sub.node_count = len(proxies)
    db.commit()
    return {"message": f"Fetched {len(proxies)} nodes"}
```

`backend/routers/nodes.py`:
```python
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
```

**Step 3: Register nodes router in main.py**

```python
from backend.routers import subscriptions, nodes
app.include_router(nodes.router)
```

**Step 4: Commit**

```bash
git add -A && git commit -m "feat: subscription fetcher, node parser (vmess/vless/trojan/ss/ssr/hy2), nodes API"
```

---

### Task 4: Mihomo Config Generator & Process Manager

**Files:**
- Create: `backend/generator.py`
- Create: `backend/mihomo_manager.py`
- Create: `backend/routers/proxy.py`
- Modify: `backend/main.py`

**Step 1: Create config generator**

`backend/generator.py`:
```python
import json
import yaml
from sqlalchemy.orm import Session
from backend.models import Node
from backend.config import MIHOMO_CONFIG_PATH, LISTENER_BASE_PORT, EXTERNAL_CONTROLLER


def generate_config(db: Session) -> dict:
    """Generate Mihomo YAML config with per-node listeners."""
    nodes = db.query(Node).filter(Node.enabled == True).all()

    proxies = []
    listeners = []
    proxy_names = []

    port = LISTENER_BASE_PORT
    for node in nodes:
        proxy_conf = json.loads(node.raw_config)
        name = proxy_conf["name"]

        # Ensure unique names
        if name in proxy_names:
            name = f"{name}-{node.id}"
            proxy_conf["name"] = name

        proxies.append(proxy_conf)
        proxy_names.append(name)

        listeners.append({
            "name": f"in-{node.id}",
            "type": "mixed",
            "port": port,
            "listen": "0.0.0.0",
            "proxy": name,
        })

        # Update assigned port in DB
        node.listener_port = port
        port += 1

    db.commit()

    config = {
        "mixed-port": 7890,
        "allow-lan": True,
        "mode": "rule",
        "log-level": "info",
        "external-controller": EXTERNAL_CONTROLLER,
        "proxies": proxies,
        "listeners": listeners,
        "proxy-groups": [
            {
                "name": "PROXY",
                "type": "select",
                "proxies": proxy_names + ["DIRECT"],
            },
            {
                "name": "AUTO",
                "type": "url-test",
                "proxies": proxy_names,
                "url": "https://www.gstatic.com/generate_204",
                "interval": 300,
            },
        ],
        "rules": [
            "MATCH,PROXY",
        ],
    }

    with open(MIHOMO_CONFIG_PATH, "w") as f:
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    return config
```

**Step 2: Create process manager**

`backend/mihomo_manager.py`:
```python
import subprocess
import signal
import os
from backend.config import MIHOMO_BINARY, MIHOMO_DIR, MIHOMO_CONFIG_PATH


class MihomoManager:
    def __init__(self):
        self._process: subprocess.Popen | None = None

    @property
    def running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def start(self) -> bool:
        if self.running:
            return True
        if not MIHOMO_CONFIG_PATH.exists():
            return False
        self._process = subprocess.Popen(
            [str(MIHOMO_BINARY), "-d", str(MIHOMO_DIR)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        return True

    def stop(self):
        if self._process and self._process.poll() is None:
            self._process.send_signal(signal.SIGTERM)
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
        self._process = None

    def restart(self) -> bool:
        self.stop()
        return self.start()

    def status(self) -> dict:
        return {
            "running": self.running,
            "pid": self._process.pid if self.running else None,
        }


mihomo = MihomoManager()
```

**Step 3: Create proxy control router**

`backend/routers/proxy.py`:
```python
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
```

**Step 4: Register in main.py and add shutdown hook**

```python
from backend.routers import subscriptions, nodes, proxy
from backend.mihomo_manager import mihomo

app.include_router(proxy.router)

@app.on_event("shutdown")
def shutdown():
    mihomo.stop()
```

**Step 5: Commit**

```bash
git add -A && git commit -m "feat: Mihomo config generator with per-node listeners and process manager"
```

---

### Task 5: Frontend — Project Setup & Layout

**Files:**
- Create: `frontend/` (via Vite scaffolding)
- Create: `frontend/src/App.vue`
- Create: `frontend/src/api.js`
- Create: `frontend/src/views/Dashboard.vue`
- Create: `frontend/src/views/Subscriptions.vue`
- Create: `frontend/src/views/Nodes.vue`

**Step 1: Scaffold Vue 3 project**

```bash
cd /Users/elanchou/MProxy
npm create vite@latest frontend -- --template vue
cd frontend
npm install
npm install vue-router@4 axios tailwindcss @tailwindcss/vite
```

**Step 2: Configure Tailwind**

`frontend/vite.config.js`:
```js
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [vue(), tailwindcss()],
  server: {
    proxy: {
      '/api': 'http://localhost:8080'
    }
  }
})
```

`frontend/src/style.css`:
```css
@import "tailwindcss";
```

**Step 3: Create API client**

`frontend/src/api.js`:
```js
import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

export default {
  // Subscriptions
  getSubs: () => api.get('/subscriptions'),
  createSub: (data) => api.post('/subscriptions', data),
  updateSub: (id, data) => api.put(`/subscriptions/${id}`, data),
  deleteSub: (id) => api.delete(`/subscriptions/${id}`),
  refreshSub: (id) => api.post(`/subscriptions/${id}/refresh`),

  // Nodes
  getNodes: (subId) => api.get('/nodes', { params: subId ? { subscription_id: subId } : {} }),
  toggleNode: (id, enabled) => api.patch(`/nodes/${id}`, { enabled }),

  // Proxy
  proxyStatus: () => api.get('/proxy/status'),
  proxyStart: () => api.post('/proxy/start'),
  proxyStop: () => api.post('/proxy/stop'),
  proxyRestart: () => api.post('/proxy/restart'),
}
```

**Step 4: Create router and layout**

`frontend/src/router.js`:
```js
import { createRouter, createWebHistory } from 'vue-router'
import Dashboard from './views/Dashboard.vue'
import Subscriptions from './views/Subscriptions.vue'
import Nodes from './views/Nodes.vue'

export default createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: Dashboard },
    { path: '/subscriptions', component: Subscriptions },
    { path: '/nodes', component: Nodes },
  ]
})
```

`frontend/src/App.vue`:
```vue
<template>
  <div class="min-h-screen bg-gray-950 text-gray-100">
    <nav class="bg-gray-900 border-b border-gray-800">
      <div class="max-w-7xl mx-auto px-4 py-3 flex items-center gap-8">
        <h1 class="text-xl font-bold text-indigo-400">MProxy</h1>
        <router-link to="/" class="nav-link">Dashboard</router-link>
        <router-link to="/subscriptions" class="nav-link">Subscriptions</router-link>
        <router-link to="/nodes" class="nav-link">Nodes</router-link>
      </div>
    </nav>
    <main class="max-w-7xl mx-auto px-4 py-6">
      <router-view />
    </main>
  </div>
</template>

<style>
.nav-link {
  @apply text-sm text-gray-400 hover:text-gray-100 transition-colors;
}
.router-link-active {
  @apply text-indigo-400;
}
</style>
```

`frontend/src/main.js`:
```js
import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import './style.css'

createApp(App).use(router).mount('#app')
```

**Step 5: Commit**

```bash
git add -A && git commit -m "feat: Vue 3 frontend scaffolding with router, Tailwind, API client"
```

---

### Task 6: Frontend — Dashboard View

**Files:**
- Create: `frontend/src/views/Dashboard.vue`

**Step 1: Build Dashboard component**

`frontend/src/views/Dashboard.vue`:
```vue
<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <h2 class="text-2xl font-bold">Dashboard</h2>
      <div class="flex items-center gap-3">
        <span :class="status.running ? 'text-green-400' : 'text-red-400'" class="text-sm font-medium">
          {{ status.running ? 'Running' : 'Stopped' }}
          <span v-if="status.pid" class="text-gray-500 ml-1">PID: {{ status.pid }}</span>
        </span>
        <button v-if="!status.running" @click="start" :disabled="loading"
          class="btn bg-green-600 hover:bg-green-700">Start</button>
        <button v-else @click="restart" :disabled="loading"
          class="btn bg-yellow-600 hover:bg-yellow-700">Restart</button>
        <button v-if="status.running" @click="stop" :disabled="loading"
          class="btn bg-red-600 hover:bg-red-700">Stop</button>
      </div>
    </div>

    <div class="grid grid-cols-3 gap-4">
      <div class="card">
        <div class="text-3xl font-bold text-indigo-400">{{ stats.subscriptions }}</div>
        <div class="text-sm text-gray-400 mt-1">Subscriptions</div>
      </div>
      <div class="card">
        <div class="text-3xl font-bold text-green-400">{{ stats.nodes }}</div>
        <div class="text-sm text-gray-400 mt-1">Total Nodes</div>
      </div>
      <div class="card">
        <div class="text-3xl font-bold text-yellow-400">{{ stats.enabledNodes }}</div>
        <div class="text-sm text-gray-400 mt-1">Active Nodes</div>
      </div>
    </div>

    <div class="card" v-if="nodes.length">
      <h3 class="text-lg font-semibold mb-3">Node Port Mapping</h3>
      <div class="overflow-auto max-h-96">
        <table class="w-full text-sm">
          <thead class="text-gray-400 border-b border-gray-700">
            <tr>
              <th class="text-left py-2 px-3">Name</th>
              <th class="text-left py-2 px-3">Type</th>
              <th class="text-left py-2 px-3">Server</th>
              <th class="text-left py-2 px-3">Local Port</th>
              <th class="text-left py-2 px-3">Status</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="n in nodes" :key="n.id" class="border-b border-gray-800 hover:bg-gray-800/50">
              <td class="py-2 px-3">{{ n.name }}</td>
              <td class="py-2 px-3">
                <span class="px-2 py-0.5 rounded text-xs font-mono"
                  :class="typeColor(n.type)">{{ n.type }}</span>
              </td>
              <td class="py-2 px-3 text-gray-400 font-mono text-xs">{{ n.server }}:{{ n.port }}</td>
              <td class="py-2 px-3 font-mono text-indigo-400">{{ n.listener_port || '-' }}</td>
              <td class="py-2 px-3">
                <span :class="n.enabled ? 'text-green-400' : 'text-gray-500'" class="text-xs">
                  {{ n.enabled ? 'Enabled' : 'Disabled' }}
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '../api'

const status = ref({ running: false, pid: null })
const stats = ref({ subscriptions: 0, nodes: 0, enabledNodes: 0 })
const nodes = ref([])
const loading = ref(false)

const typeColor = (t) => ({
  'vmess': 'bg-blue-900 text-blue-300',
  'vless': 'bg-purple-900 text-purple-300',
  'trojan': 'bg-red-900 text-red-300',
  'ss': 'bg-green-900 text-green-300',
  'hysteria2': 'bg-yellow-900 text-yellow-300',
}[t] || 'bg-gray-700 text-gray-300')

async function load() {
  const [s, n, st] = await Promise.all([
    api.getSubs(), api.getNodes(), api.proxyStatus()
  ])
  stats.value.subscriptions = s.data.length
  stats.value.nodes = n.data.length
  stats.value.enabledNodes = n.data.filter(x => x.enabled).length
  nodes.value = n.data
  status.value = st.data
}

async function start() { loading.value = true; await api.proxyStart(); await load(); loading.value = false }
async function stop() { loading.value = true; await api.proxyStop(); await load(); loading.value = false }
async function restart() { loading.value = true; await api.proxyRestart(); await load(); loading.value = false }

onMounted(load)
</script>

<style>
.card { @apply bg-gray-900 rounded-lg border border-gray-800 p-4; }
.btn { @apply px-4 py-1.5 rounded text-sm font-medium text-white transition-colors disabled:opacity-50; }
</style>
```

**Step 2: Commit**

```bash
git add -A && git commit -m "feat: Dashboard view with status, stats, and node port mapping table"
```

---

### Task 7: Frontend — Subscriptions View

**Files:**
- Create: `frontend/src/views/Subscriptions.vue`

**Step 1: Build Subscriptions component**

`frontend/src/views/Subscriptions.vue`:
```vue
<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <h2 class="text-2xl font-bold">Subscriptions</h2>
      <button @click="showAdd = true" class="btn bg-indigo-600 hover:bg-indigo-700">+ Add</button>
    </div>

    <!-- Add/Edit Modal -->
    <div v-if="showAdd" class="card">
      <h3 class="font-semibold mb-3">{{ editing ? 'Edit' : 'Add' }} Subscription</h3>
      <div class="space-y-3">
        <input v-model="form.name" placeholder="Name" class="input w-full" />
        <input v-model="form.url" placeholder="Subscription URL" class="input w-full" />
        <div class="flex gap-2">
          <button @click="save" class="btn bg-indigo-600 hover:bg-indigo-700">Save</button>
          <button @click="cancel" class="btn bg-gray-700 hover:bg-gray-600">Cancel</button>
        </div>
      </div>
    </div>

    <!-- Subscriptions List -->
    <div v-for="sub in subs" :key="sub.id" class="card flex items-center justify-between">
      <div>
        <div class="font-medium">{{ sub.name }}</div>
        <div class="text-xs text-gray-500 mt-1 font-mono truncate max-w-lg">{{ sub.url }}</div>
        <div class="text-xs text-gray-400 mt-1">{{ sub.node_count }} nodes</div>
      </div>
      <div class="flex items-center gap-2">
        <button @click="refresh(sub.id)" :disabled="refreshing === sub.id"
          class="btn bg-green-600 hover:bg-green-700 text-xs">
          {{ refreshing === sub.id ? 'Fetching...' : 'Refresh' }}
        </button>
        <button @click="edit(sub)" class="btn bg-gray-700 hover:bg-gray-600 text-xs">Edit</button>
        <button @click="remove(sub.id)" class="btn bg-red-600 hover:bg-red-700 text-xs">Delete</button>
      </div>
    </div>

    <div v-if="!subs.length" class="text-gray-500 text-center py-12">
      No subscriptions yet. Click "+ Add" to get started.
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '../api'

const subs = ref([])
const showAdd = ref(false)
const editing = ref(null)
const refreshing = ref(null)
const form = ref({ name: '', url: '' })

async function load() {
  subs.value = (await api.getSubs()).data
}

async function save() {
  if (editing.value) {
    await api.updateSub(editing.value, form.value)
  } else {
    await api.createSub(form.value)
  }
  cancel()
  await load()
}

function edit(sub) {
  editing.value = sub.id
  form.value = { name: sub.name, url: sub.url }
  showAdd.value = true
}

function cancel() {
  showAdd.value = false
  editing.value = null
  form.value = { name: '', url: '' }
}

async function refresh(id) {
  refreshing.value = id
  await api.refreshSub(id)
  await load()
  refreshing.value = null
}

async function remove(id) {
  await api.deleteSub(id)
  await load()
}

onMounted(load)
</script>

<style>
.input { @apply bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-gray-100 focus:outline-none focus:border-indigo-500; }
</style>
```

**Step 2: Commit**

```bash
git add -A && git commit -m "feat: Subscriptions management view with CRUD and refresh"
```

---

### Task 8: Frontend — Nodes View

**Files:**
- Create: `frontend/src/views/Nodes.vue`

**Step 1: Build Nodes component**

`frontend/src/views/Nodes.vue`:
```vue
<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <h2 class="text-2xl font-bold">Nodes ({{ filtered.length }})</h2>
      <div class="flex gap-3">
        <input v-model="search" placeholder="Search nodes..." class="input w-64" />
        <select v-model="typeFilter" class="input">
          <option value="">All Types</option>
          <option v-for="t in types" :key="t" :value="t">{{ t }}</option>
        </select>
      </div>
    </div>

    <div class="overflow-auto">
      <table class="w-full text-sm">
        <thead class="text-gray-400 border-b border-gray-700">
          <tr>
            <th class="text-left py-2 px-3">Enabled</th>
            <th class="text-left py-2 px-3">Name</th>
            <th class="text-left py-2 px-3">Type</th>
            <th class="text-left py-2 px-3">Server</th>
            <th class="text-left py-2 px-3">Local Port</th>
            <th class="text-left py-2 px-3">Proxy Address</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="n in filtered" :key="n.id" class="border-b border-gray-800 hover:bg-gray-800/50">
            <td class="py-2 px-3">
              <input type="checkbox" :checked="n.enabled" @change="toggle(n)" class="accent-indigo-500" />
            </td>
            <td class="py-2 px-3">{{ n.name }}</td>
            <td class="py-2 px-3">
              <span class="px-2 py-0.5 rounded text-xs font-mono"
                :class="typeColor(n.type)">{{ n.type }}</span>
            </td>
            <td class="py-2 px-3 text-gray-400 font-mono text-xs">{{ n.server }}:{{ n.port }}</td>
            <td class="py-2 px-3 font-mono text-indigo-400">{{ n.listener_port || '-' }}</td>
            <td class="py-2 px-3 font-mono text-xs text-gray-400">
              <span v-if="n.listener_port" class="select-all">127.0.0.1:{{ n.listener_port }}</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import api from '../api'

const nodes = ref([])
const search = ref('')
const typeFilter = ref('')

const types = computed(() => [...new Set(nodes.value.map(n => n.type))])

const filtered = computed(() => {
  return nodes.value.filter(n => {
    if (typeFilter.value && n.type !== typeFilter.value) return false
    if (search.value && !n.name.toLowerCase().includes(search.value.toLowerCase())) return false
    return true
  })
})

const typeColor = (t) => ({
  'vmess': 'bg-blue-900 text-blue-300',
  'vless': 'bg-purple-900 text-purple-300',
  'trojan': 'bg-red-900 text-red-300',
  'ss': 'bg-green-900 text-green-300',
  'hysteria2': 'bg-yellow-900 text-yellow-300',
}[t] || 'bg-gray-700 text-gray-300')

async function toggle(node) {
  await api.toggleNode(node.id, !node.enabled)
  node.enabled = !node.enabled
}

onMounted(async () => {
  nodes.value = (await api.getNodes()).data
})
</script>
```

**Step 2: Commit**

```bash
git add -A && git commit -m "feat: Nodes view with search, type filter, toggle, and port mapping"
```

---

### Task 9: Integration, Polish & Docker Verification

**Files:**
- Modify: `Dockerfile` (final adjustments)
- Modify: `backend/main.py` (startup auto-config)

**Step 1: Add startup event to auto-generate config if nodes exist**

In `backend/main.py`:
```python
@app.on_event("startup")
def startup():
    from backend.database import SessionLocal
    from backend.generator import generate_config
    db = SessionLocal()
    try:
        from backend.models import Node
        if db.query(Node).filter(Node.enabled == True).count() > 0:
            generate_config(db)
    finally:
        db.close()
```

**Step 2: Build and test Docker image**

```bash
cd /Users/elanchou/MProxy
docker compose build
docker compose up -d
# Verify
curl http://localhost:8080/api/health
curl http://localhost:8080/api/proxy/status
# Open browser to http://localhost:8080
docker compose down
```

**Step 3: Final commit**

```bash
git add -A && git commit -m "feat: startup auto-config, Docker integration complete"
```

---

## Summary

| Task | Description | Key Files |
|------|-------------|-----------|
| 1 | Project scaffolding | Dockerfile, docker-compose.yml, backend/main.py |
| 2 | DB models & subscription CRUD | backend/models.py, backend/routers/subscriptions.py |
| 3 | Subscription fetcher & node parser | backend/parser.py, backend/routers/nodes.py |
| 4 | Mihomo config generator & process manager | backend/generator.py, backend/mihomo_manager.py |
| 5 | Frontend setup & layout | frontend/src/App.vue, router, api client |
| 6 | Dashboard view | frontend/src/views/Dashboard.vue |
| 7 | Subscriptions view | frontend/src/views/Subscriptions.vue |
| 8 | Nodes view | frontend/src/views/Nodes.vue |
| 9 | Integration & Docker verification | Final wiring, Docker build & test |
