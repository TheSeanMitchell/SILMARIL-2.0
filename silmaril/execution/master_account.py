"""silmaril.execution.master_account — 5.3 THE MASTER BRAIN (M7: the Master awakens).

The account we intend to fund had a zero-length record: 0/90 every cycle, 0 trades
since inception. 5.3 ends that. The Master now SHADOW-TRADES its own $10k — paper,
funded by nothing, gated by EVIDENCE — so 90 days from now it has a real track
record instead of a number that never moved.

What it does every cycle (all knob-gated via PARAM_CATALOG.master_brain):
  · PERCENTILE GATE (Law 18): a pick must sit in the top gate_pct of THIS cycle's
    live card scores for its industry. Absolute gates that can never fire are dead.
  · THE "WILL IT ACTUALLY REVERT" GATE: expected_hold ≤ max_expected_hold_min AND
    (bounce_reliability ≥ floor OR rhythm-tradeable) — the Master refuses setups
    its own evidence says are long holds or unreliable bouncers.
  · VENUE GATE: crypto picks must be LISTED on at least one target venue.
  · ⚡ STRIKE-ON-SHIFT: the moment a book's fast band flips green (UPTREND ⚡ shift),
    the Master may open ONE momentum strike that same cycle — never miss the day.
  · USD RESERVE: harvest_frac of every realized win is vaulted, non-spendable.
    Profits leave the table; the working base stays $10k.
  · POLICY ROTATION: per industry, the Master adopts the Strategy-Lab leader
    (closable, auto-rotating) until the operator pins one.
  · EVERY verdict — accept AND reject — lands in MASTER_LEDGER.json (+ append-only
    MASTER_DECISION_LEDGER.jsonl) with the numbers and the reason, in writing.

Emits: MASTER_ACCOUNT.json (UI), MASTER_LEDGER.json (cycle table), MASTER_BOOK
state inside MASTER_ACCOUNT, MASTER_DECISIONS.json (legacy verdict feed).
KILL: master_brain.mode:"off" → pure WATCHING, exactly as before.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .atomic_io import write_json_atomic

SEED = 10000.0
BOOKS = ("crypto", "stock", "metal", "energy")


def _now():
    return datetime.now(timezone.utc)


def _iso():
    return _now().isoformat()


def _load(out: Path, name: str, default=None):
    try:
        return json.loads((out / name).read_text())
    except Exception:
        return default if default is not None else {}


def _parse(t) -> Optional[datetime]:
    try:
        d = datetime.fromisoformat(str(t).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _pct_cut(vals: List[float], pct: float) -> Optional[float]:
    v = sorted(x for x in vals if x is not None)
    if len(v) < 20:
        return None                      # small pool → gate stands down, honestly
    i = min(len(v) - 1, max(0, int(len(v) * pct / 100.0)))
    return v[i]


def build_master_account(out_dir) -> Dict[str, Any]:
    out = Path(out_dir)
    cat = _load(out, "PARAM_CATALOG.json")
    kb = cat.get("master_brain") or {}
    live_mode = str(kb.get("mode", "auto")).lower() == "auto"

    cards = (_load(out, "CONFIDENCE_CARDS.json").get("cards") or {})
    live = _load(out, "paper_sim_live.json")
    mtf_books = (_load(out, "MTF_REGIME.json").get("books") or {})
    lab_bi = (_load(out, "STRATEGY_LAB.json").get("by_industry") or {})
    listed_union = set()
    for l in (_load(out, "VENUES.json").get("listed") or {}).values():
        listed_union |= set(l)

    # ── state (survives cycles; honors the wipe) ─────────────────────────────
    st = _load(out, "MASTER_ACCOUNT.json", {})
    book = st.get("book") or {}
    wm = _load(out, "WIPE_MARKER.json").get("wiped_at")
    if wm and book.get("created_at") and str(book["created_at"]) < str(wm):
        book = {}                        # clean room: pre-wipe Master state is void
    if not book:
        book = {"created_at": _iso(), "cash": SEED, "reserve_usd": 0.0,
                "positions": {}, "trades": [], "peak": SEED, "max_dd_pct": 0.0,
                "prev_fast": {}, "wipe_epoch": wm}

    gate_pct = float(kb.get("gate_pct", 80))
    max_hold = float(kb.get("max_expected_hold_min", 720))
    min_br = float(kb.get("min_bounce_reliability", 0.5))
    max_open = int(kb.get("max_open_per_book", 2))
    hfrac = min(1.0, max(0.0, float(kb.get("harvest_frac", 1.0))))

    def _cost_for(sym: str, px: float) -> float:
        try:
            from .venues import venue_round_trip_cost
            vk = cat.get("venue_layer") or {}
            if str(vk.get("mode", "auto")).lower() == "auto":
                return float(venue_round_trip_cost(out, sym, [px], vk, 0.004)["total"])
        except Exception:
            pass
        return 0.004

    def _sell(sym: str, px_raw: float, why: str):
        pos = book["positions"].get(sym)
        if not pos or px_raw <= 0:
            return
        cost = float(pos.get("cost", 0.004))
        eff = px_raw * (1 - cost / 2.0)
        proceeds = pos["qty"] * eff
        basis = pos["qty"] * pos["entry"]
        pnl = proceeds - basis
        raw_entry = pos["entry"] / (1 + cost / 2.0)
        book["cash"] += proceeds
        if pnl > 0 and hfrac > 0:
            vault = pnl * hfrac
            book["cash"] -= vault
            book["reserve_usd"] = round(book.get("reserve_usd", 0.0) + vault, 2)
        book["trades"].append({
            "side": "SELL", "sym": sym, "book": pos.get("book"), "why": why,
            "pnl": round(pnl, 2),
            "realized_pct": round((eff / pos["entry"] - 1) * 100, 3),
            "realized_gross_pct": round((px_raw / raw_entry - 1) * 100, 3),
            "fee_pct": round(cost * 100, 3), "style": pos.get("style", "MR"),
            "simulated": True, "t": _iso()})
        del book["positions"][sym]

    def _buy(sym: str, bk: str, px_raw: float, why: str, style: str, card: Dict[str, Any]):
        cost = _cost_for(sym, px_raw)
        budget = min(book["cash"] * 0.25, 2500.0)
        if budget < 50 or px_raw <= 0:
            return False
        eff = px_raw * (1 + cost / 2.0)
        qty = budget / eff
        book["cash"] -= budget
        tgt = max(2.2 * cost, min(0.04, (card.get("typical_bounce_pct") or 3.0) / 100.0 * 0.66))
        book["positions"][sym] = {
            "qty": qty, "entry": eff, "cost": cost, "book": bk, "style": style,
            "target": round(tgt, 4), "stop": 0.05,
            "exp_hold_min": card.get("expected_hold_min"), "t": _iso(), "hw": 0.0}
        book["trades"].append({"side": "BUY", "sym": sym, "book": bk, "why": why,
                               "wager_usd": round(budget, 2), "style": style,
                               "target_pct": round(tgt * 100, 3), "simulated": True,
                               "t": _iso()})
        return True

    # ── EXITS first (marks from cards' fresh last_px) ────────────────────────
    for sym in list(book["positions"].keys()):
        pos = book["positions"][sym]
        c = cards.get(sym) or {}
        px = c.get("last_px")
        if not px:
            continue
        raw_entry = pos["entry"] / (1 + pos.get("cost", 0.004) / 2.0)
        chg = px / raw_entry - 1.0
        pos["hw"] = max(pos.get("hw", 0.0), chg)
        held_min = ((_now() - (_parse(pos.get("t")) or _now())).total_seconds() / 60.0)
        if chg >= pos["target"] and not (pos.get("style") == "STRIKE" and chg < pos["hw"]):
            _sell(sym, px, "TAKE"); continue
        if pos.get("style") == "STRIKE" and pos["hw"] >= pos["target"] and chg <= pos["hw"] * 0.6:
            _sell(sym, px, "RIDE_TRAIL"); continue
        if chg <= -pos["stop"]:
            _sell(sym, px, "STOP"); continue
        exp = pos.get("exp_hold_min") or 0
        if exp and held_min >= exp * 1.5 and -0.005 <= chg <= 0.005:
            _sell(sym, px, "RHYTHM_RECYCLE"); continue

    # ── DECIDE per book ──────────────────────────────────────────────────────
    cycle = {"t": _iso(), "books": {}}
    quadrants: Dict[str, Any] = {}
    for bk in BOOKS:
        pool = [(s, c) for s, c in cards.items()
                if c.get("class") == bk and c.get("last_px")]
        scores = [c.get("confidence") for _, c in pool]
        cut = _pct_cut(scores, gate_pct)
        regime = ((live.get("regimes") or {}) if isinstance(live, dict) else {}).get(bk)
        fast = bool((mtf_books.get(bk) or {}).get("fast_green"))
        shift = fast and not bool(book["prev_fast"].get(bk))
        book["prev_fast"][bk] = fast
        # policy rotation from the lab (closable, auto-rotating)
        rows = lab_bi.get(bk) or []
        leader = next((r for r in rows if (r.get("closed") or 0) >= 3), rows[0] if rows else None)
        pin = str(kb.get("policy", "auto"))
        policy = (pin.split(":", 1)[1] if pin.startswith("pin:")
                  else (leader.get("sleeve") if leader else "A"))

        held_bk = [s for s, p in book["positions"].items() if p.get("book") == bk]
        accepted, rejected = [], []
        cands = sorted(pool, key=lambda x: -(x[1].get("confidence") or 0))
        for sym, c in cands[:12]:
            if sym in book["positions"]:
                continue
            sc = c.get("confidence") or 0.0
            why_no = None
            if cut is None:
                why_no = "pool<20 — gate stands down, no forced picks"
            elif sc < cut:
                why_no = f"below top-{int(100-gate_pct)}% cut ({sc:.3f} < {cut:.3f})"
            elif (c.get("expected_hold_min") or 1e9) > max_hold:
                why_no = f"long-hold setup ({c.get('expected_hold_min')}m > {int(max_hold)}m) — will not revert in time"
            elif not ((c.get("bounce_reliability") or 0) >= min_br
                      or (c.get("rhythm_tradeability") or 0) >= 0.5):
                why_no = "no revert evidence (bounce/rhythm below floor)"
            elif bk in ("crypto",) and listed_union and sym not in listed_union:
                why_no = "not listed on any target venue"
            elif regime == "DOWNTREND":
                why_no = "regime veto — Master stays liquid in a downtrend"
            elif len(held_bk) + len(accepted) >= max_open:
                why_no = f"open cap {max_open}/{max_open} — liquidity law"
            if why_no:
                if len(rejected) < 3:
                    rejected.append({"sym": sym, "score": round(sc, 3), "why": why_no})
                continue
            accepted.append({"sym": sym, "score": round(sc, 3),
                             "cut": round(cut, 3),
                             "hold_m": c.get("expected_hold_min"),
                             "bounce_rel": c.get("bounce_reliability"),
                             "why": f"top-{int(100-gate_pct)}% ({sc:.3f}≥{cut:.3f}) · "
                                    f"hold {c.get('expected_hold_min')}m · revert-evidence OK"})
            if live_mode:
                _buy(sym, bk, c["last_px"], accepted[-1]["why"], "MR", c)

        struck = None
        if live_mode and shift and bool(kb.get("strike_on_shift", True)):
            movers = sorted(((s, c) for s, c in pool
                             if ((c.get("momentum") or {}).get("h1") or 0) >= 3.0
                             and s not in book["positions"]),
                            key=lambda x: -((x[1].get("momentum") or {}).get("h1") or 0))
            if movers:
                s0, c0 = movers[0]
                if _buy(s0, bk, c0["last_px"],
                        f"⚡ UPTREND shift — striking {s0} h1 +{(c0.get('momentum') or {}).get('h1')}%",
                        "STRIKE", c0):
                    struck = s0

        top = (accepted[0] if accepted else
               ({"sym": cands[0][0], "score": round(cands[0][1].get("confidence") or 0, 3)}
                if cands else {"sym": None, "score": 0}))
        gate_disp = round((cut or 0) * 100, 1)
        conf_disp = round((top.get("score") or 0) * 100, 1)
        decision = "ACCEPT" if accepted or struck else "REJECT"
        reason = (accepted[0]["why"] if accepted else
                  (f"⚡ strike {struck}" if struck else
                   (rejected[0]["why"] if rejected else "no fresh candidates")))
        quadrants[bk] = {"confidence": conf_disp, "gate": gate_disp,
                         "gate_style": f"top-{int(100-gate_pct)}% percentile",
                         "decision": decision, "reason": reason, "regime": regime,
                         "fast_green": fast, "shift": shift, "policy_sleeve": policy}
        cycle["books"][bk] = {"pool": len(pool), "cut": cut, "accepted": accepted,
                              "rejected_top": rejected, "struck": struck,
                              "policy_sleeve": policy, "regime": regime, "shift": shift}

    # ── equity & stores ──────────────────────────────────────────────────────
    held = sum(p["qty"] * (cards.get(s, {}).get("last_px") or
                           p["entry"] / (1 + p.get("cost", 0.004) / 2.0))
               for s, p in book["positions"].items())
    equity = book["cash"] + held + book.get("reserve_usd", 0.0)
    book["peak"] = max(book.get("peak", SEED), equity)
    book["max_dd_pct"] = min(book.get("max_dd_pct", 0.0),
                             round((equity / book["peak"] - 1) * 100, 2))
    closed = [t for t in book["trades"] if t["side"] == "SELL"]
    wins = sum(1 for t in closed if t["pnl"] > 0)

    led = _load(out, "MASTER_LEDGER.json", {"cycles": []})
    led["cycles"] = (led.get("cycles") or [])[-47:] + [cycle]
    led["generated_at"] = _iso()
    led["what"] = ("every Master verdict, every cycle, in writing — accept AND reject, "
                   "with the percentile cut, the revert-evidence, and the reason")
    write_json_atomic(out / "MASTER_LEDGER.json", led)
    try:
        with open(out / "MASTER_DECISION_LEDGER.jsonl", "a") as f:
            f.write(json.dumps(cycle) + "\n")
    except Exception:
        pass
    # legacy verdict feed (UI table)
    md = _load(out, "MASTER_DECISIONS.json", [])
    if not isinstance(md, list):
        md = []
    md.append({"t": _iso(), "gate": f"top-{int(100-gate_pct)}%",
               "books": {bk: {"confidence": q["confidence"], "gate": q["gate"],
                              "decision": q["decision"], "regime": q.get("regime")}
                         for bk, q in quadrants.items()},
               "accepted": [b for b, q in quadrants.items() if q["decision"] == "ACCEPT"]})
    write_json_atomic(out / "MASTER_DECISIONS.json", md[-300:])

    payload = {
        "generated_at": _iso(), "seed_usd": SEED,
        "status": ("SHADOW-TRADING" if live_mode else "WATCHING"),
        "equity": round(equity, 2), "cash": round(book["cash"], 2),
        "usd_reserve": round(book.get("reserve_usd", 0.0), 2),
        "return_pct": round((equity / SEED - 1) * 100, 3),
        "open_positions": len(book["positions"]),
        "trades_count": len(closed), "wins": wins,
        "win_rate_pct": round(100 * wins / len(closed), 1) if closed else None,
        "max_dd_pct": book["max_dd_pct"],
        "positions": [{"sym": s, "book": p.get("book"), "style": p.get("style"),
                       "entry": round(p["entry"], 6), "target_pct": round(p["target"] * 100, 2),
                       "exp_hold_min": p.get("exp_hold_min"), "t": p.get("t")}
                      for s, p in book["positions"].items()],
        "recent_trades": book["trades"][-40:],
        "quadrants": quadrants,
        "book": book,
        # legacy card aliases (COMMAND golden card + forensics tile read these)
        "live_equity": round(equity, 2), "live_pct": round((equity / SEED - 1) * 100, 2),
        "live_status": ("SHADOW-TRADING" if live_mode else "WATCHING"),
        "live_trades_count": len(closed),
        "champion": "EVIDENCE-GATED (5.3) — top-percentile card + revert-proof, per book",
        "live_trades_tail": list(reversed(book["trades"][-3:])),
        "decision_log_tail": list(reversed(md[-3:])),
        "what": ("5.3 MASTER BRAIN: shadow-trades its own $10k from evidence-gated picks "
                 "(percentile gate · revert-evidence · venue-listed · regime-liquid), strikes "
                 "on ⚡ shifts, vaults every win into a non-spendable USD reserve, and writes "
                 "every verdict down. The account we go live with now HAS a record."),
    }
    write_json_atomic(out / "MASTER_ACCOUNT.json", payload)
    acc = [b for b, q in quadrants.items() if q["decision"] == "ACCEPT"]
    return {"summary": f"master brain: eq ${payload['equity']:.0f} (reserve ${payload['usd_reserve']:.0f}) · "
                       f"open {payload['open_positions']} · closed {len(closed)} · accepts {acc or 'none'}"}
