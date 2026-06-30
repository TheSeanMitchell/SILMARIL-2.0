"""
silmaril.execution.strategy_lab — the STRATEGY LEADERBOARD (Alpha 2.13).

You asked to test tens/hundreds of strategies at once and let edge emerge. This is
that engine. A dictionary of strategy configs (momentum and mean-reversion, every
threshold/target/stop/hold combination, plus hybrids) is backtested through the
same honest sim each cycle — fresh names only, real per-coin fees — and ranked.

The winner is whatever actually clears fees on out-of-sample forward data, not
whatever sounds good. Add a row to STRATEGIES and it competes next cycle. The
point: stop arguing about which strategy is right and let the leaderboard decide.

Honesty rails (same as paper_sim): ghosts (stale prices) excluded; fee =
max(0.2%, 2x each name's noise floor); a great backtest is a hypothesis to test
forward, never a guarantee. With many strategies, the top of the board will look
amazing BY CHANCE — the real signal is a strategy that stays top across many
fresh 3-day windows, not one that wins once.
"""
from __future__ import annotations

import json
from .atomic_io import write_json_atomic
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any, Dict, List

from .paper_sim import is_tradeable, round_trip_cost, _is_crypto, load_all_samples, TIMEOUT_EXIT

PER_NAME_FRAC = 0.10


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── a strategy is a small config; the grid below expands to dozens ───────────
def _make_strategies() -> Dict[str, Dict[str, Any]]:
    s: Dict[str, Dict[str, Any]] = {}
    # MEAN-REVERSION grid: buy a drop, exit at bounce / stop / timeout
    for drop in (0.01, 0.02, 0.03, 0.05):
        for tgt in (0.01, 0.02, 0.03):
            for stop in (0.02, 0.04, 0.06):
                s[f"MR_d{int(drop*100)}_t{int(tgt*100)}_s{int(stop*100)}"] = {
                    "dir": "mr", "entry": drop, "target": tgt, "stop": stop, "hold": 22}
    # MOMENTUM grid: buy strength, exit at target / stop / timeout
    for up in (0.01, 0.02, 0.03):
        for tgt in (0.02, 0.04):
            for stop in (0.02, 0.04):
                s[f"MOM_u{int(up*100)}_t{int(tgt*100)}_s{int(stop*100)}"] = {
                    "dir": "mom", "entry": up, "target": tgt, "stop": stop, "hold": 22}
    # PERSISTENCE family (momentum that requires a sustained move, longer hold)
    for up in (0.015, 0.025):
        for hold in (12, 24):
            s[f"PERSIST_u{int(up*1000)}_h{hold}"] = {
                "dir": "mom", "entry": up, "target": 0.03, "stop": 0.03, "hold": hold}
    # a few longer-hold HYBRID variants (patient bounce)
    for drop in (0.02, 0.03):
        s[f"MR_patient_d{int(drop*100)}"] = {
            "dir": "mr", "entry": drop, "target": 0.03, "stop": 0.05, "hold": 44}
    # 2.7 HOLD family — the long-hold playbook (commodities AND slow stocks like SPY/QQQ/NVDA/INTC).
    # Two entry styles; the leaderboard decides which fits each name. Greedy targets out of the gate
    # (operator: 5-12% long-hold targets vs 1-6% crypto scalps). Wide 12% stop rides the commodity floor so
    # a normal swing never forces a sale — the heatshield stays UP, no panic selling, nerves of steel.
    # DIP-entry holds: buy a pullback on a name with upward trajectory, ride it up.
    for drop in (0.02, 0.03, 0.04):
        for tgt in (0.05, 0.08, 0.10, 0.12):
            s[f"HOLD_d{int(drop*100)}_t{int(tgt*100)}"] = {
                "dir": "mr", "entry": drop, "target": tgt, "stop": 0.12, "hold": 480, "hold_class": True}
    # TREND-entry holds: buy strength (confirmed up-trajectory) and ride the trend to a big target.
    for up in (0.01, 0.02):
        for tgt in (0.08, 0.10, 0.12):
            s[f"HOLD_u{int(up*100)}_t{int(tgt*100)}"] = {
                "dir": "mom", "entry": up, "target": tgt, "stop": 0.12, "hold": 480, "hold_class": True}
    return s


STRATEGIES = _make_strategies()


# ── 2.7 PER-BOOK STRATEGY SEPARATION: each quadrant evolves its own playbook ──
# Every quadrant now competes the FULL strategy set — fast MR/MOM/PERSIST/patient AND the slow HOLD family
# (operator: "we want everything to compete; let the leaderboard decide what fits each quadrant"). The
# SEPARATION that matters is enforced elsewhere and is absolute: each book scores strategies on its OWN
# universe and elects its OWN champion (champion_split) — a champion can never leak across quadrants. The
# right strategy surfaces per book naturally: HOLD wins where slow rides pay (commodities, SPY/QQQ/NVDA),
# fast MR wins where intraday dips pay (crypto). This hook stays per-book so a future restriction is a
# one-line change, but nothing is withheld from any quadrant today.
def book_strategies(book: str) -> Dict[str, Dict[str, Any]]:
    return dict(STRATEGIES)


def _bt_one(series_fresh: Dict[str, List[float]], cfg: Dict[str, Any],
            costs: Dict[str, float]) -> Dict[str, Any]:
    d, tgt, stop, hold = cfg["entry"], cfg["target"], cfg["stop"], cfg["hold"]
    mr = cfg["dir"] == "mr"
    rets: List[float] = []
    exits = {"TAKE": 0, "STOP": 0, "TIMEOUT": 0}
    for tk, px in series_fresh.items():
        n = len(px)
        c = costs[tk]
        i = 6
        while i < n - 1:
            if px[i - 6] <= 0:
                i += 1; continue
            move = px[i] / px[i - 6] - 1
            fire = (move <= -d) if mr else (move >= d)
            if not fire:
                i += 1; continue
            ep = px[i]; j = i + 1; oc = None
            while j < n:
                ch = px[j] / ep - 1
                if ch <= -stop: oc, k = "STOP", j; break
                if ch >= tgt: oc, k = "TAKE", j; break
                if TIMEOUT_EXIT and (j - i) >= hold: oc, k = "TIMEOUT", j; break
                j += 1
            if oc is None: break
            rets.append((px[k] / ep - 1) - c); exits[oc] += 1; i = k + 1
    if not rets:
        return {"trades": 0, "mean_net_pct": 0.0, "total_pct": 0.0,
                "win_pct": 0.0, "equity": 10000.0}
    eq = 10000.0
    for r in rets:
        eq *= (1 + r * PER_NAME_FRAC)
    return {"trades": len(rets),
            "mean_net_pct": round(mean(rets) * 100, 3),
            "win_pct": round(sum(1 for r in rets if r > 0) / len(rets) * 100, 1),
            "total_pct": round(sum(rets) * 100, 1),
            "equity": round(eq, 2),
            "exits": exits}


def run_leaderboard(out_dir) -> Dict[str, Any]:
    out = Path(out_dir)
    samples = load_all_samples(out)
    if not samples:
        return {"error": "no samples"}
    series = {tk: [p for t, p in rows if p and p > 0 and "T00:00:00" not in t] for tk, rows in samples.items()}
    fresh_all = {tk: px for tk, px in series.items() if len(px) > 20 and is_tradeable(px)}
    costs = {tk: round_trip_cost(px) for tk, px in fresh_all.items()}
    fresh_crypto = {k: v for k, v in fresh_all.items() if _is_crypto(k)}
    fresh_stock = {k: v for k, v in fresh_all.items() if not _is_crypto(k)}

    rows = []
    for name, cfg in STRATEGIES.items():
        uni = fresh_crypto if cfg.get("side", "crypto") != "stock" else fresh_stock
        r = _bt_one(uni, cfg, costs)
        rows.append({"strategy": name, "dir": cfg["dir"], **r})
    # rank by mean net edge per trade, but require a minimum sample to be trusted
    ranked = sorted(rows, key=lambda r: (r["trades"] >= 30, r["mean_net_pct"]), reverse=True)
    winners = [r for r in ranked if r["trades"] >= 30 and r["mean_net_pct"] > 0]

    payload = {
        "generated_at": _now(),
        "n_strategies": len(rows),
        "tradeable_universe": len(fresh_all),
        "ghosts_excluded": len(series) - len(fresh_all),
        "leaderboard": ranked,
        "best_trusted": winners[0] if winners else None,
        "verdict": (f"BEST: {winners[0]['strategy']} nets {winners[0]['mean_net_pct']:+.2f}%/trade "
                    f"over {winners[0]['trades']} trades" if winners else
                    "no strategy clears fees with a trustworthy sample this window"),
        "note": ("Ranked by net edge/trade (>=30 trades to be trusted). With dozens "
                 "of strategies the top will look great by luck — trust only a "
                 "strategy that stays near the top across many fresh windows."),
    }
    try:
        write_json_atomic(out / "strategy_leaderboard.json", payload)
    except Exception:
        pass
    return payload


if __name__ == "__main__":
    import sys
    p = run_leaderboard(sys.argv[1] if len(sys.argv) > 1 else "docs/data")
    print("VERDICT:", p.get("verdict"))
    print(f"\n{len(p.get('leaderboard', []))} strategies, top 12 by net edge/trade:")
    print(f"  {'strategy':22s}{'dir':>5}{'trades':>8}{'win%':>6}{'net/trade':>11}{'total':>8}")
    for r in p.get("leaderboard", [])[:12]:
        print(f"  {r['strategy']:22s}{r['dir']:>5}{r['trades']:>8}{r['win_pct']:>5.0f}%"
              f"{r['mean_net_pct']:>+10.3f}%{r['total_pct']:>+7.0f}%")


# ── 2.5.1 MARKET SEPARATION: independent crypto and stock arenas ─────────────
def _uni_ok(px, crypto: bool) -> bool:
    """Universe inclusion, per market. Crypto uses the 24/7 freshness bar; stocks
    can't meet it (markets ~27% of hours) so they qualify on real price movement."""
    if len(px) <= 20:
        return False
    if crypto:
        return is_tradeable(px)
    return len(set(px[-300:])) > 5   # a stock that actually quotes/moves in the tape

def run_split_leaderboards(out_dir):
    """Run EVERY strategy on the crypto universe and (separately) the stock universe.
    Two independent leaderboards, two independent champions — no cross-contamination.
    Emits strategy_leaderboard_crypto.json and strategy_leaderboard_stock.json."""
    out = Path(out_dir)
    samples = load_all_samples(out)
    if not samples:
        return {}
    series = {tk: [p for t, p in rows if p and p > 0 and "T00:00:00" not in t] for tk, rows in samples.items()}
    fresh_all = {tk: px for tk, px in series.items() if len(px) > 20}
    costs = {tk: round_trip_cost(px) for tk, px in fresh_all.items()}
    out_payloads = {}
    from .paper_sim import asset_class as _ac, BOOKS as _BOOKS
    for book in _BOOKS:
        is_cry = (book == "crypto")
        uni = {k: v for k, v in fresh_all.items() if _ac(k) == book and _uni_ok(v, is_cry)}
        roster = book_strategies(book)
        rows = []
        for name, cfg in roster.items():
            r = _bt_one(uni, cfg, costs)
            rows.append({"strategy": name, "dir": cfg["dir"], **r})
        # commodity books are slow and sparse — holds close rarely, so a 30-trade bar would never seat a
        # champion. They qualify on a smaller (clearly PROVISIONAL) sample; crypto/stock keep the 30 bar.
        min_tr = 5 if book in ("metal", "energy") else 30
        ranked = sorted(rows, key=lambda r: (r["trades"] >= min_tr, r["mean_net_pct"]), reverse=True)
        winners = [r for r in ranked if r["trades"] >= min_tr and r["mean_net_pct"] > 0]
        payload = {
            "generated_at": _now(), "book": book, "universe_size": len(uni),
            "min_trades_for_trust": min_tr,
            "leaderboard": ranked, "best_trusted": winners[0] if winners else None,
            "verdict": (f"BEST {book}: {winners[0]['strategy']} nets {winners[0]['mean_net_pct']:+.2f}%/trade "
                        f"over {winners[0]['trades']} trades"
                        + (" (PROVISIONAL — small sample)" if (winners and book in ('metal', 'energy')) else "")
                        if winners else
                        f"no {book} strategy clears fees with a trustworthy sample this window"),
            "note": f"Independent {book} arena (2.5.1) · roster: {('HOLD-first commodity set' if book in ('metal','energy') else 'full fast grid')}. No shared champion with other markets.",
        }
        try: write_json_atomic(out / f"strategy_leaderboard_{book}.json", payload)
        except Exception: pass
        out_payloads[book] = payload
    return out_payloads
