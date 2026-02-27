import threading
import time
from collections import deque


class AppLogger:
    """
    Simple thread-safe logger for UI debug window.
    - log(msg): add a timestamped line
    - drain(n): pop up to n lines
    """
    def __init__(self, max_lines=5000):
        self._lock = threading.Lock()
        self._q = deque(maxlen=max_lines)

    def log(self, msg: str):
        ts = time.strftime("%H:%M:%S")
        line = f"[{ts}] {msg}"
        with self._lock:
            self._q.append(line)

    def drain(self, max_items=200):
        out = []
        with self._lock:
            for _ in range(min(max_items, len(self._q))):
                out.append(self._q.popleft())
        return out
