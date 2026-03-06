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
