"""User profiles stored in SQLite.

The profile personalizes answers (knowledge level, risk tolerance, goals,
holdings) and records which topics a user has explored so the assistant can
gradually raise the sophistication of its explanations.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from finlit.config import get_settings

LEVELS = ("beginner", "intermediate", "advanced")
RISK = ("conservative", "moderate", "aggressive")

# Auto-progression thresholds: (min interactions, min distinct agents used)
PROMOTION = {"beginner": (10, 3), "intermediate": (30, 5)}


@dataclass
class UserProfile:
    user_id: str
    name: str = ""
    age: int | None = None
    risk_tolerance: str = "moderate"
    knowledge_level: str = "beginner"
    goals: str = ""
    holdings: list[dict] = field(default_factory=list)  # [{symbol, quantity, price?, asset_class}]
    watchlist: list[str] = field(default_factory=list)
    topics_seen: dict[str, int] = field(default_factory=dict)  # agent key -> count
    interactions: int = 0
    updated_at: str = ""

    def summary(self) -> str:
        """Compact text injected into agent prompts."""
        parts = [f"knowledge level: {self.knowledge_level}", f"risk tolerance: {self.risk_tolerance}"]
        if self.name:
            parts.insert(0, f"name: {self.name}")
        if self.age:
            parts.append(f"age: {self.age}")
        if self.goals:
            parts.append(f"stated goals: {self.goals}")
        if self.holdings:
            parts.append("holdings: " + ", ".join(
                f"{h.get('symbol')} x{h.get('quantity')}" for h in self.holdings[:15]))
        if self.topics_seen:
            top = sorted(self.topics_seen.items(), key=lambda kv: -kv[1])[:3]
            parts.append("topics explored before: " + ", ".join(k for k, _ in top))
        return "; ".join(parts)


class ProfileStore:
    def __init__(self, db_path: Path | None = None) -> None:
        settings = get_settings()
        if db_path is None:
            settings.ensure_dirs()
            db_path = settings.db_path
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        with self._conn() as c:
            c.execute("CREATE TABLE IF NOT EXISTS profiles (user_id TEXT PRIMARY KEY, data TEXT NOT NULL)")

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path, timeout=10)

    def get(self, user_id: str) -> UserProfile:
        with self._lock, self._conn() as c:
            row = c.execute("SELECT data FROM profiles WHERE user_id = ?", (user_id,)).fetchone()
        if not row:
            return UserProfile(user_id=user_id)
        data = json.loads(row[0])
        known = UserProfile.__dataclass_fields__
        return UserProfile(**{k: v for k, v in data.items() if k in known})

    def save(self, profile: UserProfile) -> UserProfile:
        if profile.knowledge_level not in LEVELS:
            raise ValueError(f"knowledge_level must be one of {LEVELS}")
        if profile.risk_tolerance not in RISK:
            raise ValueError(f"risk_tolerance must be one of {RISK}")
        profile.updated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self._lock, self._conn() as c:
            c.execute("INSERT OR REPLACE INTO profiles (user_id, data) VALUES (?, ?)",
                      (profile.user_id, json.dumps(asdict(profile))))
        return profile

    def record_interaction(self, user_id: str, agent: str) -> UserProfile:
        """Count the interaction and auto-promote the knowledge level when earned."""
        p = self.get(user_id)
        p.interactions += 1
        p.topics_seen[agent] = p.topics_seen.get(agent, 0) + 1
        rule = PROMOTION.get(p.knowledge_level)
        if rule and p.interactions >= rule[0] and len(p.topics_seen) >= rule[1]:
            p.knowledge_level = LEVELS[LEVELS.index(p.knowledge_level) + 1]
        return self.save(p)

    def list_users(self) -> list[str]:
        with self._lock, self._conn() as c:
            return [r[0] for r in c.execute("SELECT user_id FROM profiles ORDER BY user_id")]


_store: ProfileStore | None = None


def get_store() -> ProfileStore:
    global _store
    if _store is None:
        _store = ProfileStore()
    return _store


def reset_store() -> None:
    global _store
    _store = None
