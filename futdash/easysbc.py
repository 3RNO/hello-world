"""Importing an EasySBC club-stats payload.

Unlike the generic club parser, this targets one known response --
`GET /user-clubs/stats` on `api-fc27.easysbc.io` -- because it carries the
thing that actually decides fodder buying: how many cards you hold at each
rating, and what each rating contributes to an SBC.

That contribution is EasySBC's `itemScore`. Dividing it by the market
price of the rating gives score per coin, which is the number that says
which band to buy. A band can be cheap and still be poor value, and this
is what tells the two apart.

The payload holds no credentials. The auth token lives in the request
headers, which are neither needed nor stored.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from . import config, db


class StatsImportError(ValueError):
    """The payload was not an EasySBC club-stats response."""


def _ms_to_iso(ms: Any) -> str | None:
    try:
        return datetime.fromtimestamp(int(ms) / 1000, timezone.utc).isoformat(timespec="seconds")
    except (TypeError, ValueError, OSError):
        return None


def load(payload: str | bytes | dict) -> dict:
    """Parse the stats response into club totals and a fodder ladder."""
    if isinstance(payload, (str, bytes)):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise StatsImportError(f"not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise StatsImportError("expected a JSON object")

    fodder_raw = payload.get("sbcFodderCalculation")
    if not isinstance(fodder_raw, dict) or not fodder_raw:
        raise StatsImportError(
            "no sbcFodderCalculation in that payload -- this importer wants "
            "the response from /user-clubs/stats")

    ladder = []
    for rating, row in fodder_raw.items():
        if not isinstance(row, dict):
            continue
        try:
            count = int(row.get("count", 0))
            score = int(row.get("itemScore", 0))
            rating = int(rating)
        except (TypeError, ValueError):
            continue
        if count <= 0:
            continue
        ladder.append({
            "rating": rating,
            "count": count,
            "item_score": score,
            # Cards of the same rating can score differently (special
            # versions, evolutions), so this is an average, not a constant.
            "score_per_card": round(score / count, 1),
        })
    if not ladder:
        raise StatsImportError("sbcFodderCalculation held no usable rows")
    ladder.sort(key=lambda r: r["rating"])

    return {
        "club_name": payload.get("clubName"),
        "coins": payload.get("coins"),
        "club_value": payload.get("clubValue"),
        "potential_coins": payload.get("potentialCoins"),
        "transfer_list": payload.get("transferList"),
        "sbc_fodder": payload.get("sbcFodder"),
        "players_count": payload.get("playersCount"),
        "rank": payload.get("rank"),
        "scanned_at": _ms_to_iso(payload.get("lastImportedAt")),
        "fodder": ladder,
    }


def store(conn, parsed: dict) -> dict:
    """Replace the stored club stats with this reading.

    Like the club itself, this is a snapshot: keeping the previous one
    would mean counting fodder that has since been used.
    """
    ts = db.utcnow()
    conn.execute("DELETE FROM club_stats")
    conn.execute("DELETE FROM club_fodder")
    conn.execute(
        "INSERT INTO club_stats (club_name, coins, club_value, potential_coins,"
        " transfer_list, sbc_fodder, players_count, rank, scanned_at, imported_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (parsed["club_name"], parsed["coins"], parsed["club_value"],
         parsed["potential_coins"], parsed["transfer_list"], parsed["sbc_fodder"],
         parsed["players_count"], parsed["rank"], parsed["scanned_at"], ts))
    for row in parsed["fodder"]:
        conn.execute(
            "INSERT INTO club_fodder (rating, count, item_score, imported_at)"
            " VALUES (?, ?, ?, ?)",
            (row["rating"], row["count"], row["item_score"], ts))
    conn.commit()
    return {"ratings": len(parsed["fodder"]),
            "players": parsed["players_count"], "imported_at": ts}


def stats(conn) -> dict | None:
    row = conn.execute("SELECT * FROM club_stats ORDER BY id DESC LIMIT 1").fetchone()
    return dict(row) if row else None


def ladder(conn, platform: str = config.PLATFORM) -> list[dict]:
    """Fodder held per rating, priced against the market where known.

    `score_per_coin` is the buying signal: how much SBC contribution a
    coin buys at that rating. Higher is better value. It is None where no
    price has been recorded for the band, rather than guessed at.
    """
    rows = conn.execute(
        "SELECT f.rating, f.count, f.item_score,"
        " (SELECT price FROM rating_floors WHERE rating = f.rating"
        "  AND platform = ? ORDER BY ts DESC, id DESC LIMIT 1) AS price"
        " FROM club_fodder f ORDER BY f.rating DESC", (platform,)).fetchall()
    out = []
    for r in rows:
        per_card = r["item_score"] / r["count"] if r["count"] else 0
        price = r["price"]
        out.append({
            "rating": r["rating"],
            "count": r["count"],
            "item_score": r["item_score"],
            "score_per_card": round(per_card, 1),
            "price": price,
            "score_per_coin": round(per_card / price, 4) if price else None,
            "held_value": price * r["count"] if price else None,
        })
    return out


def best_buys(conn, platform: str = config.PLATFORM, limit: int = 5) -> list[dict]:
    """Rating bands giving the most SBC score per coin spent."""
    rows = [r for r in ladder(conn, platform) if r["score_per_coin"]]
    rows.sort(key=lambda r: r["score_per_coin"], reverse=True)
    if rows:
        best = rows[0]["score_per_coin"]
        for r in rows:
            # How this band compares with the best available one.
            r["vs_best_pct"] = round(r["score_per_coin"] / best * 100, 1)
    return rows[:limit]
