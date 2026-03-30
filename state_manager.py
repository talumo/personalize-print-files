import json, logging, os, tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

class StateManager:
    def __init__(self, state_file_path):
        self._path = Path(state_file_path)
        self._processed: set = set()
        self._load()

    def _load(self):
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            self._processed = set(data)
        except (json.JSONDecodeError, ValueError):
            logger.warning("State file unreadable (%s), starting fresh", self._path)

    def is_processed(self, order_id: str) -> bool:
        return str(order_id) in self._processed

    def mark_processed(self, order_id: str):
        self._processed.add(str(order_id))
        self._write()

    def _write(self):
        data = json.dumps(sorted(self._processed), indent=2)
        # Atomic write on POSIX; direct write on Windows
        try:
            fd, tmp = tempfile.mkstemp(dir=self._path.parent, suffix=".tmp")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(data)
            os.replace(tmp, self._path)
        except Exception:
            self._path.write_text(data, encoding="utf-8")
