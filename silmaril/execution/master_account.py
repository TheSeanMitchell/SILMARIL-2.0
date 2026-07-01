"""
silmaril.execution.master_account — THE MASTER ACCOUNT / PRODUCTION REHEARSAL ENGINE (2.6 v1).

The fifth book. A single virtual $10,000 that represents the ONE real account we will eventually wire
live. It does not invent trades and it does not touch the four quadrants — they keep running as R&D.
Instead it ADOPTS only proven champions: each quadrant must demonstrate a positive net-after-fees edge
to be allocated capital. Today that means crypto is accepted and the rest are rejected with reasons —
honest, not flattering.

Its headline number is NET SPENDABLE CASH: the full reality chain the operator asked for —
  gross -> exchange fee -> spread -> slippage -> withdrawal -> tax placeholder -> what lands in checking.
Every assumption is labelled. OBSERVATIONAL: changes no quadrant logic. Emits MASTER_ACCOUNT.json.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

SEED = 10000.0

# ── 2.7 MASTER CONFIDENCE GATE ───────────────────────────────────────────────
# The Master only adopts a quadrant's signal when that quadrant's CONFIDENCE clears this gate. This is the
# single tunable knob: raise it to be stricter (fewer, surer signals reach the Master), lower it to let more
# through. Confidence is DRIVEN by real evidence — never a flat number — so the data entering the Master
# actually means something. Edit this one value to tune; nothing else changes.
CONFIDENCE_GATE = 90.0

def _confidence(survivability, win, trips, net) -> float:
    """0-100 confidence from REAL evidence only. Zero if the book is losing or has no real trades — a
    quadrant cannot earn Master trust without a positive, sampled, surviving edge. Weights: forward
    survivability and sample size carry the most weight, because they predict forward behavior."""
    if net is None or net <= 0 or (trips or 0) < 1:
        return 0.0
    surv_c = min(1.0, (survivability or 0) / 100.0)             # forward survivability (champion_validation)
    win_c = max(0.0, min(1.0, ((win or 0) - 50.0) / 40.0))     # 50% win -> 0, 90%+ -> 1
    n_c = min(1.0, (trips or 0) / 50.0)                         # sample size, saturates at 50 round-trips
    return round(100.0 * (0.40 * surv_c + 0.30 * n_c + 0.30 * win_c), 1)

def _now(): return datetime.now(timezone.utc).isoformat()
def _load(out: Path, name: str, default=None):
    try: return json.loads((out / name).read_text())
    except Exception: return default if default is not None else {}

def _book_survivability(out: Path, book: str) -> float:
    """Forward survivability of the book's current champion, from champion_validation.json. 0 if unknown."""
    champ = _load(out, f"champion_{book}.json").get("champion")
    cv = _load(out, "champion_validation.json")
    if champ:
        for r in cv.get("strategies", []):
            if r.get("strategy") == champ:
                sv = r.get("survivability") or {}
                return float(sv.get("score") if isinstance(sv, dict) else (r.get("survivability_score") or 0) or 0)
    # fallback: the most-survivable score the validator found (declared, not book-specific)
    return float(cv.get("most_survivable_score") or 0)

def _quadrant_edge(out: Path, book: str) -> Dict[str, Any]:
    """Proven? = confidence (driven by survivability + sample + win + net-after-fees) clears CONFIDENCE_GATE."""
    tq = _load(out, "TRADE_QUALITY.json").get("by_book", {}).get(book, {})
    life = tq.get("lifetime", {}) if tq else {}
    net = life.get("net_realized_usd")
    trips = life.get("real_round_trips", 0) or 0
    win = life.get("real_win_rate_pct")
    surv = _book_survivability(out, book)
    confidence = _confidence(surv, win, trips, net)
    proven = confidence >= CONFIDENCE_GATE
    return {"net_realized_usd": net, "real_round_trips": trips, "win_rate_pct": win,
            "survivability": surv, "confidence": confidence, "gate": CONFIDENCE_GATE, "proven": proven}

def build_master_account(out_dir) -> Dict[str, Any]:
    out = Path(out_dir)

    # 1) per-quadrant recommendation (the decision tree)
    quadrants = {}
    for bk in ("crypto", "stock", "metal", "energy"):
        e = _quadrant_edge(out, bk)
        c, g = e["confidence"], e["gate"]
        if e["proven"]:
            decision, reason = "ACCEPT", f"confidence {c}/100 ≥ gate {g} — survivability {e['survivability']:.0f}, {e['real_round_trips']} trips, {e['win_rate_pct']}% win, net +${e['net_realized_usd']}"
        elif (e["net_realized_usd"] or 0) > 0:
            decision, reason = "REJECT", f"confidence {c}/100 < gate {g} — positive but not yet trusted (survivability {e['survivability']:.0f}, {e['real_round_trips']} trips, {e['win_rate_pct']}% win)"
        else:
            decision, reason = "REJECT", f"confidence {c}/100 — no positive net edge yet (still gathering)"
        quadrants[bk] = {**e, "decision": decision, "reason": reason}

    accepted = [b for b, q in quadrants.items() if q["decision"] == "ACCEPT"]

    # MASTER DECISION LEDGER — full transparency: one row per cycle, per-quadrant confidence vs the gate and
    # the accept/reject verdict, so "how does the Master decide" is answerable from the dashboard, not faith.
    try:
        led_path = out / "MASTER_DECISIONS.json"
        try:
            ledger = json.loads(led_path.read_text())
            if not isinstance(ledger, list):
                ledger = []
        except Exception:
            ledger = []
        row = {"t": _now(),
               "gate": CONFIDENCE_GATE,
               "books": {bk: {"confidence": q.get("confidence"), "decision": q.get("decision"),
                              "survivability": round(q.get("survivability") or 0, 1),
                              "trips": q.get("real_round_trips"), "win_pct": q.get("win_rate_pct")}
                          for bk, q in quadrants.items()},
               "accepted": accepted}
        last = ledger[-1] if ledger else None
        changed = (not last) or (last.get("accepted") != accepted) or any(
            (last.get("books", {}).get(bk, {}) or {}).get("decision") != row["books"][bk]["decision"]
            for bk in row["books"])
        # append every cycle, but mark verdict-changes so the UI can highlight them
        row["verdict_changed"] = bool(changed)
        ledger.append(row)
        ledger = ledger[-300:]
        try:
            from .atomic_io import write_json_atomic
            write_json_atomic(led_path, ledger)
        except Exception:
            led_path.write_text(json.dumps(ledger, indent=1))
    except Exception:
        ledger = []
    # 2) allocation: 100% split across accepted quadrants (today: crypto only). Honest placeholder until more prove out.
    alloc = {b: round(100 / len(accepted), 1) for b in accepted} if accepted else {}

    # 3) the reality chain on the proven book's REAL gross (crypto is the rehearsal source today)
    src = accepted[0] if accepted else "crypto"
    book = _load(out, f"paper_book_{src}.json")
    gross = float(book.get("realized_pnl", 0) or 0)

    tth = _load(out, "THRESHOLD_TAKEHOME.json")
    # fee rate: prefer the low-flat (Binance.US) scenario as the realistic live target; fall back to model
    fee_bps = 20.0
    for s in tth.get("fee_scenarios", []):
        if "Binance" in s.get("label", ""): fee_bps = s["bps_round_trip"]
    # notional turnover from daily fee reconstruction
    daily = tth.get("daily_takehome", [])
    fee_frac_model = (tth.get("fee_model_bps_round_trip", 54.0)) / 10000.0
    turnover = sum((abs(d["fees"]) / fee_frac_model) for d in daily) if (daily and fee_frac_model) else 0.0

    kr = _load(out, "KRAKEN_SPREAD.json")
    spread_bps = kr.get("median_spread_bps") or 9.0
    slip_bps = 2.0
    TAX_RATE = 0.25            # placeholder — not advice
    WITHDRAW_FLAT = 5.0        # one network withdrawal to cash out

    exch_fee = turnover * (fee_bps / 10000.0)
    spread_cost = turnover * (float(spread_bps) / 10000.0)
    slip_cost = turnover * (slip_bps / 10000.0)
    after_costs = gross - exch_fee - spread_cost - slip_cost
    tax = max(0.0, after_costs) * TAX_RATE
    net_spendable = after_costs - tax - WITHDRAW_FLAT

    chain = [
        {"step": "gross profit (proven book)", "amount": round(gross, 2)},
        {"step": f"exchange fee @ {fee_bps:.0f}bps (Binance.US flat target)", "amount": round(-exch_fee, 2)},
        {"step": f"spread @ {float(spread_bps):.1f}bps (live Kraken median)", "amount": round(-spread_cost, 2)},
        {"step": f"slippage @ {slip_bps:.0f}bps", "amount": round(-slip_cost, 2)},
        {"step": f"tax placeholder @ {int(TAX_RATE*100)}% of gains", "amount": round(-tax, 2)},
        {"step": "withdrawal to cash (1 network fee)", "amount": round(-WITHDRAW_FLAT, 2)},
    ]

    # ----- LIVE "STARTS NOW" account: a fresh $10k from inception, grows with proven trades forward -----
    prior = _load(out, "MASTER_ACCOUNT.json")
    inception = prior.get("inception_ts") or _now()
    post = [t for t in book.get("trades", [])
            if t.get("side") == "SELL" and t.get("t", "") >= inception
            and abs((t.get("qty") or 0) * (t.get("price") or 0)) >= 1.0]
    post_gross = sum(float(t.get("pnl") or 0) for t in post)
    post_turn = sum(abs((t.get("qty") or 0) * (t.get("price") or 0)) for t in post)
    post_costs = post_turn * ((fee_bps + float(spread_bps) + slip_bps) / 10000.0)
    live_net = post_gross - post_costs
    live_equity = round(SEED + live_net, 2)
    live_pct = round(live_net / SEED * 100, 2)
    live_status = "TRADING" if accepted else "WATCHING"
    equity = SEED + net_spendable
    # 4) daily briefing
    gov = _load(out, "CHAMPION_GOVERNANCE.json")
    champ = gov.get("declared_champion", {}).get("strategy") if isinstance(gov.get("declared_champion"), dict) else gov.get("declared_champion")

    # ===== 2.6 EXPANSION: recommendations, reality-validation confidence, exchange table =====
    # (A) Quadrant RECOMMENDATIONS — each lab submits a call; the Master decides from these.
    recs = {}
    for bk, q in quadrants.items():
        conf = q.get("confidence", 0)
        trips = q.get("real_round_trips") or 0
        if q["decision"] == "ACCEPT":
            sig = "BUY"
        elif (q.get("net_realized_usd") or 0) > 0:
            sig = "WAIT"
        else:
            sig = "NO-TRADE"
        recs[bk] = {"signal": sig, "confidence_pct": conf, "gate_pct": q.get("gate"),
                    "survivability": q.get("survivability"),
                    "expected_edge_pct": (round((q.get("net_realized_usd") or 0) / max(1, trips) / 1000 * 100, 3) if trips else None),
                    "reason": q["reason"]}
    master_decision = (f"Fund {', '.join(accepted)} (confidence ≥ {CONFIDENCE_GATE} gate); hold the rest in R&D."
                       if accepted else f"No quadrant clears the {CONFIDENCE_GATE} confidence gate — stay flat, keep gathering.")

    # (B) REALITY VALIDATION — a single production-readiness confidence that refuses to flatter.
    km = _load(out, "KRAKEN_MIRROR.json")
    survival = km.get("survival_pct") if km.get("available") else None
    crypto_q = quadrants.get("crypto", {})
    trips_c = crypto_q.get("real_round_trips") or 0
    wr_c = crypto_q.get("win_rate_pct") or 0
    fee_positive = any((s.get("lifetime_net") or 0) > 0 for s in tth.get("fee_scenarios", []) if "Binance" in s.get("label", ""))
    # components 0..1
    c_survival = (min(survival, 100) / 100) if survival is not None else 0.3
    c_sample = min(trips_c, 100) / 100                       # need ~100 trips for full marks
    c_win = max(0.0, min(1.0, (wr_c - 40) / 40))             # 40%->0, 80%->1
    c_fee = 1.0 if fee_positive else 0.0
    score = round((c_survival * 0.30 + c_sample * 0.30 + c_win * 0.25 + c_fee * 0.15) * 100, 1)
    verdict = ("NOT production-ready — gathering evidence" if score < 50 else
               "promising — needs more forward data" if score < 75 else
               "approaching readiness — candidate for a tiny live validation")
    reality_validation = {
        "production_readiness_score": score, "verdict": verdict,
        "components": {"live_friction_survival": round(c_survival*100,1), "sample_size": round(c_sample*100,1),
                       "win_quality": round(c_win*100,1), "nets_positive_at_real_fees": bool(fee_positive)},
        "needs": f"{max(0, 100 - trips_c)} more real round-trips to reach the 100-trip statistical bar",
        "honest_note": "Refuses to read 'ready' until live-friction survival, sample size, win quality, and fee-positivity all clear. A few good days do not move this much — that is the point.",
    }

    # (C) EXCHANGE COMPARISON — verified June 2026 rates (confirm before relying).
    exchange_comparison = [
        {"venue": "Binance.US", "maker_pct": 0.10, "taker_pct": 0.10, "us": True, "best_for_us": True,
         "note": "flat ~0.10% even on market orders (guaranteed fills); free ACH; some 0-fee BTC pairs"},
        {"venue": "Kraken Pro", "maker_pct": 0.16, "taker_pct": 0.26, "us": True, "best_for_us": False,
         "note": "drops with volume; never hacked; public API + futures demo for paper"},
        {"venue": "Robinhood", "maker_pct": 0.0, "taker_pct": 0.0, "us": True, "best_for_us": False,
         "note": "commission-free but ~0.3-0.4% spread; limited coins"},
        {"venue": "Gemini ActiveTrader", "maker_pct": 0.20, "taker_pct": 0.40, "us": True, "best_for_us": False,
         "note": "regulatory-conservative; ~80 coins"},
        {"venue": "Coinbase Advanced", "maker_pct": 0.40, "taker_pct": 0.60, "us": True, "best_for_us": False,
         "note": "too expensive for frequent trading at base tier"},
    ]

    payload = {
        "generated_at": _now(),
        "status_label": "PRODUCTION REHEARSAL v1 — single account, proven champions only, full reality chain. OBSERVATIONAL.",
        "seed_usd": SEED,
        "inception_ts": inception,
        "live_equity": live_equity,
        "live_pct": live_pct,
        "live_trades_count": len(post),
        "live_status": live_status,
        "equity_net_spendable": round(equity, 2),
        "gross_to_spendable_chain": chain,
        "net_spendable_cash": round(net_spendable, 2),
        "decision_tree": quadrants,
        "allocation_pct": alloc,
        "proven_quadrants": accepted,
        "rehearsal_source": src,
        "champion": champ,
        "quadrant_recommendations": recs,
        "master_decision": master_decision,
        "reality_validation": reality_validation,
        "exchange_comparison": exchange_comparison,
        "daily_briefing": {
            "proven_today": accepted,
            "allocation": alloc,
            "best_engine": f"{src} champion {champ}" if champ else src,
            "headline": (f"A single real account following only our proven champion would hold "
                         f"${equity:,.2f} after the FULL fee+tax+withdrawal chain — vs ${SEED+gross:,.2f} on paper."),
        },
        "what": "The dress rehearsal: one $10k account, only proven quadrants funded, headline = net spendable cash.",
        "honest_note": ("v1 adopts the proven book's REAL trades (crypto today) and runs them through the "
                        "complete reality chain — it does not yet run its own independent cross-quadrant "
                        "simulator (that is the v2 build). Tax 25% and a $5 withdrawal are placeholders, not "
                        "advice. Rejected quadrants are rejected because they have not proven a positive "
                        "net-after-fee edge — that is the honest state, and they stay in R&D until they do. "
                        "This is a rehearsal on paper; live fills still slip."),
    }
    try:
        payload["decision_log_tail"] = (ledger[-12:])[::-1]
        from .atomic_io import write_json_atomic
        write_json_atomic(out / "MASTER_ACCOUNT.json", payload)
    except Exception:
        (out / "MASTER_ACCOUNT.json").write_text(json.dumps(payload, indent=2))
    return payload

if __name__ == "__main__":
    import sys
    d = build_master_account(sys.argv[1] if len(sys.argv) > 1 else "docs/data")
    print("equity net spendable: $%.2f | proven: %s" % (d["equity_net_spendable"], d["proven_quadrants"]))
    for c in d["gross_to_spendable_chain"]: print(f"  {c['step']:48} ${c['amount']:+.2f}")
    print("  -> NET SPENDABLE CASH: $%.2f" % d["net_spendable_cash"])
    print("\n decision tree:")
    for b, q in d["decision_tree"].items(): print(f"  {b:7} {q['decision']:7} — {q['reason']}")
