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
