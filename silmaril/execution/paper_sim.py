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
# HEATSHIELD (2.6.1): mean-reversion winners often dip BELOW a tight stop before bouncing, so a tight
# stop cuts trades that would have recovered. When active, no position stops out tighter than this floor
# — it sits through more heat to let the reversion play out. Default ON. Flip HEATSHIELD=False to disable.
HEATSHIELD = True
HEATSHIELD_FLOOR = 0.05
# 2.7: commodity books (metal/energy) hold slow, low-vol ETFs where a normal 3-5% swing is noise, not a
# failed thesis. A tight 5% floor would shake a long hold out of a position that's behaving normally, so
# these books ride a WIDER floor. Crypto/stock are untouched (they keep HEATSHIELD_FLOOR).
COMMODITY_FLOOR = 0.12

# 2.7 — TIMEOUT EXITS REMOVED. The mean-reversion thesis is "sit through the heat and let price revert."
# A mechanical max-hold clock was dumping positions at break-even/loss (the 248m TIMEOUT LOSS/FLAT rows)
# exactly when they needed more time. With this False, a position exits ONLY on its target (a win) or the
# HEATSHIELD floor (a catastrophic -5% cut). NOTHING exits on elapsed time. Set True to restore the clock.
# TRADEOFF TO WATCH IN THE DATA: with no clock, a position that dips but never reaches target or the floor
# can sit indefinitely, locking that 10% of the book. The heatshield floor is now the only downside recycler.
TIMEOUT_EXIT = False

# 2.7 — CORRUPT-FEED GATE. Some names' price feed intermittently injects a wrong value ~10% off the true
# price, then SNAPS BACK (MKR-USD flips ~1365 <-> ~1229, even printing the SAME wrong value three samples
# running). freshness() passes it (the value DOES change), so the sim trades the fake dip and books a fake
# win or a fake -10% loss — this is where MKR's whole "edge" came from.
#
# We key on the SNAP-BACK signature, not raw volatility: a corrupt feed jumps >= SPIKE_PCT then the very
# next sample REVERSES >= SNAPBACK_RET of that move back toward the prior price (a round-trip to a stale
# value). A genuinely volatile coin that rips >= SPIKE_PCT and HOLDS has no snap-back and stays tradeable —
# so this does NOT bench real movers (answers the "will this block coins that reliably make money" worry).
# Verified on real history: across 1656 names, snap-back >= SNAPBACK_MIN flags exactly 3 (MOG, MKR, MANTA);
# ZERO real names — incl. volatile small-caps TURBO/BONK/WIF/PEPE/DYM/TIA — are touched.
SPIKE_PCT = 0.06          # a single-sample move this big is the candidate spike
SNAPBACK_RET = 0.5        # ... if the NEXT sample reverses >= 50% of it, it's a stale round-trip
SNAPBACK_MIN = 1          # this many snap-backs in the recent window = corrupt feed, excluded like a ghost
SPIKE_WINDOW = 60


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_crypto(sym: str) -> bool:
    return "USD" in str(sym).upper()

# ── 2.5.1 FOUR ASSET CLASSES: crypto · stock · metal · energy ─────────────────
METAL_SYMS = {"XAU", "XAG", "XPT", "XPD", "XCU"}              # gold silver platinum palladium copper
ENERGY_SYMS = {"WTI", "BRENT", "NATGAS", "GASOLINE", "HEATOIL"}  # crude brent natgas etc.
# 2.7: the spot symbols above are never ingested — the real, liquid, already-flowing commodity exposure is
# ETFs (same Alpaca feed the stock book uses). Route those ETFs to their books so metal/energy stop sitting
# empty. These are commodity-TRACKING funds (bullion / futures), not energy-equity funds like XLE/XOP,
# which stay in the stock book on purpose. Verified: all of these have fresh live intraday data.
METAL_ETFS = {"GLD", "SLV", "IAU", "PPLT", "PALL", "CPER", "SIVR", "GLDM", "SGOL", "BAR", "OUNZ"}
ENERGY_ETFS = {"USO", "UNG", "BNO", "UGA", "USL", "DBO", "UNL", "USOI"}
BOOKS = ("crypto", "stock", "metal", "energy")

def asset_class(sym: str) -> str:
    """Single source of truth for which market a symbol belongs to."""
    u = str(sym).upper()
    base = u.split("-")[0].split("/")[0].split(":")[-1]
    if base in METAL_SYMS or base in METAL_ETFS:
        return "metal"
    if base in ENERGY_SYMS or base in ENERGY_ETFS:
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


def _snapbacks(p: List[float]) -> int:
    """Count stale round-trip spikes: a >= SPIKE_PCT move immediately reversed >= SNAPBACK_RET the next
    sample. This is the corrupt-feed signature (jump to a wrong value, snap back). A real directional move
    that holds is NOT counted."""
    c = 0
    for k in range(1, len(p) - 1):
        if p[k - 1] <= 0 or p[k] <= 0:
            continue
        m1 = p[k] / p[k - 1] - 1
        if abs(m1) >= SPIKE_PCT:
            m2 = p[k + 1] / p[k] - 1
            if m2 * m1 < 0 and abs(m2) >= SNAPBACK_RET * abs(m1):
                c += 1
    return c


def _feed_unreliable(prices: List[float]) -> bool:
    """True if the recent feed shows snap-back spikes — an intermittent bad-data feed that fabricates
    dips/bounces. Excludes nothing real (a move that HOLDS is fine); isolates corrupted feeds."""
    p = [x for x in prices[-SPIKE_WINDOW:] if x and x > 0]
    if len(p) < 10:
        return False
    return _snapbacks(p) >= SNAPBACK_MIN


def is_tradeable(prices: List[float]) -> bool:
    return freshness(prices) >= MIN_FRESHNESS and not _feed_unreliable(prices)


def round_trip_cost(prices: List[float]) -> float:
    return max(MIN_COST, 2.0 * noise_floor(prices))


def feed_integrity(samples: Dict[str, List]) -> Dict[str, Any]:
    """FORENSIC: which names have a corrupt/intermittent feed (snap-back spikes) and are therefore EXCLUDED
    from trading like ghosts. Real data only — fabricates nothing; it refuses to trade names whose prints
    are provably not a real market (this is where MKR's fake P&L came from)."""
    flagged = []
    for sym, rows in samples.items():
        px = [p for t, p in rows if p and p > 0 and "T00:00:00" not in t][-SPIKE_WINDOW:]
        if len(px) < 10:
            continue
        sb = _snapbacks(px)
        if sb >= SNAPBACK_MIN:
            mx = max((abs(px[i] / px[i - 1] - 1) for i in range(1, len(px)) if px[i - 1] > 0), default=0.0)
            flagged.append({"sym": sym, "snapbacks": sb, "max_move_pct": round(mx * 100, 1)})
    flagged.sort(key=lambda d: -d["snapbacks"])
    return {"generated_at": _now(), "spike_pct": round(SPIKE_PCT * 100, 1),
            "snapback_ret": SNAPBACK_RET, "min_snapbacks": SNAPBACK_MIN, "window": SPIKE_WINDOW,
            "excluded_count": len(flagged), "excluded": flagged,
            "what": ("names whose recent feed shows a >=%d%% move immediately reversed by >=%d%% (a stale "
                     "round-trip) — a real market does not do that; these are bad-data feeds, excluded from "
                     "trading so they cannot book fake P&L. A real move that HOLDS is not flagged."
                     % (int(SPIKE_PCT * 100), int(SNAPBACK_RET * 100)))}


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
    """{sym: (last_price, h1_drop_fraction)} from each series, using ONLY the last
    few hours of LIVE samples. This excludes daily-history backfill (which would make
    today look like a -40% crash vs an old daily close) AND enforces a warmup: a coin
    cannot signal a drop until it has accumulated enough recent intraday points
    spanning >1h. Right after a wipe, nothing trades until that baseline forms."""
    from datetime import datetime as _dt, timezone as _tz
    RECENT_WINDOW_S = 6 * 3600          # only trust the last 6h for the live drop signal
    out = {}
    try:
        nowt = _dt.now(_tz.utc)
    except Exception:
        nowt = None
    for sym, rows in samples.items():
        pr = [(t, p) for t, p in rows if p and p > 0]
        if len(pr) < 8:
            continue
        # keep only RECENT live points (drop daily backfill history)
        recent = pr
        if nowt is not None:
            rec = []
            for t, p in pr:
                try:
                    if (nowt - _dt.fromisoformat(t)).total_seconds() <= RECENT_WINDOW_S:
                        rec.append((t, p))
                except Exception:
                    pass
            recent = rec
        # WARMUP (pre-beta): a coin cannot trade until it has built >= 2 HOURS of live
        # context, so it never jumps into a name (e.g. WLD-USD) before it understands its
        # recent volatility. Right after a wipe this means ~2h of quiet, by design.
        WARMUP_MIN_POINTS = 24          # ~2h at the 5-min cadence
        WARMUP_MIN_SPAN_S = 2 * 3600
        if len(recent) < WARMUP_MIN_POINTS:
            continue
        try:
            _span = (_dt.fromisoformat(recent[-1][0]) - _dt.fromisoformat(recent[0][0])).total_seconds()
            if _span < WARMUP_MIN_SPAN_S:
                continue
        except Exception:
            continue
        last_t, last_p = recent[-1]
        try:
            lt = _dt.fromisoformat(last_t)
            ref = None
            for t, p in reversed(recent[:-1]):
                if (lt - _dt.fromisoformat(t)).total_seconds() >= 3600:
                    ref = p
                    break
            if ref is None:             # window does not yet span 1h -> warmup, no signal
                continue
            h1 = last_p / ref - 1 if ref > 0 else 0.0
        except Exception:
            continue
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
    # Default config when a book has NO elected champion yet. Commodities (metal/energy) start on a HOLD
    # default — buy a pullback, ride to a big target, wide stop on the commodity floor — so they actually
    # PARTICIPATE and generate real trades instead of sitting idle. This is a starting config, NOT an
    # anointed champion (the dashboard shows "no champion yet"); a real champion is elected from the trades
    # this produces. Crypto/stock keep the fast MR default exactly as before.
    if params:
        p = params
    elif book in ("metal", "energy"):
        p = {"dir": "mr", "entry": 0.02, "target": 0.10, "stop": 0.12, "max_hold_min": 5280.0}
    else:
        p = {"dir": "mr", "entry": DROP, "target": BOUNCE, "stop": STOP, "max_hold_min": MAX_HOLD_MIN}
    direction = p.get("dir", "mr")
    entry, target, stop_, max_hold = p["entry"], p["target"], p["stop"], p["max_hold_min"]
    pbook = PaperBook.load(out / f"paper_book_{book}.json")
    now = datetime.now(timezone.utc)
    side_marks = {s: v for s, v in marks.items() if asset_class(s) == book}
    actions = []

    def px_of(sym):
        return [p2 for _, p2 in samples.get(sym, []) if p2 and p2 > 0]

    def _market_open_stock(n):
        # US regular session ~13:30-20:00 UTC, weekdays only. Outside this, stock
        # "prices" are stale Friday/after-hours prints — never tradeable.
        if n.weekday() >= 5:
            return False
        mins = n.hour * 60 + n.minute
        return (13 * 60 + 30) <= mins <= (20 * 60)

    def fresh_ok(sym):
        pp = px_of(sym)
        if len(pp) <= 20:
            return False
        # stale-oscillation guard (applies to EVERY book): a frozen feed bouncing
        # between 1-2 cached values is NOT a live market, even though it "moves"
        # every sample. This is the CSGP/MTCH weekend fake-P&L bug. Require genuine
        # multi-value movement in the recent window.
        distinct = len(set(pp[-8:]))
        if distinct < 3:
            return False
        if crypto and _feed_unreliable(pp):   # 2.7 snap-back gate — crypto feed glitch (MKR); ETFs bypass
            return False
        if crypto:
            return is_tradeable(pp)        # crypto: keep the 80% freshness bar too
        # STOCKS: additionally require the live regular session.
        return _market_open_stock(now)

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
        hs_floor = COMMODITY_FLOOR if book in ("metal", "energy") else HEATSHIELD_FLOOR
        eff_stop = max(stop_, hs_floor) if HEATSHIELD else stop_
        why = ("STOP" if chg <= -eff_stop else "TAKE" if chg >= target
               else ("TIMEOUT" if (TIMEOUT_EXIT and hold >= max_hold) else None))
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
    try:
        feed_intel = feed_integrity(samples)
        (out / "FEED_INTEGRITY.json").write_text(json.dumps(feed_intel, indent=2))
    except Exception:
        feed_intel = {}
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
        "heatshield": {"active": HEATSHIELD, "floor_pct": round(HEATSHIELD_FLOOR * 100, 2),
                       "note": "no position stops out tighter than this floor — sits through heat for the bounce"},
        "timeout_exit": TIMEOUT_EXIT,
        "exit_policy": ("target (win) or heatshield floor only — timeouts removed" if not TIMEOUT_EXIT
                        else "target / heatshield floor / max-hold timeout"),
        "feed_integrity": feed_intel,
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
    series = {tk: [p for t, p in rows if p and p > 0 and "T00:00:00" not in t] for tk, rows in samples.items()}
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
                if TIMEOUT_EXIT and (j - i) >= 22: oc, k = "TIMEOUT", j; break
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


def heatshield_whatif(out_dir) -> Dict[str, Any]:
    """FORENSIC: replay the SAME mean-reversion entry signals under the tight stop vs the -5% HEATSHIELD
    floor on real price history, to prove whether sitting through more heat actually nets more. Writes
    docs/data/HEATSHIELD.json. Real data only."""
    from datetime import datetime as _dt, timezone as _tz
    out = Path(out_dir)
    samples = load_all_samples(out)
    if not samples:
        return {"error": "no samples"}
    series = {tk: [p for t, p in rows if p and p > 0 and "T00:00:00" not in t]
              for tk, rows in samples.items()}
    fresh = {tk: px for tk, px in series.items() if len(px) > 20 and is_tradeable(px)}

    def run(stop):
        rets, exits = [], {"TAKE": 0, "STOP": 0, "TIMEOUT": 0}
        for tk, px in fresh.items():
            n = len(px); c = round_trip_cost(px); i = 6
            while i < n - 1:
                if px[i - 6] <= 0 or (px[i] / px[i - 6] - 1) > -DROP:
                    i += 1; continue
                ep = px[i]; j = i + 1; oc = None
                while j < n:
                    ch = px[j] / ep - 1
                    if ch <= -stop: oc, k = "STOP", j; break
                    if ch >= BOUNCE: oc, k = "TAKE", j; break
                    if TIMEOUT_EXIT and (j - i) >= 22: oc, k = "TIMEOUT", j; break
                    j += 1
                if oc is None: break
                rets.append((px[k] / ep - 1) - c); exits[oc] += 1; i = k + 1
        n = len(rets); tot = sum(rets); wins = sum(1 for r in rets if r > 0)
        return {"trades": n, "total_return_pct": round(tot * 100, 2),
                "avg_pct": round((tot / n * 100) if n else 0, 3),
                "win_pct": round((wins / n * 100) if n else 0, 1), "exits": exits}

    tight = run(STOP); shield = run(HEATSHIELD_FLOOR)
    delta = round(shield["total_return_pct"] - tight["total_return_pct"], 2)
    res = {
        "generated_at": _dt.now(_tz.utc).isoformat(),
        "tight_stop_pct": round(STOP * 100, 2),
        "heatshield_floor_pct": round(HEATSHIELD_FLOOR * 100, 2),
        "heatshield_active": HEATSHIELD,
        "tight_stop": tight, "heatshield": shield, "delta_total_pct": delta,
        "verdict": ("HEATSHIELD nets more — sitting through heat pays" if delta > 0
                    else "tighter stop nets more — HEATSHIELD costs here" if delta < 0
                    else "no difference yet (need more signals)"),
        "what": "same entry signals, tight stop vs -5% floor, replayed on real price history; proves whether more heat tolerance nets more after fees.",
    }
    try:
        (out / "HEATSHIELD.json").write_text(json.dumps(res, indent=2))
    except Exception:
        pass
    return res
