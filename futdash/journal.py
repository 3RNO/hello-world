"""The trade log, and what it tells you.

An open trade -- one with no sell recorded -- is a holding. That means the
journal and the investment tracker are the same table read two ways, and a
card can never be in one without the other.

Every coin figure out of this module is post-tax. Gross numbers on the
Transfer Market are a lie you tell yourself.
"""

from __future__ import annotations

from collections import defaultdict

from . import config, db, tax


def buy(conn, player_id: int, price: int, quantity: int = 1,
        method: str = "snipe", platform: str = config.PLATFORM,
        notes: str | None = None, ts: str | None = None) -> int:
    """Record a purchase. Open until `sell` is called against it."""
    cur = conn.execute(
        "INSERT INTO trades (player_id, platform, quantity, buy_price, buy_ts, method, notes)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (player_id, platform, quantity, price, ts or db.utcnow(), method, notes),
    )
    conn.commit()
    return int(cur.lastrowid)


def sell(conn, trade_id: int, price: int, ts: str | None = None) -> dict:
    """Close a trade and return what it actually made."""
    row = conn.execute("SELECT * FROM trades WHERE id = ?", (trade_id,)).fetchone()
    if row is None:
        raise KeyError(f"no trade {trade_id}")
    if row["sell_ts"]:
        raise ValueError(f"trade {trade_id} is already closed")
    conn.execute(
        "UPDATE trades SET sell_price = ?, sell_ts = ? WHERE id = ?",
        (price, ts or db.utcnow(), trade_id),
    )
    conn.commit()
    return {
        "trade_id": trade_id,
        "profit": round(tax.profit(row["buy_price"], price, row["quantity"])),
        "roi": round(tax.roi(row["buy_price"], price), 4),
    }


def _row_to_trade(row) -> dict:
    d = dict(row)
    if row["sell_price"] is not None:
        d["profit"] = round(tax.profit(row["buy_price"], row["sell_price"], row["quantity"]))
        d["roi"] = round(tax.roi(row["buy_price"], row["sell_price"]), 4)
        d["open"] = False
    else:
        d["profit"] = None
        d["roi"] = None
        d["open"] = True
    d["break_even"] = tax.break_even(row["buy_price"])
    return d


def trades(conn, limit: int = 100, open_only: bool = False) -> list[dict]:
    """Trade log, newest first, with the player's name joined in."""
    sql = ("SELECT t.*, p.name, p.rating, p.version FROM trades t"
           " JOIN players p ON p.id = t.player_id")
    if open_only:
        sql += " WHERE t.sell_ts IS NULL"
    sql += " ORDER BY t.buy_ts DESC LIMIT ?"
    return [_row_to_trade(r) for r in conn.execute(sql, (limit,)).fetchall()]


def holdings(conn, platform: str = config.PLATFORM) -> list[dict]:
    """Open positions, marked against the latest known market price.

    `unrealised` is what you would clear selling right now, after tax. It
    is None when we have no price for the card -- better to show nothing
    than to invent a mark.
    """
    rows = conn.execute(
        "SELECT t.*, p.name, p.rating, p.version FROM trades t"
        " JOIN players p ON p.id = t.player_id"
        " WHERE t.sell_ts IS NULL AND t.platform = ? ORDER BY t.buy_ts DESC",
        (platform,),
    ).fetchall()
    out = []
    for row in rows:
        mark = conn.execute(
            "SELECT price FROM price_snapshots WHERE player_id = ? AND platform = ?"
            " ORDER BY ts DESC, id DESC LIMIT 1", (row["player_id"], platform)).fetchone()
        d = _row_to_trade(row)
        if mark:
            d["market"] = mark["price"]
            d["unrealised"] = round(tax.profit(row["buy_price"], mark["price"], row["quantity"]))
            d["unrealised_roi"] = round(tax.roi(row["buy_price"], mark["price"]), 4)
        else:
            d["market"] = d["unrealised"] = d["unrealised_roi"] = None
        out.append(d)
    return out


def summary(conn) -> dict:
    """Headline P/L across every closed trade, plus coins currently tied up."""
    closed = conn.execute(
        "SELECT buy_price, sell_price, quantity FROM trades WHERE sell_price IS NOT NULL"
    ).fetchall()
    profit = sum(tax.profit(r["buy_price"], r["sell_price"], r["quantity"]) for r in closed)
    spend = sum(r["buy_price"] * r["quantity"] for r in closed)
    wins = sum(1 for r in closed if tax.profit(r["buy_price"], r["sell_price"], r["quantity"]) > 0)
    open_rows = conn.execute(
        "SELECT buy_price, quantity FROM trades WHERE sell_ts IS NULL").fetchall()
    return {
        "closed_trades": len(closed),
        "open_trades": len(open_rows),
        "profit": round(profit),
        "coins_spent": spend,
        "roi": round(profit / spend, 4) if spend else 0.0,
        "win_rate": round(wins / len(closed), 4) if closed else 0.0,
        "capital_tied_up": sum(r["buy_price"] * r["quantity"] for r in open_rows),
    }


def _group(conn, key: str) -> list[dict]:
    sql = {
        "method": "SELECT t.method AS k, t.buy_price, t.sell_price, t.quantity FROM trades t"
                  " WHERE t.sell_price IS NOT NULL",
        "player": "SELECT p.name AS k, t.buy_price, t.sell_price, t.quantity FROM trades t"
                  " JOIN players p ON p.id = t.player_id WHERE t.sell_price IS NOT NULL",
    }[key]
    buckets = defaultdict(lambda: {"trades": 0, "profit": 0.0, "spend": 0, "wins": 0})
    for r in conn.execute(sql).fetchall():
        b = buckets[r["k"]]
        p = tax.profit(r["buy_price"], r["sell_price"], r["quantity"])
        b["trades"] += 1
        b["profit"] += p
        b["spend"] += r["buy_price"] * r["quantity"]
        b["wins"] += 1 if p > 0 else 0
    out = []
    for name, b in buckets.items():
        out.append({
            key: name,
            "trades": b["trades"],
            "profit": round(b["profit"]),
            "roi": round(b["profit"] / b["spend"], 4) if b["spend"] else 0.0,
            "win_rate": round(b["wins"] / b["trades"], 4) if b["trades"] else 0.0,
        })
    out.sort(key=lambda d: d["profit"], reverse=True)
    return out


def by_method(conn) -> list[dict]:
    """Which methods actually pay -- the number that should steer your time."""
    return _group(conn, "method")


def by_player(conn) -> list[dict]:
    """Which cards actually pay."""
    return _group(conn, "player")
