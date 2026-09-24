# Price capture tools

Getting bulk prices out of FUTBIN and fut.gg is the hard part of this
project, for reasons that are worth stating plainly:

- **Neither site has a public API.** Both are read through
  reverse-engineered endpoints that change without notice.
- **FUTBIN fronts its pages with bot protection.** A server-side scraper
  gets blocked; your browser does not.
- **The one free documented API, FUTDATABASE, cannot return multiple
  prices in one request**, which makes a whole-market pull impractical.

So rather than fight that from a server, these run **in your own browser**,
where you are already a legitimate logged-in visitor. Nothing is sent
anywhere; each one prints data for you to copy.

## `capture-api.js` — read the site's own API

The general tool. It hooks `fetch` and `XMLHttpRequest`, records the JSON
the page receives, and lets you copy any of it. Because it reads API
responses rather than markup, it survives redesigns, and it works equally
on fut.gg, FUTBIN and EasySBC.

1. Open the page whose data you want.
2. `F12` → **Console** → paste the whole file → Enter.
3. Reload the page, or click through to the data.
4. `futdash.list()` — shows what was captured, largest first.
5. `futdash.copy(3)` — copies capture #3 to your clipboard.

The one you want is almost always the largest response.

## `scrape-ratings.js` — cheapest-by-rating in one go

Targeted at the cheapest-player-by-rating pages. Reads the table by
looking for number *shapes* rather than class names: a rating is an
integer from 40 to 99, a price is the largest other number on the row.

1. Open the cheapest-by-rating page, **set the platform to PC**.
2. Paste the file into the Console.
3. It prints a table and copies `{"84": 9000, "83": 4000, …}` to your
   clipboard.
4. Paste that into FUT Dash → **Fodder** tab → *Record ladder*.

It prints what it found before you import it. Check a couple of rows
against the page — a mis-read ladder is worse than no ladder, because
every downstream number quietly inherits the error.

If it finds nothing, the layout has moved: use `capture-api.js` instead.

## A note on what to copy

**Never paste a Headers tab.** Request headers carry authentication
tokens — EasySBC's is a bearer token valid for months. Response bodies
carry data. These tools only ever read response bodies.
