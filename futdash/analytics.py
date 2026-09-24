"""Turning snapshot history into the two questions worth asking:

    "where has this card been trading?"  -> `stats`
    "is it cheap right now?"             -> `dips`
"""

from __future__ import annotations

import statistics
from datetime import datetime, timedelta, timezone

from . import config, tax


def _cutoff(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="seconds")


def history(conn, player_id: int, platform: str = config.PLATFORM, days: int = 30):
    """Snapshots for a card, oldest first."""
    rows = conn.execute(
        "SELECT price, ts, source FROM price_snapshots"
        " WHERE player_id = ? AND platform = ? AND ts >= ?"
        # id breaks ties: several prices can land in the same second, and
        # without this "latest" becomes whichever row SQLite happens to emit.
        " ORDER BY ts ASC, id ASC",
        (player_id, platform, _cutoff(days)),
    ).fetchall()
    return [dict(r) for r in rows]


def stats(conn, player_id: int, platform: str = config.PLATFORM, days: int = 30) -> dict | None:
    """Window summary for one card, or None if we have no prices for it."""
    points = history(conn, player_id, platform, days)
    if not points:
        return None
    prices = [p["price"] for p in points]
    latest = prices[-1]
    first = prices[0]
    median = statistics.median(prices)
    return {
        "player_id": player_id,
        "platform": platform,
        "window_days": days,
        "samples": len(prices),
        "latest": latest,
        "first": first,
        "low": min(prices),
        "high": max(prices),
        "median": round(median, 2),
        "mean": round(statistics.fmean(prices), 2),
        # Movement across the window, and how the current price sits
        # against the middle of it -- negative means below the middle.
        "change_pct": round((latest - first) / first * 100, 2) if first else 0.0,
        "vs_median_pct": round((latest - median) / median * 100, 2) if median else 0.0,
        "updated": points[-1]["ts"],
    }


def is_new_low(points: list[dict]) -> bool:
    """True when the newest price is under everything before it."""
    if len(points) < 2:
        return False
    prices = [p["price"] for p in points]
    return prices[-1] < min(prices[:-1])


def dips(conn, platform: str = config.PLATFORM, days: int = 7,
         min_discount: float = 5.0, min_samples: int = 3) -> list[dict]:
    """Cards trading below their recent middle -- the shortlist to look at.

    `min_discount` is how far under the window median a card has to sit, in
    percent, before it is worth surfacing. Cards with fewer than
    `min_samples` snapshots are skipped: a "discount" off two data points
    is noise, not a signal.
    """
    players = conn.execute(
        "SELECT DISTINCT p.id, p.name, p.rating, p.version FROM players p"
        " JOIN price_snapshots s ON s.player_id = p.id WHERE s.platform = ?",
        (platform,),
    ).fetchall()

    out = []
    for p in players:
        points = history(conn, p["id"], platform, days)
        if len(points) < min_samples:
            continue
        st = stats(conn, p["id"], platform, days)
        if st is None or st["vs_median_pct"] > -min_discount:
            continue
        out.append({
            "player_id": p["id"],
            "name": p["name"],
            "rating": p["rating"],
            "version": p["version"],
            "price": st["latest"],
            "median": st["median"],
            "low": st["low"],
            "discount_pct": abs(st["vs_median_pct"]),
            "new_low": is_new_low(points),
            "samples": st["samples"],
            # What you'd clear reselling at the window median, after tax.
            "profit_at_median": round(tax.profit(st["latest"], st["median"])),
        })
    out.sort(key=lambda d: d["discount_pct"], reverse=True)
    return out


def movers(conn, platform: str = config.PLATFORM, days: int = 7, limit: int = 10) -> dict:
    """Biggest risers and fallers across the window."""
    players = conn.execute(
        "SELECT DISTINCT p.id, p.name, p.rating, p.version FROM players p"
        " JOIN price_snapshots s ON s.player_id = p.id WHERE s.platform = ?",
        (platform,),
    ).fetchall()
    rows = []
    for p in players:
        st = stats(conn, p["id"], platform, days)
        if st is None or st["samples"] < 2:
            continue
        rows.append({
            "player_id": p["id"], "name": p["name"], "rating": p["rating"],
            "version": p["version"], "price": st["latest"],
            "change_pct": st["change_pct"],
        })
    rows.sort(key=lambda d: d["change_pct"], reverse=True)
    return {"up": rows[:limit], "down": list(reversed(rows[-limit:]))}
