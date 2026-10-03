import hashlib
import sqlite3
from pathlib import Path


def content_hash(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()


class LLMCache:
    def __init__(self, path: Path | str = ":memory:") -> None:
        self.conn = sqlite3.connect(str(path), check_same_thread=False)
        self.conn.execute("CREATE TABLE IF NOT EXISTS llm_cache (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> str | None:
        row = self.conn.execute("SELECT value FROM llm_cache WHERE key = ?", (key,)).fetchone()
        if row is None:
            self.misses += 1
            return None
        self.hits += 1
        return row[0]

    def put(self, key: str, value: str) -> None:
        self.conn.execute("INSERT OR REPLACE INTO llm_cache (key, value) VALUES (?, ?)", (key, value))
        self.conn.commit()

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total else 0.0
