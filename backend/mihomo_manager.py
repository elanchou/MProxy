import subprocess
import signal
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
