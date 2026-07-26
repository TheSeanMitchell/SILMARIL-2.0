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
def _catalog_grid():
    """PARAM_CATALOG.json drives the arena. Editing that ONE file changes which strategies compete on the
    next cycle — no code changes, ever. This is the 'comprehensive, authoritative, tunable' layer: the full
    drop/bounce/stop space is enumerated there, and the arena breeds over exactly what the file says."""
    try:
        from pathlib import Path as _P
        for base in ("docs/data", "."):
            f = _P(base) / "PARAM_CATALOG.json"
            if f.exists():
                g = json.loads(f.read_text()).get("arena_grid") or {}
                if g:
                    return g
    except Exception:
        pass
    return {}


def _make_strategies(wide: bool = False) -> Dict[str, Dict[str, Any]]:
    s: Dict[str, Dict[str, Any]] = {}
    g = _catalog_grid() if wide else {}   # hourly arena = compact classic grid (fast); the FULL catalog grid
    # (280 MR strategies) competes once daily via run_wide_arena — same evidence, none of the cycle bloat
    mr = g.get("mr") or {}
    # MEAN-REVERSION grid: buy a drop, exit at bounce / stop / timeout
    for drop in tuple(mr.get("drops") or (0.01, 0.02, 0.03, 0.05)):
        for tgt in tuple(mr.get("targets") or (0.01, 0.02, 0.03)):
            for stop in tuple(mr.get("stops") or (0.02, 0.04, 0.06)):
                s[f"MR_d{int(drop*100)}_t{int(tgt*100)}_s{int(stop*100)}"] = {
                    "dir": "mr", "entry": drop, "target": tgt, "stop": stop, "hold": 22}
    # MOMENTUM grid: buy strength, exit at target / stop / timeout
    mom = g.get("mom") or {}
    for up in tuple(mom.get("ups") or (0.01, 0.02, 0.03)):
        for tgt in tuple(mom.get("targets") or (0.02, 0.04)):
            for stop in tuple(mom.get("stops") or (0.02, 0.04)):
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


STRATEGIES = _make_strategies(wide=True)   # FULL catalog grid (316) — backtest is ~6s/4books, so the
# hourly arena now competes the ENTIRE population, not a compact sample. The old cron balloons were the
# heavy news/IPO builders (now gated off the fast cycle), never this grid. Nothing is withheld: every
# nicknamed strategy competes every hour, per book, on its own universe.


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


# ── 7.1.2 SESSION-CONTINUITY LAW ───────────────────────────────────────────────────────
# _bt_one walks a bare price list and treats index adjacency as continuous time. For
# equities that silently let a trade opened at 3pm Monday "exit" into Tuesday's opening
# gap — an overnight move no intraday strategy could ever have captured. That artifact is
# what produced MR_d1_t7_s12 at 92.2% wins and +7.00%/trade on the stock arena: a money
# printer made of gaps. Series are now cut into SEGMENTS wherever the tape jumps more than
# the continuity window, and each segment is backtested on its own, so no position can span
# a gap it could not trade through. Crypto is 24/7 and rarely segments — there it only
# splits genuine feed outages, which is also correct.
_GAP_MIN = 90.0


def _iso_ts(t):
    """Seconds-since-epoch for an ISO stamp, or None."""
    try:
        from datetime import datetime as _dt
        return _dt.fromisoformat(str(t).replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


def _segment_series(samples):
    """{sym: rows} -> ({key: [px]}, n_segmented). Keys of split names carry a '#sN' suffix;
    callers strip it with .split('#s')[0] for class and cost lookups."""
    series, segmented = {}, 0
    for tk, rows in (samples or {}).items():
        live = []
        for r in (rows or []):
            try:
                t, px = r[0], float(r[1])
            except Exception:
                continue
            if px <= 0 or "T00:00:00" in str(t):
                continue
            ts = _iso_ts(t)
            if ts is not None:
                live.append((ts, px))
        live.sort()
        segs, cur = [], []
        for i, (ts, px) in enumerate(live):
            if cur and (ts - live[i - 1][0]) > _GAP_MIN * 60.0:
                segs.append(cur)
                cur = []
            cur.append(px)
        if cur:
            segs.append(cur)
        segs = [g for g in segs if len(g) > 8]
        if not segs:
            continue
        if len(segs) == 1:
            series[tk] = segs[0]
            continue
        segmented += 1
        for si, g in enumerate(segs):
            series["%s#s%d" % (tk, si)] = g
    return series, segmented


def _bt_one(series_fresh: Dict[str, List[float]], cfg: Dict[str, Any],
            costs: Dict[str, float]) -> Dict[str, Any]:
    d, tgt, stop, hold = cfg["entry"], cfg["target"], cfg["stop"], cfg["hold"]
    mr = cfg["dir"] == "mr"
    # ── 7.1.2 SURVIVORSHIP LAW ────────────────────────────────────────────────────────
    # THE DEFECT: TIMEOUT_EXIT is False, so a trade that hit neither target nor stop walked
    # to the end of the window and then `if oc is None: break` DISCARDED it. The arena
    # therefore counted only the trades that RESOLVED. On any series with upward drift a
    # +5% target resolves constantly while a -12% stop almost never does, so the survivors
    # were overwhelmingly winners: MR_d1_t5_s12 printed 99.0% wins at +5.59%/trade over 97
    # trades — a money printer made of the trades that were thrown away. That single line is
    # why the operator read the quadrant leaderboards as "sketch"; they were.
    # THE LAW: a position still open when the window ends is not a non-event. It is marked to
    # the last real price and counted, exactly as a live book would carry it — and reported
    # separately from realized closes so nobody mistakes a mark for a fill.
    rets: List[float] = []
    exits = {"TAKE": 0, "STOP": 0, "TIMEOUT": 0, "OPEN_MARK": 0}
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
            if oc is None:
                if n - 1 > i:                     # carry it as an open mark, never drop it
                    rets.append((px[n - 1] / ep - 1) - c); exits["OPEN_MARK"] += 1
                break
            rets.append((px[k] / ep - 1) - c); exits[oc] += 1; i = k + 1
    if not rets:
        return {"trades": 0, "mean_net_pct": 0.0, "total_pct": 0.0,
                "win_pct": 0.0, "equity": 10000.0,
                "resolved": 0, "open_marks": 0, "exits": dict(exits)}
    eq = 10000.0
    for r in rets:
        eq *= (1 + r * PER_NAME_FRAC)
    _res = exits["TAKE"] + exits["STOP"] + exits["TIMEOUT"]
    return {"trades": len(rets),
            "mean_net_pct": round(mean(rets) * 100, 3),
            "win_pct": round(sum(1 for r in rets if r > 0) / len(rets) * 100, 1),
            "total_pct": round(sum(rets) * 100, 1),
            "equity": round(eq, 2),
            "resolved": _res, "open_marks": exits["OPEN_MARK"],
            "exits": exits}


def run_leaderboard(out_dir) -> Dict[str, Any]:
    out = Path(out_dir)
    samples = load_all_samples(out)
    if not samples:
        return {"error": "no samples"}
    series, _segmented = _segment_series(samples)
    fresh_all = {tk: px for tk, px in series.items() if len(px) > 20 and is_tradeable(px)}
    costs = {tk: round_trip_cost(px) for tk, px in fresh_all.items()}
    def _base(tk):
        return tk.split("#s")[0]
    fresh_crypto = {k: v for k, v in fresh_all.items() if _is_crypto(_base(k))}
    fresh_stock = {k: v for k, v in fresh_all.items() if not _is_crypto(_base(k))}

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
    series, _segmented = _segment_series(samples)
    # ── 7.1.2 PRICE TRUTH: the arena may only run on tapes that can be traded. ────────────
    # The operator called the quadrant leaderboards "sketch" and was right: rows like
    # MR_d1_t1_s8 at 91.7% wins and -1.33% mean net are arithmetically incoherent for that
    # shape — they were the backtest dutifully "buying dips" that were feed artifacts. A
    # champion elected on artifact names is a champion of nothing.
    try:
        from .price_truth import may_learn as _ml7
        _before = len(series)
        series = {tk: px for tk, px in series.items() if _ml7(out, tk.split("#s")[0])}
        _dropped = _before - len(series)
    except Exception:
        _dropped = 0
    fresh_all = {tk: px for tk, px in series.items() if len(px) > 20}
    costs = {tk: round_trip_cost(px) for tk, px in fresh_all.items()}
    def _base(tk):
        return tk.split("#s")[0]
    out_payloads = {}
    from .paper_sim import asset_class as _ac, BOOKS as _BOOKS
    for book in _BOOKS:
        is_cry = (book == "crypto")
        uni = {k: v for k, v in fresh_all.items() if _ac(_base(k)) == book and _uni_ok(v, is_cry)}
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
            "feeds_excluded": _dropped, "names_segmented": _segmented,
            "session_law": ("series are cut at gaps > %dmin and each segment backtested alone, so no "
                            "trade can exit into an overnight gap it could never have traded through"
                            % int(_GAP_MIN)),
            "feed_law": ("names whose feed PRICE_TRUTH graded FROZEN/QUANTIZED/COARSE/DISPUTED are "
                         "excluded from this arena — a strategy cannot be scored on a tape whose "
                         "moves are the venue's tick size"),
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


# ── 2.7 DAILY-CANDLE HOLD BACKTEST: crunch MONTHS into minutes ────────────────
# Slow HOLD strategies (5-12% targets) almost never close inside a 24h intraday window, so the intraday
# leaderboard can't evaluate them and metals/energy wait weeks for a champion. This backtests HOLD over the
# YEAR of DAILY candles instead, so a real HOLD champion can be elected from real history immediately.
#
# ISOLATION (the whole point — this is the bug that has hurt the operator most): this function reads ONLY
# daily candles — the "T00:00:00" timestamps that the intraday/trading path deliberately EXCLUDES. It writes
# ONLY strategy_leaderboard_holds_{book}.json. It never touches run_split_leaderboards, never feeds the
# intraday MR path, and the intraday path never sees a daily candle. The two are rigorously separate.
def run_daily_hold_leaderboards(out_dir):
    out = Path(out_dir)
    samples = load_all_samples(out)
    if not samples:
        return {}
    # DAILY ONLY — the exact inverse of the intraday filter, kept apart on purpose.
    daily = {tk: [p for t, p in rows if p and p > 0 and "T00:00:00" in t] for tk, rows in samples.items()}
    daily = {tk: px for tk, px in daily.items() if len(px) >= 30}     # need real history to mean anything
    costs = {tk: round_trip_cost(px) for tk, px in daily.items()}
    holds = {k: v for k, v in STRATEGIES.items() if k.startswith("HOLD_")}
    from .paper_sim import asset_class as _ac, BOOKS as _BOOKS
    MIN_TR = 10
    out_payloads = {}
    for book in _BOOKS:
        uni = {k: v for k, v in daily.items() if _ac(k) == book}
        rows = []
        for name, cfg in holds.items():
            r = _bt_one(uni, cfg, costs)
            rows.append({"strategy": name, "dir": cfg["dir"], **r})
        ranked = sorted(rows, key=lambda r: (r["trades"] >= MIN_TR, r["mean_net_pct"]), reverse=True)
        winners = [r for r in ranked if r["trades"] >= MIN_TR and r["mean_net_pct"] > 0]
        payload = {
            "generated_at": _now(), "book": book, "basis": "DAILY candles (months of real history)",
            "universe_size": len(uni), "min_trades_for_trust": MIN_TR,
            "leaderboard": ranked, "best_trusted": winners[0] if winners else None,
            "verdict": (f"BEST {book} HOLD: {winners[0]['strategy']} nets {winners[0]['mean_net_pct']:+.2f}%/trade "
                        f"over {winners[0]['trades']} daily-candle trades" if winners else
                        f"no HOLD strategy clears fees over daily history for {book} yet"),
            "note": "ISOLATED daily-candle backtest — reads only daily candles, never feeds the intraday path.",
        }
        try: write_json_atomic(out / f"strategy_leaderboard_holds_{book}.json", payload)
        except Exception: pass
        out_payloads[book] = payload
    return out_payloads


def run_wide_arena(out_dir):
    """Once-daily WIDE arena: the FULL PARAM_CATALOG grid (every drop x bounce x stop, 280+ strategies)
    backtested per book on real data — the drop/bounce sweet-spot sweep. Emits
    strategy_leaderboard_wide_{book}.json. Gated to daily staleness in cli so the 10-minute trade cycle
    never carries this weight (the July-1 15-18min balloons were this grid running hourly — fixed)."""
    out = Path(out_dir)
    samples = load_all_samples(out)
    if not samples:
        return {}
    series, _segmented = _segment_series(samples)
    fresh_all = {tk: px for tk, px in series.items() if len(px) > 20}
    costs = {tk: round_trip_cost(px) for tk, px in fresh_all.items()}
    def _base(tk):
        return tk.split("#s")[0]
    wide = _make_strategies(wide=True)
    res = {}
    from .paper_sim import asset_class as _ac, BOOKS as _BOOKS
    for book in _BOOKS:
        is_cry = (book == "crypto")
        uni = {k: v for k, v in fresh_all.items() if _ac(_base(k)) == book and _uni_ok(v, is_cry)}
        rows = []
        for name, cfg in wide.items():
            r = _bt_one(uni, cfg, costs)
            rows.append({"strategy": name, "dir": cfg["dir"], **r})
        min_tr = 5 if book in ("metal", "energy") else 30
        ranked = sorted(rows, key=lambda r: (r["trades"] >= min_tr, r["mean_net_pct"]), reverse=True)
        winners = [r for r in ranked if r["trades"] >= min_tr and r["mean_net_pct"] > 0]
        payload = {"generated_at": _now(), "book": book, "universe_size": len(uni),
                   "grid_size": len(wide), "competed": len(rows), "min_trades_for_trust": min_tr,
                   "leaderboard": ranked, "best_trusted": winners[0] if winners else None,
                   "what": "FULL catalog grid swept daily — the drop/bounce possibility space on real data; every strategy that competed is listed (grid_size), ranked by trusted mean edge"}
        try:
            write_json_atomic(out / f"strategy_leaderboard_wide_{book}.json", payload)
        except Exception:
            (out / f"strategy_leaderboard_wide_{book}.json").write_text(json.dumps(payload, indent=1))
        res[book] = payload.get("best_trusted")
    return res
