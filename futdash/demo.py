"""Seeds a database with synthetic history.

Useful for seeing the dashboard populated before you have traded anything
real, and it is what the analytics tests run against. Nothing here talks
to the network.
"""

from __future__ import annotations

import json
import os
import random
from datetime import datetime, timedelta, timezone

from . import config, db, tax

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "sample_prices.json")


def seed(conn, days: int = 30, seed_value: int = 7) -> dict:
    """Fill `conn` with `days` of daily prices plus a handful of trades."""
    rng = random.Random(seed_value)
    with open(FIXTURE, encoding="utf-8") as fh:
        players = json.load(fh)

    now = datetime.now(timezone.utc)
    ids = {}
    for row in players:
        pid = db.upsert_player(conn, row["name"], row["rating"], row["version"])
        ids[row["name"]] = pid
        base = float(row["price"])
        # A slow drift plus daily noise, so trends and dips are meaningful.
        drift = rng.uniform(-0.004, 0.004)
        for d in range(days, -1, -1):
            ts = (now - timedelta(days=d)).isoformat(timespec="seconds")
            noise = rng.gauss(0, 0.035)
            price = base * (1 + drift * (days - d)) * (1 + noise)
            conn.execute(
                "INSERT INTO price_snapshots (player_id, platform, price, ts, source)"
                " VALUES (?, ?, ?, ?, 'demo')",
                (pid, config.PLATFORM, tax.round_down(max(price, tax.MIN_PRICE)), ts),
            )

    # Push two cards to a clear discount so the dip list is never empty.
    for name in ("Bukayo Saka", "Rodri"):
        pid = ids[name]
        last = conn.execute(
            "SELECT price FROM price_snapshots WHERE player_id = ?"
            " ORDER BY ts DESC, id DESC LIMIT 1", (pid,)).fetchone()["price"]
        conn.execute(
            "INSERT INTO price_snapshots (player_id, platform, price, ts, source)"
            " VALUES (?, ?, ?, ?, 'demo')",
            (pid, config.PLATFORM, tax.round_down(last * 0.85),
             now.isoformat(timespec="seconds")),
        )

    _seed_trades(conn, ids, now, rng)
    from . import fodder
    fodder.record(conn, {82: 400, 83: 500, 84: 650, 85: 800, 86: 1600,
                         87: 4200, 88: 11000, 89: 26000}, source="demo")
    conn.commit()
    return {"players": len(players), "days": days}


def _seed_trades(conn, ids, now, rng) -> None:
    closed = [
        ("Joao Neves", 3800, 4600, "snipe", 12),
        ("Nico Williams", 8800, 10500, "snipe", 10),
        ("Micky van de Ven", 12000, 14500, "bid", 8),
        ("Alexis Mac Allister", 19500, 23000, "invest", 6),
        ("Nico Williams", 9100, 9600, "snipe", 5),
        ("Joao Neves", 4100, 4000, "bid", 4),
    ]
    for name, buy, sell, method, days_ago in closed:
        buy_ts = now - timedelta(days=days_ago)
        conn.execute(
            "INSERT INTO trades (player_id, platform, quantity, buy_price, buy_ts,"
            " sell_price, sell_ts, method) VALUES (?, ?, 1, ?, ?, ?, ?, ?)",
            (ids[name], config.PLATFORM, buy, buy_ts.isoformat(timespec="seconds"), sell,
             (buy_ts + timedelta(hours=rng.randint(2, 40))).isoformat(timespec="seconds"),
             method),
        )
    # Two still-held positions, which is what the holdings view reads.
    for name, buy, method, days_ago in [("Rodri", 195000, "invest", 9),
                                        ("Bukayo Saka", 54000, "invest", 3)]:
        conn.execute(
            "INSERT INTO trades (player_id, platform, quantity, buy_price, buy_ts, method)"
            " VALUES (?, ?, 1, ?, ?, ?)",
            (ids[name], config.PLATFORM, buy, (now - timedelta(days=days_ago)).isoformat(timespec="seconds"),
             method),
        )
    for name, start, end in [("Team of the Week", 0, 7), ("Rulebreakers", 10, 24)]:
        conn.execute(
            "INSERT INTO promos (name, starts_at, ends_at) VALUES (?, ?, ?)",
            (name, (now + timedelta(days=start)).isoformat(timespec="seconds"),
             (now + timedelta(days=end)).isoformat(timespec="seconds")),
        )
