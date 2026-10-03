import unittest
from costmodel.costs import (SCHEDULES, FeeSchedule, breakeven_move_pct,
                             compare_position_counts, evaluate_setup, round_trip_costs,
                             size_position)

ZERO = FeeSchedule("zero", brokerage_flat=0.0, stt_sell_pct=0, exchange_pct=0,
                   sebi_pct=0, stamp_buy_pct=0)
FLAT10 = SCHEDULES["flat10_user_reported"]
PCT = SCHEDULES["pct_capped_20"]


class CostTests(unittest.TestCase):
    def test_zero_fees_zero_cost(self):
        self.assertEqual(round_trip_costs(500, 510, 4, "LONG", ZERO, 0).total, 0)

    def test_flat_brokerage_two_orders(self):
        c = round_trip_costs(500, 510, 4, "LONG", FLAT10, 0)
        self.assertAlmostEqual(c.brokerage, 20.0)

    def test_stt_only_on_sell_leg(self):
        # LONG: sell at exit price 510
        c = round_trip_costs(500, 510, 4, "LONG", FLAT10, 0)
        self.assertAlmostEqual(c.stt, 510 * 4 * 0.025 / 100)
        # SHORT: sell at entry price 500
        c = round_trip_costs(500, 490, 4, "SHORT", FLAT10, 0)
        self.assertAlmostEqual(c.stt, 500 * 4 * 0.025 / 100)

    def test_pct_brokerage_capped(self):
        small = round_trip_costs(100, 101, 1, "LONG", PCT, 0)
        self.assertLess(small.brokerage, 0.1)
        big = round_trip_costs(10000, 10100, 10, "LONG", PCT, 0)
        self.assertAlmostEqual(big.brokerage, 40.0)  # Rs20 cap hit on each leg

    def test_gst_applies_to_brokerage_exchange_sebi(self):
        c = round_trip_costs(500, 510, 4, "LONG", FLAT10, 0)
        self.assertAlmostEqual(c.gst, 0.18 * (c.brokerage + c.exchange + c.sebi))

    def test_slippage(self):
        c = round_trip_costs(500, 500, 4, "LONG", ZERO, 10)
        self.assertAlmostEqual(c.slippage, 1000 * 4 * 10 / 10000 * 1.0)

    def test_breakeven_makes_net_zero(self):
        be = breakeven_move_pct(500, 4, "LONG", FLAT10, 5)
        exit_ = 500 * (1 + be / 100)
        gross = (exit_ - 500) * 4
        net = gross - round_trip_costs(500, exit_, 4, "LONG", FLAT10, 5).total
        self.assertAlmostEqual(net, 0, places=4)

    def test_flat_fee_breakeven_much_worse_on_small_positions(self):
        big = breakeven_move_pct(4000, 1, "LONG", FLAT10)
        small = breakeven_move_pct(400, 1, "LONG", FLAT10)
        self.assertGreater(small, 5 * big)

    def test_position_count_comparison_flat_fee_penalises_splitting(self):
        rows = compare_position_counts(4000, [1, 10], 0.8, FLAT10)
        self.assertLess(rows[1]["net_if_all_hit"], rows[0]["net_if_all_hit"])
        self.assertLess(rows[1]["net_if_all_hit"], 0)

    def test_sizing_respects_risk_budget_including_costs(self):
        q = size_position(4000, 0.5, 500, 495, 510, PCT)
        loss = 5 * q + round_trip_costs(500, 495, q, "LONG", PCT, 5).total if q else 0
        self.assertLessEqual(loss, 20.0)

    def test_sizing_no_leverage(self):
        q = size_position(4000, 5.0, 500, 499, 502, PCT)
        self.assertLessEqual(q * 500, 4000)

    def test_zero_qty_rejected(self):
        ev = evaluate_setup(5000, 4990, 5020, 0, PCT)
        self.assertEqual(ev.verdict, "REJECT")

    def test_reject_when_costs_eat_reward(self):
        ev = evaluate_setup(500, 495, 503, 4, FLAT10)
        self.assertEqual(ev.verdict, "REJECT")

    def test_bad_stop_side_raises(self):
        with self.assertRaises(ValueError):
            evaluate_setup(500, 505, 510, 4, FLAT10)

    def test_negative_ev_rejected(self):
        ev = evaluate_setup(500, 495, 515, 4, PCT, p_win=0.2)
        self.assertEqual(ev.verdict, "REJECT")


if __name__ == "__main__":
    unittest.main()