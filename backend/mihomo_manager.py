import subprocess
import signal
import logging
from collections import deque
from backend.config import MIHOMO_BINARY, MIHOMO_DIR, MIHOMO_CONFIG_PATH

logger = logging.getLogger(__name__)


class MihomoManager:
    def __init__(self):
        self._process: subprocess.Popen | None = None
        self._logs: deque[str] = deque(maxlen=200)

    @property
    def running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def _collect_exit_logs(self):
        if self._process and self._process.stdout:
            try:
                out = self._process.stdout.read()
                if out:
                    for line in out.decode(errors="replace").splitlines():
                        self._logs.append(line)
            except Exception:
                pass

    def start(self) -> bool:
        if self.running:
            return True
        if not MIHOMO_CONFIG_PATH.exists():
            logger.warning("Config not found: %s", MIHOMO_CONFIG_PATH)
            return False
        self._process = subprocess.Popen(
            [str(MIHOMO_BINARY), "-d", str(MIHOMO_DIR)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        import time
        time.sleep(0.5)
        if not self.running:
            self._collect_exit_logs()
            logger.error("Mihomo exited with code %s", self._process.returncode)
        return self.running

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
        if not self.running and self._process:
            self._collect_exit_logs()
        return {
            "running": self.running,
            "pid": self._process.pid if self.running else None,
            "exit_code": self._process.returncode if self._process and not self.running else None,
        }

    def logs(self) -> list[str]:
        if self._process and self._process.stdout and self.running:
            pass
        return list(self._logs)


mihomo = MihomoManager()
