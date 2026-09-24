"""Tests for the parts that would quietly cost coins if they were wrong."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from futdash import analytics, club, db, demo, fodder, journal, snipe, sources, tax


class TestTax(unittest.TestCase):
    def test_tax_is_five_percent_of_the_sale(self):
        self.assertAlmostEqual(tax.net_proceeds(10_000), 9_500)

    def test_profit_is_post_tax(self):
        # The classic mistake: 10k -> 10k looks flat, but loses 500 coins.
        self.assertAlmostEqual(tax.profit(10_000, 10_000), -500)
        self.assertAlmostEqual(tax.profit(4_300, 5_000), 450)

    def test_profit_scales_with_quantity(self):
        self.assertAlmostEqual(tax.profit(1_000, 2_000, quantity=5), 4_500)

    def test_break_even_covers_the_tax_and_is_listable(self):
        be = tax.break_even(10_000)
        self.assertGreaterEqual(tax.net_proceeds(be), 10_000)
        self.assertEqual(be % tax.increment_at(be), 0)

    def test_break_even_is_the_lowest_listable_price_that_works(self):
        be = tax.break_even(10_000)
        below = be - tax.increment_at(be)
        self.assertLess(tax.net_proceeds(below), 10_000)

    def test_roi(self):
        self.assertAlmostEqual(tax.roi(10_000, 20_000), 0.9)
        self.assertEqual(tax.roi(0, 100), 0.0)


class TestIncrements(unittest.TestCase):
    CASES = [(500, 50), (999, 50), (1_000, 100), (9_999, 100), (10_000, 250),
             (49_999, 250), (50_000, 500), (99_999, 500), (100_000, 1_000),
             (2_000_000, 1_000)]

    def test_bands(self):
        for price, step in self.CASES:
            self.assertEqual(tax.increment_at(price), step, f"at {price}")

    def test_round_down_never_exceeds_input(self):
        for price in range(200, 200_000, 337):
            self.assertLessEqual(tax.round_down(price), price, f"at {price}")

    def test_round_up_never_undercuts_input(self):
        for price in range(200, 200_000, 337):
            self.assertGreaterEqual(tax.round_up(price), price, f"at {price}")

    def test_results_sit_on_the_ladder(self):
        for price in range(200, 200_000, 137):
            for fn in (tax.round_down, tax.round_up):
                v = fn(price)
                self.assertEqual(v % tax.increment_at(v), 0, f"{fn.__name__}({price}) = {v}")

    def test_floor_is_respected(self):
        self.assertEqual(tax.round_down(10), tax.MIN_PRICE)
        self.assertEqual(tax.round_up(1), tax.MIN_PRICE)


class TestMaxBuy(unittest.TestCase):
    def test_max_buy_actually_clears_the_target_margin(self):
        for sell in (1_000, 7_500, 25_000, 90_000, 500_000):
            for margin in (0.1, 0.2, 0.5):
                buy = tax.max_buy(sell, margin)
                self.assertGreaterEqual(
                    tax.roi(buy, sell), margin,
                    f"sell={sell} margin={margin} gave buy={buy}")

    def test_max_buy_is_a_placeable_bid(self):
        v = tax.max_buy(20_000, 0.2)
        self.assertEqual(v % tax.increment_at(v), 0)

    def test_rejects_impossible_margin(self):
        with self.assertRaises(ValueError):
            tax.max_buy(1_000, -1.5)


class TestJournal(unittest.TestCase):
    def setUp(self):
        self.conn = db.connect(":memory:")
        self.pid = db.upsert_player(self.conn, "Test Player", 84, "gold rare")

    def test_buy_then_sell_reports_post_tax_profit(self):
        tid = journal.buy(self.conn, self.pid, 10_000)
        result = journal.sell(self.conn, tid, 20_000)
        self.assertEqual(result["profit"], 9_000)

    def test_cannot_close_twice(self):
        tid = journal.buy(self.conn, self.pid, 1_000)
        journal.sell(self.conn, tid, 2_000)
        with self.assertRaises(ValueError):
            journal.sell(self.conn, tid, 3_000)

    def test_open_trade_is_a_holding(self):
        journal.buy(self.conn, self.pid, 5_000)
        self.assertEqual(len(journal.holdings(self.conn)), 1)
        self.assertEqual(journal.summary(self.conn)["open_trades"], 1)

    def test_holding_without_a_price_is_not_marked(self):
        journal.buy(self.conn, self.pid, 5_000)
        self.assertIsNone(journal.holdings(self.conn)[0]["unrealised"])

    def test_summary_roi_matches_the_trades(self):
        journal.sell(self.conn, journal.buy(self.conn, self.pid, 10_000), 20_000)
        s = journal.summary(self.conn)
        self.assertEqual(s["profit"], 9_000)
        self.assertAlmostEqual(s["roi"], 0.9, places=3)
        self.assertEqual(s["win_rate"], 1.0)

    def test_by_method_separates_methods(self):
        journal.sell(self.conn, journal.buy(self.conn, self.pid, 1_000, method="snipe"), 2_000)
        journal.sell(self.conn, journal.buy(self.conn, self.pid, 1_000, method="bid"), 1_000)
        rows = {r["method"]: r for r in journal.by_method(self.conn)}
        self.assertGreater(rows["snipe"]["profit"], 0)
        self.assertLess(rows["bid"]["profit"], 0)


class TestResolvePlayer(unittest.TestCase):
    def setUp(self):
        self.conn = db.connect(":memory:")

    def test_name_only_matches_an_existing_card(self):
        pid = db.upsert_player(self.conn, "Rodri", 89, "gold rare")
        self.assertEqual(db.resolve_player(self.conn, "Rodri"), pid)

    def test_match_is_case_insensitive(self):
        pid = db.upsert_player(self.conn, "Rodri", 89, "gold rare")
        self.assertEqual(db.resolve_player(self.conn, "rodri"), pid)

    def test_creates_when_nothing_matches(self):
        pid = db.resolve_player(self.conn, "Unknown Card")
        self.assertIsNotNone(pid)

    def test_prefers_the_card_that_has_prices(self):
        bare = db.upsert_player(self.conn, "Rodri", None, "standard")
        priced = db.upsert_player(self.conn, "Rodri", 89, "gold rare")
        sources.record(self.conn, [sources.Quote("Rodri", 200_000, rating=89,
                                                 version="gold rare")])
        self.assertEqual(db.resolve_player(self.conn, "Rodri"), priced)
        self.assertNotEqual(db.resolve_player(self.conn, "Rodri"), bare)


class TestAnalytics(unittest.TestCase):
    def setUp(self):
        self.conn = db.connect(":memory:")
        self.pid = db.upsert_player(self.conn, "Drifter", 85, "gold rare")

    def _prices(self, values):
        for v in values:
            sources.record(self.conn, [sources.Quote("Drifter", v, rating=85,
                                                     version="gold rare")])

    def test_stats_none_without_data(self):
        self.assertIsNone(analytics.stats(self.conn, self.pid))

    def test_stats_summarise_the_window(self):
        self._prices([1_000, 1_200, 800])
        st = analytics.stats(self.conn, self.pid)
        self.assertEqual((st["low"], st["high"], st["latest"]), (800, 1_200, 800))
        self.assertEqual(st["samples"], 3)

    def test_new_low_detection(self):
        self._prices([1_000, 1_200, 800])
        self.assertTrue(analytics.is_new_low(analytics.history(self.conn, self.pid)))
        self._prices([2_000])
        self.assertFalse(analytics.is_new_low(analytics.history(self.conn, self.pid)))

    def test_new_low_needs_history(self):
        self._prices([1_000])
        self.assertFalse(analytics.is_new_low(analytics.history(self.conn, self.pid)))

    def test_dips_ignore_thin_history(self):
        self._prices([1_000, 500])
        self.assertEqual(analytics.dips(self.conn, min_samples=3), [])

    def test_dips_surface_a_real_discount(self):
        self._prices([1_000, 1_000, 1_000, 700])
        found = analytics.dips(self.conn, min_discount=5, min_samples=3)
        self.assertEqual(len(found), 1)
        self.assertTrue(found[0]["new_low"])


class TestFodder(unittest.TestCase):
    def setUp(self):
        self.conn = db.connect(":memory:")
        fodder.record(self.conn, {84: 650, 85: 800, 86: 1_600})

    def test_step_ratio_between_bands(self):
        rows = {r["rating"]: r for r in fodder.table(self.conn)}
        self.assertAlmostEqual(rows[85]["step_ratio"], 800 / 650, places=3)
        self.assertEqual(rows[85]["step_cost"], 150)

    def test_lowest_band_has_no_step(self):
        self.assertIsNone({r["rating"]: r for r in fodder.table(self.conn)}[84]["step_ratio"])

    def test_best_value_picks_the_cheap_step(self):
        # 85s at 800 over 84s at 650 is the cheap step; 86s at double are not.
        self.assertEqual(fodder.best_value(self.conn, limit=1)[0]["rating"], 85)

    def test_latest_reading_wins(self):
        fodder.record(self.conn, {85: 900})
        self.assertEqual(fodder.latest(self.conn)[85]["price"], 900)


class TestSnipe(unittest.TestCase):
    def setUp(self):
        self.conn = db.connect(":memory:")
        self.pid = db.upsert_player(self.conn, "Target", 87, "gold rare")
        for v in (20_000, 20_000, 20_000, 20_000):
            sources.record(self.conn, [sources.Quote("Target", v, rating=87,
                                                     version="gold rare")])

    def test_filter_clears_the_requested_margin(self):
        r = snipe.for_player(self.conn, self.pid, 0.2)
        self.assertGreaterEqual(tax.roi(r["max_buy_now"], r["relist_at"]), 0.2)

    def test_bid_ceiling_sits_below_buy_now(self):
        r = snipe.for_player(self.conn, self.pid, 0.2)
        self.assertLess(r["max_bid"], r["max_buy_now"])

    def test_outputs_are_placeable_prices(self):
        r = snipe.for_player(self.conn, self.pid, 0.2)
        for key in ("max_buy_now", "max_bid", "relist_at"):
            self.assertEqual(r[key] % tax.increment_at(r[key]), 0, key)

    def test_none_without_prices(self):
        other = db.upsert_player(self.conn, "No Prices", 80, "gold")
        self.assertIsNone(snipe.for_player(self.conn, other))

    def test_confidence_reflects_sample_count(self):
        self.assertEqual(snipe.confidence(1), "insufficient")
        self.assertEqual(snipe.confidence(4), "low")
        self.assertEqual(snipe.confidence(25), "high")

    def test_manual_cap_only_lowers_the_ceiling(self):
        snipe.add_watch(self.conn, self.pid, 0.2, max_buy=1_000)
        self.assertEqual(snipe.watchlist(self.conn)[0]["max_buy_now"], 1_000)


class TestSources(unittest.TestCase):
    def test_fixture_source_loads(self):
        quotes = sources.FixtureSource(demo.FIXTURE).fetch()
        self.assertTrue(quotes)
        self.assertTrue(all(q.price > 0 for q in quotes))

    def test_fixture_source_filters_by_name(self):
        quotes = sources.FixtureSource(demo.FIXTURE).fetch(["Rodri"])
        self.assertEqual([q.name for q in quotes], ["Rodri"])

    def test_unknown_source_is_rejected(self):
        with self.assertRaises(sources.SourceError):
            sources.build("nope")

    def test_futgg_reports_a_changed_response_shape(self):
        with self.assertRaises(sources.SourceError):
            sources.FutGgSource()._parse('{"data": []}')

    def test_futbin_reports_missing_markup(self):
        with self.assertRaises(sources.SourceError):
            sources.FutbinSource()._parse("<html>blocked</html>", "123")


class TestDemo(unittest.TestCase):
    def test_seed_produces_a_working_dataset(self):
        conn = db.connect(":memory:")
        demo.seed(conn)
        self.assertTrue(analytics.dips(conn, days=7))
        self.assertTrue(journal.holdings(conn))
        self.assertTrue(fodder.table(conn))
        self.assertGreater(journal.summary(conn)["closed_trades"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestClubImport(unittest.TestCase):
    """The capture format is a guess, so tolerance is the thing under test."""

    FLAT = [{"name": "Rodri", "rating": 89, "untradeable": False, "price": 200_000},
            {"name": "Saka", "rating": 87, "untradeable": True}]
    WRAPPED = {"data": {"club": {"players": [
        {"commonName": "Rodri", "overall": 89, "isUntradeable": 0, "marketPrice": 200_000},
        {"commonName": "Saka", "overall": 87, "isUntradeable": 1}]}}}
    POSITIVE = {"items": [{"playerName": "Rodri", "ovr": 89, "tradeable": True},
                          {"playerName": "Saka", "ovr": 87, "tradeable": False}]}

    def setUp(self):
        self.conn = db.connect(":memory:")

    def test_reads_a_flat_list(self):
        self.assertEqual(len(club.load(self.FLAT)), 2)

    def test_reads_a_wrapped_payload(self):
        self.assertEqual([p["name"] for p in club.load(self.WRAPPED)], ["Rodri", "Saka"])

    def test_alternate_field_spellings(self):
        self.assertEqual(club.load(self.WRAPPED)[0]["rating"], 89)

    def test_tradeable_stated_positively_is_inverted(self):
        rows = {p["name"]: p for p in club.load(self.POSITIVE)}
        self.assertEqual(rows["Rodri"]["untradeable"], 0)
        self.assertEqual(rows["Saka"]["untradeable"], 1)

    def test_picks_players_out_of_surrounding_noise(self):
        payload = {"meta": {"v": 1}, "filters": [{"id": 1}], "squad": {"players": [
            {"name": "A", "rating": 84}, {"name": "B", "rating": 85}]}}
        self.assertEqual(len(club.load(payload)), 2)

    def test_accepts_a_json_string(self):
        import json as _json
        self.assertEqual(len(club.load(_json.dumps(self.FLAT))), 2)

    def test_rejects_non_json(self):
        with self.assertRaises(club.ClubImportError):
            club.load("<html>blocked</html>")

    def test_rejects_a_payload_with_no_players(self):
        with self.assertRaises(club.ClubImportError):
            club.load({"settings": {"theme": "dark"}})

    def test_store_and_inventory(self):
        club.store(self.conn, club.load(self.FLAT))
        inv = {r["rating"]: r for r in club.inventory(self.conn)}
        self.assertEqual(inv[89]["tradeable"], 1)
        self.assertEqual(inv[87]["untradeable"], 1)

    def test_import_replaces_rather_than_accumulates(self):
        club.store(self.conn, club.load(self.FLAT))
        club.store(self.conn, club.load(self.FLAT))
        self.assertEqual(sum(r["total"] for r in club.inventory(self.conn)), 2)

    def test_value_excludes_untradeable_cards(self):
        club.store(self.conn, club.load(self.FLAT))
        v = club.value(self.conn)
        # Only Rodri is sellable, and the 5% tax comes off.
        self.assertEqual(v["gross"], 200_000)
        self.assertEqual(v["after_tax"], 190_000)
        self.assertEqual(v["tradeable_cards"], 1)

    def test_prices_in_the_capture_are_recorded(self):
        info = club.store(self.conn, club.load(self.FLAT))
        self.assertEqual(info["with_prices"], 1)

    def test_fodder_gaps_report_shortfall(self):
        club.store(self.conn, club.load(self.FLAT))
        fodder.record(self.conn, {87: 4_000, 89: 25_000})
        gaps = {g["rating"]: g for g in club.fodder_gaps(self.conn, need={89: 3})}
        self.assertEqual(gaps[89]["have"], 1)
        self.assertEqual(gaps[89]["short_by"], 2)
        self.assertEqual(gaps[89]["cost_to_fill"], 50_000)
