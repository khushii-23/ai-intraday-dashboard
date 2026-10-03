"""Intraday equity cost model and setup evaluator.

All fee numbers live in FeeSchedule objects and are INPUTS, not facts. Rates change
(exchange charges, STT, broker plans, promos). Check your broker's pricing page and
edit the schedules below before trusting any output.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass(frozen=True)
class FeeSchedule:
    name: str
    # Brokerage: either flat per order, or pct of turnover capped per order.
    brokerage_flat: float | None = None
    brokerage_pct: float = 0.0      # percent of turnover, e.g. 0.03 means 0.03%
    brokerage_cap: float = float("inf")
    # Statutory/exchange charges (percent of turnover). Defaults are approximate
    # NSE equity-intraday values as I last knew them. VERIFY before use.
    stt_sell_pct: float = 0.025
    exchange_pct: float = 0.00297
    sebi_pct: float = 0.0001
    stamp_buy_pct: float = 0.003
    gst_pct: float = 18.0           # on brokerage + exchange + SEBI
    note: str = ""


# User-editable broker profiles. None of these are verified by this code.
SCHEDULES = {
    "flat10_user_reported": FeeSchedule(
        "Flat Rs10/order (as reported in your project doc; unverified)",
        brokerage_flat=10.0),
    "flat20": FeeSchedule("Flat Rs20/order", brokerage_flat=20.0),
    "pct_capped_20": FeeSchedule(
        "0.03% or Rs20, whichever lower (common discount-broker style; verify)",
        brokerage_pct=0.03, brokerage_cap=20.0),
    # Upstox's own calculator page (2026) lists Rs20 or 0.1%, whichever lower; other sites
    # list 0.05% or flat Rs20. CONFIRM IN YOUR APP before relying on it.
    "upstox_0.1pct_cap20": FeeSchedule(
        "Upstox per its own page: 0.1% or Rs20, whichever lower (confirm in app)",
        brokerage_pct=0.1, brokerage_cap=20.0, exchange_pct=0.00345),
    # Confirmed from the user's Upstox account screen (Plus plan active):
    # intraday = Rs30 or 0.10% per order, whichever lower. Basic plan = Rs20 cap.
    "upstox_plus": FeeSchedule("Upstox Plus: 0.10% or Rs30 (from account screen)",
                               brokerage_pct=0.10, brokerage_cap=30.0, exchange_pct=0.00345),
    "upstox_basic": FeeSchedule("Upstox Basic: 0.10% or Rs20 (from account screen)",
                                brokerage_pct=0.10, brokerage_cap=20.0, exchange_pct=0.00345),
    "zerodha_dhan_fyers_0.03pct_cap20": FeeSchedule(
        "Zerodha/Dhan/Fyers style: 0.03% or Rs20, whichever lower (confirm)",
        brokerage_pct=0.03, brokerage_cap=20.0, exchange_pct=0.00345),
    "zero_brokerage": FeeSchedule("Zero brokerage (statutory charges only)",
                                  brokerage_flat=0.0),
}


@dataclass(frozen=True)
class Costs:
    brokerage: float
    stt: float
    exchange: float
    sebi: float
    stamp: float
    gst: float
    slippage: float

    @property
    def charges(self) -> float:
        return self.brokerage + self.stt + self.exchange + self.sebi + self.stamp + self.gst

    @property
    def total(self) -> float:
        return self.charges + self.slippage


def _leg(turnover: float, is_buy: bool, s: FeeSchedule) -> dict:
    if s.brokerage_flat is not None:
        brokerage = s.brokerage_flat
    else:
        brokerage = min(turnover * s.brokerage_pct / 100, s.brokerage_cap)
    exchange = turnover * s.exchange_pct / 100
    sebi = turnover * s.sebi_pct / 100
    return {
        "brokerage": brokerage,
        "stt": 0.0 if is_buy else turnover * s.stt_sell_pct / 100,
        "exchange": exchange,
        "sebi": sebi,
        "stamp": turnover * s.stamp_buy_pct / 100 if is_buy else 0.0,
        "gst": (brokerage + exchange + sebi) * s.gst_pct / 100,
    }


def round_trip_costs(entry: float, exit_: float, qty: int, side: str,
                     schedule: FeeSchedule, slippage_bps: float = 5.0) -> Costs:
    """Costs for one complete intraday trade. side is 'LONG' or 'SHORT'.

    slippage_bps is applied adversely on each leg (entry and exit).
    """
    if qty <= 0 or entry <= 0 or exit_ <= 0:
        raise ValueError("entry, exit and qty must be positive")
    if side not in ("LONG", "SHORT"):
        raise ValueError("side must be LONG or SHORT")
    buy_price, sell_price = (entry, exit_) if side == "LONG" else (exit_, entry)
    buy = _leg(buy_price * qty, True, schedule)
    sell = _leg(sell_price * qty, False, schedule)
    slip = (entry + exit_) * qty * slippage_bps / 10_000
    return Costs(**{k: buy[k] + sell[k] for k in buy}, slippage=slip)


def breakeven_move_pct(entry: float, qty: int, side: str, schedule: FeeSchedule,
                       slippage_bps: float = 5.0) -> float:
    """Price move (in %, in your favour) needed for net P&L = 0. Solved numerically."""
    sign = 1 if side == "LONG" else -1
    lo, hi = 0.0, 0.2  # search 0%..20%
    for _ in range(60):
        mid = (lo + hi) / 2
        exit_ = entry * (1 + sign * mid)
        gross = (exit_ - entry) * qty * sign
        net = gross - round_trip_costs(entry, exit_, qty, side, schedule, slippage_bps).total
        lo, hi = (mid, hi) if net < 0 else (lo, mid)
    return hi * 100


@dataclass(frozen=True)
class SetupEvaluation:
    verdict: str                 # TRADEABLE / REJECT
    reasons: list[str]
    qty: int
    gross_reward: float
    gross_risk: float
    cost_at_target: float
    cost_at_stop: float
    net_reward: float
    net_loss: float
    net_rr: float
    breakeven_pct: float
    cost_share_of_reward: float  # costs / gross reward
    required_win_prob: float     # win rate needed for zero expectancy
    expected_value: float | None = None


def evaluate_setup(entry: float, stop: float, target: float, qty: int,
                   schedule: FeeSchedule, slippage_bps: float = 5.0,
                   min_net_rr: float = 1.5, max_cost_share: float = 0.25,
                   p_win: float | None = None) -> SetupEvaluation:
    side = "LONG" if target > entry else "SHORT"
    if (side == "LONG" and not stop < entry) or (side == "SHORT" and not stop > entry):
        raise ValueError("stop must be on the opposite side of entry from target")
    if qty <= 0:
        return SetupEvaluation("REJECT", ["quantity is zero (capital/risk too small)"],
                               0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1.0)
    sign = 1 if side == "LONG" else -1
    gross_reward = abs(target - entry) * qty
    gross_risk = abs(entry - stop) * qty
    c_t = round_trip_costs(entry, target, qty, side, schedule, slippage_bps).total
    c_s = round_trip_costs(entry, stop, qty, side, schedule, slippage_bps).total
    net_reward = gross_reward - c_t
    net_loss = gross_risk + c_s
    net_rr = net_reward / net_loss if net_loss > 0 else 0.0
    be = breakeven_move_pct(entry, qty, side, schedule, slippage_bps)
    share = c_t / gross_reward if gross_reward > 0 else 1.0
    req_p = net_loss / (net_reward + net_loss) if net_reward > 0 else 1.0
    reasons = []
    if net_reward <= 0:
        reasons.append("target does not cover costs")
    if net_rr < min_net_rr:
        reasons.append(f"net R:R {net_rr:.2f} below minimum {min_net_rr}")
    if share > max_cost_share:
        reasons.append(f"costs are {share:.0%} of gross reward (max {max_cost_share:.0%})")
    ev = None if p_win is None else p_win * net_reward - (1 - p_win) * net_loss
    if ev is not None and ev <= 0:
        reasons.append("expected value after costs is not positive at the given win probability")
    return SetupEvaluation("REJECT" if reasons else "TRADEABLE", reasons, qty,
                           gross_reward, gross_risk, c_t, c_s, net_reward, net_loss,
                           net_rr, be, share, req_p, ev)


def size_position(capital: float, risk_pct: float, entry: float, stop: float,
                  target: float, schedule: FeeSchedule, max_exposure_pct: float = 100.0,
                  slippage_bps: float = 5.0) -> int:
    """Largest qty such that NET loss at the stop (incl. costs) <= risk budget,
    and notional <= max_exposure_pct of capital (no leverage by default)."""
    budget = capital * risk_pct / 100
    side = "LONG" if target > entry else "SHORT"
    qty = min(int(capital * max_exposure_pct / 100 // entry),
              int(budget // abs(entry - stop)))
    while qty > 0:
        loss = abs(entry - stop) * qty + round_trip_costs(
            entry, stop, qty, side, schedule, slippage_bps).total
        if loss <= budget:
            return qty
        qty -= 1
    return 0


def compare_position_counts(capital: float, counts: list[int], target_move_pct: float,
                            schedule: FeeSchedule, slippage_bps: float = 5.0) -> list[dict]:
    """If capital is split equally across N long positions that each hit a target move,
    how much of the gross gain do costs eat? Ignores whole-share rounding."""
    rows = []
    for n in counts:
        per = capital / n
        entry = 100.0
        qty_f = per / entry
        exit_ = entry * (1 + target_move_pct / 100)
        # scale: use qty=1 at price per-share equal to 'per' so turnover = per
        c = round_trip_costs(per, per * (1 + target_move_pct / 100), 1, "LONG",
                             schedule, slippage_bps)
        gross = per * target_move_pct / 100
        rows.append({
            "positions": n, "per_position": round(per, 2),
            "gross_if_all_hit": round(gross * n, 2),
            "total_costs": round(c.total * n, 2),
            "net_if_all_hit": round((gross - c.total) * n, 2),
            "costs_pct_of_gross": round(100 * c.total / gross, 1) if gross else None,
            "breakeven_move_pct": round(breakeven_move_pct(per, 1, "LONG", schedule, slippage_bps), 3),
        })
    return rows