"""Local HTTP server for the dashboard.

Standard library only, so there is nothing to install. It binds to
localhost by default and has no auth -- it is a personal tool holding your
own trade history, and it should not be exposed to a network.
"""

from __future__ import annotations

import json
import mimetypes
import os
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from . import analytics, club, config, db, fodder, journal, snipe, sources

STATIC = os.path.join(os.path.dirname(__file__), "static")
_lock = threading.Lock()


class Api:
    """Request handlers, kept apart from the HTTP plumbing."""

    def __init__(self, conn):
        self.conn = conn

    # -- reads ----------------------------------------------------------
    def summary(self, q):
        plat = q.get("platform", config.PLATFORM)
        return {
            "journal": journal.summary(self.conn),
            "platform": plat,
            "game_year": config.GAME_YEAR,
            "watching": self.conn.execute(
                "SELECT COUNT(*) c FROM watchlist WHERE active = 1").fetchone()["c"],
            "tracked_players": self.conn.execute(
                "SELECT COUNT(*) c FROM players").fetchone()["c"],
        }

    def dips(self, q):
        return analytics.dips(
            self.conn, q.get("platform", config.PLATFORM),
            int(q.get("days", 7)), float(q.get("min_discount", 5)))

    def movers(self, q):
        return analytics.movers(
            self.conn, q.get("platform", config.PLATFORM), int(q.get("days", 7)))

    def players(self, q):
        rows = self.conn.execute(
            "SELECT p.id, p.name, p.rating, p.version,"
            " (SELECT price FROM price_snapshots WHERE player_id = p.id"
            "  ORDER BY ts DESC LIMIT 1) AS price"
            " FROM players p ORDER BY p.name").fetchall()
        return [dict(r) for r in rows]

    def history(self, q, player_id):
        return analytics.history(
            self.conn, int(player_id), q.get("platform", config.PLATFORM),
            int(q.get("days", 30)))

    def trades(self, q):
        return journal.trades(self.conn, int(q.get("limit", 100)))

    def holdings(self, q):
        return journal.holdings(self.conn, q.get("platform", config.PLATFORM))

    def performance(self, q):
        return {"by_method": journal.by_method(self.conn),
                "by_player": journal.by_player(self.conn)}

    def snipe(self, q):
        if "player_id" in q:
            return snipe.for_player(
                self.conn, int(q["player_id"]),
                float(q.get("margin", config.TARGET_MARGIN)),
                q.get("platform", config.PLATFORM), int(q.get("days", 7)))
        return snipe.watchlist(
            self.conn, q.get("platform", config.PLATFORM), int(q.get("days", 7)))

    def fodder(self, q):
        plat = q.get("platform", config.PLATFORM)
        return {"table": fodder.table(self.conn, plat),
                "best_value": fodder.best_value(self.conn, plat)}

    def club(self, q):
        plat = q.get("platform", config.PLATFORM)
        last = self.conn.execute("SELECT MAX(imported_at) t FROM club").fetchone()["t"]
        return {"inventory": club.inventory(self.conn),
                "value": club.value(self.conn, plat),
                "gaps": club.fodder_gaps(self.conn, platform=plat),
                "imported_at": last}

    def promos(self, q):
        return [dict(r) for r in self.conn.execute(
            "SELECT * FROM promos ORDER BY starts_at").fetchall()]

    # -- writes ---------------------------------------------------------
    def add_price(self, body):
        """Manual price entry: {name, price, rating?, version?, platform?}"""
        quote = sources.Quote(
            name=body["name"], price=int(body["price"]),
            platform=body.get("platform", config.PLATFORM),
            rating=body.get("rating"), version=body.get("version", "standard"),
            source="manual")
        sources.record(self.conn, [quote])
        return {"ok": True}

    def add_trade(self, body):
        pid = db.resolve_player(self.conn, body["name"], body.get("rating"),
                                body.get("version"))
        tid = journal.buy(self.conn, pid, int(body["buy_price"]),
                          int(body.get("quantity", 1)), body.get("method", "snipe"),
                          body.get("platform", config.PLATFORM), body.get("notes"))
        return {"ok": True, "trade_id": tid}

    def close_trade(self, body):
        return {"ok": True, **journal.sell(
            self.conn, int(body["trade_id"]), int(body["sell_price"]))}

    def add_fodder(self, body):
        """{prices: {rating: price}, platform?}"""
        n = fodder.record(self.conn, {int(k): int(v) for k, v in body["prices"].items()},
                          body.get("platform", config.PLATFORM), "manual")
        return {"ok": True, "recorded": n}

    def import_club(self, body):
        """Takes the capture itself, or {"payload": <capture>}."""
        payload = body.get("payload", body) if isinstance(body, dict) else body
        try:
            players = club.load(payload)
        except club.ClubImportError as exc:
            return {"ok": False, "error": str(exc)}
        return {"ok": True, **club.store(self.conn, players,
                                         (body or {}).get("platform", config.PLATFORM)
                                         if isinstance(body, dict) else config.PLATFORM)}

    def add_watch(self, body):
        pid = db.resolve_player(self.conn, body["name"], body.get("rating"),
                                body.get("version"))
        snipe.add_watch(self.conn, pid, float(body.get("margin", config.TARGET_MARGIN)),
                        body.get("platform", config.PLATFORM),
                        int(body["max_buy"]) if body.get("max_buy") else None)
        return {"ok": True, "player_id": pid}

    def refresh(self, body):
        """Pull from a configured source. Errors come back as readable text."""
        kind = body.get("source", "csv")
        kwargs = {k: v for k, v in body.items() if k in ("path", "platform")}
        try:
            src = sources.build(kind, **kwargs)
            quotes = src.fetch(body.get("targets", []))
            n = sources.record(self.conn, quotes)
            return {"ok": True, "recorded": n, "source": kind}
        except sources.SourceError as exc:
            return {"ok": False, "error": str(exc)}
        except (OSError, KeyError, ValueError) as exc:
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


GETS = {
    "/api/summary": "summary", "/api/dips": "dips", "/api/movers": "movers",
    "/api/players": "players", "/api/trades": "trades", "/api/holdings": "holdings",
    "/api/performance": "performance", "/api/snipe": "snipe",
    "/api/fodder": "fodder", "/api/promos": "promos", "/api/club": "club",
}
POSTS = {
    "/api/prices": "add_price", "/api/trades": "add_trade",
    "/api/trades/close": "close_trade", "/api/fodder": "add_fodder",
    "/api/watch": "add_watch", "/api/refresh": "refresh",
    "/api/club": "import_club",
}
HISTORY_RE = re.compile(r"^/api/history/(\d+)$")


def make_handler(api: Api):
    class Handler(BaseHTTPRequestHandler):
        server_version = "futdash"

        def log_message(self, fmt, *args):  # quieter console
            pass

        def _send(self, payload, status=200):
            body = json.dumps(payload, default=str).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            parsed = urlparse(self.path)
            path = parsed.path
            q = {k: v[0] for k, v in parse_qs(parsed.query).items()}
            try:
                if path in GETS:
                    with _lock:
                        return self._send(getattr(api, GETS[path])(q))
                m = HISTORY_RE.match(path)
                if m:
                    with _lock:
                        return self._send(api.history(q, m.group(1)))
            except Exception as exc:  # surface the reason, don't 500 blankly
                return self._send({"error": f"{type(exc).__name__}: {exc}"}, 400)
            return self._static(path)

        def do_POST(self):
            path = urlparse(self.path).path
            if path not in POSTS:
                return self._send({"error": "not found"}, 404)
            length = int(self.headers.get("Content-Length") or 0)
            try:
                body = json.loads(self.rfile.read(length) or b"{}")
                with _lock:
                    return self._send(getattr(api, POSTS[path])(body))
            except Exception as exc:
                return self._send({"error": f"{type(exc).__name__}: {exc}"}, 400)

        def _static(self, path):
            rel = "index.html" if path in ("/", "") else path.lstrip("/")
            full = os.path.normpath(os.path.join(STATIC, rel))
            if not full.startswith(STATIC) or not os.path.isfile(full):
                return self._send({"error": "not found"}, 404)
            ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
            with open(full, "rb") as fh:
                data = fh.read()
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    return Handler


def serve(conn, host: str = config.HOST, port: int = config.PORT):
    httpd = ThreadingHTTPServer((host, port), make_handler(Api(conn)))
    return httpd
