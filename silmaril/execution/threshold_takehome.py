"""
silmaril.execution.threshold_takehome — TAKE-HOME AFTER FEES (2.5.5).

Two honest views, both built to answer one question: how do we cut the fat and trade fewer, more
profitable trades?

BOX A — DAILY TAKE-HOME (last 7 days): from the REAL book trades, per Vegas-midnight day, the actual
  gross, the fee bill (documented 54 bps/round-trip from fees_truth.json), and the net take-home. This
  is what we ACTUALLY kept each day. Lets us see whether early-day over-trading dragged the lifetime
  number down vs. how recent days look.

BOX B — THRESHOLD SWEEP: a simulation over REAL crypto price history (same engine as the drop×bounce
  champion — real prices, no fabricated trades). For each drop trigger and each bounce target it
  reports how many signals fired (trade count), the average captured move, and — the new part — the
  average NET take-home PER TRADE after the 54 bps fee, plus the count. A trade must clear ~0.54% just
  to break even on fees, so this shows precisely which thresholds produce trades worth taking and how
  "fewer but deeper" changes the math.

OBSERVATIONAL. Changes no trading logic. Emits THRESHOLD_TAKEHOME.json.
"""
from __future__ import annotations
import json
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List

try:
    from .threshold_champion import _signals_for_drop, LOOKBACK, HORIZON, DROPS, BOUNCES
    from ._trade_helpers import price_series
    from .paper_sim import asset_class
except Exception:
    LOOKBACK, HORIZON = 6, 18
    DROPS = [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0]
    BOUNCES = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0]
    def _signals_for_drop(px, drop_pct):
        return [i for i in range(LOOKBACK, len(px) - HORIZON)
                if (px[i] / px[i - LOOKBACK] - 1) * 100 <= -drop_pct]

def _now(): return datetime.now(timezone.utc).isoformat()

# --- fee model (documented; same as Reality Check) ---
def _fee_bps(out: Path) -> float:
    try:
        f = json.loads((out / "fees_truth.json").read_text())
        taker = float(f.get("crypto_taker_bps_future_zone", 25))
        slip = float(f.get("slippage_bps_market_orders", 2))
        return (taker + slip) * 2          # round-trip = both sides
    except Exception:
        return 54.0

NOTIONAL = 1000.0   # representative full-size trade for per-trade economics

def _vegas_day(ts: str) -> str:
    """Vegas-midnight day key for an ISO ts (PDT = UTC-7)."""
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return (dt - timedelta(hours=7)).date().isoformat()
    except Exception:
        return ts[:10]

def build_threshold_takehome(out_dir) -> Dict[str, Any]:
    out = Path(out_dir)
    fee_bps = _fee_bps(out)
    fee_frac = fee_bps / 10000.0
    fee_per_trade = round(NOTIONAL * fee_frac, 2)

    # ---- BOX A: daily real take-home after fees ----
    daily = []
    try:
        trades = json.loads((out / "paper_book_crypto.json").read_text()).get("trades", [])
        sells = [t for t in trades if t.get("side") == "SELL" and t.get("pnl") is not None]
        byday = defaultdict(lambda: {"gross": 0.0, "fees": 0.0, "trips": 0})
        for t in sells:
            notional = abs((t.get("qty") or 0) * (t.get("price") or 0))
            if notional < 1.0:               # skip dust
                continue
            d = _vegas_day(t.get("t", ""))
            byday[d]["gross"] += float(t.get("pnl") or 0)
            byday[d]["fees"] += notional * fee_frac
            byday[d]["trips"] += 1
        for d in sorted(byday)[-7:]:
            g = byday[d]
            net = g["gross"] - g["fees"]
            daily.append({"day": d, "gross": round(g["gross"], 2), "fees": round(-g["fees"], 2),
                          "net_takehome": round(net, 2), "trips": g["trips"]})
    except Exception:
        pass

    # ---- BOX B: threshold sweep over real price history ----
    sweep = {"available": False}
    try:
        series = price_series(out)
        names = sorted([s for s in series if asset_class(s) == "crypto"
                        and len(series[s]) > LOOKBACK + HORIZON],
                       key=lambda s: len(series[s]), reverse=True)[:45]
        seqs = {s: [p for _, p in series[s]] for s in names}
        entries = {d: [] for d in DROPS}
        for s in names:
            px = seqs[s]
            for d in DROPS:
                for i in _signals_for_drop(px, d):
                    fwd = px[i:i + HORIZON]
                    best = (max(fwd) / px[i] - 1) * 100
                    end = (fwd[-1] / px[i] - 1) * 100
                    entries[d].append((best, end))

        # drop sweep: hold bounce at current live 3% target; vary the drop trigger (controls COUNT)
        live_bounce = 3.0
        drop_rows = []
        for d in DROPS:
            rows = entries[d]
            if not rows:
                continue
            outcomes = [live_bounce if best >= live_bounce else end for best, end in rows]
            exp = mean(outcomes)
            net_per = NOTIONAL * (exp / 100) - fee_per_trade
            drop_rows.append({"drop_pct": d, "bounce_pct": live_bounce, "signals": len(rows),
                              "avg_captured_pct": round(exp, 3),
                              "gross_per_trade": round(NOTIONAL * exp / 100, 2),
                              "fee_per_trade": fee_per_trade,
                              "net_per_trade": round(net_per, 2),
                              "total_net_est": round(net_per * len(rows), 2),
                              "clears_fees": exp > fee_bps / 100})

        # bounce sweep: hold drop at current live 3% trigger; vary the bounce target (controls win SIZE)
        live_drop = 3.0
        base = entries.get(live_drop, [])
        bounce_rows = []
        for b in BOUNCES:
            if not base:
                continue
            outcomes = [b if best >= b else end for best, end in base]
            hits = sum(1 for best, _ in base if best >= b)
            exp = mean(outcomes)
            net_per = NOTIONAL * (exp / 100) - fee_per_trade
            bounce_rows.append({"bounce_pct": b, "drop_pct": live_drop, "signals": len(base),
                                "hit_rate_pct": round(hits / len(base) * 100, 1),
                                "avg_captured_pct": round(exp, 3),
                                "net_per_trade": round(net_per, 2),
                                "total_net_est": round(net_per * len(base), 2),
                                "clears_fees": exp > fee_bps / 100})
        sweep = {"available": True, "drop_sweep": drop_rows, "bounce_sweep": bounce_rows,
                 "names_simulated": len(names)}
    except Exception as e:
        sweep = {"available": False, "error": str(e)[:120]}

    # ---- FEE SCENARIOS: what we keep under different order types / venues (real 2026 rates) ----
    # Round-trip bps = both sides. Limit (maker) orders cost less than market (taker) but may not fill.
    SCENARIOS = [
        ("Kraken taker / market order", 60.0),
        ("our current model", fee_bps),
        ("Kraken maker / limit order", 40.0),
        ("Binance.US 0.10% flat", 20.0),
    ]
    gross_total = sum(r["gross"] for r in daily) if daily else 0.0
    scen_rows = []
    for label, bps in SCENARIOS:
        frac = bps / 10000.0
        per_day = []
        net_total = 0.0
        for r in daily:
            # reconstruct notional from the fee we stored at the model rate
            day_notional = (abs(r["fees"]) / fee_frac) if fee_frac else 0.0
            day_fee = day_notional * frac
            net = r["gross"] - day_fee
            net_total += net
            per_day.append({"day": r["day"], "net": round(net, 2)})
        scen_rows.append({"label": label, "bps_round_trip": bps,
                          "lifetime_net": round(net_total, 2), "per_day": per_day})

    # low-fee drop sweep: same signals, charged the 20bps flat venue, to show the table go green
    low_fee_per_trade = NOTIONAL * 0.0020
    low_fee_sweep = []
    if sweep.get("available"):
        for r in sweep["drop_sweep"]:
            gross_pt = r["gross_per_trade"]
            low_net = round(gross_pt - low_fee_per_trade, 2)
            low_fee_sweep.append({"drop_pct": r["drop_pct"], "signals": r["signals"],
                                  "net_per_trade_lowfee": low_net, "clears_fees": gross_pt > 0.20})

    payload = {
        "generated_at": _now(),
        "status_label": "OBSERVATIONAL — what we kept after fees, and what different thresholds would yield.",
        "fee_model_bps_round_trip": fee_bps,
        "fee_per_1k_trade": fee_per_trade,
        "breakeven_pct_per_trade": round(fee_bps / 100, 3),
        "notional_assumed": NOTIONAL,
        "daily_takehome": daily,
        "threshold_sweep": sweep,
        "fee_scenarios": scen_rows,
        "low_fee_drop_sweep": low_fee_sweep,
        "gross_total_window": round(gross_total, 2),
        "what": "BOX A = real net take-home per day after fees. BOX B = simulated trade-count + net-per-trade after fees at each drop/bounce threshold.",
        "how_to_read": (f"Every trade must clear {round(fee_bps/100,2)}% just to pay its fees. In BOX B, "
                        "rows where clears_fees is false LOSE money on average — that's the fat to cut. "
                        "A higher drop trigger means fewer signals (lower 'signals') but usually a higher "
                        "net_per_trade — the 'fewer but deeper' tradeoff, in dollars."),
        "honest_note": ("BOX A is real realized history. BOX B is a simulation over real price paths across "
                        "the top-45 crypto names — it shows opportunity economics, not a guarantee, and "
                        "total_net_est assumes a $1k trade per signal (real capital caps how many you can "
                        "hold at once, so treat totals as an upper sketch and net_per_trade as the honest "
                        "per-trade truth). Bounce targets here are evaluated against actual forward price "
                        "paths; they are not yet auto-tuned by trajectory — that is the judge-mode step."),
    }
    try:
        from .atomic_io import write_json_atomic
        write_json_atomic(out / "THRESHOLD_TAKEHOME.json", payload)
    except Exception:
        (out / "THRESHOLD_TAKEHOME.json").write_text(json.dumps(payload, indent=2))
    return payload

if __name__ == "__main__":
    import sys
    d = build_threshold_takehome(sys.argv[1] if len(sys.argv) > 1 else "docs/data")
    print("daily days:", len(d["daily_takehome"]), "| sweep avail:", d["threshold_sweep"].get("available"))
    for r in d["daily_takehome"]:
        print(f"  {r['day']}  gross ${r['gross']:+.2f}  fees ${r['fees']:.2f}  NET ${r['net_takehome']:+.2f}  ({r['trips']} trips)")
    if d["threshold_sweep"].get("available"):
        print(" DROP sweep (bounce held 3%):")
        for r in d["threshold_sweep"]["drop_sweep"]:
            print(f"  drop>={r['drop_pct']}%  {r['signals']:4d} trips  net/trade ${r['net_per_trade']:+.2f}  clears_fees={r['clears_fees']}")
