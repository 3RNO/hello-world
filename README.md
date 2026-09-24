# FUT Dash

A local trading dashboard for EA FC Ultimate Team. It tracks prices, works
out what you can pay, and tells you honestly whether you made money.

Built for **FC 27, PC market** — both configurable.

It is decision support for manual trading. It does not connect to the Web
App, automate bidding, or touch your EA account. You place every trade
yourself.

---

## Why

The hard part of trading is not clicking. It is knowing what a card is
worth, what you can pay to hit a margin, and whether last week actually
made coins. Those are the three things here.

The tax is the reason most of this exists. EA takes 5% of every sale, so
a card bought at 10,000 and sold at 10,000 loses 500 coins, and its real
break-even is 10,750. The dashboard never shows you a gross number.

## Install

Nothing to install. Python 3.11+, standard library only.

```bash
python3 -m futdash --demo      # example data, nothing written to disk
python3 -m futdash             # your own database
```

Then open <http://127.0.0.1:8765>.

It binds to localhost and has no authentication. It holds your trade
history — do not expose it to a network.

## What's in it

**Market** — cards trading below their own recent median, with a *new low*
marker and a *thin* warning when there is too little history to trust.
Risers and fallers alongside, because a card 10% below median in a
downtrend is not a bargain.

**Snipe filters** — give it a target margin, get a max buy-now, a max bid
and a relist price. Every number is snapped down to a legal price
increment, so they are values you can actually type into a search. It also
says how much history the figure rests on; a margin computed from two
snapshots is fiction and it will tell you so.

**Fodder** — cheapest price per rating, and the cost of each step up the
ladder. The *step ratio* is the useful column: where it is low, that band
is cheap for what it contributes. At the time of writing 85s cost 1.23×
what 84s cost, which is why they were worth buying ahead of the first
SBCs.

**Holdings** — open positions marked against the latest known price, with
break-even including tax.

**Club** — paste a club scan in and it records what you own, split by
tradeable and untradeable, with tradeable value after tax. This is what
turns the fodder tab from *which band is cheap* into *which band is cheap
and you are short of*.

**Journal** — every trade, and post-tax ROI grouped by method. This is the
number that should steer where you spend your time.

## Getting prices in

Four ways, in order of how much you should trust them:

| Source | How | Reliability |
|---|---|---|
| Manual | Type it into the dashboard | Always works |
| CSV | `python3 -m futdash --import prices.csv` | Always works |
| fut.gg | `POST /api/refresh {"source": "fut.gg", "targets": [...]}` | **Unverified** |
| futbin | `POST /api/refresh {"source": "futbin", "targets": [...]}` | **Unverified** |

CSV columns: `name`, `price`, and optionally `rating`, `version`,
`platform`.

**On the two scrapers:** they were written against the sites' documented
shape but could not be tested — the sandbox this was built in blocks both
domains at the network policy, so neither adapter has ever made a real
request. Treat them as a starting point. Each keeps its parsing in a
single `_parse` method, and both raise a readable error rather than
silently recording nothing, so when a site moves its markup you will know
and there is one method to fix. `FUTDATABASE` (futdatabase.com) is a free
API and is probably the better long-term source; there is no adapter for
it yet.

Manual and CSV never break. Keep one wired up.

## Importing your club

The club scanners (EasySBC and similar) have no export button, so the
import takes a JSON capture from your browser instead:

1. Open your club page on the scanner site while signed in.
2. DevTools (`F12`) → **Network** tab → reload the page.
3. Find the request whose response holds your player list — usually the
   largest JSON response, often named something like `club` or `players`.
4. Copy the response body, and paste it into the **Club** tab.

The parser does not assume a schema. It searches the payload for the
largest list of objects carrying both a name and a rating, and accepts the
field spellings these tools are known to use (`name` / `commonName` /
`playerName`, `rating` / `overall` / `ovr`, and `untradeable` or
`tradeable` either way round). If the capture carries prices, those are
recorded too.

If it cannot read the payload it says why rather than importing nothing
quietly. **The exact capture format is unverified** — it was built against
plausible shapes, not a real response, so expect to send a sample if it
does not take.

## Configuration

Environment variables, all optional:

```
FUTDASH_YEAR=27          # game year, used to build source URLs
FUTDASH_PLATFORM=pc      # pc | console -- separate markets, different prices
FUTDASH_MARGIN=0.2       # default target margin
FUTDASH_DB=~/.futdash/futdash.db
FUTDASH_HOST / FUTDASH_PORT
```

Platform matters more than it looks. The PC and console markets are
completely separate and their prices are not interchangeable — most
guides and price sites quote console by default.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

46 tests, covering the tax and price-increment maths, journal P/L, dip
detection, fodder ratios and filter generation. The maths tests check
properties rather than fixed values — that a max-buy always clears the
margin it promised, and that every price the app produces is one the
market would accept.

## Layout

```
futdash/
  tax.py         5% tax, price-increment ladder     <- everything depends on this
  db.py          SQLite schema and player resolution
  sources.py     price adapters (manual, CSV, fut.gg, futbin)
  analytics.py   trends, dips, movers
  fodder.py      cheapest-by-rating, step ratios
  journal.py     trades, holdings, post-tax P/L
  snipe.py       filter calculator
  server.py      JSON API + static serving
  static/        dashboard (vanilla JS, no dependencies)
docs/research.md FUT trading playbook — methods, cycles, signals
tests/
```

## Further reading

[`docs/research.md`](docs/research.md) is a researched playbook covering
trading methods and what each needs in capital and time, the weekly and
promo market cycles, how to read price floors and extinction, and what is
different about the PC market. It is worth reading before the dashboard is
much use to you.
