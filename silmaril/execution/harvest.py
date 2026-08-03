"""
HARVEST CHECKPOINT — 7.2.3. Making a win STAY a win.

THE OPERATOR'S ASK, verbatim: *"if it is truly at above 400... can we call a 400 dollar profit
swing a HUGE success and can we set something so that when accounts get to a checkpoint like
this they know we have hit a monthly goal and then figure out a way to pocket this profit,
balancing the account back to a 10k account while truly harvesting the 400 into something
un-spendable? We have tried to set up a system in the past that allows wins to stay wins and
avoid wins sliding back into a 10k value on their own with no harvest."*

THE UNCOMFORTABLE FIRST ANSWER. On 2026-08-03 stock:E showed +$438.40. Broken down:

    realized (banked, fee-paid) ... +$102.83
    unrealized (open marks) ....... +$335.57
    ---------------------------------------
    headline ...................... +$438.40

**Only $102.83 exists.** The other $335.57 is four open positions marked to the last print. It
can evaporate before it is ever banked — and this project has watched exactly that happen 17
times (positions up more than 2% that closed negative). So a harvest that swept $438 would be
inventing $335 of it, and the vault would be a lie.

THEREFORE: **this module harvests REALIZED profit only.** That is the whole discipline. It is
also precisely why wins have historically slid back to $10k — the gain was never banked in the
first place, so there was nothing to protect.

TWO MODES, both explicit:

  BANK_REALIZED (default, always honest)
      When realized profit crosses the checkpoint, sweep it to the vault. Working capital
      returns to its starting size. Open positions are untouched and keep running.

  REALIZE_AND_BANK (opt-in, and this is what a human means by "take it off the table")
      When TOTAL profit crosses the checkpoint but realized alone does not, close the winning
      positions that are comfortably above cost — converting marks into money — then sweep.
      It costs the remaining upside on those names, which is the honest price of certainty.
      Never closes a loser to manufacture a number.

THE VAULT IS NON-SPENDABLE BY CONSTRUCTION. `_avail()` in the sleeve engine returns `cash`, and
harvest moves money from `cash` to `vault_usd`. There is no path in the engine that spends the
vault, so a harvested dollar cannot be re-risked. That is what makes a win stay a win.

Knobs: `harvest` {mode, checkpoint_usd, checkpoint_pct, min_realized_usd, realize_gate_pct}
KILL: mode "off".
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from .atomic_io import write_json_atomic
except Exception:                                            # pragma: no cover
    def write_json_atomic(path, payload):                    # type: ignore
        Path(path).write_text(json.dumps(payload, indent=2))

DEFAULTS = {
    "mode": "bank_realized",     # bank_realized | realize_and_bank | off
    "checkpoint_pct": 3.0,       # of starting equity — 3% of $10k = $300
    "checkpoint_usd": 0.0,       # absolute alternative; whichever is larger applies
    "min_realized_usd": 50.0,    # never sweep trivial amounts; fees make it pointless
    "realize_gate_pct": 1.0,     # in realize_and_bank, only close positions this far above cost
    "cooldown_h": 20.0,          # one harvest per book per ~day, so it cannot churn
}

STORE = "STRATEGY_LAB.json"


def _knobs(out: Path) -> Dict[str, Any]:
    k = dict(DEFAULTS)
    try:
        cat = json.loads((out / "PARAM_CATALOG.json").read_text()) or {}
        for kk, vv in (cat.get("harvest") or {}).items():
            k[kk] = vv
    except Exception:
        pass
    return k


def _ts(x) -> Optional[datetime]:
    try:
        d = datetime.fromisoformat(str(x).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def build_harvest(out_dir, marks: Dict[str, float] = None) -> Dict[str, Any]:
    """Check every sleeve book against its checkpoint and bank what has genuinely been earned."""
    out = Path(out_dir)
    k = _knobs(out)
    now = datetime.now(timezone.utc)
    mode = str(k.get("mode") or "bank_realized").lower()

    if mode == "off":
        payload = {"generated_at": now.isoformat(), "mode": "off",
                   "note": "harvest KILLED by knob — nothing is swept"}
        write_json_atomic(out / "HARVEST.json", payload)
        return payload

    try:
        lab = json.loads((out / STORE).read_text())
    except Exception:
        payload = {"generated_at": now.isoformat(), "mode": mode,
                   "note": "no STRATEGY_LAB.json to harvest from"}
        write_json_atomic(out / "HARVEST.json", payload)
        return payload

    if marks is None:
        marks = {}
        try:
            from .canon_keys import canonical_samples
            for sym, rows in (canonical_samples(out) or {}).items():
                for r in reversed(rows or []):
                    try:
                        if r and len(r) >= 2 and r[1] and float(r[1]) > 0 and "T00:00:00" not in str(r[0]):
                            marks[sym] = float(r[1])
                            break
                    except Exception:
                        break
        except Exception:
            marks = {}

    harvests: List[Dict[str, Any]] = []
    status: List[Dict[str, Any]] = []
    changed = False

    for key, b in (lab.get("sleeves") or {}).items():
        start = float(b.get("start_equity") or 10000.0)
        cash = float(b.get("cash") or 0.0)
        vault = float(b.get("vault_usd") or 0.0)
        real = float(b.get("realized_pnl") or 0.0)
        pos = b.get("positions") or {}

        unreal = 0.0
        for sym, p in pos.items():
            try:
                mk = marks.get(sym)
                if mk and p.get("entry") and p.get("qty"):
                    unreal += (float(mk) - float(p["entry"])) * float(p["qty"])
            except Exception:
                pass

        checkpoint = max(float(k.get("checkpoint_usd") or 0.0),
                         start * float(k.get("checkpoint_pct") or 3.0) / 100.0)
        banked_before = vault
        total_profit = real + unreal

        # cooldown: one harvest per book per window, so a book cannot churn its own vault
        last = _ts(b.get("_last_harvest_t"))
        cooling = bool(last and (now - last).total_seconds() / 3600.0 < float(k.get("cooldown_h") or 20.0))

        row = {"book": key, "start": start, "realized": round(real, 2),
               "unrealized": round(unreal, 2), "total_profit": round(total_profit, 2),
               "vault": round(vault, 2), "checkpoint": round(checkpoint, 2),
               "cooling": cooling}

        if cooling or real - vault < float(k.get("min_realized_usd") or 50.0):
            # nothing bankable yet — but say WHY, because "no harvest" and "broken" look alike
            row["verdict"] = ("cooling down" if cooling else
                              "realized profit not yet banked-worthy (%.2f of %.2f needed)"
                              % (real - vault, float(k.get("min_realized_usd") or 50.0)))
            status.append(row)
            continue

        sweep = 0.0
        realized_from_positions: List[Dict[str, Any]] = []

        if real - vault >= checkpoint:
            sweep = real - vault
            row["verdict"] = "CHECKPOINT MET on realized profit alone"
        elif mode == "realize_and_bank" and total_profit >= checkpoint:
            # convert marks into money by closing the comfortable winners, then sweep
            gate = float(k.get("realize_gate_pct") or 1.0) / 100.0
            for sym in list(pos.keys()):
                p = pos[sym]
                mk = marks.get(sym)
                if not mk or not p.get("entry") or not p.get("qty"):
                    continue
                chg = float(mk) / float(p["entry"]) - 1.0
                cost = float(p.get("cost") or 0.004)
                if chg <= gate + cost:
                    continue                       # not comfortably ahead; leave it running
                qty = float(p["qty"])
                eff = float(mk) * (1 - cost / 2.0)
                pnl = (eff - float(p["entry"])) * qty
                cash += eff * qty
                real += pnl
                realized_from_positions.append({
                    "sym": sym, "pnl": round(pnl, 2), "net_pct": round((eff / p["entry"] - 1) * 100, 3)})
                b.setdefault("trades", []).append({
                    "side": "SELL", "sym": sym, "why": "HARVEST_REALIZE", "simulated": True,
                    "entry": p.get("entry"), "exit": round(eff, 10),
                    "pnl": round(pnl, 2),
                    "realized_pct": round((eff / p["entry"] - 1) * 100, 3),
                    "opened_t": p.get("t"), "t": now.isoformat(),
                    "style": p.get("style", "MR"),
                })
                pos.pop(sym, None)
            sweep = max(0.0, real - vault)
            row["verdict"] = ("CHECKPOINT MET after realizing %d winning position(s)"
                              % len(realized_from_positions)) if sweep >= checkpoint else \
                             "closed winners but still short of the checkpoint"
            if sweep < checkpoint:
                sweep = 0.0
        else:
            row["verdict"] = ("total profit %.2f (of which only %.2f is REAL) — below the %.2f "
                              "checkpoint on banked money"
                              % (total_profit, real - vault, checkpoint))

        if sweep >= max(checkpoint, float(k.get("min_realized_usd") or 50.0)) and cash >= sweep:
            cash -= sweep
            vault += sweep
            b["cash"] = round(cash, 2)
            b["vault_usd"] = round(vault, 2)
            b["realized_pnl"] = round(real, 2)
            b["positions"] = pos
            b["_last_harvest_t"] = now.isoformat()
            changed = True
            h = {"book": key, "swept_usd": round(sweep, 2),
                 "vault_before": round(banked_before, 2), "vault_after": round(vault, 2),
                 "working_capital_after": round(cash + sum(
                     float(p.get("qty") or 0) * float(p.get("entry") or 0) for p in pos.values()), 2),
                 "realized_positions": realized_from_positions,
                 "at": now.isoformat(),
                 "why": ("banked %.2f of REALIZED profit into the non-spendable vault. Working "
                         "capital returns toward %.2f; the vault can never be re-risked, so this "
                         "win cannot slide back." % (sweep, start))}
            harvests.append(h)
            row["harvested"] = h
        status.append(row)

    if changed:
        write_json_atomic(out / STORE, lab)
        try:
            with open(out / "HARVEST_LEDGER.jsonl", "a") as f:
                for h in harvests:
                    f.write(json.dumps(h) + "\n")
        except Exception:
            pass

    total_vault = sum(float((b or {}).get("vault_usd") or 0.0)
                      for b in (lab.get("sleeves") or {}).values())
    payload = {
        "generated_at": now.isoformat(), "mode": mode, "knobs": k,
        "law": ("only REALIZED, fee-paid profit may be harvested. An unrealized mark is not a "
                "win; sweeping one would put a number in the vault that was never earned."),
        "harvested_now": harvests,
        "total_vaulted_usd": round(total_vault, 2),
        "books": sorted(status, key=lambda r: -(r.get("total_profit") or 0))[:40],
        "honesty": ("stock:E showed +$438.40 on 2026-08-03: $102.83 realized and $335.57 in open "
                    "marks. Only the first number is money."),
    }
    write_json_atomic(out / "HARVEST.json", payload)
    return payload


if __name__ == "__main__":                                   # pragma: no cover
    import sys
    p = build_harvest(sys.argv[1] if len(sys.argv) > 1 else "docs/data")
    print("HARVEST mode=%s | total vaulted $%.2f" % (p.get("mode"), p.get("total_vaulted_usd", 0)))
    for h in p.get("harvested_now") or []:
        print("  SWEPT %-10s $%.2f -> vault $%.2f" % (h["book"], h["swept_usd"], h["vault_after"]))
    for r in (p.get("books") or [])[:8]:
        print("  %-10s realized %+8.2f unrealized %+8.2f | %s"
              % (r["book"], r["realized"], r["unrealized"], r["verdict"][:70]))
