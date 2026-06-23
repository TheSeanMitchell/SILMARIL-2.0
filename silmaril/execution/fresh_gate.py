"""
silmaril.execution.fresh_gate — the FRESH-WINDOW ENTRY GATE (Dash to 2.1).

THE BUG THIS FIXES (bootstrap §6 — "nosedive entries"):
  The momentum-chain composite is a WEIGHTED SUM across windows. A name that
  is dropping RIGHT NOW (negative 10-min read) can still score POSITIVE because
  an earlier daily run pulls the composite up. Real example from the repo data:

      XTZ: since_last = -0.085%  (NEGATIVE, weight .40)
           d1         = +4.292%  (weight .10)
           => composite = +0.735 (POSITIVE)  fire = 0.3

  So the router admitted XTZ via sentiment/daily-delta and SIZED it on the
  positive composite — buying a falling knife on STALE daily strength. Same
  story for XRP and BONK. These become the "exited_at_loss_on_up_move" and the
  bulk of the realized-loss leak.

THE LAW (operator's words, restated):
  The FRESH window is a GATE, not just a weight. A BUY is only allowed if the
  name is NOT falling on the freshest read. The longer windows may SIZE UP an
  already-rising name; they may NEVER RESCUE a falling one.

  Concretely: the 10-min read (`since_last`) must be >= FRESH_GATE_MIN_PCT
  (default 0.0% — "not falling"). If it is below that, the name is blocked from
  entry regardless of composite, sentiment, fire, or daily strength.

WHAT IT DELIBERATELY DOES NOT DO:
  • It does not touch sizing, scoring, conviction, or any engine logic. It is a
    pure routing gate: it removes falling names from the buyable set.
  • It does not gate EXITS — only entries. (Exit timing is the momentum-exit's
    job in alpaca_paper.py.)
  • If there is NO fresh read yet (chain too cold — needs >= 2 samples to
    compute `since_last`), it cannot judge, so it ALLOWS the name and flags it
    `ungated`. We never freeze all buying just because the chain is warming up;
    the gate only bites once it can actually see the 10-min read.

This module is the SINGLE SOURCE OF TRUTH for the rule. Both the router
(primary, pre-sizing) and the executor (belt-and-suspenders, pre-submit) call
`passes_fresh_entry_gate` so no legacy buy path can sneak a nosedive through.
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

VERSION = "fresh-gate-1.0"

# A BUY is allowed only if the freshest 10-min read is >= this (percent).
# 0.0 == "must not be falling right now". Raise to e.g. 0.05 to demand a real
# upward tick; lower (negative) to tolerate tiny noise. This is the one knob.
FRESH_GATE_MIN_PCT = 0.0

# Optional rescue: a name flat/just-below the floor on the 10-min read but
# RIPPING on the hour (a one-read pause inside a strong climb) may still pass.
# OFF by the operator's "stop nosedives" priority — kept here, disabled, so it
# is trivial to enable later if pauses prove to cost real entries.
ALLOW_PAUSED_RIPPER = False
PAUSED_FLOOR_PCT = -0.10     # 10-min may be this low ...
PAUSED_RIPPER_H1_PCT = 1.0   # ... only if the hour is at least this green

# MULTI-WINDOW CONFIRMATION (Dash 2.1). A name green on the 10-min read is STILL
# blocked if the hour is in a clear downtrend — a fresh spike inside a falling
# hour is the classic "buy the dead-cat bounce, revert next read, sell the
# bottom" loss. We only block when the hour is meaningfully red (below the
# floor), so a flat/mildly-mixed hour still passes; this targets the spike-into-
# downtrend pattern, not normal noise.
REQUIRE_HOUR_CONFIRM = True
CONFIRM_H1_FLOOR = -0.5      # block a fresh-green name only if h1 is below this %


def _chain_entry_for(chain: Dict[str, Any], ticker: str) -> Optional[Dict[str, Any]]:
    """Find a ticker's chain entry, tolerating the USD / -USD aliasing the rest
    of the system uses (BTCUSD vs BTC-USD vs BTC/USD)."""
    if not chain or not ticker:
        return None
    t = str(ticker).upper()
    cands = [
        t,
        t.replace("/", ""),
        t.replace("USD", "-USD"),
        t.replace("-USD", "USD"),
        (t[:-3] + "-USD") if t.endswith("USD") and not t.endswith("-USD") else t,
    ]
    seen = set()
    for c in cands:
        if c in seen:
            continue
        seen.add(c)
        if c in chain:
            return chain[c]
    return None


def passes_fresh_entry_gate(
    chain_entry: Optional[Dict[str, Any]],
    min_pct: float = FRESH_GATE_MIN_PCT,
) -> Tuple[bool, str, Dict[str, Any]]:
    """Decide whether a name may be BOUGHT given its fresh-window read.

    Returns (allow, reason, detail) where detail carries the numbers behind the
    decision (since_last / h1 / composite / fire) so the dashboard can show the
    operator EXACTLY why a moving name was or was not bought.
    """
    detail: Dict[str, Any] = {"since_last": None, "h1": None,
                              "composite": None, "fire": None}

    if not chain_entry:
        return True, "ungated: no fresh chain read yet (chain cold)", detail

    w = chain_entry.get("windows") or {}
    slr = w.get("since_last")
    h1 = w.get("h1")
    detail.update({
        "since_last": slr,
        "h1": h1,
        "composite": chain_entry.get("composite"),
        "fire": chain_entry.get("fire"),
    })

    # No 10-min read computed yet -> cannot judge freshness -> allow + flag.
    if slr is None:
        return True, "ungated: 10-min read not available yet", detail

    # GREEN on the fresh read -> the name is rising NOW. But require the hour to
    # not be in a clear downtrend: a 10-min spike inside a falling hour reverts.
    if slr >= min_pct:
        if (REQUIRE_HOUR_CONFIRM and h1 is not None and h1 < CONFIRM_H1_FLOOR):
            return (False,
                    f"CONFIRM BLOCK: 10-min +{slr:.2f}% but hour {h1:+.2f}% "
                    f"(fresh spike inside an hourly downtrend — likely to "
                    f"revert)", detail)
        return True, f"fresh 10-min read +{slr:.2f}% (rising now)", detail

    # Optional paused-ripper rescue (disabled by default).
    if (ALLOW_PAUSED_RIPPER and slr > PAUSED_FLOOR_PCT
            and h1 is not None and h1 >= PAUSED_RIPPER_H1_PCT):
        return (True,
                f"10-min paused ({slr:+.2f}%) but hour ripping (+{h1:.2f}%) "
                f"— allowed", detail)

    # FALLING NOW -> blocked, no matter what the longer windows say.
    comp = chain_entry.get("composite")
    comp_s = f"{float(comp):+.3f}" if comp is not None else "n/a"
    return (False,
            f"FRESH-GATE BLOCK: falling now (10-min {slr:+.2f}%, composite "
            f"{comp_s}) — stale daily strength can't rescue a name dropping now",
            detail)


def apply_fresh_entry_gate(
    pool,
    chain: Dict[str, Any],
    min_pct: float = FRESH_GATE_MIN_PCT,
) -> Tuple[list, Dict[str, Any]]:
    """Filter a candidate pool (list of debate dicts, each with a `ticker`)
    through the fresh gate.

    Returns (admitted_pool, gate_log). gate_log is a JSON-ready dict suitable
    for writing to docs/data/entry_gate.json and rendering in the UI.
    """
    admitted = []
    admitted_log = []
    blocked_log = []
    ungated_log = []

    for d in (pool or []):
        ticker = str(d.get("ticker") or "")
        ce = _chain_entry_for(chain or {}, ticker)
        allow, reason, detail = passes_fresh_entry_gate(ce, min_pct=min_pct)
        row = {
            "ticker": ticker.upper(),
            "surfaced_by": d.get("_surfaced_by", "sentiment"),
            "reason": reason,
            **detail,
        }
        if allow:
            admitted.append(d)
            (ungated_log if reason.startswith("ungated") else admitted_log).append(row)
        else:
            blocked_log.append(row)

    # blocked names sorted by how hard they were falling (worst first)
    blocked_log.sort(key=lambda r: (r.get("since_last") if r.get("since_last")
                                    is not None else 0.0))

    from datetime import datetime, timezone
    gate_log = {
        "version": VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "min_pct": min_pct,
        "summary": {
            "considered": len(pool or []),
            "admitted": len(admitted_log),
            "blocked_falling_now": len(blocked_log),
            "ungated_no_fresh_read": len(ungated_log),
        },
        "blocked": blocked_log[:200],
        "admitted": admitted_log[:200],
        "ungated": ungated_log[:200],
        "note": ("The FRESH-WINDOW ENTRY GATE. A name is BLOCKED from buying "
                 "when its 10-min read is falling, no matter how strong its "
                 "daily/weekly windows are — this is the fix for nosedive "
                 "entries (buying XTZ/XRP/BONK while they dropped on stale "
                 "daily strength). 'blocked' lists every moving name that was "
                 "kept out and exactly why."),
    }
    return admitted, gate_log


if __name__ == "__main__":  # pragma: no cover
    # Proof on the bootstrap's real XTZ shape + a healthy riser.
    import json
    xtz = {"windows": {"since_last": -0.085, "h1": -0.2, "d1": 4.292},
           "composite": 0.735, "fire": 0.3}
    good = {"windows": {"since_last": 0.42, "h1": 1.1, "d1": 3.0},
            "composite": 0.9, "fire": 0.8}
    cold = {"windows": {"since_last": None, "h1": None}, "composite": 0.0}
    for name, c in [("XTZ (nosedive)", xtz), ("GOOD (rising)", good),
                    ("COLD (no read)", cold)]:
        allow, reason, _ = passes_fresh_entry_gate(c)
        print(f"{name:18s} -> {'ALLOW' if allow else 'BLOCK'} :: {reason}")
