"""Turning a target margin into numbers you can type into a search filter.

The output is deliberately a filter, not an action: a max Buy-Now, a max
bid, and the price to relist at. You place them.

Two details that decide whether a filter is any good:

* the max buy has to sit on the market's price ladder, or it is not a
  price you can enter -- `tax.round_down` handles that;
* a margin computed off two snapshots is fiction. `confidence` says how
  much history the number rests on, and thin cards get flagged.
"""

from __future__ import annotations

from . import analytics, config, db, tax

# Sale price to work back from. The median of the window is the honest
# choice: the high is a price you got once, and pricing off it is how
# people end up holding cards they cannot shift.
BASIS = "median"


def confidence(samples: int) -> str:
    if samples >= 20:
        return "high"
    if samples >= 8:
        return "medium"
    if samples >= 3:
        return "low"
    return "insufficient"


def for_player(conn, player_id: int, target_margin: float = config.TARGET_MARGIN,
               platform: str = config.PLATFORM, days: int = 7,
               basis: str = BASIS) -> dict | None:
    """Filter values for one card, or None if we have no prices for it."""
    st = analytics.stats(conn, player_id, platform, days)
    if st is None:
        return None
    player = conn.execute(
        "SELECT name, rating, version FROM players WHERE id = ?", (player_id,)).fetchone()

    sale = st[basis] if basis in st else st["median"]
    max_buy = tax.max_buy(sale, target_margin)
    relist = tax.round_down(sale)

    return {
        "player_id": player_id,
        "name": player["name"] if player else str(player_id),
        "rating": player["rating"] if player else None,
        "version": player["version"] if player else None,
        "platform": platform,
        "target_margin": target_margin,
        # The numbers you type in.
        "max_buy_now": max_buy,
        # A card usually goes for a bit under buy-now at auction, so the
        # bid ceiling sits a step below to leave room for the bid war.
        "max_bid": tax.round_down(max_buy - tax.increment_at(max_buy)),
        "relist_at": relist,
        # The numbers that tell you whether to bother.
        "sale_basis": basis,
        "sale_price": round(sale),
        "market_now": st["latest"],
        "break_even": tax.break_even(max_buy),
        "profit_per_flip": round(tax.profit(max_buy, relist)),
        "already_cheap": st["latest"] <= max_buy,
        "samples": st["samples"],
        "confidence": confidence(st["samples"]),
        "window_days": days,
    }


def watchlist(conn, platform: str = config.PLATFORM, days: int = 7) -> list[dict]:
    """Filters for every active watchlist entry, best profit first."""
    rows = conn.execute(
        "SELECT player_id, target_margin, max_buy FROM watchlist"
        " WHERE active = 1 AND platform = ?", (platform,)).fetchall()
    out = []
    for row in rows:
        calc = for_player(conn, row["player_id"], row["target_margin"], platform, days)
        if calc is None:
            continue
        if row["max_buy"]:
            # A manual ceiling always wins, but only downward -- it is there
            # to cap risk, not to talk you into paying more.
            calc["max_buy_now"] = min(calc["max_buy_now"], row["max_buy"])
            calc["manual_cap"] = row["max_buy"]
        out.append(calc)
    out.sort(key=lambda d: d["profit_per_flip"], reverse=True)
    return out


def add_watch(conn, player_id: int, target_margin: float = config.TARGET_MARGIN,
              platform: str = config.PLATFORM, max_buy: int | None = None) -> int:
    cur = conn.execute(
        "INSERT INTO watchlist (player_id, platform, target_margin, max_buy, active)"
        " VALUES (?, ?, ?, ?, 1)"
        " ON CONFLICT(player_id, platform) DO UPDATE SET"
        " target_margin = excluded.target_margin, max_buy = excluded.max_buy, active = 1",
        (player_id, platform, target_margin, max_buy),
    )
    conn.commit()
    return int(cur.lastrowid)


def remove_watch(conn, player_id: int, platform: str = config.PLATFORM) -> None:
    conn.execute("UPDATE watchlist SET active = 0 WHERE player_id = ? AND platform = ?",
                 (player_id, platform))
    conn.commit()
