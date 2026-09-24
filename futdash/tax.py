"""EA FC Transfer Market money maths.

Two things everything else in the dashboard leans on:

* the 5% tax EA takes off every completed sale, and
* the fact that the market only accepts prices on a fixed ladder of
  increments, so a "max bid" that isn't on the ladder is not a bid you
  can actually place.
"""

from __future__ import annotations

# EA takes 5% of the sale price on every completed sale.
EA_TAX = 0.05

MIN_PRICE = 150
MAX_PRICE = 15_000_000

# (upper_bound_exclusive, step) -- the market's price ladder.
_INCREMENTS = (
    (1_000, 50),
    (10_000, 100),
    (50_000, 250),
    (100_000, 500),
    (float("inf"), 1_000),
)


def increment_at(price: float) -> int:
    """The step size the market uses around `price`."""
    for upper, step in _INCREMENTS:
        if price < upper:
            return step
    return 1_000


def _clamp(price: int) -> int:
    return max(MIN_PRICE, min(MAX_PRICE, price))


def round_down(price: float) -> int:
    """Snap `price` down to a bid you can actually place.

    Rounding down matters for a max bid: rounding up would quietly hand
    back a number above the ceiling you asked for.
    """
    if price < MIN_PRICE:
        return MIN_PRICE
    step = increment_at(price)
    snapped = int(price // step) * step
    # Rounding down can drop us under the band we started in (e.g. 10,000
    # snaps by 250, but 10,000 itself is the band's floor), so re-snap with
    # the step that actually applies to the result.
    lower_step = increment_at(snapped)
    if lower_step != step:
        snapped = int(price // lower_step) * lower_step
    return _clamp(snapped)


def round_up(price: float) -> int:
    """Snap `price` up to a listable price -- used for sell-side targets."""
    if price <= MIN_PRICE:
        return MIN_PRICE
    step = increment_at(price)
    snapped = -(-int(price) // step) * step
    if snapped != price and increment_at(snapped) != step:
        step = increment_at(snapped)
        snapped = -(-int(price) // step) * step
    return _clamp(snapped)


def net_proceeds(sell_price: float) -> float:
    """What actually lands in your club after EA's cut."""
    return sell_price * (1 - EA_TAX)


def profit(buy_price: float, sell_price: float, quantity: int = 1) -> float:
    """Post-tax coin profit. Negative means the trade lost coins."""
    return (net_proceeds(sell_price) - buy_price) * quantity


def roi(buy_price: float, sell_price: float) -> float:
    """Post-tax return on the coins tied up. 0.2 == 20%."""
    if buy_price <= 0:
        return 0.0
    return profit(buy_price, sell_price) / buy_price


def break_even(buy_price: float) -> int:
    """Lowest listable price that doesn't lose coins on `buy_price`."""
    return round_up(buy_price / (1 - EA_TAX))


def max_buy(sell_price: float, target_margin: float) -> int:
    """Most you can pay and still clear `target_margin` after tax.

    `target_margin` is ROI on coins spent: 0.2 means a 20% return. The
    result is snapped down so it is a bid the market will accept.
    """
    if target_margin <= -1:
        raise ValueError("target_margin must be greater than -1")
    raw = net_proceeds(sell_price) / (1 + target_margin)
    return round_down(raw)


def margin_at(buy_price: float, sell_price: float) -> float:
    """Alias of `roi`, named for the snipe-filter side of the app."""
    return roi(buy_price, sell_price)
