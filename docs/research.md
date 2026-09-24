# FUT Trading Playbook — EA FC 27, PC Market

Research compiled 24 September 2026. Sources listed at the end.

Everything here is decision support for manual trading. Prices and dates
move fast; treat the numbers as of the compile date and re-check before
acting on them.

---

## 0. Where we are in the cycle (read this first)

FC 27's calendar puts us at the single most volatile moment of the year:

| Event | When |
|---|---|
| Web App opened | 16 Sep 2026, 17:00 UTC |
| Early access + first SBCs + Ones to Watch | 18 Sep 2026 |
| **PC unlock** | **24 Sep 2026, 23:00 UTC** |
| Full launch (all platforms) | 25 Sep 2026 |

Two consequences that dominate everything else in this document:

1. **Launch week is the widest-margin window of the year.** The market is
   thin, everyone needs the same handful of cards for the first SBCs, and
   consumables are scarce. Thin markets misprice things constantly, which
   is exactly what a trader wants.
2. **Launch prices are a peak, not a baseline.** They settle downward over
   roughly the first fortnight. Buying the bulk of a squad in the first
   Saturday–Monday window after launch typically saves 15–30% on mid-tier
   players versus launch-day prices. So: trade actively now, but do not
   *accumulate* a squad now.

The practical read for a PC trader today: your market unlocks tonight at
23:00 UTC, one day behind console. Console has had six days of price
discovery you can read for free before your own market opens.

---

## 1. Method playbook

Ranked by what actually suits an early-cycle PC market.

### 1.1 Sniping

Buying underpriced cards the moment they list, via a saved search with a
max Buy-Now just under market value.

- **Capital:** works from ~5k, scales with bank.
- **Mechanics:** the profit is small per flip and comes from volume. A card
  worth ~5,000 sniped at 4,300 returns 4,750 after tax — about **450 coins
  a flip**. Twenty to thirty landed snipes an hour is tens of thousands of
  coins.
- **Why it works now:** thin markets mean more mispriced listings.
- **Caveat:** it is the most attention-expensive method per coin earned.

### 1.2 Consumable sniping (best launch-week edge)

Contracts and chemistry styles are scarcest in the opening days, before
pack volume catches up.

- **Capital:** very low — hundreds of coins.
- **Why it works now:** this window closes as packs flood supply. It is
  specifically an early-cycle method, which makes it the highest-priority
  one this week.

### 1.3 SBC fodder flipping (the structural method)

Buying the rating bands SBCs consume, and selling into SBC releases.

- **Capital:** low to medium, scales cleanly.
- **The key number is score per coin, not price.** At the time of research,
  85-rated cards sat around 800 coins and contribute 2,900 SBC score —
  roughly **four times the score-per-coin of 84s at 650 coins**. That gap
  is a pricing error, and it closes the moment Ones to Watch SBCs go live
  and people work out they need high-score cards.
- **Read the rating combinations**, not individual players: the cheap way
  to hit a target rating is "top-heavy" — one or two high cards carrying a
  squad of much cheaper ones. An 89 squad is commonly 2×91 + 9×88; an 86 is
  commonly 2×88 + 9×85.
- This is the method the dashboard's price-by-rating tracking is built for.

### 1.4 Bronze Pack Method (BPM)

Open bronze packs, list the contents. No filter, no timing, no skill.

- **Capital:** trivial.
- **Return:** a steady few thousand coins per session — reliable, low
  ceiling. Worth it as background activity, not as a strategy.

### 1.5 Promo-cycle investing

Buying into the dip a promo causes, selling into the recovery.

- **Capital:** medium to high; requires patience and holding risk.
- **Mechanics:** during promos, packs are opened heavily and prices drop.
  After promos, supply dries up and prices recover. Buying *after* prices
  have corrected downward beats chasing a card at its pre-promo peak.
- **Special-card variant:** buy special cards (TOTW, informs) as close to
  discard value as possible, while no SBC requiring special players is
  live. SBCs demanding special players are common, and that demand is what
  you are selling into.

### 1.6 Chemistry-style arbitrage

A card carrying a desirable chemistry style (Hunter, Shadow) sells for
meaningfully more than its base card.

- **Method:** search a meta player with no chem-style filter to establish
  the base price, then search the same player *with* the in-demand style to
  establish the boosted price. Snipe listings sitting below the boosted
  price. The seller who did not apply the filter is the one mispricing.

---

## 2. Market cycles — when to buy and when to sell

### Weekly rhythm

This is the most dependable pattern in the game.

| Window | What happens | Action |
|---|---|---|
| **Sun night – Tue** | Weekend League supply floods in, prices sag | **Buy** |
| **Wed** | Drift, TOTW arrives | Hold |
| **Thu – Fri** | Rivals rewards land, squads built pre-WL, demand spikes | **Sell** |
| **Fri 20:00 → Mon 09:00** | Weekend League runs | Market thins |

"Buy Monday, sell Friday" is the compressed version and it holds up.

### Promo rhythm

- Promo release → packs opened heavily → **prices crash**. The steepest
  single-day drops come when a batch of cards re-enters packs, especially
  landing on a weekend low.
- Post-promo → supply dries up → **prices recover**.
- Large campaigns (TOTY, TOTS, big Friday campaigns) are the cases where
  holding packs rather than opening them can be worth more.

### Seasonal rhythm

Launch is expensive and volatile → the first fortnight settles downward →
content cycles then drive the market until the endgame, when everything
inflates against a shrinking supply.

---

## 3. Price signals and filters

### What makes a card snipeable

- **Liquidity.** Meta cards in top-five leagues trade constantly. An
  obscure card may be cheap and simply never sell.
- **A gap between base and boosted price** — position changes and chemistry
  styles both create one.
- **SBC utility.** Rating and league/nation links matter more than stats for
  fodder.

### Filter construction

A workable sniping filter:

1. Pick a top-five league.
2. Filter to a position that carries a premium — fullbacks, pacey wingers,
   CDMs.
3. Quality: Gold, Rare.
4. Set a **minimum** price to exclude worthless fodder from the results.
5. Set max Buy-Now just under market value — that number is what the
   dashboard's snipe calculator produces, snapped to a legal bid increment.

### Floors, extinction and discard value

- EA sets a price **range** per card. When a card's demand exceeds its
  maximum permitted price, it cannot be listed at what it is worth and
  **goes extinct** — it vanishes from the market. Extinction is a signal
  that EA has not updated a price range, and it is tradeable.
- **Discard value** is the hard floor: a card can never be worth less,
  because quick-selling always pays it. Special cards bought near discard
  have almost no downside and real SBC upside.

### Reading a price graph

Three things matter, and all three are in the dashboard:

1. **Where is it against its own recent median?** — the discount signal.
2. **Is this a new low, or just noise?** — a low against a 2-point history
   is meaningless; against 30 points it is a signal.
3. **Which way is the trend running?** A card 10% below median but in a
   sustained downtrend is not a bargain, it is a falling knife.

---

## 4. PC market specifics

The PC market is **entirely separate** from console — PlayStation and Xbox
share one market, PC has its own. Consequences:

- **Thinner liquidity.** Fewer buyers and sellers. Cards take longer to
  sell, and the spread between a snipe price and a realistic sale price is
  wider. Sizing matters: ten copies of a card that clears twice a day is
  a trap.
- **Prices diverge from console.** Console-based price sites and YouTube
  guides quote numbers that do **not** transfer. Always confirm PC prices
  on a site that lets you switch platform.
- **Smaller and shrinking population.** FC 26 averaged around 30,000
  concurrent PC players against a launch peak above 100,000.
- **More bot and coin-seller activity**, which distorts the low end of the
  market in particular.
- **One genuine edge:** PC unlocks after console. Console price discovery
  from the preceding days is free information about where PC prices are
  heading.

---

## 5. Data sources

| Source | What it gives | Notes |
|---|---|---|
| **FUTBIN** | Prices, price history graphs, cheapest-by-rating, SBC rating combinations | The reference. Has bot protection, so scraping is unreliable |
| **fut.gg** | Prices, trends, cheapest-by-rating, FC 27 pages already live | Cleaner structure; no documented public API |
| **FUTDATABASE** | Players, prices, clubs, nations, leagues | A small, genuinely free API — **the most promising programmatic source** |
| **SBC Cruncher** | Cheapest rating combinations from FUTBIN/FUTWIZ data | Solves the fodder maths directly |

Both FUTBIN and fut.gg expose **cheapest player by rating**, which is the
single most valuable page for fodder trading and the one worth polling
regularly.

**Important:** always set these sites to the **PC** market. They default to
console, and the numbers are not interchangeable.

---

## Sources

- [FC 27 launch-week trading guide](https://timesaver.gg/blog/fc-27-fut-market-launch-week-trading-85s-otw-prep)
- [FC 27 best coin methods, launch week](https://timesaver.gg/blog/fc-27-trading-best-coin-methods-launch-week)
- [FC 27 early access market timeline](https://timesaver.gg/blog/fc-27-sell-or-hold-early-access-market-crash-timeline)
- [FC 27 launch day checklist](https://timesaver.gg/blog/fc-27-launch-day-checklist-september-25-full-release)
- [EA FC 26 trading guide and methods](https://timesaver.gg/blog/ea-fc-26-fut-trading-guide)
- [Sniping filters and coin trading guide](https://www.itemd2r.com/en/blog/fc-26/ea-fc-26-ultimate-team-sniping-filters-coin-trading-guide)
- [FUTBIN cheapest players by rating](https://www.futbin.com/26/squad-building-challenges/cheapest)
- [FUTBIN SBC rating combinations](https://www.futbin.com/26/squad-building-challenges/rating-combinations)
- [fut.gg cheapest by rating (FC 27)](https://www.fut.gg/cheapest-by-rating/)
- [FUTDATABASE API](https://www.futdatabase.com/)
- [SBC Cruncher](https://sbccruncher.cc/)
- [Extinct cards and price ranges](https://futfc.gg/fc-25-extinct-cards-why-ea-isnt-updating-prices-and-how-to-profit/)
- [Discard-value special players method](https://www.futtradingmethods.com/discard-value-special-totw-informs)
- [What makes a card hold value](https://sportshistorynetwork.com/esports/what-actually-makes-a-fut-card-a-smart-long-term-hold/)
- [How the Transfer Market affects card prices](https://www.fifa-infinity.com/ea-sports-fc/ultimate-team-pricing-no-trade-window/)
- [PC vs console market separation (EA Forums)](https://forums.ea.com/discussions/fc-24-general-discussion-en/re-cross-market-between-pc-and-consoles-in-fc-25-or-next-fc-come-on/7658659)
- [FC 26 PC playerbase figures](https://www.sportskeeda.com/esports/ea-fc-26-gets-40-discount-player-numbers-decline)
