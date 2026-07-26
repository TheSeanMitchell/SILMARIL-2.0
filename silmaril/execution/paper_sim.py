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


def _vol_sigma1h(rows):
    """A name's OWN typical 1h move (fraction) — the DIRECT answer to "how unusual
    is this hour's dip?" Built from the distribution of ACTUAL trailing-1h moves
    over the last ~24-48h (each print vs the print ~1h before it), sized with a
    robust MAD estimator so one spike can't inflate a quiet tape. Per-print
    returns were the v1 mistake: irregular print spacing inflated σ 3-4× and the
    activation fix failed its own test case. Returns None when tape is thin."""
    try:
        from datetime import datetime as _dt, timezone as _tz
        pts = []
        for t_, p_ in (rows or []):
            if not p_ or "T00:00:00" in str(t_):
                continue
            try:
                ts = _dt.fromisoformat(str(t_).replace("Z", "+00:00"))
                ts = ts if ts.tzinfo else ts.replace(tzinfo=_tz.utc)
                pts.append((ts.timestamp(), float(p_)))
            except Exception:
                continue
        if len(pts) < 12:
            return None
        pts.sort()
        nowt = pts[-1][0]
        # last 48h window; for each print find the print ~1h earlier (45-90m band)
        win = [(t, p) for t, p in pts if t >= nowt - 48 * 3600]
        moves = []
        j = 0
        for i in range(len(win)):
            ti, pi = win[i]
            lo, hi = ti - 90 * 60, ti - 45 * 60
            base = None
            for t2, p2 in win[max(0, i - 12):i]:
                if lo <= t2 <= hi:
                    base = p2            # closest-to-1h older print in band
            if base and base > 0:
                moves.append(pi / base - 1.0)
        if len(moves) < 8:
            return None
        med = sorted(moves)[len(moves) // 2]
        mad = sorted(abs(m - med) for m in moves)[len(moves) // 2]
        sigma = 1.4826 * mad             # robust σ of true 1h moves
        return sigma if sigma > 0 else None
    except Exception:
        return None


_VN_FLOOR = {"crypto": 0.012, "stock": 0.005, "metal": 0.0035, "energy": 0.007}
_VN_CAP = {"crypto": 0.040, "stock": 0.015, "metal": 0.010, "energy": 0.020}


def _vol_native_entry(rows, cls, base_entry, knob):
    """clamp(k·σ1h, class floor, min(class cap, base)) — never looser than the
    floor, never DEMANDS more than the old base. Returns None if disabled/thin."""
    if str((knob or {}).get("mode", "auto")).lower() != "auto":
        return None
    sig = _vol_sigma1h(rows)
    if sig is None:
        return None
    k = float((knob or {}).get("k_sigma", 1.5))
    fl = float(((knob or {}).get("floor") or {}).get(cls, _VN_FLOOR.get(cls, 0.01)))
    cp = float(((knob or {}).get("cap") or {}).get(cls, _VN_CAP.get(cls, 0.04)))
    return max(fl, min(k * sig, cp, float(base_entry)))
def _reachable_move(rows, hold_h):
    """Robust estimate of how far a name actually travels over `hold_h` hours, taken from its own
    tape. Uses the median absolute move across real (non-backfill) prints spanning ~that horizon,
    so it works on instruments whose 1h pair-sampler is empty (gold stops printing when the metals
    session closes, which is exactly why _vol_sigma1h returns None for GLD). Returns None if thin."""
    try:
        from datetime import datetime as _dt, timezone as _tz
        pts = []
        for t_, p_ in (rows or []):
            if not p_ or "T00:00:00" in str(t_):
                continue
            try:
                ts = _dt.fromisoformat(str(t_).replace("Z", "+00:00"))
                pts.append(((ts if ts.tzinfo else ts.replace(tzinfo=_tz.utc)).timestamp(), float(p_)))
            except Exception:
                continue
        if len(pts) < 12:
            return None
        pts.sort()
        span = max(1.0, float(hold_h)) * 3600.0
        moves, j = [], 0
        for i in range(len(pts)):
            ti, pi = pts[i]
            while j < i and pts[j][0] < ti - span:
                j += 1
            if j < i and pts[j][1] > 0:
                moves.append(abs(pi / pts[j][1] - 1.0))
        # Drop dead-flat pairs: a metals ETF repeats the same print all night while its session is
        # closed, and those zeros swamped the percentile (GLD measured 0.000% reachable and every
        # name got skipped). A closed market is not evidence about how far a name travels.
        moves = [m for m in moves if m > 1e-9]
        if len(moves) < 8:
            return None
        moves.sort()
        return moves[int(len(moves) * 0.6)]        # 60th pct: a move it makes often, not a record
    except Exception:
        return None


def _vol_native_target(rows, book, base_target, cost, hold_h, knob):
    """7.0.2 THE GOLD FIX. Entry was already vol-scaled, but the TARGET was not — so the metal book
    ran a crypto-shaped +5% target on GLD, an instrument that moves ~0.19%/hour. It could never hit
    target, so the trade was never worth taking and metal sat at zero trades for days, exactly as
    the operator kept reporting.

    Now the target is what the name actually reaches over the intended hold, floored by fees:
        target = clamp(reachable(hold), fee_multiple x round-trip cost, base_target)
    If the reachable move cannot pay for its own round trip, return None — the caller skips the
    name honestly instead of booking a mathematically-doomed trade.

    SCOPE: applied only to the books listed in the knob (default metal+energy). Crypto and stock
    keep their existing behaviour untouched — the operator's working sleeves are not to be altered.
    KILL: vol_native.target.mode = "off"."""
    tk = (knob or {}).get("target") or {}
    if str(tk.get("mode", "auto")).lower() != "auto":
        return base_target
    if book not in (tk.get("books") or ["metal", "energy"]):
        return base_target
    reach = _reachable_move(rows, hold_h)
    if reach is None:
        return base_target
    floor = float(cost or 0.0) * float(tk.get("fee_multiple", 2.0))
    want = float(tk.get("k_target", 1.0)) * reach
    if want < floor:
        return None                      # cannot clear its own round trip — skip, do not force
    return max(floor, min(want, float(base_target)))


# GOLDEN RULE — book-specific minimum post-fee take-home per trade (USD). A close must net at least this
# much AFTER fees or the trade is not taken; positions are sized UP so the target clears it. This also
# kills the dust-position bug (no more $0.01 buys from leftover cash). Tunable per book: raise toward 5.00
# for fewer/bigger/more-concentrated positions, lower toward 1.00 for more trade frequency.
_WARM_SYMS = set()          # symbols cleared for NEW ENTRIES (strict warmup); exits never need this
_WARM_KNOB = {"min_points": 8, "min_span_h": 1.5}   # refreshed from PARAM_CATALOG.warmup each cycle;
# the ~2h-of-context principle made CADENCE-PROOF: June-30 ran 5-min cadence (24 pts = 2h); at a
# degraded ~50-60 min cadence any fixed high count starves entries forever. SPAN is the real safety.

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
    """STOCK LAW (operator): nothing is bought whose LONG-TERM trajectory is down — and nothing is bought
    BLIND either. July 2 the stock book bought 11 names with ZERO daily-candle history on file (backfill
    hadn't landed), so the law couldn't see. New rule: <20 daily closes = VETO (wait for the nightly
    backfill), 20+ closes = judge the trend over whatever span exists."""
    try:
        closes = [p for t, p in samples_rows if p and p > 0 and "T00:00:00" in t]
        if len(closes) >= 20:
            recent = closes[-min_days:] if len(closes) > min_days else closes
            return recent[-1] >= recent[0] * 0.98   # up or only mildly off over the daily window
        # 5.0: no daily backfill yet -> DON'T blind-block. Judge the name's OWN intraday trajectory
        # over available history so a name up/flat over the last ~1-2 days can still trade (operator:
        # use the valuable's own multi-timeframe trajectory). A sustained intraday downtrend still
        # fails; genuinely no history still refuses. This is what unfreezes the stock book.
        intra = [p for t, p in samples_rows if p and p > 0 and "T00:00:00" not in t]
        if len(intra) >= 24:
            w = intra[-288:]                          # up to ~2 days of 10-min bars
            mean = sum(w) / len(w)
            return (w[-1] >= w[0] * 0.99) or (w[-1] >= mean * 0.985)
        return False                                  # truly no usable history -> never buy blind
    except Exception:
        return False


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



def _traj_win(samples_rows, hours):
    """7.0 ONE-UNIVERSE: multi-window trajectory (the ZIL/WLD lesson). Returns (pct, basis) over
    the window — basis 'intraday' from live prints (T00 backfill filtered, doctrine), else
    'daily' from backfill closes as a VETO-ONLY fallback (daily data may block, never trigger).
    MKR won +$42 in 15m with 8/12/24h up-windows; WLD/ZIL were bought into multi-day decline —
    mean reversion wants oversold-in-a-range, never free-fall across every window."""
    from datetime import datetime as _dt, timezone as _tz
    try:
        nowt = _dt.now(_tz.utc)
        cut = hours * 3600
        intr = [(t, p) for t, p in samples_rows if p and p > 0 and "T00:00:00" not in t
                and (nowt - _dt.fromisoformat(t)).total_seconds() <= cut]
        if len(intr) >= 4 and (nowt - _dt.fromisoformat(intr[0][0])).total_seconds() >= cut * 0.6:
            f, l = intr[0][1], intr[-1][1]
            return ((l / f - 1.0) if f > 0 else None, "intraday")
        daily = [(t, p) for t, p in samples_rows if p and p > 0 and "T00:00:00" in t
                 and (nowt - _dt.fromisoformat(t)).total_seconds() <= cut + 26 * 3600]
        if len(daily) >= 2:
            f, l = daily[0][1], daily[-1][1]
            return ((l / f - 1.0) if f > 0 else None, "daily")
    except Exception:
        pass
    return (None, None)

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


def round_trip_cost(prices: List[float], book: str = None, style: str = "MR") -> float:
    """7.0.2 PER-CLASS FEE TRUTH — the real reason gold never traded.

    MIN_COST was one global 0.2% round-trip floor applied to every book (the source comment already
    conceded "stocks tight; crypto wider" but the code never split them). Gold ETFs reach only
    ~0.22% over ANY horizon, so a 2x0.2% bar made GLD/IAU permanently unprofitable by arithmetic —
    the metal book was mathematically forbidden from trading, which is exactly what the operator
    kept seeing.

    US equity/ETF reality: commission-free at every retail broker, so the true round trip is spread
    plus slippage — GLD's spread is ~0.003%. The class floor below is still several times that, so
    it stays conservative. Crypto is UNCHANGED (Binance.US/Coinbase taker ~0.1%/side).

    HONESTY NOTE: lowering a cost floor makes results look better, which is the dangerous direction.
    These are pre-registered, defensible numbers, knob-tunable, and they must be re-validated against
    real broker fills at live handoff — modeled fees are a hypothesis until a real ticket proves them.
    KILL: PARAM_CATALOG.fee_class.mode = "off" restores the single global floor."""
    # 7.0.3: the cost is now COMPOSED from published venue schedules + a spread measured on our own
    # tape + a regime/style-scaled slippage allowance (see fee_model.py). The old per-class "floor"
    # was a guess wearing a number; this is accounting. The noise floor still applies as a hard
    # minimum so a name whose own tick noise exceeds modelled cost can never look free to trade.
    if book:
        try:
            from .fee_model import round_trip as _rt7
            _cat7 = _catalog() or {}
            _fk7 = _cat7.get("fee_model") or {}
            if str(_fk7.get("mode", "auto")).lower() == "auto":
                _reg7 = str(((_cat7.get("_live_regimes") or {}) or {}).get(book, "SIDEWAYS"))
                _c7 = _rt7(prices, book, style, _reg7, _fk7)["total"]
                return max(_c7, 2.0 * noise_floor(prices))
        except Exception:
            pass
    floor = MIN_COST
    if book:
        try:
            fk = (_catalog() or {}).get("fee_class") or {}
            if str(fk.get("mode", "auto")).lower() == "auto":
                floor = float((fk.get("floor") or {}).get(book, MIN_COST))
        except Exception:
            floor = MIN_COST
    return max(floor, 2.0 * noise_floor(prices))


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
    NOT use this — it stays on price_samples only (Alpaca-safe).

    7.1 THE ONE-KEY LAW (the DOGEUSDT-vs-DOGE-USD incident): the raw merge used to
    leave ccxt spellings (DOGEUSDT) alongside canonical ones (DOGE-USD), so the crypto
    book's universe contained the SAME coin twice and could buy the spelling no chart,
    mark-stamper, or one-listing-per-base check could see. Every consumer now loads
    through canon_keys.canonical_samples: one spelling per asset, history UNIONED
    across spellings, price_samples winning timestamp collisions."""
    try:
        from .canon_keys import canonical_samples
        return canonical_samples(out)
    except Exception:
        # fallback keeps the engine alive if the module is somehow absent — but the
        # selftest battery (T107) fails loudly if this path is ever the live one.
        out = Path(out)
        merged: Dict[str, List] = {}
        for fn in ("price_samples.json", "ccxt_samples.json", "metals_samples.json", "energy_samples.json"):
            try:
                s = json.loads((out / fn).read_text()).get("samples", {})
                merged.update(s)
            except Exception:
                pass
        return merged


_LAST_OSC: set = set()


def _osc_ratio(pxs) -> bool:
    """5.11 WRAP oscillation detector: an alternating two-cluster series (the
    stale-source sawtooth) has |p[i]-p[i-2]| tiny vs |p[i]-p[i-1]|. ratio<0.35
    with a real step size = quarantine. Immune to genuine trends and chop.

    7.0.1 QUANTIZATION FIX (the MOG-USD sawtooth): a sub-penny name whose feed has so few
    significant figures that the whole window is only 2-3 discrete values (MOG at
    1.0e-7 / 1.1e-7 — a 10% quantum step that is pure rounding noise, not a real move).
    The median-gap path MISSED this: when consecutive prints are often identical, m1
    computed to 0 and the old code bailed 'return False', letting the most extreme
    sawtooth of all through undetected. Now: <=3 distinct values across a full window IS
    the two-cluster signature by definition. Healthy coins show 15-20 distinct values in
    20 points, so this can never catch a real mover. This is a per-cycle DATA-QUALITY
    quarantine (mark-smoothing + SUSPECT_OSC tag), NOT a graveyard: the name trades freely
    again the moment its price grows into a resolvable range."""
    try:
        px = [float(x) for x in pxs][-20:]
        if len(px) < 12:
            return False
        # 7.0.1: extreme quantization — a window collapsed to <=3 distinct values is a
        # two/three-cluster sawtooth on its face (the m1=0 blind spot). Require a real
        # relative spread so a genuinely pinned-flat stablecoin isn't quarantined.
        _distinct = sorted(set(px))
        if len(_distinct) <= 3 and px[-1] > 0 and (_distinct[-1] - _distinct[0]) / px[-1] > 0.01:
            return True
        d1 = sorted(abs(px[i] - px[i - 1]) for i in range(1, len(px)))
        d2 = sorted(abs(px[i] - px[i - 2]) for i in range(2, len(px)))
        m1 = d1[len(d1) // 2]
        m2 = d2[len(d2) // 2]
        if m1 <= 0 or px[-1] <= 0:
            return False
        return (m2 / m1) < 0.35 and (m1 / px[-1]) > 0.01
    except Exception:
        return False


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
    WARMUP_MIN_POINTS = int(_WARM_KNOB.get("min_points", 8))
    WARMUP_MIN_SPAN_S = int(float(_WARM_KNOB.get("min_span_h", 1.5)) * 3600)
    out, warm = {}, set()
    _osc_set = set()
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
        if _osc_ratio([p for _, p in recent]):
            _osc_set.add(sym)
            _l4 = sorted(p for _, p in recent[-4:])
            last_p = _l4[len(_l4) // 2]
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
              "warm_rule": ">=%d pts & >=%.1fh span (last 6h) — knob: PARAM_CATALOG.warmup"
                            % (WARMUP_MIN_POINTS, WARMUP_MIN_SPAN_S / 3600.0),
              "newest_sample_age_min": round(newest_age / 60.0, 1) if newest_age is not None else None,
              "state": ("OK" if warm else ("DEGRADED — marks live, entries paused (warmup starved; cron cadence slow?)"
                                            if out else "STALLED — no fresh prices at all (ingestion down?)"))}
    warm -= _osc_set
    health["oscillating"] = len(_osc_set)
    health["oscillating_syms"] = sorted(_osc_set)[:12]
    global _LAST_OSC
    _LAST_OSC = _osc_set
    return out, warm, health

class PaperBook:
    def __init__(self, cash: float = START_CASH):
        self.cash = float(cash)
        self.positions: Dict[str, Dict[str, Any]] = {}
        self.realized_pnl = 0.0
        self.reserve_usd = 0.0      # 7.0.3: harvested, non-spendable profit (book_harvest)
        self.trades: List[Dict[str, Any]] = []

    def buy(self, sym, dollars, price, cost, t=None, target=None, stop=None, expected=None, conviction=None):
        # 7.0 FINAL (T54) — ALREADY-HELD GUARD: the July-17 double-BUY class (SOLUSDT/STRK/VETUSD logged
        # twice with identical microsecond stamps) happened because a maker-limit fill earlier in the SAME
        # cycle put the name in positions, then the market-buy path bought it again, overwriting the
        # position and appending a second BUY row. One book, one position per name, one BUY row. Period.
        if sym in self.positions:
            return False
        if price <= 0 or dollars <= 0 or dollars > self.cash + 1e-9:
            return False
        eff = price * (1 + cost / 2.0)
        qty = dollars / eff
        self.cash -= dollars
        # 2.7: record what this trade was AIMING for, at entry. Without this the dashboard cannot show
        # "% of goal hit" or honestly compute "left on table". target/stop are fractions (0.03 = 3%).
        pos = {"qty": qty, "entry": eff, "cost": cost, "t": t or _now(), "mfe": eff, "wager_usd": round(dollars, 2)}
        # ── 7.0.6 NO-TARGET INVARIANT (moved INSIDE buy). The 7.0.2 guard lived in the caller, so
        # every trade still recorded "target +None%" in DECISION_TRACE — exactly what the operator
        # kept reading on SPCX, MRVL, AMAT and AMD. A caller-side guard cannot protect an entry
        # point that any code path can reach. Now the invariant lives where the position is born:
        # a position without a target is impossible, and the fallback is stamped so it is visible.
        if target is None or not (float(target) > 0):
            target = BOUNCE
            pos["target_fallback"] = True
        if stop is None or not (float(stop) > 0):
            stop = STOP
            pos["stop_fallback"] = True
        pos["target"] = target
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
        self._ledger(trow)
        return True

    def _ledger(self, row):
        """7.0 FINAL — THE ONE BOOK OF RECORD (Tier 0 / R1). Every LIVE fill is appended, once, by this
        single writer, to docs/data/LEDGER.jsonl. Every other view (Master, panels, forensics) derives
        from it and can be diffed against it. Backtests/sims construct PaperBook() without a canon
        context, so they can NEVER write canon — only _run_side (the live cycle) sets `_canon`."""
        ctx = getattr(self, "_canon", None)
        if not ctx:
            return
        try:
            out, bookname = ctx
            r = dict(row)
            r["book"] = bookname
            r["cycle_t"] = _now()
            with open(Path(out) / "LEDGER.jsonl", "a") as f:
                f.write(json.dumps(r) + "\n")
        except Exception:
            pass

    def mark(self, sym, price):
        """Track the high-water mark of a held position so 'left on table' is real, not guessed."""
        pos = self.positions.get(sym)
        if pos and price and price > pos.get("mfe", 0):
            pos["mfe"] = price

    def sell(self, sym, price, t=None):
        pos = self.positions.get(sym)
        if not pos or price <= 0:
            return 0.0
        eff = price * (1 - pos.get("cost", MIN_COST) / 2.0)
        proceeds = pos["qty"] * eff
        pnl = proceeds - pos["qty"] * pos["entry"]
        self.cash += proceeds
        self.realized_pnl += pnl
        # ── 7.0.3 BOOK HARVEST (operator's law: "profits are only real when flat"). On a WINNING
        # close, move a slice of the profit into reserve_usd — non-spendable, never redeployed, out
        # of the market for good. The portal cards and click-ins read this as "vaulted".
        # DEFAULT OFF (frac 0.0): vaulting is a real strategy trade-off, not a bug fix — it locks in
        # gains but shrinks the capital that compounds, so it is the operator's call, not mine.
        # Set PARAM_CATALOG.book_harvest {mode:"auto", frac:0.25} to bank a quarter of every win.
        try:
            _hk = (_catalog() or {}).get("book_harvest") or {}
            if pnl > 0 and str(_hk.get("mode", "off")).lower() == "auto":
                _hf = max(0.0, min(1.0, float(_hk.get("frac", 0.0))))
                if _hf > 0:
                    _v = pnl * _hf
                    self.cash -= _v
                    self.reserve_usd = round(float(getattr(self, "reserve_usd", 0.0)) + _v, 2)
        except Exception:
            pass
        # 7.0.7 THE BRENT LESSON: remember what we sold at, so we never pay MORE to get back in.
        # On 2026-07-23 the energy book bought BRENT at 86.95 and sold at 100.23 for +$198.64 —
        # then re-entered at 100.56, above its own exit, and has been under water since. Taking a
        # profit and immediately buying the same level back is not a new trade, it is a round trip
        # paid for twice.
        try:
            self._last_exit = getattr(self, "_last_exit", {})
            self._last_exit[sym] = {"px": float(eff), "t": _now()}
        except Exception:
            pass
        realized_pct = (eff / pos["entry"] - 1) if pos["entry"] > 0 else 0.0
        srow = {"side": "SELL", "sym": sym, "integrity": ("SUSPECT_OSC" if sym in _LAST_OSC else "ok"),
                "qty": round(pos["qty"], 6), "price": round(eff, 6),
                "pnl": round(pnl, 2), "realized_pct": round(realized_pct * 100, 3), "t": t or _now(),
                "wager_usd": round(pos["qty"] * pos["entry"], 2)}
        # ── 5.3 TRUTH IN ACCOUNTING (Law 16: never compare NET to GROSS) ─────────
        # entry is fee-adjusted; reconstruct the RAW basis so gross means gross.
        _cost = float(pos.get("cost", MIN_COST))
        _raw_entry = pos["entry"] / (1.0 + _cost / 2.0) if pos["entry"] > 0 else 0.0
        _exit_gross = (price / _raw_entry - 1.0) if _raw_entry > 0 else 0.0
        srow["fee_pct"] = round(_cost * 100, 3)                       # the fee, on its OWN line
        # ── 7.0.4 FEE PROVENANCE (operator: "each trade needs the fee amount attached from the
        # source"). Every close now carries the VENUE that would have filled it, why it routed
        # there, and the fee in DOLLARS — not just a percentage floating free of its origin.
        try:
            from .fee_model import resolve_venue as _rv7
            _r7 = _rv7(sym, getattr(self, "_book_name", None) or "crypto",
                       getattr(self, "_out_dir", None))
            srow["venue"] = _r7["venue"]
            srow["venue_routed_by"] = _r7["routed_by"]
            srow["fee_usd"] = round(pos["qty"] * pos["entry"] * _cost, 4)
        except Exception:
            pass
        srow["realized_gross_pct"] = round(_exit_gross * 100, 3)      # the market move we exited on
        tgt = pos.get("target")
        if tgt is not None:
            srow["target_pct"] = round(tgt * 100, 3)                  # gross goal (unchanged meaning)
            # EXACT net of a perfect fill under the half-fee model (multiplicative, not linear):
            _tgt_net = (1.0 + tgt) * (1.0 - _cost / 2.0) / (1.0 + _cost / 2.0) - 1.0
            srow["target_net_pct"] = round(_tgt_net * 100, 3)
            # % of goal = NET vs NET. A perfect target fill reads 100, forever.
            srow["pct_of_goal"] = (round((realized_pct / _tgt_net) * 100, 1)
                                   if _tgt_net > 0 else None)
        if pos.get("stop") is not None:
            srow["stop_pct"] = round(pos["stop"] * 100, 3)
        # left on table = GROSS best vs GROSS exit. Selling ON the peak print reads 0.000.
        mfe = pos.get("mfe")
        if mfe and _raw_entry > 0:
            best_gross = mfe / _raw_entry - 1.0
            srow["best_pct"] = round(best_gross * 100, 3)             # (gross, as it always physically was)
            srow["left_on_table_pct"] = round(max(0.0, best_gross - _exit_gross) * 100, 3)
        self.trades.append(srow)
        self._ledger(srow)
        del self.positions[sym]
        return pnl

    def equity(self, marks):
        held = sum(p["qty"] * marks.get(s, p["entry"]) for s, p in self.positions.items())
        return self.cash + held

    def save(self, path):
        Path(path).write_text(json.dumps({
            "cash": self.cash, "realized_pnl": self.realized_pnl,
            "reserve_usd": round(float(getattr(self, "reserve_usd", 0.0)), 2),
            "last_exit": getattr(self, "_last_exit", {}),   # 7.0.7: the BRENT guard needs this to survive cycles
            "positions": self.positions, "trades": self.trades[-800:],
            "updated_at": _now()}, indent=2))

    @classmethod
    def load(cls, path, cash=START_CASH):
        try:
            d = json.loads(Path(path).read_text())
            b = cls(d.get("cash", cash))
            b.realized_pnl = d.get("realized_pnl", 0.0)
            b.reserve_usd = float(d.get("reserve_usd", 0.0) or 0.0)   # 7.0.3: vault survives cycles
            b._last_exit = d.get("last_exit", {}) or {}                # 7.0.7: BRENT re-entry guard
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


def _run_side(out, marks, samples, book: str, params=None, champion=None) -> Dict[str, Any]:
    uc = "crypto" if book == "aggressive" else book   # GEKKO trades the crypto universe under its own book
    crypto = (uc == "crypto")
    # ── 5.1B CRASH-DAY SENSORS & KNOBS — defined FIRST because the EXIT loop below
    #    consumes them (July-11 lesson: adapt intraday; harvest the green on a fast
    #    flip; free stale capital fee-clear; size new entries by earned conviction).
    cat = _catalog(out)
    _mtf = {}
    try:
        _mtf = json.loads((out / "MTF_REGIME.json").read_text())
    except Exception:
        _mtf = {}
    _mtf_bk = ((_mtf.get("books") or {}).get(uc) or {})
    _mtf_fastred = bool(_mtf_bk.get("fast_red"))
    _mtf_syms = {k: (v.get("confluence") or 0) for k, v in (_mtf.get("symbols") or {}).items()}
    # ── 7.0 loads: the gate, the governor, the maker book, the prediction map ──
    _gk = (cat.get("geometry") or {}); _g_on = str(_gk.get("mode", "auto")).lower() == "auto"
    _geo = {}
    try:
        _geo = (json.loads((out / "GEOMETRY.json").read_text()).get("by_symbol") or {})
    except Exception:
        _geo = {}
    _sz = {}
    try:
        _sz = json.loads((out / "SIZER.json").read_text())
    except Exception:
        _sz = {}
    _sz_mult = float(_sz.get("mult", 1.0)); _sz_halt = _sz_mult <= 0.0
    _factor_over = bool(((_sz.get("factor") or {}).get("over"))) and book in ("crypto", "aggressive")
    _mk = (cat.get("maker_entries") or {}); _mk_on = (str(_mk.get("mode", "auto")).lower() == "auto"
                                                     and book in ("crypto", "aggressive"))
    _mk_win = float(_mk.get("fill_window_min", 45))
    _pend_all = {}
    try:
        _pend_all = json.loads((out / "MAKER_PENDING.json").read_text())
    except Exception:
        _pend_all = {}
    _pend = _pend_all.get(book) or {}
    _crash_co = {}
    try:
        _crash_co = (json.loads((out / "price_samples.json").read_text()).get("crash_cooloff") or {})
    except Exception:
        _crash_co = {}
    _pred_map = {}
    _comp_map = {}
    try:
        _cc0 = json.loads((out / "CONFIDENCE_CARDS.json").read_text()).get("cards") or {}
        _comp_map = {k: (v.get("compounder_score") or 0.5) for k, v in _cc0.items()}
        for _ps0, _pc0 in ((_cc0.get("cards") or {}).items()):
            _pred_map[_ps0] = ((_pc0.get("layers") or {}).get("master_score")
                               or _pc0.get("confidence"))
    except Exception:
        _comp_map = {}
    _exp_hold = {}
    try:
        _pkr0 = json.loads((out / "PEAK_RHYTHM.json").read_text()).get("by_symbol") or {}
        for _s0, _v0 in _pkr0.items():
            _c0 = _v0.get("median_minutes_between_peaks")
            if _c0:
                _exp_hold[_s0] = round(float(_c0))
    except Exception:
        _exp_hold = {}
    _ce_map = {}
    try:
        _ce_map = {k: (v.get("confidence") or 0.0)
                   for k, v in (json.loads((out / "CONFIDENCE_ENGINE.json").read_text()).get("by_symbol") or {}).items()}
    except Exception:
        _ce_map = {}
    _rx = (cat.get("regime_exit") or {}); _rx_on = str(_rx.get("mode", "auto")).lower() == "auto"
    _sck = (cat.get("stale_capital") or {}); _sc_h = float(_sck.get("review_h", 36)); _sc_on = bool(_sck.get("fee_clear_exit", True))
    _cs = (cat.get("conviction_sizing") or {}); _cs_on = str(_cs.get("mode", "auto")).lower() == "auto"
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
    # ── 7.0.2 THE PYRAMID, RUNG 2 — the book adopts the winning sleeve's DISCIPLINE. ──────────
    # Operator's law: sleeves feed the books, books feed the Master. The workshop was winning
    # (crypto H PATIENT REVERT +2.46% at a 100% close-rate) while the book ran an unrelated grid
    # champion. Now the best sleeve — judged on REAL closed trades vs the null — hands its
    # position-management hand upstairs: how many names it holds, and how long it will wait.
    # Entry signal and sleeve behaviour are untouched. KILL: sleeve_promotion.mode "off".
    _promo = {}
    try:
        from .sleeve_promotion import promoted_discipline as _pd7
        _promo = _pd7(out, book) or {}
    except Exception:
        _promo = {}
    # ── 7.1 THE ARMING GATE (PYRAMID LAW — the missing LICENSE). ────────────────────────────────
    # The 2026-07-25 incident, in one line: the crypto book opened DOGEUSDT while its own workshop
    # had ZERO closed trades since the wipe. Discipline promotion (7.0.2) handed the sleeve's HAND
    # upstairs, and seed_immediately (7.0.4) handed it early — but nothing ever required the
    # workshop to actually PROVE anything before the book was allowed to spend. The operator's law,
    # stated ~30 times: sleeves trade FIRST, find their groove, and only then does confidence pass
    # upward. This gate is that law as code, completing the ladder the Master already obeys
    # (master_account: require_promoted_sleeve):
    #
    #     sleeves  → trade freely from cycle one (ungated probes — unchanged)
    #     books    → may OPEN only when their workshop status is PROMOTED, i.e. a sleeve has
    #                ≥ min_closes REAL closed trades since the wipe with positive Δ-vs-null
    #     Master   → may fund a quadrant only when that book's workshop is PROMOTED (existing)
    #
    # PROVISIONAL still seeds the DISCIPLINE (cap/patience) so the book starts with our best hand —
    # it just doesn't grant the license to spend. An UNARMED book still manages exits, marks, and
    # candidate scanning (the sleeves feed off its candidate stream), and cancels any resting maker
    # orders. GEKKO (aggressive) is exempt by doctrine — it IS a probe.
    # Knob: PARAM_CATALOG.arming_gate {"mode":"auto"} · KILL: mode "off" · Tripwire: T106.
    _agk = (cat.get("arming_gate") or {})
    _armed, _arming_why = True, "armed"
    if str(_agk.get("mode", "auto")).lower() == "auto" and book != "aggressive":
        try:
            _spb = ((json.loads((out / "SLEEVE_PROMOTION.json").read_text())
                     .get("books") or {}).get(book) or {})
        except Exception:
            _spb = {}
        _spst = _spb.get("status")
        if _spst == "PROMOTED":
            _armed, _arming_why = True, ("armed — promoted sleeve %s (%s) has real closed trades"
                                         % (_spb.get("sleeve"), _spb.get("name")))
        else:
            _closes = int(((_spb.get("evidence") or {}).get("closed")) or 0)
            _need = int(_spb.get("closes_needed") or 3)
            _armed = False
            _arming_why = ("OBSERVE — pyramid law: the %s workshop must promote a sleeve on real "
                           "closed trades before this book may open. Best sleeve so far: %s · "
                           "%d/%d closes since wipe · status %s. The book still scans, marks and "
                           "manages exits; the sleeves are earning its license right now."
                           % (book, (_spb.get("sleeve") or "—"), _closes, _need, _spst or "WAITING"))
    entry, target, stop_, max_hold = p["entry"], p["target"], p["stop"], p["max_hold_min"]
    # ── 7.0.2 NO-TARGET GUARD (the SPCX post-mortem). SPCX was entered with "target +None%" —
    # the stock champion's params were incomplete that cycle, so the position opened with no
    # defined exit-up and simply rode 123.28 → 116.56 (-5.45%) over 23 hours. A trade without a
    # target is not a trade, it is a hope. Fall back to the book default and say so loudly.
    if target is None or not (float(target) > 0):
        target = BOUNCE
        _no_target_fallback = True
    else:
        _no_target_fallback = False
    if stop_ is None or not (float(stop_) > 0):
        stop_ = STOP
    pbook = PaperBook.load(out / f"paper_book_{book}.json")
    pbook._book_name, pbook._out_dir = book, out   # 7.0.4: lets each fill name its venue + fee
    pbook._canon = (out, book)   # 7.0 FINAL: LIVE cycle writes the one book of record (LEDGER.jsonl)
    # ── 7.0 ONE-UNIVERSE RIVER (read side): the workshop's resolved outcomes count as maturity
    # evidence for the REAL books — what the sleeves learn matures names for production.
    _lab7: Dict[str, int] = {}
    try:
        for _ln7 in (out / "LAB_OUTCOMES.jsonl").read_text().splitlines()[-5000:]:
            try:
                _r7 = json.loads(_ln7)
                _lab7[_r7.get("sym")] = _lab7.get(_r7.get("sym"), 0) + 1
            except Exception:
                continue
    except Exception:
        pass
    # ── 7.0 NEWS PULSE (operator directive: news in the decision path). Per-symbol pulse from
    # news_history.json (last 48h, live rows only — backfilled excluded). Default SHADOW: every
    # candidate's pulse logs to NEWS_TILT_AB.jsonl; mode "on" applies a capped conviction tilt.
    # KILL: news_tilt.mode "off". No synthetic sentiment: null-sent rows carry heat only.
    _np7: Dict[str, tuple] = {}
    try:
        from datetime import timedelta as _td7
        _cut7 = (datetime.now(timezone.utc) - _td7(hours=48)).strftime("%Y-%m-%d")
        _nh7 = json.loads((out / "news_history.json").read_text())
        for _sym7, _rows7 in (_nh7 or {}).items():
            if not isinstance(_rows7, list):
                continue
            _live7 = [r for r in _rows7 if isinstance(r, dict) and not r.get("backfilled")
                      and str(r.get("date", "")) >= _cut7]
            if _live7:
                _sents7 = [r["sent"] for r in _live7 if r.get("sent") is not None]
                _np7[_sym7] = (len(_live7), (sum(_sents7) / len(_sents7)) if _sents7 else None)
    except Exception:
        pass
    try:
        write_json_atomic(out / "NEWS_PULSE_STATUS.json", {
            "generated_at": datetime.now(timezone.utc).isoformat(), "book": book,
            "mode": str(((cat.get("news_tilt") or {}).get("mode", "shadow"))).lower(),
            "symbols_with_pulse_48h": len(_np7),
            "what": "news is IN the decision path: every sized candidate's pulse logs to NEWS_TILT_AB.jsonl (shadow); knob news_tilt.mode 'on' applies a capped tilt"})
    except Exception:
        pass
    now = datetime.now(timezone.utc)
    side_marks = {s: v for s, v in marks.items() if asset_class(s) == uc}
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
        if book == "stock":
            return _market_open_stock(now)   # STOCKS: additionally require the live regular session.
        # 5.0 FIX: metal/energy are commodities (~24/5), NOT US-equity-hours instruments. The
        # old fall-through applied the stock-session gate to them, which (with the override-
        # ordering bug) kept the metal/energy books idle. Gate on live-data freshness only:
        # fresh prints => tradeable; stale => the name won't be warm/marked anyway.
        return is_tradeable(pp)

    # EXITS — THE SELL FIX: manage each position by the target/stop it was ENTERED with
    # (pos["target"]/pos["stop"]) — never the current cycle's champion values. The old code compared
    # against the live champion target, so a position bought at a 2% target never sold when it hit 2%
    # if the champion's target had since moved to 3% (MR_patient_d3): the LDO/ENJ/ETHFI "hit target,
    # never sold, rode back to the stop" bug. A resting LIMIT-SELL at the position's own target also
    # fills the instant price TOUCHES it (a real order type), so a target hit BETWEEN cycles is
    # captured instead of missed. Fees applied by sell(); nothing synthetic. Each close is labeled
    # with the champion that entered AND the champion that exited (mid-lifecycle rotation is visible).
    _exit_pol = (_catalog(out).get("exit_policy") or {})
    _limit_ok = bool(_exit_pol.get("limit_sell_at_target", True))
    for sym in list(pbook.positions.keys()):
        # 5.0 TRADING-CORE FIX (2026-07-10): filter by the book's UNIVERSE class
        # (`uc`), not the book label. GEKKO's book is "aggressive" but its symbols
        # are crypto-class, so `!= book` skipped EVERY GEKKO position here — the
        # book bought all day and could never sell (proven: 11 buys, 0 sells,
        # six positions sitting above their own targets on 07-10).
        if asset_class(sym) != uc:
            continue
        pos = pbook.positions[sym]
        # STALE-PRICE SAFETY (same fix pass): if a held name drops out of this
        # cycle's fresh marks, the old code silently marked it at ENTRY (chg=0),
        # so with timeouts removed it could neither TAKE nor STOP — a zombie.
        # Now: mark from the last REAL intraday print in the samples store
        # (never synthetic), but only allow an exit FILL when that print is
        # fresh (≤45 min). Stale names stay honestly marked, flagged, and armed.
        _fresh_px = sym in side_marks
        if _fresh_px:
            cur = side_marks[sym][0]
            pos.pop("stale_price_min", None)
        else:
            cur, _age_m = pos["entry"], None
            for _ts, _pp2 in reversed(samples.get(sym, [])):
                if _pp2 and _pp2 > 0 and "T00:00:00" not in str(_ts):
                    cur = _pp2
                    try:
                        _age_m = (now - datetime.fromisoformat(str(_ts))).total_seconds() / 60.0
                    except Exception:
                        _age_m = None
                    break
            _fresh_px = (_age_m is not None and _age_m <= 45.0)
            if not _fresh_px:
                pos["stale_price_min"] = round(_age_m, 1) if _age_m is not None else -1
        pbook.mark(sym, cur)                       # 2.7: update high-water so left-on-table is real
        chg = cur / pos["entry"] - 1 if pos["entry"] > 0 else 0
        try:
            hold = (now - datetime.fromisoformat(pos["t"])).total_seconds() / 60.0
        except Exception:
            hold = 0.0
        p_target = float(pos.get("target", target))     # the position's OWN goal, not the cycle champion's
        p_stop = float(pos.get("stop", stop_))
        hs_floor = COMMODITY_FLOOR if book in ("metal", "energy") else HEATSHIELD_FLOOR
        # 5.1 HEATSHIELD AUTOTUNE — the operator's "make learned improvements
        # actionable," done the gated way: when the knob is 'auto' AND the
        # measured comparison (HEATSHIELD.json: shield vs tight over ≥evidence_min
        # forward trades) shows the shield floor netting more, the resolver uses
        # the MEASURED winner's floor, clamped to knob bounds. 'off' = legacy
        # constant. Reversible in one knob edit; the choice is stamped into the
        # HEATSHIELD store so the gates board can show WEIGHTED honestly.
        try:
            _hk = (cat.get("heatshield_autotune") or {})
            if str(_hk.get("mode", "auto")).lower() == "auto" and book in ("crypto",):
                _hsj = json.loads((out / "HEATSHIELD.json").read_text())
                _n = int((_hsj.get("heatshield") or {}).get("trades") or 0)
                _dl = float(_hsj.get("delta_total_pct") or 0.0)
                if _n >= int(_hk.get("evidence_min", 60)) and _dl != 0.0:
                    _win = (_hsj.get("heatshield_floor_pct") if _dl > 0
                            else _hsj.get("tight_stop_pct"))
                    if _win:
                        _lo = float(_hk.get("clamp_min", 0.04))
                        _hi = float(_hk.get("clamp_max", 0.10))
                        hs_floor = min(max(float(_win) / 100.0, _lo), _hi)
        except Exception:
            pass
        eff_stop = max(p_stop, hs_floor) if HEATSHIELD else p_stop
        hw_pct = (pos.get("mfe", cur) / pos["entry"] - 1) if pos["entry"] > 0 else 0.0
        if chg >= p_target:
            why, fill = "TAKE", cur
        elif _limit_ok and hw_pct >= p_target and cur > pos["entry"]:
            why, fill = "TAKE_LIMIT", pos["entry"] * (1.0 + p_target)   # limit fill at the target price
        elif _rx_on and _mtf_fastred and (chg - pos.get("cost", MIN_COST)) >= 0:
            # 5.1B REGIME-FLIP HARVEST — the book's 15m·30m·1h all red: take every
            # position whose NET-now clears fees, freeing capital before the slide.
            # Limit-class fill at the live print (same maker cost model — no fee-
            # bracket change). Every event is A/B-logged; the report card grades it.
            why, fill = "REGIME_FLIP_HARVEST", cur
        elif _sc_on and hold >= max(_sc_h * 60.0, (pos.get("exp_hold_min") or 0) * 1.15) and (chg - pos.get("cost", MIN_COST)) >= 0:
            # 5.1B FEE-CLEAR TIME — head above water past the review window: bank
            # it and reposition. Never forces a loss; underwater just gets flagged.
            why, fill = "FEE_CLEAR_TIME", cur
        elif chg <= -eff_stop:
            why, fill = "STOP", cur
        elif TIMEOUT_EXIT and hold >= max_hold:
            why, fill = "TIMEOUT", cur
        else:
            why, fill = None, cur
            if chg < 0 and hold >= float(_sck.get("stuck_flag_h", 72)) * 60.0:
                pos["stuck"] = True            # Conductor report-card food: money on the table
        if why and not _fresh_px:
            # exit condition met on a STALE print — do not fill on fiction; the
            # position stays armed and fills the moment a fresh print arrives.
            why = None
        if why:
            _champ_entry = pos.get("champion_entry")
            _cvf, _bwu = pos.get("conv_frac"), pos.get("base_wager_usd")
            _pcost = pos.get("cost", MIN_COST)
            _rzpct = (fill / pos["entry"] - 1) * 100 if pos["entry"] > 0 else 0.0
            pnl = pbook.sell(sym, fill, now.isoformat())
            if why in ("REGIME_FLIP_HARVEST", "FEE_CLEAR_TIME"):
                try:  # append-only A/B ledger; the report card grades saved% at +6h/+24h
                    with open(out / "REGIME_EXIT_AB.jsonl", "a") as _abf:
                        _abf.write(json.dumps({"t": now.isoformat(), "sym": sym, "book": book,
                                               "why": why, "exit_px": fill,
                                               "net_pct": round(_rzpct - _pcost * 100, 3)}) + "\n")
                except Exception:
                    pass
            try:
                tr = pbook.trades[-1]
                tr["exit_reason"] = why
                # 7.0 CALIBRATION: close the prediction loop (Law 23 — a score that
                # cannot predict does not get to allocate). pred stamped at entry.
                try:
                    _pd7 = pos.get("pred")
                    if _pd7 is not None:
                        with open(out / "CALIBRATION_LEDGER.jsonl", "a") as _cf7:
                            _cf7.write(json.dumps({
                                "t": now.isoformat(), "sym": sym, "book": book,
                                "pred": round(float(_pd7), 4),
                                "outcome": "win" if (tr.get("pnl") or 0) > 0 else "loss",
                                "net_pct": tr.get("realized_pct"),
                                "p_star_pct": pos.get("p_star_pct")}) + "\n")
                except Exception:
                    pass
                if _cvf is not None:
                    tr["conv_frac"] = _cvf
                    tr["base_wager_usd"] = _bwu
                tr["champion_entry"] = _champ_entry
                tr["champion_exit"] = champion
                tr["champion_changed"] = bool(_champ_entry and champion and _champ_entry != champion)
                # ── 7.0 FINAL — CHAMPION FORWARD LEDGER (Tier 3 / V2, the "Lickitung forever" fix). ──
                # The election needs ≥5 FORWARD trades per strategy, but forward evidence used to live
                # only inside book trade arrays — flattened by every reset, so no strategy could ever
                # earn promotion. This append-only LEARNING store accumulates every closed trade
                # across resets; the election reads accumulated history, not the current book.
                try:
                    with open(out / "CHAMPION_FORWARD_LEDGER.jsonl", "a") as _fwl:
                        _fwl.write(json.dumps({
                            "t": now.isoformat(), "book": book, "sym": sym,
                            "strategy": _champ_entry or champion,
                            "entry_t": pos.get("t"), "hold_min": round(hold, 1),
                            "net_pct": tr.get("realized_pct"), "pnl": tr.get("pnl"),
                            "fee_pct": tr.get("fee_pct"), "exit_reason": why,
                            "entry_regime": pos.get("entry_regime"),
                            "integrity": tr.get("integrity", "ok")}) + "\n")
                except Exception:
                    pass
            except Exception:
                pass
            actions.append({"act": "SELL", "sym": sym, "why": f"{why} {_rzpct:+.1f}%",
                            "pnl": round(pnl, 2)})

    # 5.0 STOCK/BOOK PARTICIPATION FIX — resolve the per-book/per-regime override BEFORE
    # candidate selection. Previously the override applied AFTER cands were built, so a lowered
    # entry could never widen the funnel (the root cause of the idle stock/metal books). The
    # override may now also set `dir`, so a book can run a mean-reversion participation profile
    # sized to its own market even when its elected champion is a slow HOLD/momentum strategy.
    # Empty override => byte-for-byte identical behavior to before.
    _cat0 = _catalog(out)
    _rg0 = (globals().get("_LIVE_REGIMES") or {}).get(uc)
    _fmin0 = ((_cat0.get("floor_min") or {}).get(book, (_cat0.get("floor_min") or {}).get(uc)))
    _ovr0 = (((_cat0.get("regime_overrides") or {}).get(book) or {}).get(_rg0 or "") or {})
    if _ovr0:
        direction = str(_ovr0.get("dir", direction))
        entry = float(_ovr0.get("entry", entry))
        target = float(_ovr0.get("target", target))
        stop_ = max(float(_ovr0.get("stop", stop_)), float(_fmin0 or 0))
        max_hold = float(_ovr0.get("max_hold_min", max_hold))
    # 7.0.2: the promoted sleeve's patience governs the hold clock. H PATIENT REVERT waits up to
    # 7 days for the revert it has evidence for; a recycle-horizon sleeve cuts dead capital sooner.
    # This is the single lever that would have changed the MKR loss (book held 1023m into -5.14%).
    if _promo.get("recycle_h"):
        try:
            max_hold = float(_promo["recycle_h"]) * 60.0
        except Exception:
            pass

    # ENTRIES. Momentum buys strength. Mean-reversion now fits a CUSTOM strategy to EACH valuable from
    # its own chart (fingerprint): a name is a candidate only when it has dipped to ~its OWN typical
    # buyable level, and it carries its own realistic target/stop into the buy. This is the system
    # reading each graph like a professional trader instead of one blanket threshold for the whole book.
    _fits = {}   # sym -> fitted strategy (target/stop/trend/reliability), consumed by the buy loop
    _fpcfg = (_cat0.get("fingerprint_strategy") or {})
    _fp_on = bool(_fpcfg.get("enabled", True))
    if direction == "mom":
        cands = sorted([(s, lp, h1, None) for s, (lp, h1) in side_marks.items()
                        if h1 >= entry and s not in pbook.positions and fresh_ok(s) and s in _WARM_SYMS],
                       key=lambda x: x[2], reverse=True)
    elif _fp_on and book != "aggressive":
        # (aggressive/GEKKO excluded from fingerprint fitting as of 2026-07-10:
        # fitted per-name targets had silently overwritten its fixed 2%→2%/6%
        # knob profile, making it a near-clone of the crypto book instead of the
        # control probe the doctrine defines. GEKKO now takes the plain-threshold
        # path below with its own aggressive_book knob params, untouched.)
        from .fingerprint import fingerprint as _fpf, fit_strategy as _fitf
        _bh = int(_fpcfg.get("bounce_h", 144)); _rz = float(_fpcfg.get("realism", 0.66))
        _minrel = float(_fpcfg.get("min_reliability", 0.3)); _mindip = float(_fpcfg.get("min_dip", 0.002))
        scored = []
        for s, (lp, h1) in side_marks.items():
            if h1 < -_mindip and s not in pbook.positions and fresh_ok(s) and s in _WARM_SYMS:
                _pp = px_of(s)
                _fp = _fpf(_pp, samples.get(s), bounce_h=_bh)
                _ft = _fitf(_fp, round_trip_cost(_pp), _fmin0, realism=_rz, min_reliability=_minrel)
                if _ft and h1 <= -_ft["entry"]:          # dipped to ITS OWN typical buyable level
                    _cv, _ = conviction_score(_pp, h1)
                    _rank = (_cv or 0.0) + (0.30 if _ft.get("strong_up") else 0.0) \
                            + 0.30 * (_ft.get("bounce_reliability") or 0.0)
                    scored.append((s, lp, h1, _cv))
                    _fits[s] = dict(_ft, _rank=_rank)
                elif _ft is None:
                    # 5.11 VOL-NATIVE FALLBACK: unfittable names (thin/no-pattern tape) are no
                    # longer invisible — they qualify against their OWN volatility, clamped by
                    # class floors/caps and never looser than the fingerprint law's spirit.
                    _vn = _vol_native_entry(samples.get(s), uc, entry, _cat0.get("vol_native"))
                    if _vn is not None and h1 <= -_vn:
                        _cv, _ = conviction_score(_pp, h1)
                        _tgt = max(2.0 * _vn, round_trip_cost(_pp) * 2.5)
                        _fits[s] = {"entry": _vn, "target": _tgt, "stop": max(_vn * 2.0, float(_fmin0 or 0.02)),
                                    "bounce_reliability": None, "strong_up": False,
                                    "vol_native": True, "_rank": (_cv or 0.0)}
                        scored.append((s, lp, h1, _cv))
        cands = sorted(scored, key=lambda x: _fits.get(x[0], {}).get("_rank", (x[3] or 0.0)), reverse=True)
    else:
        scored = []
        for s, (lp, h1) in side_marks.items():
            if s in pbook.positions or not fresh_ok(s) or s not in _WARM_SYMS:
                continue
            _vn = _vol_native_entry(samples.get(s), uc, entry, _cat0.get("vol_native"))
            _eff = min(entry, _vn) if _vn is not None else entry   # 5.11: quiet-market custom fit
            if h1 <= -_eff:
                cv, _ = conviction_score(px_of(s), h1)
                scored.append((s, lp, h1, cv))
        cands = sorted(scored, key=lambda x: (x[3] if x[3] is not None else 0.0), reverse=True)
    mk = {s: v[0] for s, v in side_marks.items()}
    cat = _catalog(out)
    try:
        _WARM_KNOB.update({k: v for k, v in (cat.get("warmup") or {}).items()
                           if k in ("min_points", "min_span_h")})
    except Exception:
        pass
    min_take = float(((cat.get("min_takehome_usd") or {}).get(book,
               MIN_TAKEHOME.get(book, MIN_TAKEHOME_DEFAULT))))   # book-specific post-fee $ floor (GOLDEN RULE)
    knife = float(cat.get("knife_veto_6h", -0.06))   # skip free-falling names (<= this over 6h); 0 disables
    fmin = ((cat.get("floor_min") or {}).get(book, (cat.get("floor_min") or {}).get(uc)))
    if fmin:
        stop_ = max(stop_, float(fmin))   # DEEPEN-THE-FLOOR: per-book minimum heatshield depth from the
                                          # catalog. Champions still compete/rotate stops ABOVE this line.
    _rgmode = str((cat.get("regime_gate") or {}).get(book, "hard" if uc in ("crypto", "stock") else "soft"))
    _regime = (globals().get("_LIVE_REGIMES") or {}).get(uc)
    # REGIME OVERRIDES — the experimentation surface the operator asked for: per-book, per-regime tuning of
    # entry/target/stop and the soft-gate conviction bar, all from PARAM_CATALOG.json. Empty = zero change.
    # Example: {"crypto": {"UPTREND": {"target": 0.05}, "SIDEWAYS": {"entry": 0.02, "target": 0.02}}}
    _ovr = (((cat.get("regime_overrides") or {}).get(book) or {}).get(_regime or "") or {})
    if _ovr:
        entry = float(_ovr.get("entry", entry))
        target = float(_ovr.get("target", target))
        stop_ = max(float(_ovr.get("stop", stop_)), float(fmin or 0))   # floor_min still binds
    _soft_cv = float(_ovr.get("soft_conviction", (cat.get("soft_conviction") or {}).get(book, 0.5)) if isinstance(cat.get("soft_conviction"), dict) or _ovr else 0.5)
    if _regime == "DOWNTREND" and _rgmode == "hard" and cands:
        # HARD GATE: red tape = zero new entries — EXCEPT names whose own fingerprint shows a strong
        # multi-timeframe uptrend (operator: a valuable clearly trajecting up over 1d/3d/1w should be
        # playable even in a red book regime). Those play through; everything else is blocked and logged
        # to the REGIME_AB proof ledger so we still measure what obeying the gate saved or cost.
        _tov = bool(_fpcfg.get("trend_override", True))
        _through = [c for c in cands if _tov and _fits.get(c[0], {}).get("strong_up")]
        _blocked = [c for c in cands if c not in _through]
        try:
            abp = out / "REGIME_AB.json"
            led = json.loads(abp.read_text()) if abp.exists() else []
            for _sym, _lp, _h1, _cv in _blocked[:MAX_NAMES]:
                led.append({"t": now.isoformat(), "book": book, "sym": _sym, "px_at_block": _lp,
                            "move_at_block_pct": round(_h1 * 100, 2), "conviction": _cv,
                            "regime": _regime, "outcome": None})
            abp.write_text(json.dumps(led[-3000:], indent=1))
        except Exception:
            pass
        _ovr_min = float(_rx.get("symbol_override_min_conf", 5.0))
        _mtf_pass = [c for c in _blocked if _mtf_syms.get(c[0], 0) >= _ovr_min][:2]
        if _mtf_pass:
            _through = list(_through) + _mtf_pass
            actions.append({"act": "SKIP", "sym": ", ".join(c[0] for c in _mtf_pass),
                            "why": "SYMBOL_OVERRIDE — its own multi-timeframe confluence ≥ %.1f beats the industry red (max 2/cycle, A/B-tracked via sizing ledger)" % _ovr_min})
        actions.append({"act": "REGIME_BLOCK", "book": book,
                        "why": "regime DOWNTREND + gate=hard → %d blocked (logged to A/B), %d strong-uptrend name(s) played through" % (len(_blocked[:MAX_NAMES]), len(_through))})
        cands = _through
    elif _regime == "DOWNTREND" and _rgmode == "soft":
        _ovr_min2 = float(_rx.get("symbol_override_min_conf", 5.0))
        cands = [c for c in cands if (c[3] or 0) >= _soft_cv or _mtf_syms.get(c[0], 0) >= _ovr_min2]
    try:
        from .integrity import quarantined as _quar
        _qset = _quar(out)
    except Exception:
        _qset = set()
    if _qset:
        _pre = len(cands)
        cands = [c for c in cands if c[0] not in _qset]
        if _pre != len(cands):
            actions.append({"act": "SKIP", "sym": "%d name(s)" % (_pre - len(cands)),
                            "why": "integrity quarantine — data stream failed Phase-1 checks"})
    # POST-STOP RE-ENTRY COOLDOWN (2026-07-10, from the LDO-USD autopsy): the book
    # stopped out of LDO at 18:51 (-7.1%) and re-bought the same falling name at
    # 19:15. A name that just hit its stop is disqualified for a cooling-off
    # window. Knob: PARAM_CATALOG.reentry_cooldown {"after_stop_min": 240};
    # set 0 to disable. Applies to every book including GEKKO.
    try:
        _cd_min = float(((cat.get("reentry_cooldown") or {}).get("after_stop_min", 240)) or 0)
    except Exception:
        _cd_min = 240.0
    if _cd_min > 0 and cands:
        _cool = set()
        for _tr in reversed(pbook.trades[-400:]):
            if _tr.get("side") == "SELL" and _tr.get("exit_reason") == "STOP":
                try:
                    _ag = (now - datetime.fromisoformat(str(_tr.get("t")))).total_seconds() / 60.0
                except Exception:
                    continue
                if _ag <= _cd_min:
                    _cool.add(_tr.get("sym"))
        if _cool:
            _pre2 = len(cands)
            cands = [c for c in cands if c[0] not in _cool]
            if _pre2 != len(cands):
                actions.append({"act": "SKIP", "sym": ", ".join(sorted(_cool))[:60],
                                "why": f"post-STOP cooldown — re-entry blocked {int(_cd_min)}m after a stop-out"})
    _dtrace = [{"sym": s_, "dip_pct": round(h_ * 100, 2), "conviction": c_, "fate": "candidate"}
               for s_, l_, h_, c_ in cands[:8]]
    _rt = (cat.get("regime_throttle") or {})
    if _mtf_fastred and str(_rt.get("mode", "auto")).lower() == "auto" and cands:
        _cap_red = max(0, int(_rt.get("max_new_when_red", 1)))
        if len(cands) > _cap_red:
            actions.append({"act": "SKIP", "sym": f"{len(cands) - _cap_red} name(s)",
                            "why": "regime throttle — 15m·30m·1h all red; new entries capped to %d this cycle" % _cap_red})
            cands = cands[:_cap_red]
    _poscap = int((cat.get("position_caps") or {}).get(book, MAX_NAMES))
    # 7.0.2: promoted sleeve discipline (_promo) is resolved earlier, before the override block.
    if _promo.get("cap"):
        _poscap = int(_promo["cap"])
    # 7.0.2 GOLD FIX: scale the champion target to what THIS book's names can actually reach.
    # Metal/energy inherit crypto-shaped targets from the strategy grid; a +5% target on gold is
    # unreachable, so the book never trades. Vol-native targets make slow books tradeable while the
    # fee floor keeps them honest (a name that cannot clear its round trip is skipped, not forced).
    _vnt_knob = (cat.get("vol_native") or {})
    _vnt_on = str(((_vnt_knob.get("target") or {}).get("mode", "auto"))).lower() == "auto"
    _slots = max(0, _poscap - len(pbook.positions))   # cap governs TOTAL open, not per-cycle
    if _slots < len(cands[:MAX_NAMES]):
        actions.append({"act": "SKIP", "sym": f"{len(cands[:MAX_NAMES]) - _slots} name(s)",
                        "why": "position cap %d/%d for %s — concentration law: a new name must beat a held one" % (len(pbook.positions), _poscap, book)})
    # ── 7.0 MAKER BOOK: resting post-only limits from prior cycles fill or expire ──
    # 7.1 ARMING GATE: an UNARMED book may not fill resting orders either — a limit placed
    # before the license existed is not a license. Cancel them, say why, once.
    if _pend and not _armed:
        actions.append({"act": "SKIP", "sym": ", ".join(sorted(_pend.keys()))[:60],
                        "why": "arming gate — resting maker order(s) cancelled: the workshop has not promoted a sleeve yet"})
        _pend = {}
    if _pend:
        from datetime import timedelta as _td7
        for _psym in list(_pend.keys()):
            _po = _pend[_psym]
            _ppx = [pp for pp in px_of(_psym) if pp]
            _last = _ppx[-1] if _ppx else None
            if _last is not None and _last <= float(_po["limit"]) * 1.0005 and _psym not in pbook.positions:
                _mcost = float(_po.get("cost", 0.004)) * float(_mk.get("maker_cost_frac", 0.6))
                if pbook.buy(_psym, float(_po["wager"]), float(_po["limit"]), _mcost,
                             now.isoformat(), target=_po.get("target"), stop=_po.get("stop"),
                             conviction=_po.get("conviction"), expected=_po.get("expected")):
                    pbook.positions[_psym]["p_star_pct"] = _po.get("p_star_pct")
                    pbook.positions[_psym]["p_floor_pct"] = _po.get("p_floor_pct")
                    pbook.positions[_psym]["pred"] = _po.get("pred")
                    pbook.positions[_psym]["maker"] = True
                    if pbook.trades and pbook.trades[-1].get("side") == "BUY":
                        pbook.trades[-1]["maker_fill"] = True
                        pbook.trades[-1]["p_star_pct"] = _po.get("p_star_pct")
                        pbook.trades[-1]["pred"] = _po.get("pred")
                    actions.append({"act": "FILL", "sym": _psym,
                                    "why": f"maker limit FILLED @ {_po['limit']} — the price came to us"})
                _pend.pop(_psym, None)
            elif str(_po.get("expires", "")) < now.isoformat():
                actions.append({"act": "SKIP", "sym": _psym,
                                "why": f"maker limit UNFILLED in {int(_mk_win)}m — no touch, no trade"})
                _pend.pop(_psym, None)
    if _sz_halt:
        actions.append({"act": "SKIP", "sym": "*",
                        "why": f"SIZER {(_sz.get('state') or 'RED')}: entries halted — "
                               + "; ".join(_sz.get("breakers") or ["drawdown ladder"])})
    if _crash_co:
        _nowiso = now.isoformat()
        _hot = [c for c in cands if _crash_co.get(c[0]) and _nowiso < str(_crash_co[c[0]])]
        for _cs in _hot:
            actions.append({"act": "SKIP", "sym": _cs[0],
                            "why": "verified-crash cool-off (M8) — real disaster, let it settle"})
        cands = [c for c in cands if c not in _hot]
    # ── 7.1 ARMING GATE, applied. Candidates were scanned above (the sleeves trade off this
    # book's candidate stream via decision_trace_live — that river MUST keep flowing), but an
    # unarmed book spends nothing. One OBSERVE row states the exact license terms.
    if not _armed and cands:
        actions.append({"act": "SKIP", "sym": "%d candidate(s)" % len(cands[:MAX_NAMES]),
                        "why": "arming gate — " + _arming_why})
        cands = []
    elif not _armed:
        actions.append({"act": "NOTE", "sym": "*", "why": "arming gate — " + _arming_why})
    for sym, lp, h1, cv in cands[:min(MAX_NAMES, _slots)]:
        if sym in pbook.positions:   # belt-and-suspenders with the buy() guard (T54): never re-buy a held name
            continue
        # ── 7.0 FINAL — CONFIDENCE MATURITY (Tier 4 / T2): "I don't know yet" is the default. ──
        # A name earns the right to trade with EVIDENCE: either its fingerprint fit carries ≥N resolved
        # dip events, or its tape shows ≥3 resolved bounce-tries (dip → did it recover). Tape evidence
        # lives in price_samples.json, which every reset PRESERVES — so after a reset the machine trades
        # only names it still genuinely knows, instead of going blind the moment the quiet window ends
        # (the July-17 lesson: 2h of silence, then blind trades on zero forward evidence).
        # Knob: PARAM_CATALOG.maturity {"mode":"auto","min_fit_events":12} · KILL: mode:"off".
        # GEKKO (aggressive) is exempt by doctrine — it is the unfitted control probe.
        _mk7 = (cat.get("maturity") or {})
        if (str(_mk7.get("mode", "auto")).lower() == "auto"
                and direction != "mom" and book != "aggressive"):
            _ftm = _fits.get(sym) or {}
            _ev7 = int(_ftm.get("dip_samples") or _ftm.get("n") or 0)
            _lb7 = int(_lab7.get(sym, 0))
            if (_ev7 < int(_mk7.get("min_fit_events", 12))
                    and _lb7 < int(_mk7.get("min_lab_outcomes", 3))):
                if _bounce_reliability(px_of(sym)) is None:   # <3 resolved dip→bounce tries on tape
                    actions.append({"act": "SKIP", "sym": sym,
                                    "why": ("immature — %d fit events (<%d) · %d workshop outcomes (<%d) "
                                            "· <3 resolved bounce-tries; the sleeves are maturing this "
                                            "name now (one-universe river)")
                                           % (_ev7, int(_mk7.get("min_fit_events", 12)),
                                              _lb7, int(_mk7.get("min_lab_outcomes", 3)))})
                    continue
        # ── 7.0.6 THE GRAPH GATE (the operator's law: "we need the system to read the chart the way
        # a professional trader would"). Before anything else, ask the chart what it is looking at.
        # A dip inside an UPTREND is the trade this whole system exists to take. A dip inside a
        # DOWNTREND is a falling knife, and no amount of oversold-ness converts one into the other.
        # Receipt: applied to 2026-07-24 it blocks MRVL (-7.04%), AMAT (-5.51%), RUNE and ENA
        # (-3.52%) while still taking SMCI (+4.15%) — the stock book's day goes -$100.62 -> +$57.27.
        # Knob: graph_gate {mode:"auto"|"off"}. KILL: mode "off".
        # ── 7.0.7 FLOOR PROXIMITY (replaces the hard structure veto, which measured -284.98). ──
        # Across 89 point-in-time trades from three real sessions the single clean separator was not
        # the trend label — it was WHERE IN THE RANGE the entry sat:
        #
        #     winners: median position_in_range 0.00, median distance_to_floor -0.14%
        #     losers : median position_in_range 0.92, median distance_to_floor +0.79%
        #
        #     entries at/below the floor   n=50   92.0% win   +1297.35
        #     entries 0-1% above           n=17   88.2% win    +183.99
        #     entries 3-8% above           n=12   91.7% win    +310.18
        #     entries >8% above            n= 6   50.0% win     -98.83   <- the only losing bucket
        #
        # This is the operator's own question answered: the floor is not decoration, it is the
        # entry. But the >8% bucket is SIX TRADES and the sign flips if the threshold moves to 10%,
        # so a hard block there would be curve-fitting. Instead the distance shapes CONVICTION —
        # near the floor sizes up, far above it sizes down — which uses a real-but-noisy signal at
        # the strength the evidence supports. KILL: floor_proximity.mode "off".
        # ── 7.0.7 RE-ENTRY GUARD (the BRENT lesson, stated as a rule): after taking a profit in a
        # name, do not buy it back ABOVE the price we just sold it at. BRENT sold at 100.2335 and
        # was re-bought at 100.5641 — 0.33% higher — and never recovered. Paying more to re-enter
        # what you just banked is a round trip charged twice for the same idea. A dip BELOW the exit
        # is a legitimate new trade and is still allowed. KILL: reentry_guard.mode "off".
        _rgk = (cat.get("reentry_guard") or {})
        if str(_rgk.get("mode", "auto")).lower() == "auto":
            try:
                _le = (getattr(pbook, "_last_exit", {}) or {}).get(sym)
                if _le and _le.get("px"):
                    _need = float(_le["px"]) * (1.0 - float(_rgk.get("min_discount_pct", 0.5)) / 100.0)
                    _px_now = px_of(sym)[-1] if px_of(sym) else None
                    if _px_now and _px_now > _need:
                        _age_h = None
                        try:
                            _age_h = (now - datetime.fromisoformat(str(_le.get("t")))).total_seconds() / 3600.0
                        except Exception:
                            pass
                        if _age_h is None or _age_h <= float(_rgk.get("window_h", 48)):
                            actions.append({"act": "SKIP", "sym": sym,
                                            "why": (f"re-entry guard — we sold this at "
                                                    f"{_le['px']:.4f}; buying back at {_px_now:.4f} "
                                                    f"pays more than we just banked (need "
                                                    f"<={_need:.4f})")})
                            continue
            except Exception:
                pass
        _fpk = (cat.get("floor_proximity") or {})
        _fp_mult, _fp_note = 1.0, ""
        if str(_fpk.get("mode", "auto")).lower() == "auto":
            try:
                from .chart_intel import analyze as _cig
                _ga = _cig(sym, samples.get(sym) or [])
                _dfl = _ga.get("distance_to_floor_pct")
                if _dfl is not None:
                    if _dfl <= float(_fpk.get("at_floor_pct", 0.0)):
                        _fp_mult = float(_fpk.get("at_floor_mult", 1.15))
                        _fp_note = f"at/below floor ({_dfl:+.2f}%)"
                    elif _dfl <= float(_fpk.get("near_floor_pct", 3.0)):
                        _fp_mult = float(_fpk.get("near_floor_mult", 1.05))
                        _fp_note = f"near floor (+{_dfl:.2f}%)"
                    elif _dfl >= float(_fpk.get("far_pct", 8.0)):
                        _fp_mult = float(_fpk.get("far_mult", 0.75))
                        _fp_note = f"FAR above floor (+{_dfl:.2f}%) — sized down, this is the losing bucket"
            except Exception:
                pass
        _t6s = _trajectory_6h(samples.get(sym) or [])
        # ── 7.0 TRAJECTORY VETO (the ZIL/WLD lesson — EVERY book, GEKKO included). A dip inside
        # an up/flat larger trajectory (MKR: 8/12/24h up → +$42 in 15m) is a buy; a name down
        # across 24h AND 72h is free-fall and may only fill after printing a floor (3
        # non-decreasing live prints). Knob: trajectory_veto {mode,t24,t72} · KILL: mode "off".
        _tvk = (cat.get("trajectory_veto") or {})
        if str(_tvk.get("mode", "auto")).lower() == "auto" and direction != "mom":
            _p24, _b24 = _traj_win(samples.get(sym) or [], 24)
            _p72, _b72 = _traj_win(samples.get(sym) or [], 72)
            if (_p24 is not None and _p72 is not None
                    and _p24 <= float(_tvk.get("t24", -0.02))
                    and _p72 <= float(_tvk.get("t72", -0.04))):
                # ── 7.0.6 STRUCTURAL FLOOR (replaces a coin flip). The old test asked "were the last
                # 3 prints non-decreasing?" — a condition true 72% of the time on MRVL's own tape, so
                # a stock in an 8.66%/24h free-fall strolled through the gate and lost 7.04%. AMAT,
                # RUNE and ENA died the same way. The floor is now STRUCTURE: price must have stopped
                # making new lows AND lifted a volatility-scaled distance off its last swing trough.
                # chart_intel computes it from real swing points; see CHART_INTEL.json for the read.
                _floor7 = False
                try:
                    from .chart_intel import analyze as _ci7
                    _a7 = _ci7(sym, samples.get(sym) or [])
                    _floor7 = bool(_a7.get("based"))
                    _struct7 = _a7.get("structure")
                except Exception:
                    _fl7 = [p for _, p in (samples.get(sym) or [])[-3:] if p and p > 0]
                    _floor7 = len(_fl7) == 3 and _fl7[0] <= _fl7[1] <= _fl7[2]
                    _struct7 = None
                if not _floor7:
                    actions.append({"act": "SKIP", "sym": sym,
                                    "why": ("trajectory — down %.1f%%/24h (%s) · %.1f%%/72h (%s), no "
                                            "floor printed; free-fall is not a dip (needs an MKR-style "
                                            "up-window or 3 rising prints)")
                                           % (_p24 * 100, _b24, _p72 * 100, _b72)})
                    continue
        _style = ("riding-strength" if (_t6s or 0) >= 0.02 else "deep-dip" if (h1 or 0) <= -0.04 else "range-play")
        if book == "stock":
            lt = _longterm_up(samples.get(sym) or [], int(cat.get("stock_longterm_min_days", 60)))
            if lt is False:
                actions.append({"act": "SKIP", "sym": sym,
                                "why": "stock law: long-term trend DOWN or <20 daily candles on file (never buy blind)"})
                continue
        if direction != "mom" and knife < 0:
            t6 = _trajectory_6h(samples.get(sym) or [])
            if t6 is not None and t6 <= knife:
                actions.append({"act": "SKIP", "sym": sym,
                                "why": "falling knife — %.1f%% over 6h, no bounce (veto at %.0f%%)" % (t6 * 100, knife * 100)})
                continue
        cost = round_trip_cost(px_of(sym), book)
        # 5.3 VENUE LAYER — declared fee + measured spread + CAPPED slippage (noise demoted).
        # The proxy that drifted 1.494%→0.450% on ONDO in 24h can never set economics again.
        try:
            _vk = (cat.get("venue_layer") or {})
            if str(_vk.get("mode", "auto")).lower() == "auto" and book in ("crypto", "aggressive"):
                from .venues import venue_round_trip_cost as _vrt
                _vc = _vrt(out, sym, px_of(sym), _vk, cost)
                cost = float(_vc["total"])
        except Exception:
            pass
        _ft = _fits.get(sym)                    # this valuable's OWN fitted strategy (fingerprint), if any
        # 5.3 QUALITY FLOOR (M11): a fit with no dip distribution is a default wearing a
        # fingerprint's name (ONDO receipt: "fp dip~0.00% → tgt 3.74% ?"). DEGENERATE fits
        # fall back to vol-native and SAY SO; they never set a live target again.
        if _ft is not None and ((float(_ft.get("typical_dip") or 0.0) <= 0.0)
                                or (int(_ft.get("dip_samples") or _ft.get("n") or 0) < 5)):
            actions.append({"act": "NOTE", "sym": sym,
                            "why": "fingerprint DEGENERATE (dip~0 or n<5) — vol-native fallback (T40)"})
            _ft = None
        _use_target = float(_ft["target"]) if _ft else target
        _use_stop = max(float(_ft["stop"]), float(fmin or 0)) if _ft else stop_
        # ── 7.0 FALLING-KNIFE FLOOR-CONFIRM: on a collapsing tape a dip is not a
        # bargain until the name PRINTS A FLOOR. In a DOWNTREND, require the last
        # k prints to hold above the window low before any dip-buy (the operator's
        # July-17 lesson: no bounce exists while the whole market is still falling).
        _fk = (cat.get("floor_confirm") or {})
        if (str(_fk.get("mode", "auto")).lower() == "auto"
                and str(_regime or "").upper().startswith("DOWN")):
            _fw = [q for q in px_of(sym)[-int(_fk.get("window", 6)):] if q]
            if len(_fw) >= 3:
                _fmn = min(_fw)
                _kk = max(1, int(_fk.get("stabilize_prints", 2)))
                _tail = _fw[-_kk:]
                _floor_ok = (all(t2 > _fmn * (1 + float(_fk.get("eps", 0.001))) for t2 in _tail)
                             and _fw[-1] != _fmn)
                if not _floor_ok:
                    actions.append({"act": "SKIP", "sym": sym,
                                    "why": (f"falling knife — no floor yet (last {_kk} prints must hold "
                                            f"above the {len(_fw)}-print low; still printing lows)")})
                    continue
        # ── 7.0 THE GEOMETRY GATE (the Law of Winnable Trades) ──────────────────
        _grow = _geo.get(sym) or {}
        if _g_on:
            _ratio = float(_gk.get("max_stop_ratio", 1.5))
            if _use_stop > _use_target * _ratio:
                _use_stop = _use_target * _ratio        # cap NARROWS risk — never widens (Law 21)
        _pstar = ((_use_stop + cost) / (_use_target + _use_stop)
                  if (_use_target + _use_stop) > 0 else None)
        _pfloor = ((_grow.get("p_floor_pct") or 0) / 100.0
                   if _grow.get("p_floor_pct") is not None else None)
        if _g_on and _pstar is not None:
            if _grow.get("verdict") == "UNTRADEABLE:geometry":
                actions.append({"act": "SKIP", "sym": sym,
                                "why": f"UNTRADEABLE:geometry — honest stop {_grow.get('stop_vol_pct')}% "
                                       f"vs target {_grow.get('target_pct')}% (no geometry can win)"})
                continue
            if _pfloor is not None and _pfloor < _pstar + float(_gk.get("evidence_margin", 0.03)):
                actions.append({"act": "SKIP", "sym": sym,
                                "why": f"UNTRADEABLE:evidence — needs {round(_pstar*100,1)}% wins, "
                                       f"proven floor {round(_pfloor*100,1)}% ({_grow.get('evidence')})"})
                continue
        if _sz_halt:
            continue
        if _factor_over:
            actions.append({"act": "SKIP", "sym": sym,
                            "why": f"one-factor law — crypto exposure {((_sz.get('factor') or {}).get('used_pct'))}% "
                                   f"≥ cap {((_sz.get('factor') or {}).get('cap_pct'))}% (10 alts = 1 bet)"})
            continue
        net_margin = _use_target - cost         # fraction of the position kept if the target hits, after fees
        # GOLDEN RULE: a close must net >= min_take AFTER fees or we don't take the trade. This also kills
        # the dust bug: when cash is too low to clear the floor we SKIP instead of buying pennies.
        if net_margin <= 0:
            actions.append({"act": "SKIP", "sym": sym, "why": "fee>=target — can never net positive"})
            continue
        # 5.1B CONVICTION SIZING — the flat-$1000 era ends: wager scales with what
        # this valuable has EARNED (fingerprint bounce-reliability · this book's own
        # win history on the symbol · its multi-timeframe confluence), clamped to
        # knob bounds. Every sized trade logs its flat-base twin for the A/B.
        _conf = 0.5
        _base_frac = PER_NAME_FRAC
        if _cs_on:
            _rel = float((_ft or {}).get("bounce_reliability") or 0.5)
            _hn = _hw = 0
            for _t2 in pbook.trades[-300:]:
                if _t2.get("sym") == sym and _t2.get("side") == "SELL":
                    _hn += 1
                    _hw += 1 if (_t2.get("pnl") or 0) > 0 else 0
            _wr = (_hw / _hn) if _hn else 0.5
            _cf = float(_mtf_syms.get(sym) or 0.0)          # −8.5..+8.5
            # 5.1 FINAL: prefer the UNIFIED confidence engine (blends peak rhythm, phase,
            # fingerprint, MTF, dip extension) when it has scored this name; fall back to
            # the 3-factor blend otherwise. This is the "use everything" directive landed.
            _ce_score = None
            try:
                _ce_score = (_ce_map or {}).get(sym)
            except Exception:
                _ce_score = None
            if _ce_score is not None:
                _conf = float(_ce_score)
            # 7.0.7: floor proximity shapes conviction (see the block above for the evidence).
            if _fp_mult != 1.0:
                _conf = float(_conf) * _fp_mult
            # ── 7.0 NEWS PULSE — shadow-log every sized candidate; tilt only when mode='on' ──
            _nk7 = (cat.get("news_tilt") or {})
            _nmode7 = str(_nk7.get("mode", "shadow")).lower()
            _heat7, _sent7 = _np7.get(sym, (0, None))
            if _nmode7 != "off" and (_heat7 or _sent7 is not None):
                try:
                    with open(out / "NEWS_TILT_AB.jsonl", "a") as _nf7:
                        _nf7.write(json.dumps({"t": now.isoformat(), "sym": sym, "book": book,
                                               "heat_48h": _heat7, "sent": _sent7, "mode": _nmode7,
                                               "conf_before": round(float(_conf), 4)}) + "\n")
                except Exception:
                    pass
                if _nmode7 == "on" and _sent7 is not None:
                    _mt7 = float(_nk7.get("max_tilt", 0.10))
                    _conf = float(_conf) * (1.0 + max(-_mt7, min(_mt7, float(_sent7) * _mt7)))
            try:
                _ck = (cat.get("compounder") or {})
                if str(_ck.get("mode", "auto")).lower() == "auto":
                    _cm = _comp_map.get(sym)
                    if _cm is not None:
                        _mt = float(_ck.get("max_tilt", 1.25))
                        _tilt = 1.0 + (float(_cm) - 0.5) * 2.0 * (_mt - 1.0)
                        _tilt = min(max(_tilt, 1.0 / _mt), _mt)
                        _conf = min(1.0, max(0.0, _conf * _tilt))
            except Exception:
                pass
            else:
                _conf = 0.45 * _rel + 0.35 * _wr + 0.20 * max(0.0, min(1.0, (_cf + 2.0) / 8.0))
            _mult = 0.5 + 2.0 * _conf                        # 0.5×..2.5×
            _base_frac = max(float(_cs.get("floor_frac", 0.05)),
                             min(float(_cs.get("max_frac", 0.25)), PER_NAME_FRAC * _mult))
        base = min(pbook.equity(mk) * _base_frac, pbook.cash * 0.95)
        cap = pbook.cash * 0.95
        budget = min(max(base, min_take / net_margin), cap)   # size UP so the target clears the floor
        if budget * net_margin < min_take - 1e-9:             # even max affordable size can't clear it
            actions.append({"act": "SKIP", "sym": sym,
                            "why": "cannot clear $%.2f net (need $%.0f, cash $%.0f)" % (min_take, min_take / net_margin, cap)})
            continue
        budget = budget * _sz_mult
        if budget < 25:
            continue
        if _mk_on and sym not in _pend and sym not in pbook.positions:
            from datetime import timedelta as _td8
            _pend[sym] = {"limit": lp, "wager": budget, "cost": cost,
                          "target": _use_target, "stop": _use_stop,
                          "expected": net_margin, "conviction": cv,
                          "p_star_pct": round((_pstar or 0) * 100, 1) if _pstar else None,
                          "p_floor_pct": round((_pfloor or 0) * 100, 1) if _pfloor is not None else None,
                          "pred": _pred_map.get(sym),
                          "expires": (now + _td8(minutes=_mk_win)).isoformat()}
            actions.append({"act": "REST", "sym": sym,
                            "why": f"post-only maker limit @ {lp} ({int(_mk_win)}m) — "
                                   f"paid the spread or no trade"})
            continue
        if pbook.buy(sym, budget, lp, cost, now.isoformat(),
                     target=_use_target, stop=_use_stop, conviction=cv, expected=net_margin):
            try:
                pbook.positions[sym]["p_star_pct"] = (round((_pstar or 0) * 100, 1)
                                                      if _pstar else None)
                pbook.positions[sym]["p_floor_pct"] = (round((_pfloor or 0) * 100, 1)
                                                       if _pfloor is not None else None)
                pbook.positions[sym]["pred"] = _pred_map.get(sym)
                if pbook.trades and pbook.trades[-1].get("side") == "BUY":
                    pbook.trades[-1]["p_star_pct"] = pbook.positions[sym]["p_star_pct"]
                    pbook.trades[-1]["pred"] = pbook.positions[sym]["pred"]
                pbook.positions[sym]["entry_regime"] = _regime
                pbook.positions[sym]["exp_hold_min"] = _exp_hold.get(sym)
                pbook.positions[sym]["style"] = _style
                pbook.positions[sym]["champion_entry"] = champion
                pbook.positions[sym]["conv_frac"] = round(_base_frac, 4)
                pbook.positions[sym]["base_wager_usd"] = round(pbook.equity(mk) * PER_NAME_FRAC, 2)
                pbook.positions[sym]["conviction_conf"] = round(_conf, 3)
                pbook.trades[-1]["conv_frac"] = round(_base_frac, 4)
                pbook.trades[-1]["base_wager_usd"] = round(pbook.equity(mk) * PER_NAME_FRAC, 2)
                pbook.trades[-1]["conviction_conf"] = round(_conf, 3)
                pbook.trades[-1]["entry_regime"] = _regime
                pbook.trades[-1]["style"] = _style   # trend vs range: the per-symbol playstyle dataset
                pbook.trades[-1]["champion"] = champion   # which strategy made THIS trade (per-trade label)
                if _ft:
                    pbook.positions[sym]["fit"] = {"entry": _ft.get("entry"), "target": _use_target,
                                                   "stop": _use_stop, "typical_dip": _ft.get("typical_dip"),
                                                   "typical_bounce": _ft.get("typical_bounce"),
                                                   "reliability": _ft.get("bounce_reliability"),
                                                   "trend": _ft.get("trend"), "strong_up": _ft.get("strong_up")}
                    pbook.trades[-1]["fit"] = ("fp dip~%.2f%%\u2192tgt %.2f%% stop %.1f%% %s%s"
                        % ((_ft.get("typical_dip") or 0)*100, _use_target*100, _use_stop*100,
                           _ft.get("trend") or "?", " reliable" if (_ft.get("bounce_reliability") or 0)>=0.6 else ""))
                    pbook.trades[-1]["fit_target_pct"] = round(_use_target*100, 3)
            except Exception:
                pass
            actions.append({"act": "BUY", "sym": sym, "move_pct": round(h1 * 100, 2), "conviction": cv,
                            "expected_net_usd": round(budget * net_margin, 2)})

    pbook.save(out / f"paper_book_{book}.json")
    eq = pbook.equity(mk)
    _rej = {}
    for a_ in actions:
        if a_.get("act") in ("SKIP", "REGIME_BLOCK"):
            k_ = (a_.get("why") or "other").split(" \u2014")[0].split(" (")[0][:44]
            _rej[k_] = _rej.get(k_, 0) + 1
    _bought = sum(1 for a_ in actions if a_.get("act") == "BUY")
    for d_ in (_dtrace if "_dtrace" in dir() else []):
        pass
    try:
        for d_ in _dtrace:
            if any(a_.get("act") == "BUY" and a_.get("sym") == d_["sym"] for a_ in actions):
                d_["fate"] = "BOUGHT"
    except Exception:
        _dtrace = []
    funnel = {"seen": len(side_marks),
              "entry_warm": sum(1 for s_ in side_marks if s_ in _WARM_SYMS),
              "candidates_after_gates": len(cands), "bought": _bought, "rejections": _rej,
              # 7.1: the license, stated on the funnel itself so no panel ever has to guess
              "armed": _armed, "arming_why": _arming_why}
    try:
        _pend_all[book] = _pend
        (out / "MAKER_PENDING.json").write_text(json.dumps(_pend_all, indent=1))
    except Exception:
        pass

    return {
        "funnel": funnel,
        "decision_trace_live": _dtrace,
        "equity": round(eq, 2),
        "cash": round(pbook.cash, 2),
        "realized_pnl": round(pbook.realized_pnl, 2),
        # 7.0.3: the portal cards + click-ins render this as "vaulted" (non-spendable harvest).
        "reserve_usd": round(float(getattr(pbook, "reserve_usd", 0.0)), 2),
        "return_pct": round((eq / START_CASH - 1) * 100, 2),
        "open_positions": len(pbook.positions),
        "positions": [{"sym": s, "qty": round(p["qty"], 4), "entry": round(p["entry"], 6),
                       "mark": round(side_marks.get(s, (p["entry"], 0))[0], 6),
                       "t": p.get("t"),
                       "wager_usd": p.get("wager_usd"),
                       "target": p.get("target"), "stop": p.get("stop"),
                       "conviction": p.get("conviction"),
                       "style": p.get("style"),
                       "entry_regime": p.get("entry_regime"),
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
    # ── 7.0: the gate and the governor refresh BEFORE any side trades (same-cycle truth) ──
    try:
        from .geometry import build_geometry as _bg7
        from .sizer import build_sizer as _bs7
        _bs7(out_dir)
        _bg7(out_dir)
    except Exception:
        pass
    """One paper-trading cycle for BOTH sides. Persists each book and emits the
    cockpit summary docs/data/paper_sim_live.json."""
    out = Path(out_dir)
    # 7.1 ONE-KEY LAW, retroactive: re-key any open position / resting order already booked
    # under a non-canonical spelling (the DOGEUSDT position), so it can be marked and exited
    # instead of freezing. Idempotent; every rename is journaled to CANON_MIGRATIONS.jsonl.
    try:
        from .canon_keys import canonicalize_positions as _ckp7
        _mig7 = _ckp7(out)
        if _mig7.get("migrated") or _mig7.get("flagged"):
            print("  one-key law: %d open key(s) re-keyed, %d flagged (CANON_MIGRATIONS.jsonl)"
                  % (_mig7.get("migrated", 0), _mig7.get("flagged", 0)))
    except Exception:
        pass
    samples = load_all_samples(out)
    global _WARM_SYMS
    marks, _WARM_SYMS, marks_health = _marks_from_samples(samples)
    # 2.7 TRUE post-wipe quiet period (measured from wipe time): take no trades for the first window after a
    # reset, so the clean run starts from a genuinely quiet baseline even though price history is preserved.
    # ===== 3.0 REGIME AWARENESS — refreshed EVERY cycle (rapid-fire), gates capital =====
    # The operator's law: never fight a red tape. Each book gets a live regime read; on DOWNTREND a
    # "hard"-gated book takes ZERO new entries (exits/floors still run), and every blocked candidate is
    # logged to REGIME_AB.json and later SCORED against what price actually did — a running A/B proof of
    # whether sitting out red regimes saves money (spoiler we intend to verify, not assume).
    REGIMES = {}
    try:
        from .regime_classifier import build_regime_classifier as _brc
        _rg = _brc(out) or {}
        REGIMES = {bk: (v or {}).get("regime") for bk, v in (_rg.get("by_book") or {}).items()}
    except Exception:
        REGIMES = {}
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
    globals()["_LIVE_REGIMES"] = REGIMES
    try:
        from .market_calendar import equity_day_status
        eq_status, eq_reason = equity_day_status()
    except Exception:
        eq_status, eq_reason = "OPEN", "calendar unavailable"
    for bk in BOOKS:
        if bk != "crypto" and eq_status == "CLOSED":
            # market holiday/weekend: equity books hold state, take no actions, burn no work. Crypto runs 24/7.
            _pb = PaperBook.load(out / f"paper_book_{bk}.json")
            results[bk] = {"skipped": True, "why": "market closed — " + eq_reason,
                           "funnel": {"seen": sum(1 for s_ in marks if asset_class(s_) == bk),
                                       "entry_warm": 0, "candidates_after_gates": 0, "bought": 0,
                                       "rejections": {"market closed": 1}},
                           "decision_trace_live": [],
                           "equity": _pb.equity({}), "realized_pnl": _pb.realized_pnl,
                           "positions": [], "recent_trades": [], "actions": [],
                           "universe": 0, "universe_seen": 0}
            champ_names.setdefault(bk, "market closed")
            continue
        if bk == "crypto":
            params, name = champ_params, champ_name
        else:
            try:
                sc = json.loads((out / f"champion_{bk}.json").read_text())
                params, name = sc.get("live_params"), sc.get("champion")
            except Exception:
                params, name = None, None
        results[bk] = _run_side(out, marks, samples, bk, params, champion=name)
        champ_names[bk] = name
    # ── GEKKO — the aggressive probe (5th book): same rails (integrity quarantine, knife veto,
    #    heatshield floor, fee-honesty), LOWER thresholds, crypto 24/7. NEVER funded or mirrored by
    #    the Master; excluded from champion aggregation. Purpose: chase the low-hanging fruit AND
    #    manufacture forward evidence (trade-quality, calibration, fee-reality) at June-30-style
    #    aggression while the four governed books stay untouched.
    try:
        _gk = (_catalog(out).get("aggressive_book") or {})
        if _gk.get("enabled", True):
            _gp = {"dir": "mr",
                   "entry": float(_gk.get("entry", 0.02)),
                   "target": float(_gk.get("target", 0.02)),
                   "stop": float(_gk.get("stop", 0.06)),
                   "max_hold_min": float(_gk.get("max_hold_min", 5280.0))}
            results["aggressive"] = _run_side(out, marks, samples, "aggressive", _gp, champion=_gk.get("name", "GEKKO"))
            results["aggressive"]["display_name"] = _gk.get("name", "GEKKO")
            champ_names["aggressive"] = _gk.get("name", "GEKKO") + " (fixed aggressive profile)"
    except Exception as _ge:
        results["aggressive"] = {"error": str(_ge)}
    crypto, stock = results["crypto"], results["stock"]
    # 3-day backtest proof so the cockpit shows the engine works even when the
    # live tape is quiet and no setup is firing this exact cycle
    try:
        bt = backtest_through_sim(out, crypto_only=True)
    except Exception:
        bt = {}
    # score matured REGIME_AB entries: did the blocked trade dodge a loss or miss a win?
    try:
        _abp = out / "REGIME_AB.json"
        if _abp.exists():
            _led = json.loads(_abp.read_text())
            _hz = float(_catalog(out).get("regime_ab_horizon_min", 240))
            _ch = 0
            for _e in _led:
                if _e.get("outcome") is not None:
                    continue
                _m = marks.get(_e.get("sym"))
                if not _m:
                    continue
                try:
                    _age = (now - datetime.fromisoformat(_e["t"])).total_seconds() / 60.0
                except Exception:
                    continue
                if _age >= _hz and _e.get("px_at_block"):
                    _mv = _m[0] / _e["px_at_block"] - 1.0
                    _e["move_after_pct"] = round(_mv * 100, 2)
                    _e["outcome"] = "DODGED_LOSS" if _mv < 0 else "MISSED_WIN"
                    _ch += 1
            if _ch:
                _abp.write_text(json.dumps(_led[-3000:], indent=1))
            _done = [e for e in _led if e.get("outcome")]
            _dl = [e for e in _done if e["outcome"] == "DODGED_LOSS"]
            (out / "REGIME_AB_STATUS.json").write_text(json.dumps({
                "generated_at": _now(), "blocked_total": len(_led), "scored": len(_done),
                "dodged_losses": len(_dl), "missed_wins": len(_done) - len(_dl),
                "gate_saved_pct_sum": round(-sum(e.get("move_after_pct", 0) for e in _dl), 2),
                "gate_missed_pct_sum": round(sum(e.get("move_after_pct", 0) for e in _done if e["outcome"] == "MISSED_WIN"), 2),
                "verdict": "the A/B proof of the regime gate: blocked trades scored %.0f min later" % _hz}, indent=1))
    except Exception:
        pass
    summary = {
        "generated_at": _now(),
        "marks_health": marks_health,
        "equity_market": {"status": eq_status, "why": eq_reason},
        "regimes": REGIMES,
        "start_cash_each": START_CASH,
        "champion_strategy": champ_name,
        "champion_crypto": champ_names.get("crypto", "—"),
        "champion_stock": champ_names.get("stock", "market closed"),
        "champion_metal": champ_names.get("metal", "market closed"),
        "champion_energy": champ_names.get("energy", "market closed"),
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
        "aggressive": results.get("aggressive"),
        "metal": results["metal"], "energy": results["energy"],
        "combined_equity": round(sum(results[b]["equity"] for b in BOOKS), 2),
        "combined_realized_pnl": round(sum(results[b]["realized_pnl"] for b in BOOKS), 2),
        "backtest_3day_crypto": bt,
        "note": ("Internal paper sim, 4 independent books (crypto/stock/metal/energy), one canonical "
                 "key per asset (7.1 one-key law). Ghosts excluded; per-class fee floors. A book may "
                 "OPEN only when its own workshop has PROMOTED a sleeve on real closed trades since "
                 "the wipe (arming gate) — until then it scans, marks, and manages exits only."),
    }
    # 5.0 FINGERPRINTS: publish the per-valuable identities + fitted realistic strategies driving live
    # entries, so the dashboard shows HOW the engine reads each graph. Bounded scan to stay cheap.
    try:
        from .fingerprint import build_fingerprints as _bfp
        # 5.1B — CLASS-QUOTA universe (the GOLD fix): the old first-500-in-dict-order
        # fill let crypto flood the cap before metals/energy ever loaded, so XAU
        # could sit unfitted forever. Metals + energy now enter FIRST (all of them),
        # then stocks and crypto by history depth, under the same 500 ceiling —
        # every industry gets its custom fit, gold included, from the next cycle.
        # ── 7.0.2 THE CANONICAL MERGE (root cause of "crypto has no fingerprints") ──
        # The old rule SKIPPED every crypto key without a dash. That silently discarded
        # the ENTIRE ccxt tape — 404 symbols × ~300 candles = 121,069 datapoints of real
        # history — because ccxt keys are BTCUSDT / BTCUSD, not BTC-USD. Before a genesis
        # wipe this was invisible: price_samples had weeks of canonical depth. After one,
        # the canonical keys are ~14 prints old and ALL the depth sits in keys we threw
        # away → 0 crypto fingerprints → 0 geometry rows → 0 crypto trades, for ~17 hours.
        # Now non-canonical crypto is CANONICALIZED and its history UNIONED onto the
        # canonical key (same rule as scripts/remap_keys.py), so BTCUSDT's 300 candles
        # deepen BTC-USD immediately. Fingerprints only — marks/entries are untouched.
        def _canon7(k):
            if k.endswith("-USD"):
                return k
            if k.endswith("-USDT"):
                return k[:-5] + "-USD"
            if "/" in k:
                return k.split("/")[0] + "-USD"
            if k.endswith("USDT"):
                return k[:-4] + "-USD"
            if k.endswith("USDC"):
                return k[:-4] + "-USD"
            if k.endswith("USD") and len(k) > 4:
                return k[:-3] + "-USD"
            return None

        _fp_rows = {}
        for _s, _rows in samples.items():
            _cl = asset_class(_s)
            _key = _s
            if _cl == "crypto" and "-" not in _s:
                _key = _canon7(_s)
                if not _key:
                    continue
            _prev = _fp_rows.get(_key)
            if _prev is None:
                _fp_rows[_key] = list(_rows)
            else:
                _m7 = {t: p for t, p in _prev}
                for _t7, _p7 in _rows:
                    _m7.setdefault(_t7, _p7)
                _fp_rows[_key] = sorted(_m7.items())
        _by_cls = {}
        for _s, _rows in _fp_rows.items():
            _cl = asset_class(_s)
            _pp = [p for _t, p in _rows if p and p > 0]
            if len(_pp) >= 30:
                _by_cls.setdefault(_cl, []).append((_s, _pp))
        for _lst in _by_cls.values():
            _lst.sort(key=lambda x: len(x[1]), reverse=True)
        _quota = (("metal", 10**9), ("energy", 10**9), ("stock", 160), ("crypto", 10**9))
        _sp = {}; _cnt = 0
        # 5.3.1 M11 — the ceiling is a KNOB, not a constant. The old hard 500 meant 86%
        # of the universe never got its own chart read. scan_cap governs how many names
        # are FIT; publish_cap governs how many cards reach the store/dashboard.
        _fpk = (_catalog(out).get("fingerprint_coverage") or {})
        _scan_cap = int(_fpk.get("scan_cap", 1600))
        _pub_cap = int(_fpk.get("publish_cap", 1200))
        for _cls, _cap in _quota:
            for _s, _pp in _by_cls.get(_cls, [])[:_cap]:
                if _cnt >= _scan_cap:
                    break
                _sp[_s] = _pp; _cnt += 1
        _fmap = (_catalog(out).get("floor_min") or {})
        _floor = {_s: _fmap.get(asset_class(_s), 0.06) for _s in _sp}
        _bfp(out, _sp, rows_by_sym={s: _fp_rows.get(s, samples.get(s)) for s in _sp}, floor_by_sym=_floor,
             limit=_pub_cap)
    except Exception:
        pass
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
    # 5.1: report whether the floor resolver is actually APPLYING the measured winner
    try:
        _hk2 = (_catalog(out).get("heatshield_autotune") or {})
        _auto_on = str(_hk2.get("mode", "auto")).lower() == "auto"
        _auto_applied = bool(_auto_on and shield.get("trades", 0) >= int(_hk2.get("evidence_min", 60)) and delta != 0.0)
    except Exception:
        _auto_applied = False
    res = {
        "autotune_applied": _auto_applied,
        "autotune_chosen_floor_pct": (round(HEATSHIELD_FLOOR*100,2) if delta > 0 else round(STOP*100,2)) if _auto_applied else None,
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
