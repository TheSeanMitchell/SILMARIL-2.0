"""
silmaril.execution.leaned_in_router — holdings mirror the leaned-in list,
weighted by conviction and momentum, gated by regime. (June 16, keys granted.)

OPERATOR MANDATE: the Alpaca holdings should track the dashboard's
"leaned-in" names — pile capital onto the strongest/rising names, weed out
the ones that fall off or cool, on every cron read. Aggressive on crypto.
Always keep enough cash to rotate in/out each cycle.

This module SELECTS and SIZES; it does not change any agent, score, or
conviction. It reads signals.json (the same artifact the dashboard reads)
and emits a per-account target book the executor carries out under all the
existing safety rails. It never invents a signal or overrides a rail.

THE RULES IT ENCODES
  1. List membership = the dashboard's exact buckets:
       Strong Positive  : sentiment >= 0.50   (always eligible)
       Mildly Positive  : 0.15 < sentiment < 0.50
     REGIME SWITCH: in a strong/constructive tape we ALSO trade Mildly
     Positive (wider net); in a defensive/stress tape we trade Strong
     Positive ONLY (tighten to best ideas). Regime read from
     regime_axes.json composite.
  2. Weight by CONVICTION: a name's target weight scales with its
     sentiment strength — higher conviction gets more capital.
  3. Weight by MOMENTUM: a name rising since the last read (pct_since_prev
     / pct_today from news_fingerprint deltas) gets a multiplier — money
     moves toward what's working THIS read (the XLM-30%-run lesson).
  4. ROTATION RESERVE: never deploy 100%. Keep RESERVE_PCT in cash so
     there's always capital to enter a fresh winner and absorb a sell.
  5. SCALE in/out: targets are weights, so a name that strengthens pulls
     more on the next read (double-down) and one that weakens sheds
     (scale-out) — the executor diffs target vs held each cycle.

Output: docs/data/leaned_in_plan.json — fully transparent target book per
account with the weight math shown. Deterministic, offline-safe.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

VERSION = "leaned-in-router-2.0"
STRONG_POS_THRESHOLD = 0.50
MILD_POS_LOW = 0.15
TOP_N_PER_CLASS = 8

# capital discipline — OPERATOR DIRECTIVE June 16: FULL AGGRESSION.
# No idle reserve (deploy the whole book); no soft per-name cap beyond a
# loose safety ceiling so a single on-fire name CAN dominate. Momentum is
# the dominant lever — a strong run should drain capital out of the rest.
RESERVE_PCT = 0.0             # deploy the full 10k (operator: "screw the reserves")
MAX_NAME_WEIGHT = 0.60        # loose safety ceiling only — one fire can take most of the book
MOMENTUM_MULT_MAX = 4.0       # a strong run pulls HARD (up to 4x) — pile onto winners
MOMENTUM_MULT_MIN = 0.25      # a breaking run sheds fast (down to 0.25x) — scale out early

_VAL_CLASSES = {"crypto", "token", "commodity", "commodities", "fx",
                "macro", "bonds/rates"}

# regimes in which we WIDEN the net to include Mildly Positive
_RISK_ON_COMPOSITES = {"FULL_RISK_ON", "CONSTRUCTIVE", "RISK_ON"}
_DEFENSIVE_COMPOSITES = {"DEFENSIVE", "STRESS", "CHOP"}


def _is_valuable(d: Dict[str, Any]) -> bool:
    t = str(d.get("ticker") or "").upper()
    if t.endswith("-USD") or t.endswith("USDT"):
        return True
    return str(d.get("asset_class") or "").lower() in _VAL_CLASSES


def _load(p: Path, default: Any) -> Any:
    try:
        return json.loads(p.read_text())
    except Exception:
        return default


def _dump(path: Path, obj: Any) -> None:
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(obj, f, indent=2, allow_nan=False)
        os.replace(tmp, str(path))
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def _regime_allows_mild(out: Path) -> Dict[str, Any]:
    """Read the composite regime; decide whether Mildly Positive names are
    in play this cycle. Strong/constructive -> yes (wider). Defensive ->
    no (Strong only). Unknown -> conservative default (Strong only)."""
    ax = (_load(out / "regime_axes.json", {}) or {}).get("axes", {})
    comp = str(ax.get("composite") or "UNKNOWN")
    if comp in _RISK_ON_COMPOSITES:
        return {"include_mild": True, "composite": comp,
                "stance": "RISK-ON — widen to Mildly Positive too"}
    return {"include_mild": False, "composite": comp,
            "stance": ("DEFENSIVE/UNKNOWN — Strong Positive only"
                       if comp in _DEFENSIVE_COMPOSITES or comp == "UNKNOWN"
                       else f"{comp} — Strong Positive only")}


def _momentum_mult(delta: Optional[Dict[str, Any]]) -> float:
    """Map a name's since-last-read move to a capital multiplier. Rising ->
    >1 (double down), falling -> <1 (scale out). Uses pct_since_prev first
    (move since the previous read — the cleanest 'is it working NOW' signal),
    then pct_today. No delta yet -> neutral 1.0."""
    if not delta:
        return 1.0
    pct = delta.get("pct_since_prev")
    if pct is None:
        pct = delta.get("pct_today")
    if pct is None:
        return 1.0
    # AGGRESSIVE momentum slope (operator: "let momentum dictate
    # everything"). +3%/read -> ~1.6x; +10% -> ~3x; +20% -> capped 4x;
    # -3% -> ~0.7x; -8%+ -> floor 0.25x (a breaking run is exited fast).
    m = 1.0 + float(pct) * 0.20
    return max(MOMENTUM_MULT_MIN, min(MOMENTUM_MULT_MAX, m))


def _candidates(debates, include_mild: bool, deltas=None, chain=None):
    """Select the candidate pool. THREE doors in:
      DOOR 1 — sentiment: score >= STRONG_POS_THRESHOLD (or > MILD when risk-on)
      DOOR 2 — daily momentum (delta): rising since last read / on the week.
      DOOR 3 — THE FIRE LIST (operator's golden law, June 18): any name HOT on
               the 10-min sample chain (positive composite + consistent green
               across windows) is admitted DIRECTLY, regardless of sentiment.
               'The hot list is GOD.' The chain decides; sentiment no longer
               gates a genuinely-moving name out of the buyable set.
    """
    deltas = deltas or {}
    chain = chain or {}

    def sent(d):
        return float(d.get("sentiment_score") or 0.0)

    def mom_of(t):
        x = deltas.get(str(t).upper()) or deltas.get(str(t).upper().replace("USD", "-USD"))
        if not x:
            return None
        prev = x.get("pct_since_prev")
        wk = x.get("pct_wtd")
        tod = x.get("pct_today")
        return {"prev": prev, "wk": wk, "tod": tod}

    def chain_of(t):
        return (chain.get(str(t).upper())
                or chain.get(str(t).upper().replace("USD", "-USD"))
                or chain.get(str(t).upper().replace("-USD", "USD")))

    pool = {}
    # DOOR 1 — sentiment
    for d in debates:
        s = sent(d)
        if s >= STRONG_POS_THRESHOLD or (include_mild and MILD_POS_LOW < s < STRONG_POS_THRESHOLD):
            pool[str(d.get("ticker"))] = d
    # DOOR 2 — daily-delta momentum
    for d in debates:
        t = str(d.get("ticker"))
        if t in pool:
            continue
        if sent(d) <= 0:
            continue
        m = mom_of(t)
        if not m:
            continue
        rising_now = (m["prev"] is not None and m["prev"] >= 1.0)
        strong_week = (m["wk"] is not None and m["wk"] >= 8.0)
        up_today = (m["tod"] is not None and m["tod"] >= 1.5)
        if rising_now or strong_week or up_today:
            d = dict(d); d["_surfaced_by"] = "momentum"
            pool[t] = d
    # DOOR 3 — THE FIRE LIST: the 10-min chain admits hot names directly.
    # A name is "on fire" when its weighted composite is positive AND it's
    # green across enough windows (fire >= 0.6) — i.e. it satisfied the 10-min
    # threshold and is holding/climbing. Sentiment is NOT consulted here; a
    # hot tape with neutral/no news still gets bought (that's the edge). We
    # still exclude names with clearly BAD news (sentiment < -0.5) to avoid
    # buying into an active disaster, but neutral/unknown sentiment is fine.
    for d in debates:
        t = str(d.get("ticker"))
        if t in pool:
            continue
        c = chain_of(t)
        if not c:
            continue
        comp = float(c.get("composite") or 0.0)
        fire = float(c.get("fire") or 0.0)
        w = c.get("windows") or {}
        slr = w.get("since_last")
        # ON FIRE: positive composite + consistent green, OR a fresh 10-min pop
        on_fire = (comp > 0.5 and fire >= 0.6) or (slr is not None and slr >= 0.5)
        if on_fire and sent(d) > -0.5:
            d = dict(d); d["_surfaced_by"] = "fire_list"
            pool[t] = d
    return list(pool.values())


def _target_book(names: List[Dict[str, Any]], deltas: Dict[str, Any],
                 chain: Optional[Dict[str, Any]] = None
                 ) -> List[Dict[str, Any]]:
    """Conviction × momentum weighting → deployable fraction, capped per name.
    When the intraday momentum CHAIN is present, it drives the momentum term
    (composite + fire), so capital flows to what's actually moving across the
    10-min/hour/day windows — not to whatever has the highest news sentiment.
    """
    chain = chain or {}

    def _chain_mult(t):
        c = chain.get(t) or chain.get(t.replace("USD", "-USD"))
        if not c:
            return None
        comp = float(c.get("composite") or 0.0)
        fire = float(c.get("fire") or 0.0)
        # composite (weighted % move) sets direction/size; fire (consistency
        # of green across windows) amplifies. +0.5% composite, all-green →
        # strong pull; negative composite → shrinks toward the floor.
        m = 1.0 + comp * 0.6 + (fire - 0.5) * 1.2
        return max(MOMENTUM_MULT_MIN, min(MOMENTUM_MULT_MAX, m))

    scored = []
    for d in names:
        t = str(d.get("ticker")).upper()
        conv = abs(float(d.get("sentiment_score") or 0.0))     # conviction (floor)
        cm = _chain_mult(t)
        mom = cm if cm is not None else _momentum_mult(deltas.get(t))
        # momentum SQUARED so a name on fire drains capital from the rest.
        # conviction has a FLOOR of 0.3 so a hot-but-mild-sentiment name
        # (the ALGO/JTO case) still gets real size from its momentum.
        raw = max(conv, 0.30) * (mom ** 2)
        scored.append({"ticker": t, "conviction": round(conv, 3),
                       "momentum_mult": round(mom, 3),
                       "raw_weight": raw})
    total = sum(s["raw_weight"] for s in scored) or 1.0
    deployable = 1.0 - RESERVE_PCT
    # First pass: proportional weights. Then redistribute any overflow from
    # names that hit MAX_NAME_WEIGHT back across the uncapped names, so the
    # FULL book always deploys (no idle capital just because a winner capped).
    weights = {s["ticker"]: (s["raw_weight"] / total) * deployable
               for s in scored}
    for _ in range(6):  # converges fast
        capped = {t: w for t, w in weights.items() if w > MAX_NAME_WEIGHT}
        if not capped:
            break
        overflow = sum(w - MAX_NAME_WEIGHT for t, w in capped.items())
        for t in capped:
            weights[t] = MAX_NAME_WEIGHT
        uncapped = [t for t in weights if weights[t] < MAX_NAME_WEIGHT - 1e-9]
        base = sum(weights[t] for t in uncapped) or 1.0
        for t in uncapped:
            weights[t] += overflow * (weights[t] / base)
    out = []
    for s in scored:
        out.append({**s, "target_weight": round(weights[s["ticker"]], 4)})
    out.sort(key=lambda x: x["target_weight"], reverse=True)
    return out


def _held(state: Dict[str, Any]) -> List[str]:
    out = []
    for p in (state.get("positions_snapshot")
              or state.get("positions") or []):
        s = str(p.get("symbol") or p.get("ticker") or "").upper()
        if s and s.replace("/", "").replace("-", "") != "SGOV":
            out.append(s)
    return out


# Account roles: which list each account mirrors.
#   LEGACY (#1)    -> the STOCK leaned-in book
#   HARVEST_3 (#2) -> the CRYPTO book WITH daily-goal harvest (experiment)
#   HARVEST_5 (#3) -> the CRYPTO book, hold-on-conviction
# #2 and #3 trade the SAME crypto hotlist so the only difference is the
# harvest strategy — a clean head-to-head comparison.
_STOCK_ACCOUNTS = (("LEGACY", "alpaca_paper_state.json"),)
_VALUABLES_ACCOUNTS_R = (("HARVEST_3", "alpaca_h3_state.json"),
                         ("HARVEST_5", "alpaca_h5_state.json"))


def _norm_held_to_dash(sym: str) -> str:
    """Alpaca reports crypto positions as BTCUSD; dashboard/signals use
    BTC-USD. Normalize a held crypto symbol back to the -USD form so it
    diffs cleanly against targets."""
    s = sym.upper().replace("/", "")
    if s.endswith("USD") and not s.endswith("-USD") and len(s) > 3:
        return s[:-3] + "-USD"
    return sym.upper()


def build_leaned_in_plan(out_dir,
                         debates: Optional[List[Dict[str, Any]]] = None
                         ) -> Dict[str, Any]:
    out = Path(out_dir)
    if debates is None:
        debates = (_load(out / "signals.json", {}) or {}).get("debates") or []
    deltas = (_load(out / "news_fingerprint.json", {}) or {}).get("deltas") or {}
    regime = _regime_allows_mild(out)

    # Load the 10-min sample chain FIRST so it can drive both candidate
    # selection (DOOR 3 — the fire list) and ranking below.
    _chain = (_load(out / "momentum_chain.json", {}) or {}).get("chains") or {}

    pool = _candidates(debates, regime["include_mild"], deltas, _chain)

    # ── MEAN-REVERSION FLIP (Alpha 2.11) — CRYPTO ONLY ───────────────────────
    # edge_lab proved it on 200k+ points: momentum loses here, oversold bounces.
    # So in MR mode we drop momentum crypto from the buyable set and replace it
    # with OVERSOLD LIQUID names (the momentum doors never admit a falling name).
    # Stocks are untouched — the finding is a crypto-universe finding. Marginal
    # and from a short window; the live paper run is the real out-of-sample test.
    _mr_active = False
    try:
        from .mean_reversion import MEAN_REVERSION_ENABLED, select_oversold
        if MEAN_REVERSION_ENABLED:
            _mr_active = True
            _os = list(select_oversold(debates, _chain).values())
            pool = [d for d in pool if not _is_valuable(d)] + _os
            print(f"[router][mean-rev] CRYPTO flipped to mean-reversion: "
                  f"{len(_os)} oversold liquid name(s) buyable; momentum crypto dropped")
    except Exception as _mre:
        print(f"[router][mean-rev] selection skipped: {_mre}")

    # FRESH-WINDOW ENTRY GATE (Dash to 2.1 — bootstrap §6). The PRIMARY fix for
    # nosedive entries: a name that is FALLING on the freshest 10-min read is
    # removed from the buyable set, no matter how strong its daily/weekly
    # windows are. The longer windows size up an already-rising name below; they
    # never rescue a falling one. Writes docs/data/entry_gate.json so the
    # operator can see, per name, exactly why a mover was bought or kept out.
    try:
        from .fresh_gate import apply_fresh_entry_gate
        _pre_gate = len(pool)
        if _mr_active:
            # MR mode: gate STOCKS only. Oversold crypto names are supposed to be
            # falling — gating them would block the entire strategy.
            _stx = [d for d in pool if not _is_valuable(d)]
            _cry = [d for d in pool if _is_valuable(d)]
            _stx, _gate_log = apply_fresh_entry_gate(_stx, _chain)
            pool = _stx + _cry
            _gate_log.setdefault("summary", {})["mean_reversion_crypto_exempt"] = len(_cry)
        else:
            pool, _gate_log = apply_fresh_entry_gate(pool, _chain)
        _dump(out / "entry_gate.json", _gate_log)
        _blocked = _gate_log["summary"]["blocked_falling_now"]
        if _blocked:
            print(f"[router][fresh-gate] blocked {_blocked} falling name(s) of "
                  f"{_pre_gate} considered; {len(pool)} remain buyable")
    except Exception as _fg_e:  # never let the gate take down routing
        print(f"[router][fresh-gate] skipped: {_fg_e}")

    # SELF-CORRECTING TRADABILITY FILTER (June 19): drop any name Alpaca has
    # rejected as "asset not found" (422). This is the fix for the expanded
    # universe surfacing on-fire coins Alpaca doesn't actually list (WLD,
    # DYDX, GALA, JTO, MANA, SAND, AXS...). Without this the chain ranks them
    # #1, the executor submits them, Alpaca 422s, and the cash sits idle while
    # only the few tradeable on-fire coins (AAVE/SOL) fill. Now untradeable
    # names never reach the book, so capital flows to what CAN be bought.
    try:
        from .tradability import load_blocklist, _norm as _tb_norm
        _blocked = load_blocklist(out)
        if _blocked:
            _before = len(pool)
            pool = [d for d in pool if _tb_norm(d.get("ticker")) not in _blocked]
            _dropped = _before - len(pool)
            if _dropped:
                print(f"[router] tradability: dropped {_dropped} untradeable "
                      f"name(s) Alpaca doesn't list")
    except Exception:
        pass

    # ── THE 10-MIN SAMPLE CHAIN drives ranking (June 17 golden law). When the
    # intraday momentum chain is available (built each run from price_samples),
    # rank by its composite (10-min read heaviest for crypto, longer windows
    # for stocks) and its fire meter. Sentiment is only the floor/tie-break.
    # Falls back to the daily-delta momentum if the chain is still warming up.

    def _chain_of(t):
        return _chain.get(str(t).upper()) or _chain.get(str(t).upper().replace("USD", "-USD"))

    def _mom(t):
        c = _chain_of(t)
        if c and c.get("composite") is not None:
            return float(c["composite"])
        # fallback: daily delta
        x = deltas.get(str(t).upper()) or deltas.get(str(t).upper().replace("USD", "-USD"))
        if not x:
            return 0.0
        prev = x.get("pct_since_prev")
        if prev is None:
            prev = x.get("pct_today")
        return float(prev or 0.0)

    def heat(d):
        t = d.get("ticker")
        s = abs(float(d.get("sentiment_score") or 0.0))
        c = _chain_of(t)
        # momentum composite leads; fire meter amplifies a consistently-green
        # name; sentiment is the floor/tie-break.
        comp = _mom(t)
        fire = float(c["fire"]) if (c and c.get("fire") is not None) else 0.0
        return comp * 1.0 + fire * 2.0 + s * 0.5
    stocks = sorted([d for d in pool if not _is_valuable(d)],
                    key=heat, reverse=True)[:TOP_N_PER_CLASS]
    if _mr_active:
        # MR mode: rank crypto by how oversold (deepest drop first — it bounces
        # hardest), not by momentum heat.
        try:
            from .mean_reversion import oversold_rank
            valuables = sorted([d for d in pool if _is_valuable(d)],
                               key=lambda d: oversold_rank(d.get("ticker"), _chain),
                               reverse=True)[:TOP_N_PER_CLASS]
        except Exception:
            valuables = [d for d in pool if _is_valuable(d)][:TOP_N_PER_CLASS]
    else:
        valuables = sorted([d for d in pool if _is_valuable(d)],
                           key=heat, reverse=True)[:TOP_N_PER_CLASS]

    stock_book = _target_book(stocks, deltas, _chain)
    val_book = _target_book(valuables, deltas, _chain)

    # DEFENSIVE BRAKE (operator directive June 17 — "common sense"): if even
    # the top candidates are broadly RED right now, don't deploy the full
    # book into a falling tape. Measure the median momentum of the top names;
    # if it's negative, raise the cash reserve and trim the book so we sit
    # out the bleed and wait for things to turn green — instead of buying the
    # same losers every cycle. When the tape is green, full aggression stands.
    def _book_tone(book):
        # Tone of the names we'd ACTUALLY buy heaviest (the top of the book),
        # not the whole list — a few weak tail names shouldn't make us sit out
        # when the leaders are green. Weight by target_weight so the tone
        # reflects where the capital is going.
        num = 0.0
        wsum = 0.0
        for b in book[:6]:  # the names that get real capital
            x = deltas.get(b["ticker"]) or deltas.get(b["ticker"].replace("USD", "-USD"))
            w = float(b.get("target_weight") or 0.0)
            if x and w > 0:
                v = x.get("pct_since_prev")
                if v is None:
                    v = x.get("pct_today")
                if v is not None:
                    num += float(v) * w
                    wsum += w
        # also fold in the 10-min chain composite of the leaders (the fire list)
        for b in book[:6]:
            c = _chain.get(b["ticker"]) or _chain.get(b["ticker"].replace("USD", "-USD"))
            w = float(b.get("target_weight") or 0.0)
            if c and c.get("composite") is not None and w > 0:
                num += float(c["composite"]) * w * 0.5
                wsum += w * 0.5
        return (num / wsum) if wsum > 0 else 0.0

    def _defensive_reserve(book):
        tone = _book_tone(book)
        # Operator directive (June 18 — "go hard on green, up to 100%"): only
        # pull back when the LEADERS are genuinely, deeply red. Any green or
        # flat leadership → deploy everything. This stops the brake from
        # idling capital while the hot list is full of green windows.
        if tone >= -0.25:
            return RESERVE_PCT          # green/flat/slightly-soft → FULL deploy
        if tone <= -3.0:
            return 0.50                 # deeply red leaders → hold half
        # gentle ramp only in the clearly-negative zone
        return min(0.50, (abs(tone) - 0.25) * 0.18)

    def account_plan(book, fn, role):
        st = _load(out / fn, {})
        held_raw = _held(st)
        held = [_norm_held_to_dash(h) for h in held_raw]
        tgt = [b["ticker"] for b in book]
        tgt_set = set(tgt)
        held_set = set(held)
        buy = [b for b in book if b["ticker"] not in held_set]
        sell = [h for h in held if h not in tgt_set]
        keep = [b for b in book if b["ticker"] in held_set]
        equity = float((st.get("account") or {}).get("equity") or 10000.0)
        _resv = _defensive_reserve(book)
        _deploy_frac = 1.0 - _resv
        deployable_cash = round(equity * _deploy_frac, 2)
        # attach a dollar target for each name (× deploy frac so a red tape
        # shrinks every position, not just leaves leftover cash unspent)
        for b in book:
            b["target_notional"] = round(equity * b["target_weight"] * _deploy_frac, 2)
        return {
            "role": role,
            "equity": equity,
            "reserve_pct": RESERVE_PCT,
            "deployable_cash": deployable_cash,
            "target_book": book,
            "buy": [b["ticker"] for b in buy],
            "sell": sell,
            "keep": [b["ticker"] for b in keep],
            "narrative": (
                f"{role}: mirror the leaned-in book — "
                f"buy {len(buy)} new ({', '.join(b['ticker'] for b in buy) or '—'}), "
                f"sell {len(sell)} cooled/fell-off ({', '.join(sell) or '—'}), "
                f"hold+resize {len(keep)}; {RESERVE_PCT:.0%} kept in cash to rotate"),
        }

    per_account = {}
    for account_id, fn in _STOCK_ACCOUNTS:
        per_account[account_id] = account_plan(stock_book, fn, "STOCKS")
    for account_id, fn in _VALUABLES_ACCOUNTS_R:
        per_account[account_id] = account_plan(val_book, fn, "CRYPTO/VALUABLES")

    plan = {
        "version": VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "regime": regime,
        "definition": (
            f"leaned-in = sentiment >= {STRONG_POS_THRESHOLD}"
            + (f" (+ mildly positive {MILD_POS_LOW}-{STRONG_POS_THRESHOLD} "
               f"because tape is risk-on)" if regime["include_mild"]
               else " only (defensive/unknown tape — tightened to best ideas)")
            + f", top {TOP_N_PER_CLASS}/class, weighted by conviction x momentum"),
        "weighting": {
            "reserve_pct": RESERVE_PCT,
            "max_name_weight": MAX_NAME_WEIGHT,
            "momentum_mult_range": [MOMENTUM_MULT_MIN, MOMENTUM_MULT_MAX],
            "note": ("target_weight = (conviction x momentum) normalized to "
                     f"{1-RESERVE_PCT:.0%} deployable, capped {MAX_NAME_WEIGHT:.0%}/name. "
                     "Rising-since-last-read names pull more (double-down); "
                     "cooling names pull less (scale-out)."),
        },
        "accounts": per_account,
        "law": ("holdings mirror the weighted leaned-in book each cron read: "
                "strengthen -> add, cool/fall-off -> trim/exit, always keep "
                "rotation cash. Executor still applies every safety rail; this "
                "selects + sizes only, never touches engine/agent logic."),
    }
    _dump(out / "leaned_in_plan.json", plan)

    # ── PRIORITY #0: TICKER COVERAGE AUDIT — prove the funnel every cycle.
    try:
        from .coverage_audit import build_coverage_audit
        _bought = {}
        for aid, apn in per_account.items():
            _bl = apn.get("buy") or []
            _bought[aid] = [(b if isinstance(b, str) else b.get("ticker"))
                            for b in _bl]
        build_coverage_audit(out, debates, pool, _bought, _chain)
    except Exception:
        pass

    return plan


if __name__ == "__main__":  # pragma: no cover
    import sys
    print(json.dumps(build_leaned_in_plan(
        Path(sys.argv[1]) if len(sys.argv) > 1 else Path("docs/data")),
        indent=2)[:1800])


# ─────────────────────────────────────────────────────────────────────
# EXECUTOR BRIDGE (June 16): convert the weighted target book into the
# plan-entry format execute_consensus_signals consumes, per account, so
# the leaned-in list actually drives orders. Each target becomes a BUY
# plan whose `score` carries the conviction x momentum weight (the
# executor sizes by score), and whose asset_class routes it correctly.
# Names NOT in the target book are emitted as SELL so the executor's
# existing exit logic rotates them out (fall-off => sell). The executor
# still applies every safety rail; this only supplies the selection.
# ─────────────────────────────────────────────────────────────────────

def _stale_rotation_sells(out_dir, account_id, acct, deltas, held_norm):
    """Operator's capital-rotation rule (June 16): when fresh HOT names are
    rising up the hotlist but the account is low on cash to buy them, shed
    the STALEST current holdings — ones that have gone flat (little/no move
    since recent reads) while others are jumping — to free capital for the
    risers. Returns a list of held tickers to trim.

    "Stale" = held, still on/near the list, but momentum ~flat, while at
    least one WANTED-but-unheld name has clearly stronger momentum. We only
    rotate when cash is genuinely tight, and only shed the flattest names,
    capped so we never churn the whole book.
    """
    try:
        st = _load(Path(out_dir) / acct.get("_state_file", ""), {})
    except Exception:
        st = {}
    acct_obj = st.get("account") or {}
    equity = float(acct_obj.get("equity") or 10000.0)
    cash = float(acct_obj.get("cash") or 0.0)
    # only rotate when cash is tight (< 8% of equity free)
    if equity <= 0 or (cash / equity) >= 0.08:
        return []

    def mom_of(t):
        x = deltas.get(t) or deltas.get(str(t).replace("USD", "-USD"))
        if not x:
            return 0.0
        v = x.get("pct_since_prev")
        if v is None:
            v = x.get("pct_today")
        return float(v or 0.0)

    book = acct.get("target_book", [])
    held_set = set(held_norm)
    # names we WANT but don't hold, ranked by momentum
    wanted_unheld = [(b["ticker"], mom_of(b["ticker"])) for b in book
                     if b["ticker"] not in held_set]
    hot_wanted = [t for t, m in wanted_unheld if m >= 1.5]  # clearly rising
    if not hot_wanted:
        return []  # nothing hot enough to rotate INTO

    # held names ranked by how FLAT they are (lowest momentum first)
    held_mom = sorted([(h, mom_of(h)) for h in held_norm], key=lambda x: x[1])
    # shed the flattest holders that are NOT themselves rising (mom < 0.5),
    # at most as many as there are hot names wanting in, capped at 2/cycle.
    sheddable = [h for h, m in held_mom if m < 0.5][:min(len(hot_wanted), 2)]
    return sheddable


def plans_by_account_from_leaned_in(out_dir,
                                    debates: Optional[List] = None
                                    ) -> Dict[str, List[Dict[str, Any]]]:
    """Return {account_id: [plan_entry, ...]} ready for
    run_all_harvest_accounts(plans_by_account=...)."""
    plan = build_leaned_in_plan(out_dir, debates=debates)
    deltas = (_load(Path(out_dir) / "news_fingerprint.json", {}) or {}).get("deltas") or {}
    # state-file lookup so stale-rotation can read each account's cash/holdings
    _state_files = {"LEGACY": "alpaca_paper_state.json",
                    "HARVEST_3": "alpaca_h3_state.json",
                    "HARVEST_5": "alpaca_h5_state.json"}
    out: Dict[str, List[Dict[str, Any]]] = {}
    for account_id, acct in plan.get("accounts", {}).items():
        entries: List[Dict[str, Any]] = []
        is_val_account = (acct.get("role") == "CRYPTO/VALUABLES")
        # BUY/scale targets — score scales with weight (0..2 range the
        # executor expects: weight 0.60 cap -> ~2.0, small -> ~0.5).
        for b in acct.get("target_book", []):
            w = float(b.get("target_weight") or 0)
            score = max(0.4, min(2.0, w / 0.30 * 2.0))  # 0.30 weight -> 2.0
            entries.append({
                "ticker": b["ticker"],
                "consensus_signal": "STRONG_BUY" if w >= 0.20 else "BUY",
                "consensus_conviction": round(min(0.95, 0.5 + w), 3),
                "score": round(score, 3),
                "asset_class": "crypto" if is_val_account else "equity",
                "target_weight": w,
                "target_notional": b.get("target_notional"),
                "source": "leaned_in_router",
            })
        # SELL fall-offs — names held but no longer in the book
        sell_syms = list(acct.get("sell", []))
        # STALE-ROTATION — shed flat holders to fund rising new names when
        # cash is tight (operator's rotate-toward-momentum rule).
        acct["_state_file"] = _state_files.get(account_id, "")
        held_norm = [_norm_held_to_dash(h) for h in
                     _held(_load(Path(out_dir) / acct["_state_file"], {}))]
        stale = _stale_rotation_sells(out_dir, account_id, acct, deltas, held_norm)
        for s in stale:
            if s not in sell_syms:
                sell_syms.append(s)
        for sym in sell_syms:
            _is_stale = sym in stale
            entries.append({
                "ticker": sym,
                "consensus_signal": "STRONG_SELL",
                "consensus_conviction": 0.9,
                "score": 0.0,
                "asset_class": "crypto" if is_val_account else "equity",
                "source": ("leaned_in_router_stale_rotation" if _is_stale
                           else "leaned_in_router_falloff"),
            })
        out[account_id] = entries
    return out
