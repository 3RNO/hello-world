"""Cheapest-player-by-rating tracking -- the SBC fodder side.

Fodder is priced by rating band, not by player, so this tracks one price
per rating rather than per card. The question it answers is the one that
decides every SBC: *which rating band is currently cheap relative to the
band below it?*

There is no attempt here to reproduce EA's internal SBC scoring. The
comparison is the defensible one -- what each step up in rating actually
costs -- which is what makes a band look under- or over-priced.
"""

from __future__ import annotations

import statistics
from datetime import datetime, timedelta, timezone

from . import config, db


def record(conn, prices: dict[int, int], platform: str = config.PLATFORM,
           source: str = "manual") -> int:
    """Store a {rating: cheapest_price} reading."""
    ts = db.utcnow()
    for rating, price in prices.items():
        conn.execute(
            "INSERT INTO rating_floors (rating, platform, price, ts, source)"
            " VALUES (?, ?, ?, ?, ?)",
            (int(rating), platform, int(price), ts, source),
        )
    conn.commit()
    return len(prices)


def latest(conn, platform: str = config.PLATFORM) -> dict[int, dict]:
    """Newest price per rating band."""
    rows = conn.execute(
        "SELECT rating, price, ts, source FROM rating_floors f WHERE platform = ?"
        " AND id = (SELECT id FROM rating_floors WHERE rating = f.rating"
        "           AND platform = f.platform ORDER BY ts DESC, id DESC LIMIT 1)"
        " ORDER BY rating",
        (platform,),
    ).fetchall()
    return {r["rating"]: dict(r) for r in rows}


def table(conn, platform: str = config.PLATFORM) -> list[dict]:
    """Rating ladder with the cost of each step up.

    `step_cost` is the extra coins a rating costs over the band below it,
    and `step_ratio` the same as a multiple. A low ratio means that band is
    cheap for what it contributes -- the 85s-at-800-vs-84s-at-650 case from
    the research is a ratio of 1.23, which is why it was worth buying.
    """
    current = latest(conn, platform)
    out = []
    for rating in sorted(current):
        price = current[rating]["price"]
        below = current.get(rating - 1)
        step_cost = price - below["price"] if below else None
        step_ratio = round(price / below["price"], 3) if below and below["price"] else None
        out.append({
            "rating": rating,
            "price": price,
            "step_cost": step_cost,
            "step_ratio": step_ratio,
            "updated": current[rating]["ts"],
            "source": current[rating]["source"],
        })
    return out


def best_value(conn, platform: str = config.PLATFORM, limit: int = 5) -> list[dict]:
    """Bands that cost least to step up into -- where fodder value sits.

    Only bands with a band below them to compare against are considered.
    """
    rows = [r for r in table(conn, platform) if r["step_ratio"]]
    if not rows:
        return []
    ratios = [r["step_ratio"] for r in rows]
    median = statistics.median(ratios)
    for r in rows:
        # How far below the typical step this band's step is. Positive
        # means it is cheaper than the ladder's usual step.
        r["value_score"] = round((median - r["step_ratio"]) / median * 100, 1)
    rows.sort(key=lambda r: r["step_ratio"])
    return rows[:limit]


def movement(conn, platform: str = config.PLATFORM, days: int = 7) -> list[dict]:
    """How each band has moved since its earliest reading in the window.

    This is what says whether an edge is still open. A band that was cheap
    yesterday and is 40% dearer today has been noticed, and the window on
    it is closing.
    """
    ratings = [r["rating"] for r in conn.execute(
        "SELECT DISTINCT rating FROM rating_floors WHERE platform = ? ORDER BY rating DESC",
        (platform,)).fetchall()]
    out = []
    for rating in ratings:
        d = drift(conn, rating, platform, days)
        if d is None:
            # Only one reading so far -- report it rather than hiding the band.
            cur = latest(conn, platform).get(rating)
            if cur:
                out.append({"rating": rating, "latest": cur["price"], "first": None,
                            "change_pct": None, "samples": 1})
            continue
        out.append(d)
    return out


def drift(conn, rating: int, platform: str = config.PLATFORM, days: int = 7) -> dict | None:
    """How one band has moved over `days` -- fodder trends before an SBC."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="seconds")
    rows = conn.execute(
        "SELECT price, ts FROM rating_floors WHERE rating = ? AND platform = ?"
        " AND ts >= ? ORDER BY ts ASC, id ASC",
        (rating, platform, cutoff),
    ).fetchall()
    if len(rows) < 2:
        return None
    first, last = rows[0]["price"], rows[-1]["price"]
    return {
        "rating": rating,
        "first": first,
        "latest": last,
        "low": min(r["price"] for r in rows),
        "high": max(r["price"] for r in rows),
        "change_pct": round((last - first) / first * 100, 2) if first else 0.0,
        "samples": len(rows),
    }
