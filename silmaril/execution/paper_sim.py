"""
silmaril.execution.paper_sim — internal paper-trading engine (Alpha 2.12).

The idea you loved: bring execution IN-HOUSE so we can simulate the FULL universe
(stocks + crypto, side by side), true to life with fees, every cycle — without
Alpaca's ~20-coin cap and without waiting on a broker's paper mode. This is the
fast iteration loop: test any strategy on the whole universe, see the honest P&L,
change it, run again.

Two honesty rules are baked in, because the full universe is a minefield:

  1. FRESHNESS FILTER ("excluding the ghosts"). ~92% of the 3000+ crypto universe
     is STALE — the price sits frozen for long stretches, then jumps when it
     finally updates. A backtest reads that frozen-then-jump as a "drop then
     bounce" and prints a fantasy +2000%. But you can't fill an order at a frozen
     quote, so those names are NOT tradeable. Any coin whose price doesn't move in
     >=`MIN_FRESHNESS` of recent samples is excluded. Those are the ghosts. It is
     a FEATURE — trading them is trading noise.

  2. HONEST PER-COIN FEES. Each fill is charged max(`MIN_COST`, 2x the coin's own
     noise floor). A volatile mid-cap does NOT trade at a major's tight spread,
     and a stale coin doesn't get a zero-cost free lunch. This single number
     decides profitability, so the sim refuses to flatter it.

Hard truth this file cannot fix: a sim's P&L is only as good as its fee/fill
model. Real fills add slippage, partial fills, latency and market impact — which
is exactly where most paper-to-live transitions disappoint. This tool tells you
whether a strategy has *any* edge worth taking live; it cannot promise the live
number will match. Treat a good sim result as "worth a real-money-prices test,"
never as "this is income."
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any, Dict, List, Optional, Tuple

MIN_FRESHNESS = 0.80
MIN_COST = 0.002          # 0.2% round-trip floor (stocks tight; crypto wider)
FRESHNESS_LOOKBACK = 60
START_CASH = 10000.0
PER_NAME_FRAC = 0.10      # 10% of the book per position
MAX_NAMES = 10
# mean-reversion params (the proven-direction strategy; tune in one place)
DROP, BOUNCE, STOP, MAX_HOLD_MIN = 0.02, 0.02, 0.04, 240.0


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_crypto(sym: str) -> bool:
    return "USD" in str(sym).upper()

# ── 2.5.1 FOUR ASSET CLASSES: crypto · stock · metal · energy ─────────────────
METAL_SYMS = {"XAU", "XAG", "XPT", "XPD", "XCU"}              # gold silver platinum palladium copper
ENERGY_SYMS = {"WTI", "BRENT", "NATGAS", "GASOLINE", "HEATOIL"}  # crude brent natgas etc.
BOOKS = ("crypto", "stock", "metal", "energy")

def asset_class(sym: str) -> str:
    """Single source of truth for which market a symbol belongs to."""
    u = str(sym).upper()
    base = u.split("-")[0].split("/")[0].split(":")[-1]
    if base in METAL_SYMS:
        return "metal"
    if base in ENERGY_SYMS:
        return "energy"
    return "crypto" if _is_crypto(sym) else "stock"



# ── tradeability gates ───────────────────────────────────────────────────────
def freshness(prices: List[float]) -> float:
    p = [x for x in prices[-FRESHNESS_LOOKBACK:] if x and x > 0]
    if len(p) < 5:
        return 0.0
    return sum(1 for i in range(1, len(p)) if p[i] != p[i - 1]) / (len(p) - 1)


def noise_floor(prices: List[float]) -> float:
    p = [x for x in prices[-FRESHNESS_LOOKBACK:] if x and x > 0]
    rr = [abs(p[i] / p[i - 1] - 1) for i in range(1, len(p)) if p[i - 1] > 0]
    return median(rr) if rr else 0.0


def is_tradeable(prices: List[float]) -> bool:
    return freshness(prices) >= MIN_FRESHNESS


def round_trip_cost(prices: List[float]) -> float:
    return max(MIN_COST, 2.0 * noise_floor(prices))


def load_all_samples(out) -> Dict[str, List]:
    """Merge the system's own price_samples with the CCXT-widened universe so the
    sim/leaderboard test hundreds of fresh names, not 52. The live executor does
    NOT use this — it stays on price_samples only (Alpaca-safe)."""
    out = Path(out)
    merged: Dict[str, List] = {}
    for fn in ("price_samples.json", "ccxt_samples.json", "metals_samples.json", "energy_samples.json"):
        try:
            s = json.loads((out / fn).read_text()).get("samples", {})
            merged.update(s)
        except Exception:
            pass
    return merged


def _marks_from_samples(samples: Dict[str, List]) -> Dict[str, tuple]:
    """{sym: (last_price, h1_drop_fraction)} computed straight from each series by
    timestamp (works across cadences: 11-min system samples and 5-min CCXT)."""
    from datetime import datetime as _dt
    out = {}
    for sym, rows in samples.items():
        pr = [(t, p) for t, p in rows if p and p > 0]
        if len(pr) < 8:
            continue
        last_t, last_p = pr[-1]
        try:
            lt = _dt.fromisoformat(last_t)
            ref = last_p
            for t, p in reversed(pr[:-1]):
                if (lt - _dt.fromisoformat(t)).total_seconds() >= 3600:
                    ref = p
                    break
            h1 = last_p / ref - 1 if ref > 0 else 0.0
        except Exception:
            h1 = last_p / pr[-7][1] - 1 if pr[-7][1] > 0 else 0.0
        out[sym] = (last_p, h1)
    return out


# ── the paper book ───────────────────────────────────────────────────────────
class PaperBook:
    def __init__(self, cash: float = START_CASH):
        self.cash = float(cash)
        self.positions: Dict[str, Dict[str, Any]] = {}
        self.realized_pnl = 0.0
        self.trades: List[Dict[str, Any]] = []

    def buy(self, sym, dollars, price, cost, t=None):
        if price <= 0 or dollars <= 0 or dollars > self.cash + 1e-9:
            return False
        eff = price * (1 + cost / 2.0)
        qty = dollars / eff
        self.cash -= dollars
        self.positions[sym] = {"qty": qty, "entry": eff, "cost": cost, "t": t or _now()}
        self.trades.append({"side": "BUY", "sym": sym, "qty": round(qty, 6),
                            "price": round(eff, 6), "t": t or _now()})
        return True

    def sell(self, sym, price, t=None):
        pos = self.positions.get(sym)
        if not pos or price <= 0:
            return 0.0
        eff = price * (1 - pos["cost"] / 2.0)
        proceeds = pos["qty"] * eff
        pnl = proceeds - pos["qty"] * pos["entry"]
        self.cash += proceeds
        self.realized_pnl += pnl
        self.trades.append({"side": "SELL", "sym": sym, "qty": round(pos["qty"], 6),
                            "price": round(eff, 6), "pnl": round(pnl, 2), "t": t or _now()})
        del self.positions[sym]
        return pnl

    def equity(self, marks):
        held = sum(p["qty"] * marks.get(s, p["entry"]) for s, p in self.positions.items())
        return self.cash + held

    def save(self, path):
        Path(path).write_text(json.dumps({
            "cash": self.cash, "realized_pnl": self.realized_pnl,
            "positions": self.positions, "trades": self.trades[-800:],
            "updated_at": _now()}, indent=2))

    @classmethod
    def load(cls, path, cash=START_CASH):
        try:
            d = json.loads(Path(path).read_text())
            b = cls(d.get("cash", cash))
            b.realized_pnl = d.get("realized_pnl", 0.0)
            b.positions = d.get("positions", {})
            b.trades = d.get("trades", [])
            return b
        except Exception:
            return cls(cash)


# ── live one-cycle trade, per side, off the chain ────────────────────────────
def _chain(out) -> Dict[str, Tuple[float, float]]:
    """{symbol: (last_price, h1_drop_fraction)} from the momentum chain."""
    try:
        ch = json.loads((Path(out) / "momentum_chain.json").read_text()).get("chains", {})
    except Exception:
        return {}
    res = {}
    for sym, c in ch.items():
        lp = c.get("last_price")
        h1 = (c.get("windows") or {}).get("h1")
        if lp and lp > 0 and h1 is not None:
            res[sym] = (float(lp), float(h1) / 100.0)
    return res


def _run_side(out, marks, samples, book: str, params=None) -> Dict[str, Any]:
    crypto = (book == "crypto")
    p = params or {"dir": "mr", "entry": DROP, "target": BOUNCE, "stop": STOP,
                   "max_hold_min": MAX_HOLD_MIN}
    direction = p.get("dir", "mr")
    entry, target, stop_, max_hold = p["entry"], p["target"], p["stop"], p["max_hold_min"]
    pbook = PaperBook.load(out / f"paper_book_{book}.json")
    now = datetime.now(timezone.utc)
    side_marks = {s: v for s, v in marks.items() if asset_class(s) == book}
    actions = []

    def px_of(sym):
        return [p2 for _, p2 in samples.get(sym, []) if p2 and p2 > 0]

    def fresh_ok(sym):
        pp = px_of(sym)
        if len(pp) <= 20:
            return False
        if crypto:
            return is_tradeable(pp)        # crypto path UNCHANGED (24/7, 80% bar)
        # STOCKS: the crypto 80%-of-all-intervals freshness bar is structurally
        # impossible — stocks only quote ~6.5h of 24 (and not on weekends), so they
        # are "frozen" most of the time and were ALL rejected (0/536). Instead, treat
        # a stock as tradeable when it is ACTIVELY quoting right now — its price has
        # moved within the last few samples — which naturally gates to market hours.
        recent = pp[-6:]
        return len(set(recent)) > 1

    # EXITS — target / stop / timeout (same for either direction once we're long)
    for sym in list(pbook.positions.keys()):
        if asset_class(sym) != book:
            continue
        pos = pbook.positions[sym]
        cur = side_marks.get(sym, (pos["entry"], 0))[0]
        chg = cur / pos["entry"] - 1 if pos["entry"] > 0 else 0
        try:
            hold = (now - datetime.fromisoformat(pos["t"])).total_seconds() / 60.0
        except Exception:
            hold = 0.0
        why = ("STOP" if chg <= -stop_ else "TAKE" if chg >= target
               else "TIMEOUT" if hold >= max_hold else None)
        if why:
            pnl = pbook.sell(sym, cur, now.isoformat())
            actions.append({"act": "SELL", "sym": sym, "why": f"{why} {chg*100:+.1f}%",
                            "pnl": round(pnl, 2)})

    # ENTRIES — mean-reversion buys dips (deepest first); momentum buys strength
    if direction == "mom":
        cands = sorted([(s, lp, h1) for s, (lp, h1) in side_marks.items()
                        if h1 >= entry and s not in pbook.positions and fresh_ok(s)],
                       key=lambda x: x[2], reverse=True)
    else:
        cands = sorted([(s, lp, h1) for s, (lp, h1) in side_marks.items()
                        if h1 <= -entry and s not in pbook.positions and fresh_ok(s)],
                       key=lambda x: x[2])
    mk = {s: v[0] for s, v in side_marks.items()}
    for sym, lp, h1 in cands[:MAX_NAMES]:
        budget = min(pbook.equity(mk) * PER_NAME_FRAC, pbook.cash * 0.95)
        if pbook.buy(sym, budget, lp, round_trip_cost(px_of(sym)), now.isoformat()):
            actions.append({"act": "BUY", "sym": sym, "move_pct": round(h1 * 100, 2)})

    pbook.save(out / f"paper_book_{book}.json")
    eq = pbook.equity(mk)
    return {
        "equity": round(eq, 2),
        "cash": round(pbook.cash, 2),
        "realized_pnl": round(pbook.realized_pnl, 2),
        "return_pct": round((eq / START_CASH - 1) * 100, 2),
        "open_positions": len(pbook.positions),
        "positions": [{"sym": s, "qty": round(p["qty"], 4), "entry": round(p["entry"], 6),
                       "mark": round(side_marks.get(s, (p["entry"], 0))[0], 6),
                       "upl_pct": round((side_marks.get(s, (p["entry"], 0))[0] / p["entry"] - 1) * 100, 2)}
                      for s, p in pbook.positions.items()],
        "recent_trades": pbook.trades[-25:][::-1],
        "tradeable_universe": sum(1 for s in side_marks if fresh_ok(s)),
        "universe_seen": len(side_marks),
    }


def live_step(out_dir) -> Dict[str, Any]:
    """One paper-trading cycle for BOTH sides. Persists each book and emits the
    cockpit summary docs/data/paper_sim_live.json."""
    out = Path(out_dir)
    samples = load_all_samples(out)
    marks = _marks_from_samples(samples)
    # CHAMPION MODE: trade whatever the champion currently is on the crypto side
    champ_params = None
    champ_name = None
    try:
        from .champion import champion_params
        champ_params = champion_params(out)
        champ_name = json.loads((out / "champion.json").read_text()).get("champion")
    except Exception:
        pass
    # per-book champions (2.5.1): every book trades its OWN arena champion —
    # crypto, stock, metal, energy are independent. champion_crypto = champion.json.
    results, champ_names = {}, {}
    for bk in BOOKS:
        if bk == "crypto":
            params, name = champ_params, champ_name
        else:
            try:
                sc = json.loads((out / f"champion_{bk}.json").read_text())
                params, name = sc.get("live_params"), sc.get("champion")
            except Exception:
                params, name = None, None
        results[bk] = _run_side(out, marks, samples, bk, params)
        champ_names[bk] = name
    crypto, stock = results["crypto"], results["stock"]
    # 3-day backtest proof so the cockpit shows the engine works even when the
    # live tape is quiet and no setup is firing this exact cycle
    try:
        bt = backtest_through_sim(out, crypto_only=True)
    except Exception:
        bt = {}
    summary = {
        "generated_at": _now(),
        "start_cash_each": START_CASH,
        "champion_strategy": champ_name,
        "champion_crypto": champ_names["crypto"],
        "champion_stock": champ_names["stock"],
        "champion_metal": champ_names["metal"],
        "champion_energy": champ_names["energy"],
        "champion_live_params": champ_params,
        "strategy": (f"CHAMPION: {champ_name}" if champ_name else
                     "mean_reversion (default — champion not set yet)"),
        "params": {"drop": DROP, "bounce": BOUNCE, "stop": STOP, "max_hold_min": MAX_HOLD_MIN,
                   "per_name_frac": PER_NAME_FRAC, "min_freshness": MIN_FRESHNESS,
                   "min_cost": MIN_COST},
        "crypto": crypto, "stock": stock,
        "metal": results["metal"], "energy": results["energy"],
        "combined_equity": round(sum(results[b]["equity"] for b in BOOKS), 2),
        "combined_realized_pnl": round(sum(results[b]["realized_pnl"] for b in BOOKS), 2),
        "backtest_3day_crypto": bt,
        "note": ("Internal paper sim, 4 independent books (crypto/stock/metal/energy). "
                 "Ghosts excluded; fees = max(0.2%, 2x noise floor). Metal/energy stay "
                 "empty until their data feed is wired (metals_samples.json / energy_samples.json)."),
    }
    try:
        (out / "paper_sim_live.json").write_text(json.dumps(summary, indent=2))
    except Exception:
        pass
    return summary


# ── historical backtest through the sim (per side) ───────────────────────────
def backtest_through_sim(out_dir, crypto_only: Optional[bool] = None) -> Dict[str, Any]:
    out = Path(out_dir)
    samples = load_all_samples(out)
    if not samples:
        return {"error": "no samples"}
    series = {tk: [p for _, p in rows if p and p > 0] for tk, rows in samples.items()}
    fresh = {tk: px for tk, px in series.items()
             if len(px) > 20 and is_tradeable(px)
             and (crypto_only is None or _is_crypto(tk) == crypto_only)}
    rets, exits = [], {"TAKE": 0, "STOP": 0, "TIMEOUT": 0}
    for tk, px in fresh.items():
        n = len(px); c = round_trip_cost(px); i = 6
        while i < n - 1:
            if px[i - 6] <= 0 or (px[i] / px[i - 6] - 1) > -DROP:
                i += 1; continue
            ep = px[i]; j = i + 1; oc = None
            while j < n:
                ch = px[j] / ep - 1
                if ch <= -STOP: oc, k = "STOP", j; break
                if ch >= BOUNCE: oc, k = "TAKE", j; break
                if (j - i) >= 22: oc, k = "TIMEOUT", j; break
                j += 1
            if oc is None: break
            rets.append((px[k] / ep - 1) - c); exits[oc] += 1; i = k + 1
    if not rets:
        return {"tradeable": len(fresh), "trades": 0}
    eq = START_CASH
    for r in rets:
        eq *= (1 + r * PER_NAME_FRAC)
    return {"universe_total": len(series), "tradeable": len(fresh),
            "ghosts_excluded": len(series) - len(fresh), "trades": len(rets),
            "win_rate_pct": round(sum(1 for r in rets if r > 0) / len(rets) * 100, 1),
            "mean_net_pct": round(sum(rets) / len(rets) * 100, 3),
            "exits": exits, "equity_after": round(eq, 2)}


if __name__ == "__main__":
    import sys
    a = sys.argv[1] if len(sys.argv) > 1 else "docs/data"
    print("BACKTEST:", json.dumps(backtest_through_sim(a)))
    print("LIVE STEP:", json.dumps(live_step(a))[:400])
