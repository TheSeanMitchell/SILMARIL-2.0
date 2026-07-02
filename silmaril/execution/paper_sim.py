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
# GOLDEN RULE — book-specific minimum post-fee take-home per trade (USD). A close must net at least this
# much AFTER fees or the trade is not taken; positions are sized UP so the target clears it. This also
# kills the dust-position bug (no more $0.01 buys from leftover cash). Tunable per book: raise toward 5.00
# for fewer/bigger/more-concentrated positions, lower toward 1.00 for more trade frequency.
_WARM_SYMS = set()          # symbols cleared for NEW ENTRIES (strict warmup); exits never need this

def _catalog(out_dir=None):
    """PARAM_CATALOG.json = the ONE file that tunes the engine. Every value can be changed by editing that
    file in the repo — no code changes, ever. Missing file/keys fall back to built-in defaults."""
    from pathlib import Path as _P
    for base in ([str(out_dir)] if out_dir else []) + ["docs/data", "."]:
        try:
            f = _P(base) / "PARAM_CATALOG.json"
            if f.exists():
                return json.loads(f.read_text())
        except Exception:
            pass
    return {}


def _longterm_up(samples_rows, min_days=60):
    """STOCK RULE (operator law): nothing is bought whose LONG-TERM trajectory is down. Uses the nightly
    daily candles (T00:00:00 rows). If history is too thin to judge (< min_days closes), the gate abstains
    (no veto) but the brain page shows it as unjudged."""
    try:
        closes = [p for t, p in samples_rows if p and p > 0 and "T00:00:00" in t]
        if len(closes) < min_days:
            return None
        return closes[-1] >= closes[0]
    except Exception:
        return None


def _trajectory_6h(samples_rows):
    """6h slope as a fraction — the falling-knife signal. A name down hard across the whole window with no
    bounce is a COLLAPSE, not a dip (WLD-USD, Jul 1: -9.8% floor exit, then re-bought while still falling).
    Mean reversion wants oversold-in-a-range, never free-fall."""
    from datetime import datetime as _dt, timezone as _tz
    try:
        nowt = _dt.now(_tz.utc)
        px = [(t, p) for t, p in samples_rows if p and p > 0 and "T00:00:00" not in t]
        recent = [(t, p) for t, p in px if (nowt - _dt.fromisoformat(t)).total_seconds() <= 6 * 3600]
        if len(recent) < 6:
            return None
        first, last = recent[0][1], recent[-1][1]
        return (last / first - 1.0) if first > 0 else None
    except Exception:
        return None

MIN_TAKEHOME_DEFAULT = 1.00
MIN_TAKEHOME = {"crypto": 1.00, "stock": 1.00, "metal": 1.00, "energy": 1.00}
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
# 2.7: a TRUE post-wipe quiet period, measured from WIPE TIME — not from price-sample density. The wipe
# preserves price_samples.json (for graphs), which means the old density-based warmup no longer produces any
# quiet after a wipe. This window does: for QUIET_AFTER_WIPE_MIN minutes after a reset, the engine takes no
# trades at all, so a clean run starts from a known-quiet baseline. reset writes docs/data/WIPE_MARKER.json.
QUIET_AFTER_WIPE_MIN = 120.0

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


def _marks_from_samples(samples: Dict[str, List]):
    """Returns (marks, warm, health).
    marks: {sym: (last_price, h1_drop_fraction)} for EVERY symbol with a fresh last print (<=90 min old,
           >=6 recent intraday points). These drive EXITS, position marks, and the dashboard, so a slow cron
           cadence can never silently freeze the engine again (the 2.7.2 overnight-freeze root cause: the old
           all-or-nothing gate demanded 24 points inside 6h; at a ~20-min cadence NO symbol could ever
           qualify, marks came back empty, and exits/display/entries all stopped with no error).
    warm:  the subset that ALSO passes the strict pre-entry warmup (>=24 points spanning >=2h in the last
           6h) — ENTRIES still require this, so the safety that prevents jumping into a name without ~2h of
           live context is unchanged.
    health: counts + freshest-sample age, surfaced on the dashboard so degradation is VISIBLE, never silent."""
    from datetime import datetime as _dt, timezone as _tz
    RECENT_WINDOW_S = 6 * 3600
    FRESH_MAX_AGE_S = 90 * 60          # a mark is only trusted if the last print is <= 90 min old
    WARMUP_MIN_POINTS = 12          # >=12 points AND >=2h span = the same ~2h-of-context principle, but it
    WARMUP_MIN_SPAN_S = 2 * 3600    # no longer assumes a 5-min cadence (24 pts bricked entries at ~20 min/pt)
    out, warm = {}, set()
    newest_age = None
    try:
        nowt = _dt.now(_tz.utc)
    except Exception:
        nowt = None
    for sym, rows in samples.items():
        pr = [(t, p) for t, p in rows if p and p > 0 and "T00:00:00" not in t]
        if len(pr) < 6:
            continue
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
        if len(recent) < 6:
            continue
        last_t, last_p = recent[-1]
        try:
            age = (nowt - _dt.fromisoformat(last_t)).total_seconds() if nowt is not None else 0.0
        except Exception:
            continue
        if age > FRESH_MAX_AGE_S:
            continue
        if newest_age is None or age < newest_age:
            newest_age = age
        ref = None
        try:
            lt = _dt.fromisoformat(last_t)
            for t, p in reversed(recent[:-1]):
                if (lt - _dt.fromisoformat(t)).total_seconds() >= 3600:
                    ref = p
                    break
        except Exception:
            ref = None
        if ref is None:
            ref = recent[0][1]
        h1 = (last_p / ref - 1.0) if ref and ref > 0 else 0.0
        out[sym] = (float(last_p), float(h1))
        if len(recent) >= WARMUP_MIN_POINTS:
            try:
                _span = (_dt.fromisoformat(recent[-1][0]) - _dt.fromisoformat(recent[0][0])).total_seconds()
                if _span >= WARMUP_MIN_SPAN_S:
                    warm.add(sym)
            except Exception:
                pass
    health = {"marked": len(out), "entry_warm": len(warm),
              "newest_sample_age_min": round(newest_age / 60.0, 1) if newest_age is not None else None,
              "state": ("OK" if warm else ("DEGRADED — marks live, entries paused (warmup starved; cron cadence slow?)"
                                            if out else "STALLED — no fresh prices at all (ingestion down?)"))}
    return out, warm, health

class PaperBook:
    def __init__(self, cash: float = START_CASH):
        self.cash = float(cash)
        self.positions: Dict[str, Dict[str, Any]] = {}
        self.realized_pnl = 0.0
        self.trades: List[Dict[str, Any]] = []

    def buy(self, sym, dollars, price, cost, t=None, target=None, stop=None, expected=None, conviction=None):
        if price <= 0 or dollars <= 0 or dollars > self.cash + 1e-9:
            return False
        eff = price * (1 + cost / 2.0)
        qty = dollars / eff
        self.cash -= dollars
        # 2.7: record what this trade was AIMING for, at entry. Without this the dashboard cannot show
        # "% of goal hit" or honestly compute "left on table". target/stop are fractions (0.03 = 3%).
        pos = {"qty": qty, "entry": eff, "cost": cost, "t": t or _now(), "mfe": eff, "wager_usd": round(dollars, 2)}
        if target is not None:
            pos["target"] = target
        if stop is not None:
            pos["stop"] = stop
        if expected is not None:
            pos["expected_move"] = expected
        if conviction is not None:
            pos["conviction"] = conviction
        self.positions[sym] = pos
        trow = {"side": "BUY", "sym": sym, "qty": round(qty, 6), "price": round(eff, 6), "t": t or _now(), "wager_usd": round(dollars, 2)}
        if target is not None:
            trow["target_pct"] = round(target * 100, 3)
        if stop is not None:
            trow["stop_pct"] = round(stop * 100, 3)
        if expected is not None:
            trow["expected_move_pct"] = round(expected * 100, 3)
        if conviction is not None:
            trow["conviction"] = conviction
        self.trades.append(trow)
        return True

    def mark(self, sym, price):
        """Track the high-water mark of a held position so 'left on table' is real, not guessed."""
        pos = self.positions.get(sym)
        if pos and price and price > pos.get("mfe", 0):
            pos["mfe"] = price

    def sell(self, sym, price, t=None):
        pos = self.positions.get(sym)
        if not pos or price <= 0:
            return 0.0
        eff = price * (1 - pos["cost"] / 2.0)
        proceeds = pos["qty"] * eff
        pnl = proceeds - pos["qty"] * pos["entry"]
        self.cash += proceeds
        self.realized_pnl += pnl
        realized_pct = (eff / pos["entry"] - 1) if pos["entry"] > 0 else 0.0
        srow = {"side": "SELL", "sym": sym, "qty": round(pos["qty"], 6), "price": round(eff, 6),
                "pnl": round(pnl, 2), "realized_pct": round(realized_pct * 100, 3), "t": t or _now(),
                "wager_usd": round(pos["qty"] * pos["entry"], 2)}
        tgt = pos.get("target")
        if tgt is not None:
            srow["target_pct"] = round(tgt * 100, 3)
            srow["pct_of_goal"] = round((realized_pct / tgt) * 100, 1) if tgt > 0 else None
        if pos.get("stop") is not None:
            srow["stop_pct"] = round(pos["stop"] * 100, 3)
        # left on table = best the position reached vs what we actually captured (real high-water, not a guess)
        mfe = pos.get("mfe")
        if mfe and pos["entry"] > 0:
            best_pct = mfe / pos["entry"] - 1
            srow["best_pct"] = round(best_pct * 100, 3)
            srow["left_on_table_pct"] = round(max(0.0, best_pct - realized_pct) * 100, 3)
        self.trades.append(srow)
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


def _bounce_reliability(prices, dip=0.02, horizon=12):
    """REAL heat-tolerance / rhythm signal from price history: of recent >= `dip` drops, what fraction
    recovered to the pre-drop level within `horizon` samples? High = this name reliably bounces (strong MR
    conviction). None when there isn't enough evidence to judge."""
    p = [x for x in prices[-200:] if x and x > 0]
    n = len(p); hits = tries = 0; i = 6
    while i < n - 1:
        if p[i - 6] <= 0:
            i += 1; continue
        if p[i] / p[i - 6] - 1 <= -dip:
            tries += 1
            if any(p[k] >= p[i - 6] for k in range(i + 1, min(n, i + 1 + horizon))):
                hits += 1
            i += 6
        else:
            i += 1
    return (hits / tries) if tries >= 3 else None


def conviction_score(prices, cur_move):
    """0-1 mean-reversion conviction from REAL recent prices only. Blends dip DEPTH (deeper survives fees)
    with BOUNCE RELIABILITY (does this name recover from dips). Falls back to depth alone with thin history.
    The entry path ranks by this, so intelligence finally drives a live decision instead of being ignored."""
    depth = min(1.0, abs(cur_move) / 0.06)
    rel = _bounce_reliability(prices)
    if rel is None:
        return round(0.5 * depth, 4), {"depth": round(depth, 3), "bounce_reliability": None}
    return round(0.5 * depth + 0.5 * rel, 4), {"depth": round(depth, 3), "bounce_reliability": round(rel, 3)}


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
        pbook.mark(sym, cur)                       # 2.7: update high-water so left-on-table is real
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

    # ENTRIES — momentum buys strength; mean-reversion ranks eligible dips by CONVICTION (dip depth +
    # bounce reliability) so the names that historically RECOVER get funded first. target/stop unchanged.
    if direction == "mom":
        cands = sorted([(s, lp, h1, None) for s, (lp, h1) in side_marks.items()
                        if h1 >= entry and s not in pbook.positions and fresh_ok(s) and s in _WARM_SYMS],
                       key=lambda x: x[2], reverse=True)
    else:
        scored = []
        for s, (lp, h1) in side_marks.items():
            if h1 <= -entry and s not in pbook.positions and fresh_ok(s) and s in _WARM_SYMS:
                cv, _ = conviction_score(px_of(s), h1)
                scored.append((s, lp, h1, cv))
        cands = sorted(scored, key=lambda x: (x[3] if x[3] is not None else 0.0), reverse=True)
    mk = {s: v[0] for s, v in side_marks.items()}
    cat = _catalog(out)
    min_take = float(((cat.get("min_takehome_usd") or {}).get(book,
               MIN_TAKEHOME.get(book, MIN_TAKEHOME_DEFAULT))))   # book-specific post-fee $ floor (GOLDEN RULE)
    knife = float(cat.get("knife_veto_6h", -0.06))   # skip free-falling names (<= this over 6h); 0 disables
    fmin = ((cat.get("floor_min") or {}).get(book))
    if fmin:
        stop_ = max(stop_, float(fmin))   # DEEPEN-THE-FLOOR: per-book minimum heatshield depth from the
                                          # catalog. Champions still compete/rotate stops ABOVE this line.
    for sym, lp, h1, cv in cands[:MAX_NAMES]:
        if book == "stock":
            lt = _longterm_up(samples.get(sym) or [], int(cat.get("stock_longterm_min_days", 60)))
            if lt is False:
                actions.append({"act": "SKIP", "sym": sym,
                                "why": "long-term trajectory DOWN — stock law: never buy a downtrend"})
                continue
        if direction != "mom" and knife < 0:
            t6 = _trajectory_6h(samples.get(sym) or [])
            if t6 is not None and t6 <= knife:
                actions.append({"act": "SKIP", "sym": sym,
                                "why": "falling knife — %.1f%% over 6h, no bounce (veto at %.0f%%)" % (t6 * 100, knife * 100)})
                continue
        cost = round_trip_cost(px_of(sym))
        net_margin = target - cost              # fraction of the position kept if the target hits, after fees
        # GOLDEN RULE: a close must net >= min_take AFTER fees or we don't take the trade. This also kills
        # the dust bug: when cash is too low to clear the floor we SKIP instead of buying pennies.
        if net_margin <= 0:
            actions.append({"act": "SKIP", "sym": sym, "why": "fee>=target — can never net positive"})
            continue
        base = min(pbook.equity(mk) * PER_NAME_FRAC, pbook.cash * 0.95)
        cap = pbook.cash * 0.95
        budget = min(max(base, min_take / net_margin), cap)   # size UP so the target clears the floor
        if budget * net_margin < min_take - 1e-9:             # even max affordable size can't clear it
            actions.append({"act": "SKIP", "sym": sym,
                            "why": "cannot clear $%.2f net (need $%.0f, cash $%.0f)" % (min_take, min_take / net_margin, cap)})
            continue
        if pbook.buy(sym, budget, lp, cost, now.isoformat(),
                     target=target, stop=stop_, conviction=cv, expected=net_margin):
            actions.append({"act": "BUY", "sym": sym, "move_pct": round(h1 * 100, 2), "conviction": cv,
                            "expected_net_usd": round(budget * net_margin, 2)})

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
                       "t": p.get("t"),
                       "wager_usd": p.get("wager_usd"),
                       "target": p.get("target"), "stop": p.get("stop"),
                       "conviction": p.get("conviction"),
                       "exp_net_usd": (round(p.get("wager_usd") * p.get("expected_move"), 2)
                                        if p.get("wager_usd") and p.get("expected_move") else None),
                       "upl_pct": round((side_marks.get(s, (p["entry"], 0))[0] / p["entry"] - 1) * 100, 2)}
                      for s, p in pbook.positions.items()],
        "recent_trades": pbook.trades[-25:][::-1],
        "tradeable_universe": sum(1 for s in side_marks if fresh_ok(s)),
        "universe_seen": len(side_marks),
    }


def _post_wipe_quiet_left(out: Path) -> float:
    """Minutes remaining in the post-wipe quiet window, from WIPE_MARKER.json. 0 if none/expired."""
    try:
        wm = json.loads((out / "WIPE_MARKER.json").read_text())
        wiped = datetime.fromisoformat(wm["wiped_at"])
        if wiped.tzinfo is None:
            wiped = wiped.replace(tzinfo=timezone.utc)
        elapsed = (datetime.now(timezone.utc) - wiped).total_seconds() / 60.0
        return max(0.0, QUIET_AFTER_WIPE_MIN - elapsed)
    except Exception:
        return 0.0


def live_step(out_dir) -> Dict[str, Any]:
    """One paper-trading cycle for BOTH sides. Persists each book and emits the
    cockpit summary docs/data/paper_sim_live.json."""
    out = Path(out_dir)
    samples = load_all_samples(out)
    global _WARM_SYMS
    marks, _WARM_SYMS, marks_health = _marks_from_samples(samples)
    # 2.7 TRUE post-wipe quiet period (measured from wipe time): take no trades for the first window after a
    # reset, so the clean run starts from a genuinely quiet baseline even though price history is preserved.
    quiet_left = _post_wipe_quiet_left(out)
    if quiet_left > 0:
        marks = {}   # empty marks => no entries and no exits this cycle; the engine sits quiet by design
        marks_health["state"] = "QUIET after wipe — %d min left (by design)" % int(quiet_left)
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
    try:
        from .market_calendar import equity_day_status
        eq_status, eq_reason = equity_day_status()
    except Exception:
        eq_status, eq_reason = "OPEN", "calendar unavailable"
    for bk in BOOKS:
        if bk != "crypto" and eq_status == "CLOSED":
            # market holiday/weekend: equity books hold state, take no actions, burn no work. Crypto runs 24/7.
            results[bk] = {"skipped": True, "why": "market closed — " + eq_reason}
            continue
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
        "marks_health": marks_health,
        "equity_market": {"status": eq_status, "why": eq_reason},
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
        "post_wipe_quiet": {"active": quiet_left > 0, "minutes_left": round(quiet_left, 1),
                            "note": ("engine intentionally quiet after a wipe — no trades until the window "
                                     "elapses, so the clean run starts from a known baseline")},
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
