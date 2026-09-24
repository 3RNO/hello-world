"""SQLite storage for the dashboard.

One file on disk, no server to run. `connect()` creates the schema on
first use, so there is no separate migration step.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone

DEFAULT_PATH = os.environ.get(
    "FUTDASH_DB", os.path.join(os.path.expanduser("~"), ".futdash", "futdash.db")
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS players (
    id          INTEGER PRIMARY KEY,
    ext_id      TEXT,
    name        TEXT NOT NULL,
    rating      INTEGER,
    version     TEXT NOT NULL DEFAULT 'standard',
    position    TEXT,
    club        TEXT,
    league      TEXT,
    nation      TEXT,
    UNIQUE (name, rating, version)
);

CREATE TABLE IF NOT EXISTS price_snapshots (
    id          INTEGER PRIMARY KEY,
    player_id   INTEGER NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    platform    TEXT NOT NULL DEFAULT 'console',
    price       INTEGER NOT NULL,
    ts          TEXT NOT NULL,
    source      TEXT NOT NULL DEFAULT 'manual'
);
CREATE INDEX IF NOT EXISTS idx_snapshots_player
    ON price_snapshots (player_id, platform, ts);

CREATE TABLE IF NOT EXISTS trades (
    id          INTEGER PRIMARY KEY,
    player_id   INTEGER NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    platform    TEXT NOT NULL DEFAULT 'console',
    quantity    INTEGER NOT NULL DEFAULT 1,
    buy_price   INTEGER NOT NULL,
    buy_ts      TEXT NOT NULL,
    sell_price  INTEGER,
    sell_ts     TEXT,
    method      TEXT NOT NULL DEFAULT 'snipe',
    notes       TEXT
);
CREATE INDEX IF NOT EXISTS idx_trades_open ON trades (sell_ts);

CREATE TABLE IF NOT EXISTS watchlist (
    id            INTEGER PRIMARY KEY,
    player_id     INTEGER NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    platform      TEXT NOT NULL DEFAULT 'console',
    target_margin REAL NOT NULL DEFAULT 0.2,
    max_buy       INTEGER,
    active        INTEGER NOT NULL DEFAULT 1,
    UNIQUE (player_id, platform)
);

CREATE TABLE IF NOT EXISTS club (
    id          INTEGER PRIMARY KEY,
    player_id   INTEGER REFERENCES players(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    rating      INTEGER,
    version     TEXT NOT NULL DEFAULT 'standard',
    untradeable INTEGER NOT NULL DEFAULT 0,
    quantity    INTEGER NOT NULL DEFAULT 1,
    imported_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_club_rating ON club (rating, untradeable);

CREATE TABLE IF NOT EXISTS rating_floors (
    id       INTEGER PRIMARY KEY,
    rating   INTEGER NOT NULL,
    platform TEXT NOT NULL DEFAULT 'pc',
    price    INTEGER NOT NULL,
    ts       TEXT NOT NULL,
    source   TEXT NOT NULL DEFAULT 'manual'
);
CREATE INDEX IF NOT EXISTS idx_rating_floors
    ON rating_floors (rating, platform, ts);

CREATE TABLE IF NOT EXISTS promos (
    id        INTEGER PRIMARY KEY,
    name      TEXT NOT NULL,
    starts_at TEXT,
    ends_at   TEXT,
    notes     TEXT
);
"""


def utcnow() -> str:
    """ISO-8601 UTC, the only timestamp format stored."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(path: str | None = None) -> sqlite3.Connection:
    path = path or DEFAULT_PATH
    if path != ":memory:":
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


def resolve_player(conn: sqlite3.Connection, name: str, rating: int | None = None,
                   version: str | None = None) -> int:
    """Find the player a form means, creating one only if nothing matches.

    The UI's buy and watch forms send a bare name, so an exact-name match
    against an already-tracked card has to win. Without this a watch on
    "Rodri" would create a second, price-less Rodri and silently go dead.
    """
    if rating is None and version is None:
        row = conn.execute(
            "SELECT p.id FROM players p"
            " LEFT JOIN price_snapshots s ON s.player_id = p.id"
            " WHERE LOWER(p.name) = LOWER(?)"
            " GROUP BY p.id ORDER BY COUNT(s.id) DESC LIMIT 1",
            (name,),
        ).fetchone()
        if row:
            return row["id"]
    return upsert_player(conn, name, rating, version or "standard")


def upsert_player(conn: sqlite3.Connection, name: str, rating: int | None = None,
                  version: str = "standard", **extra) -> int:
    """Return the id for this player, inserting it if it is new."""
    cur = conn.execute(
        "SELECT id FROM players WHERE name = ? AND rating IS ? AND version = ?",
        (name, rating, version),
    )
    row = cur.fetchone()
    if row:
        if extra:
            sets = ", ".join(f"{k} = ?" for k in extra)
            conn.execute(f"UPDATE players SET {sets} WHERE id = ?",
                         (*extra.values(), row["id"]))
            conn.commit()
        return row["id"]
    cols = ["name", "rating", "version", *extra.keys()]
    vals = [name, rating, version, *extra.values()]
    cur = conn.execute(
        f"INSERT INTO players ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
        vals,
    )
    conn.commit()
    return int(cur.lastrowid)
