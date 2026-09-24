"""Where prices come from.

Every source returns the same thing -- a list of `Quote` -- so the rest of
the app never knows or cares which one is in use.

The two scraping sources (`FutGgSource`, `FutbinSource`) read public pages
that can change shape without notice, so each keeps its parsing in one
small method. If a site moves its markup, that method is the only thing
that needs rewriting. `ManualSource` and `CsvSource` never break, and are
the fallback worth keeping wired up.
"""

from __future__ import annotations

import csv
import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Iterable, Sequence

from . import config, db

USER_AGENT = "futdash/1.0 (personal trading journal)"
TIMEOUT = 15


class SourceError(RuntimeError):
    """A source could not produce prices. Message says why."""


@dataclass
class Quote:
    name: str
    price: int
    platform: str = config.PLATFORM
    rating: int | None = None
    version: str = "standard"
    source: str = "manual"
    ext_id: str | None = None
    meta: dict = field(default_factory=dict)


class PriceSource:
    """Interface every source implements."""

    name = "base"

    def fetch(self, targets: Sequence[str]) -> list[Quote]:
        raise NotImplementedError

    # Shared HTTP helper -- keeps the UA and timeout consistent.
    def _get(self, url: str) -> str:
        req = urllib.request.Request(url, headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json, text/html;q=0.9",
        })
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            raise SourceError(f"{self.name}: HTTP {exc.code} for {url}") from exc
        except urllib.error.URLError as exc:
            raise SourceError(f"{self.name}: cannot reach {url} ({exc.reason})") from exc


class FixtureSource(PriceSource):
    """Reads a JSON file. Used by the tests and for offline demos."""

    name = "fixture"

    def __init__(self, path: str):
        self.path = path

    def fetch(self, targets: Sequence[str] = ()) -> list[Quote]:
        with open(self.path, encoding="utf-8") as fh:
            payload = json.load(fh)
        wanted = {t.lower() for t in targets}
        out = []
        for row in payload:
            if wanted and row["name"].lower() not in wanted:
                continue
            out.append(Quote(
                name=row["name"], price=int(row["price"]),
                platform=row.get("platform", config.PLATFORM),
                rating=row.get("rating"), version=row.get("version", "standard"),
                source=self.name,
            ))
        return out


class CsvSource(PriceSource):
    """Reads a CSV you exported yourself.

    Expected columns: name, price. Optional: rating, version, platform.
    """

    name = "csv"

    def __init__(self, path: str):
        self.path = path

    def fetch(self, targets: Sequence[str] = ()) -> list[Quote]:
        wanted = {t.lower() for t in targets}
        out = []
        with open(self.path, newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                name = (row.get("name") or "").strip()
                raw_price = (row.get("price") or "").replace(",", "").strip()
                if not name or not raw_price:
                    continue
                if wanted and name.lower() not in wanted:
                    continue
                rating = row.get("rating")
                out.append(Quote(
                    name=name, price=int(float(raw_price)),
                    platform=(row.get("platform") or config.PLATFORM).strip().lower(),
                    rating=int(rating) if rating and rating.strip() else None,
                    version=(row.get("version") or "standard").strip(),
                    source=self.name,
                ))
        return out


class ManualSource(PriceSource):
    """Prices typed straight into the dashboard."""

    name = "manual"

    def __init__(self, quotes: Iterable[Quote] = ()):
        self.quotes = list(quotes)

    def fetch(self, targets: Sequence[str] = ()) -> list[Quote]:
        wanted = {t.lower() for t in targets}
        return [q for q in self.quotes if not wanted or q.name.lower() in wanted]


class FutGgSource(PriceSource):
    """fut.gg's public price endpoint.

    UNVERIFIED against the live site -- see README. `_parse` is the only
    part that needs changing if the response shape has moved.
    """

    name = "fut.gg"
    BASE = "https://www.fut.gg/api/fut/player-prices"

    def __init__(self, platform: str = config.PLATFORM):
        self.platform = platform

    def fetch(self, targets: Sequence[str]) -> list[Quote]:
        if not targets:
            return []
        ids = ",".join(str(t) for t in targets)
        url = f"{self.BASE}/{config.GAME_YEAR}/?ids={ids}&platform={self.platform}"
        return self._parse(self._get(url))

    def _parse(self, body: str) -> list[Quote]:
        try:
            payload = json.loads(body)
        except json.JSONDecodeError as exc:
            raise SourceError(f"{self.name}: response was not JSON") from exc
        rows = payload.get("data", payload) if isinstance(payload, dict) else payload
        if isinstance(rows, dict):
            rows = list(rows.values())
        out = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            price = row.get("price") or row.get("currentPrice") or row.get("lowest")
            name = row.get("name") or row.get("playerName") or row.get("commonName")
            if price is None or not name:
                continue
            out.append(Quote(
                name=str(name), price=int(price), platform=self.platform,
                rating=row.get("rating") or row.get("overall"),
                version=str(row.get("version") or "standard"),
                source=self.name, ext_id=str(row.get("id") or "") or None,
            ))
        if not out:
            raise SourceError(
                f"{self.name}: parsed 0 prices -- the response shape has "
                "probably changed; update FutGgSource._parse"
            )
        return out


class FutbinSource(PriceSource):
    """futbin player pages.

    UNVERIFIED against the live site -- see README. futbin fronts its pages
    with bot protection, so treat this as a best effort and fall back to CSV.
    """

    name = "futbin"
    BASE = f"https://www.futbin.com/{config.GAME_YEAR}/playerPrices"
    _PRICE_RE = re.compile(r'"LCPrice"\s*:\s*"([\d,]+)"')

    def __init__(self, platform: str = config.PLATFORM):
        self.platform = platform

    def fetch(self, targets: Sequence[str]) -> list[Quote]:
        out = []
        for target in targets:
            body = self._get(f"{self.BASE}?player={target}")
            out.extend(self._parse(body, str(target)))
        return out

    def _parse(self, body: str, target: str) -> list[Quote]:
        match = self._PRICE_RE.search(body)
        if not match:
            raise SourceError(
                f"{self.name}: no price found for {target} -- markup has "
                "probably changed, or the request was blocked"
            )
        price = int(match.group(1).replace(",", ""))
        return [Quote(name=target, price=price, platform=self.platform,
                      source=self.name, ext_id=target)]


class FutDatabaseSource(PriceSource):
    """futdatabase.com -- the only documented, official API of the three.

    It needs a free API key (`FUTDASH_FUTDB_KEY`, or pass `api_key`), and
    it returns one player per request, so it is no use for sweeping the
    market. For the thing it is actually needed for -- looking up a card
    you are about to bid on -- one request is exactly right.

    Prices refresh between 30 minutes and 24 hours depending on rating and
    rarity, so treat a reading as recent rather than live.

    UNVERIFIED against the live API -- see README.
    """

    name = "futdatabase"
    BASE = "https://futdb.app/api"

    def __init__(self, api_key: str | None = None, platform: str = config.PLATFORM):
        self.api_key = api_key or os.environ.get("FUTDASH_FUTDB_KEY", "")
        self.platform = platform

    def _get(self, url: str) -> str:
        if not self.api_key:
            raise SourceError(
                f"{self.name}: no API key. Get a free one at futdb.app and set "
                "FUTDASH_FUTDB_KEY, or pass api_key.")
        req = urllib.request.Request(url, headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
            "X-AUTH-TOKEN": self.api_key,
        })
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                raise SourceError(f"{self.name}: key rejected (HTTP {exc.code})") from exc
            if exc.code == 429:
                raise SourceError(f"{self.name}: rate limited -- slow down") from exc
            raise SourceError(f"{self.name}: HTTP {exc.code} for {url}") from exc
        except urllib.error.URLError as exc:
            raise SourceError(f"{self.name}: cannot reach {url} ({exc.reason})") from exc

    def fetch(self, targets: Sequence[str]) -> list[Quote]:
        """`targets` are futdb player ids. One request each -- it has no
        bulk endpoint, so this is deliberately serial."""
        out = []
        for target in targets:
            out.extend(self._parse(self._get(f"{self.BASE}/players/{target}/price"),
                                   str(target)))
        return out

    def _parse(self, body: str, target: str) -> list[Quote]:
        try:
            payload = json.loads(body)
        except json.JSONDecodeError as exc:
            raise SourceError(f"{self.name}: response was not JSON") from exc
        # Documented shape is {"price": {"ps": {...}, "xbox": {...}, "pc": {...}}}
        prices = payload.get("price", payload)
        block = prices.get(self.platform) if isinstance(prices, dict) else None
        if block is None and isinstance(prices, dict):
            # PC is sometimes keyed differently; fall back to any block.
            block = next((v for v in prices.values() if isinstance(v, dict)), None)
        price = None
        if isinstance(block, dict):
            price = block.get("LCPrice") or block.get("lowest") or block.get("price")
        if price in (None, "", 0):
            raise SourceError(
                f"{self.name}: no {self.platform} price for {target} -- either the "
                "card is unpriced or the response shape has moved")
        return [Quote(name=str(payload.get("name") or target),
                      price=int(str(price).replace(",", "")),
                      platform=self.platform, source=self.name, ext_id=target)]


def build(kind: str, **kwargs) -> PriceSource:
    """Look up a source by name."""
    kinds = {
        "fixture": FixtureSource, "csv": CsvSource, "manual": ManualSource,
        "fut.gg": FutGgSource, "futgg": FutGgSource, "futbin": FutbinSource,
        "futdatabase": FutDatabaseSource, "futdb": FutDatabaseSource,
    }
    if kind not in kinds:
        raise SourceError(f"unknown source {kind!r}; have {sorted(kinds)}")
    return kinds[kind](**kwargs)


def record(conn, quotes: Iterable[Quote]) -> int:
    """Write quotes into price_snapshots, creating players as needed."""
    ts = db.utcnow()
    count = 0
    for q in quotes:
        pid = db.upsert_player(conn, q.name, q.rating, q.version)
        conn.execute(
            "INSERT INTO price_snapshots (player_id, platform, price, ts, source)"
            " VALUES (?, ?, ?, ?, ?)",
            (pid, q.platform, q.price, ts, q.source),
        )
        count += 1
    conn.commit()
    return count
