import queue
import datetime


class ActivityLogger:
    def __init__(self):
        self._q = queue.Queue()

    def log(self, message):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self._q.put(f"[{ts}] {message}")

    def drain(self, max_items=200):
        items = []
        for _ in range(max_items):
            try:
                items.append(self._q.get_nowait())
            except queue.Empty:
                break
        return items
