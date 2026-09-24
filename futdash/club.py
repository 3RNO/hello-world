"""Importing a scanned club, and working out what it means.

There is no documented export from the club scanners, so what actually
arrives here is a JSON capture from the browser's network tab. Its shape
is not guaranteed and will change without warning, so the parser does not
assume a schema: it hunts for the list of players and accepts any of the
field spellings these tools are known to use.

Anything it cannot read, it says so about. A club import that silently
produced nine players out of six hundred would be worse than one that
fails.
"""

from __future__ import annotations

import json
from typing import Any

from . import config, db, tax

# Field spellings seen across club scanners and EA's own payloads.
_NAME_KEYS = ("name", "playerName", "commonName", "displayName", "fullName",
              "lastName", "knownAs")
_RATING_KEYS = ("rating", "overall", "ovr", "score")
_UNTRADEABLE_KEYS = ("untradeable", "untradable", "isUntradeable", "isUntradable")
_TRADEABLE_KEYS = ("tradeable", "tradable", "isTradeable", "isTradable")
_VERSION_KEYS = ("version", "cardType", "rarity", "cardVersion", "quality")
_QUANTITY_KEYS = ("quantity", "count", "duplicates", "amount")
_PRICE_KEYS = ("price", "value", "currentPrice", "marketPrice", "lowestBin")


class ClubImportError(ValueError):
    """The payload could not be read as a club."""


def _first(row: dict, keys, default=None):
    for k in keys:
        if k in row and row[k] not in (None, ""):
            return row[k]
    return default


def _looks_like_player(row: Any) -> bool:
    """A player has a name and a rating. Almost nothing else does."""
    if not isinstance(row, dict):
        return False
    has_rating = _first(row, _RATING_KEYS) is not None
    has_name = _first(row, _NAME_KEYS) is not None
    return has_rating and has_name


def find_players(payload: Any, _depth: int = 0) -> list[dict]:
    """Walk an arbitrary JSON structure and return the biggest player list.

    Captures are usually wrapped -- {"data": {"club": {"players": [...]}}}
    and similar -- and the wrapper differs per tool, so rather than guess
    the path we find every list that looks like players and take the
    longest.
    """
    if _depth > 8:
        return []
    best: list[dict] = []
    if isinstance(payload, list):
        players = [r for r in payload if _looks_like_player(r)]
        if len(players) > len(best):
            best = players
        for item in payload:
            if isinstance(item, (dict, list)):
                found = find_players(item, _depth + 1)
                if len(found) > len(best):
                    best = found
    elif isinstance(payload, dict):
        for value in payload.values():
            if isinstance(value, (dict, list)):
                found = find_players(value, _depth + 1)
                if len(found) > len(best):
                    best = found
    return best


def _untradeable(row: dict) -> int:
    """Untradeable can be stated either way round; honour whichever is set."""
    flag = _first(row, _UNTRADEABLE_KEYS)
    if flag is not None:
        return 1 if flag in (True, 1, "true", "True", "1") else 0
    flag = _first(row, _TRADEABLE_KEYS)
    if flag is not None:
        return 0 if flag in (True, 1, "true", "True", "1") else 1
    return 0


def normalise(rows: list[dict]) -> list[dict]:
    """Map raw capture rows onto the fields the dashboard stores."""
    out = []
    for row in rows:
        name = _first(row, _NAME_KEYS)
        rating = _first(row, _RATING_KEYS)
        if name is None or rating is None:
            continue
        try:
            rating = int(rating)
        except (TypeError, ValueError):
            continue
        price = _first(row, _PRICE_KEYS)
        try:
            price = int(price) if price not in (None, "") else None
        except (TypeError, ValueError):
            price = None
        out.append({
            "name": str(name).strip(),
            "rating": rating,
            "version": str(_first(row, _VERSION_KEYS, "standard")).strip().lower(),
            "untradeable": _untradeable(row),
            "quantity": int(_first(row, _QUANTITY_KEYS, 1) or 1),
            "price": price,
        })
    return out


def load(payload: str | bytes | dict | list) -> list[dict]:
    """Parse a capture into club rows, or explain why it could not."""
    if isinstance(payload, (str, bytes)):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ClubImportError(f"not valid JSON: {exc}") from exc
    rows = find_players(payload)
    if not rows:
        raise ClubImportError(
            "found no players in that payload -- it needs objects carrying "
            "both a name and a rating. Check you saved the response that "
            "returns your player list rather than the page itself.")
    players = normalise(rows)
    if not players:
        raise ClubImportError(f"found {len(rows)} candidate rows but could not "
                              "read a name and rating from any of them")
    return players


def store(conn, players: list[dict], platform: str = config.PLATFORM) -> dict:
    """Replace the stored club with this import.

    A club is a snapshot, not a ledger -- keeping older imports around
    would mean counting cards you have since sold.
    """
    ts = db.utcnow()
    conn.execute("DELETE FROM club")
    priced = 0
    for p in players:
        pid = db.resolve_player(conn, p["name"], p["rating"],
                                p["version"] if p["version"] != "standard" else None)
        conn.execute(
            "INSERT INTO club (player_id, name, rating, version, untradeable,"
            " quantity, imported_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (pid, p["name"], p["rating"], p["version"], p["untradeable"],
             p["quantity"], ts))
        # A capture that carries prices saves a lot of manual entry.
        if p.get("price"):
            conn.execute(
                "INSERT INTO price_snapshots (player_id, platform, price, ts, source)"
                " VALUES (?, ?, ?, ?, 'club-import')",
                (pid, platform, p["price"], ts))
            priced += 1
    conn.commit()
    return {"imported": len(players), "with_prices": priced, "imported_at": ts}


def inventory(conn) -> list[dict]:
    """What you hold per rating, split by whether you could sell it."""
    rows = conn.execute(
        "SELECT rating,"
        " SUM(CASE WHEN untradeable = 0 THEN quantity ELSE 0 END) AS tradeable,"
        " SUM(CASE WHEN untradeable = 1 THEN quantity ELSE 0 END) AS untradeable,"
        " SUM(quantity) AS total"
        " FROM club GROUP BY rating ORDER BY rating DESC").fetchall()
    return [dict(r) for r in rows]


def value(conn, platform: str = config.PLATFORM) -> dict:
    """Tradeable club value at the latest known prices, after tax.

    Untradeable cards are excluded: they are worth nothing you can spend.
    """
    rows = conn.execute(
        "SELECT c.quantity, c.untradeable,"
        " (SELECT price FROM price_snapshots WHERE player_id = c.player_id"
        "  AND platform = ? ORDER BY ts DESC, id DESC LIMIT 1) AS price"
        " FROM club c", (platform,)).fetchall()
    gross = sum(r["price"] * r["quantity"] for r in rows
                if r["price"] and not r["untradeable"])
    unpriced = sum(1 for r in rows if not r["price"] and not r["untradeable"])
    return {
        "gross": gross,
        "after_tax": round(tax.net_proceeds(gross)),
        "cards": sum(r["quantity"] for r in rows),
        "tradeable_cards": sum(r["quantity"] for r in rows if not r["untradeable"]),
        "unpriced_cards": unpriced,
    }


def fodder_gaps(conn, need: dict[int, int] | None = None,
                platform: str = config.PLATFORM) -> list[dict]:
    """What to buy: cheap rating bands you are short of.

    Without a `need` the shortfall is unknown, so this reports holdings
    against the market instead of inventing a target.
    """
    from . import fodder
    held = {r["rating"]: r["tradeable"] for r in inventory(conn)}
    out = []
    for band in fodder.table(conn, platform):
        rating = band["rating"]
        have = held.get(rating, 0)
        row = {
            "rating": rating,
            "price": band["price"],
            "step_ratio": band["step_ratio"],
            "have": have,
        }
        if need:
            row["need"] = need.get(rating, 0)
            row["short_by"] = max(0, need.get(rating, 0) - have)
            row["cost_to_fill"] = row["short_by"] * band["price"]
        out.append(row)
    return out
