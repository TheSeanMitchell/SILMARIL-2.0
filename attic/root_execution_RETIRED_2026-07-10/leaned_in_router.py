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


def _candidates(debates, include_mild: bool):
    def heat(d):
        return abs(float(d.get("sentiment_score") or 0.0))
    strong = [d for d in debates
              if float(d.get("sentiment_score") or 0.0) >= STRONG_POS_THRESHOLD]
    pool = list(strong)
    if include_mild:
        mild = [d for d in debates
                if MILD_POS_LOW < float(d.get("sentiment_score") or 0.0)
                < STRONG_POS_THRESHOLD]
        pool += mild
    return pool


def _target_book(names: List[Dict[str, Any]], deltas: Dict[str, Any]
                 ) -> List[Dict[str, Any]]:
    """Conviction x momentum weighting, normalized to the deployable
    fraction (1 - RESERVE_PCT), capped per name."""
    scored = []
    for d in names:
        t = str(d.get("ticker")).upper()
        conv = abs(float(d.get("sentiment_score") or 0.0))     # conviction
        mom = _momentum_mult(deltas.get(t))                    # momentum
        # momentum SQUARED so a name on fire drains capital from the rest
        # (operator: "drain out every other investment on things on fire").
        raw = conv * (mom ** 2)
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
#   LEGACY, HARVEST_3 -> the STOCK leaned-in book
#   HARVEST_5         -> the CRYPTO/VALUABLES leaned-in book (aggressive)
_STOCK_ACCOUNTS = (("LEGACY", "alpaca_paper_state.json"),
                   ("HARVEST_3", "alpaca_h3_state.json"))
_VALUABLES_ACCOUNT = ("HARVEST_5", "alpaca_h5_state.json")


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

    pool = _candidates(debates, regime["include_mild"])

    def heat(d):
        return abs(float(d.get("sentiment_score") or 0.0))
    stocks = sorted([d for d in pool if not _is_valuable(d)],
                    key=heat, reverse=True)[:TOP_N_PER_CLASS]
    valuables = sorted([d for d in pool if _is_valuable(d)],
                       key=heat, reverse=True)[:TOP_N_PER_CLASS]

    stock_book = _target_book(stocks, deltas)
    val_book = _target_book(valuables, deltas)

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
        deployable_cash = round(equity * (1.0 - RESERVE_PCT), 2)
        # attach a dollar target for each name from its weight
        for b in book:
            b["target_notional"] = round(equity * b["target_weight"], 2)
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
    aid, fn = _VALUABLES_ACCOUNT
    per_account[aid] = account_plan(val_book, fn, "CRYPTO/VALUABLES")

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

def plans_by_account_from_leaned_in(out_dir,
                                    debates: Optional[List] = None
                                    ) -> Dict[str, List[Dict[str, Any]]]:
    """Return {account_id: [plan_entry, ...]} ready for
    run_all_harvest_accounts(plans_by_account=...)."""
    plan = build_leaned_in_plan(out_dir, debates=debates)
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
        for sym in acct.get("sell", []):
            entries.append({
                "ticker": sym,
                "consensus_signal": "STRONG_SELL",
                "consensus_conviction": 0.9,
                "score": 0.0,
                "asset_class": "crypto" if is_val_account else "equity",
                "source": "leaned_in_router_falloff",
            })
        out[account_id] = entries
    return out
