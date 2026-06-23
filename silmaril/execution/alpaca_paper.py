"""silmaril.execution.alpaca_paper — Alpha 6.0 wired executor.

This file is the BRAIN→HANDS bridge. Compared to Alpha 3.x:
  * Consumes policy.position_directives (PROFIT_LOCK, SCALE_OUT,
    MOMENTUM_DECAY, INTRADAY_EXHAUSTION, BREAK_EVEN_STOP, TIGHTEN_STOP,
    SCALE_IN) via execution.directive_consumer.
  * Enforces policy.deployment_floor.max_sweep_today PRE-cycle (not
    only post-audit).
  * Executes policy.forced_rotations from conviction_engine.
  * Reacts to orchestrator.system_objective_today (DEPLOY_IDLE_CAPITAL
    wakes HARVEST_5, REDEPLOY_FROM_SGOV triggers SGOV unwind).
  * Honors policy.hard_stops[account_id] — halts opens during
    daily/weekly drawdown.
  * Submits extended-hours+limit orders during pre/post sessions.
  * Refuses opens when account.cash < 0 (no margin pile-on).
  * Consults policy.order_quality for limit/defer decisions.
  * Consults policy.correlation_book for concentration suppression.

Back-compat: every new branch is wrapped to fall through to legacy
behavior if the relevant policy block is absent.
"""
from __future__ import annotations
import json
import os
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

_BASE_URL = "https://paper-api.alpaca.markets"
_ORDERS_ENDPOINT = f"{_BASE_URL}/v2/orders"
_POSITIONS_ENDPOINT = f"{_BASE_URL}/v2/positions"
_ACCOUNT_ENDPOINT = f"{_BASE_URL}/v2/account"
_MAX_RETRIES = 3
_RETRY_DELAY_S = 2.0
_SKIP_ASSET_CLASSES = {"crypto", "token"}

_RESERVED_VAULT_SYMBOLS = {"SGOV", "BIL", "SHY", "TFLO", "USFR"}


def _is_equity_mission(ticker) -> bool:
    """True only for traditional US equities / equity ETFs — the ONLY
    instruments any Alpaca account may order. Structural + fail-closed:
    if the universe helper is unavailable, fall back to the structural
    crypto pattern check alone (still blocks every -USD/-USDT name)."""
    t = str(ticker or "").upper()
    if not t:
        return False
    if "-USD" in t or t.endswith("USDT"):
        return False
    try:
        from silmaril.universe.core import is_equity_ticker
        return bool(is_equity_ticker(t))
    except Exception:
        return True  # structural check above already excluded crypto


# Accounts permitted to hold CRYPTO/VALUABLES. Per the project's design:
# Account #1 (LEGACY) = stocks only. Account #3 (HARVEST_5) = crypto (hold).
# Account #2 (HARVEST_3) = crypto WITH daily-goal harvest (June 16 experiment)
# so #2 vs #3 compare two crypto strategies head-to-head.
_VALUABLES_ACCOUNTS = {"HARVEST_5", "HARVEST_3"}


def _is_crypto_symbol(ticker) -> bool:
    t = str(ticker or "").upper()
    return t.endswith("-USD") or t.endswith("USDT") or "/USD" in t


def _can_hold_asset(ticker, account_id) -> bool:
    """Account-aware mission gate (June 16). Crypto is allowed ONLY in the
    designated valuables account (HARVEST_5); everywhere else the strict
    equity-only rule stands. Stocks are allowed in every account as before.
    This replaces the blanket equity-only block that made crypto untradeable
    in ALL accounts — the reason XLM's 30% run could never be taken."""
    if _is_crypto_symbol(ticker):
        return account_id in _VALUABLES_ACCOUNTS
    return _is_equity_mission(ticker)


def _harvest_clock_gate(fp, bucket, gain_pct, min_gain_pct):
    """Clock-aware harvest law (Alpha 0.007): with a confident fingerprint,
    routine tier-harvests WAIT for the stock's typical daily-HIGH window —
    the old 1%/3% tiers sold winners at random clock positions, which is how
    gains got harvested at the floor. Only an outsized move (>= 2x the tier
    threshold) may harvest off-window. Learning names keep legacy behavior.
    Returns (allow, note)."""
    try:
        if not fp or fp.get("learning", True):
            return True, None
        bsw = fp.get("best_sell_window")
        if not bucket or not bsw or bucket == bsw:
            return True, None
        if gain_pct >= 2.0 * max(min_gain_pct, 1e-9):
            return True, f"outsized +{gain_pct*100:.1f}% — harvesting off-window"
        return False, (f"harvest waits for his high window ({bsw} ET) — "
                       f"+{gain_pct*100:.1f}% banks on HIS clock, not ours")
    except Exception:
        return True, None

DEFAULT_PROFIT_TAKE_PCT = 0.05
DEFAULT_TRAIL_STOP_PCT = 0.04
# Disaster backstop that fires EVEN with a live momentum chain — a collapse so
# fast the 10-min read can't catch it. Wide on purpose: it must never trip on a
# normal pullback (that is the momentum exit's call, not a fixed %). (Dash 2.1)
CATASTROPHE_DROP_PCT = 0.08

# RE-ENTRY COOLDOWN (Dash 2.1). After a name is CLOSED, the buy path will not
# re-open it for this many minutes. This is the fix for the buy-XTZ / sell-XTZ /
# re-buy-XTZ-next-cycle churn: a freshly-dumped name keeps reading "green" on the
# 10-min snapshot and gets re-bought immediately, round-tripping into losses. The
# cooldown forces it to settle. Tune up to trade the same name less often, down to
# allow faster re-entry. Time-based so it's robust to the run cadence.
REENTRY_COOLDOWN_MIN = 45.0


def _get_headers():
    key = os.environ.get("ALPACA_API_KEY", "").strip()
    secret = os.environ.get("ALPACA_API_SECRET", "").strip()
    if not key or not secret:
        return None
    return {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret,
            "Content-Type": "application/json"}


def _api_get(url, headers, error_log=None):
    try:
        import requests
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code in (200, 201):
            return r.json()
        msg = f"GET {url} -> HTTP {r.status_code}: {r.text[:300]}"
        print(f"[alpaca] {msg}")
        if error_log is not None:
            error_log.append({"time": _now_iso(), "msg": msg, "status": r.status_code})
        return None
    except Exception as e:
        msg = f"GET {url} raised {type(e).__name__}: {e}"
        print(f"[alpaca] {msg}")
        if error_log is not None:
            error_log.append({"time": _now_iso(), "msg": msg})
        return None


# When True, NEW order submissions are deferred (market is closed). Set per-run
# at the top of execute_consensus_signals. Equity market orders submitted while
# the market is closed never fill — they just sit until the stale-order canceller
# clears them, wasting quota and looping. Gating submission here (one chokepoint)
# means off-hours runs still do bookkeeping/sweeps but don't fire dead orders.
_DEFER_ORDER_SUBMIT = False


def _market_is_regular_session() -> bool:
    """True only during the regular US cash session (when market orders fill)."""
    from datetime import datetime, timezone
    try:
        from ..portfolios.market_clock import _session_for
        return _session_for(datetime.now(timezone.utc)) == "regular"
    except Exception:
        now = datetime.now(timezone.utc)
        if now.weekday() >= 5:
            return False
        mins = now.hour * 60 + now.minute
        # 13:30–20:00 UTC ≈ 09:30–16:00 ET (EDT). Conservative single window.
        return (13 * 60 + 30) <= mins <= (20 * 60)


def _api_post(url, headers, payload, error_log=None):
    # Single-point order-submission gate: skip NEW orders when the market is
    # closed — EXCEPT crypto, which trades 24/7 (no market hours). A crypto
    # symbol carries a /USD or -USD pair; those submit any time, including
    # nights/weekends. This is what lets HARVEST_5's crypto hotlist actually
    # fire off-hours (the reason XLM's weekend/overnight runs were missed).
    if url == _ORDERS_ENDPOINT and _DEFER_ORDER_SUBMIT:
        sym = (payload or {}).get("symbol", "?")
        _su = str(sym).upper()
        _is_crypto = ("/USD" in _su) or _su.endswith("-USD") or _su.endswith("USDT")
        if not _is_crypto:
            print(f"[alpaca] market closed — deferring {(payload or {}).get('side','?')} "
                  f"{sym} (would not fill); will submit during regular hours")
            return None  # falsy: callers (if r:) treat this as not submitted
        # crypto falls through and submits 24/7
    for attempt in range(_MAX_RETRIES):
        try:
            import requests
            r = requests.post(url, headers=headers, json=payload, timeout=15)
            if r.status_code in (200, 201):
                return r.json()
            msg = f"POST {url} -> HTTP {r.status_code}: {r.text[:300]}"
            print(f"[alpaca] {msg}")
            if error_log is not None:
                error_log.append({"time": _now_iso(), "msg": msg, "status": r.status_code})
            # SELF-CORRECTING TRADABILITY (June 19): if Alpaca says the asset
            # isn't found (422), permanently record it so the router stops
            # booking it — this is the fix for the expanded universe including
            # coins Alpaca doesn't list (WLD/DYDX/GALA/JTO/MANA/SAND/AXS...).
            if url == _ORDERS_ENDPOINT and r.status_code == 422:
                try:
                    from .tradability import record_if_not_found
                    record_if_not_found((payload or {}).get("symbol", ""),
                                        r.status_code, r.text)
                except Exception:
                    pass
            return None
        except Exception as e:
            if attempt < _MAX_RETRIES - 1:
                time.sleep(_RETRY_DELAY_S)
            else:
                msg = f"POST {url} raised {type(e).__name__}: {e}"
                print(f"[alpaca] {msg}")
                if error_log is not None:
                    error_log.append({"time": _now_iso(), "msg": msg})
                return None


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _api_delete(url, headers, error_log=None):
    try:
        import requests
        r = requests.delete(url, headers=headers, timeout=15)
        if r.status_code in (200, 204, 207):
            return True
        msg = f"DELETE {url} -> HTTP {r.status_code}: {r.text[:200]}"
        print(f"[alpaca] {msg}")
        if error_log is not None:
            error_log.append({"time": _now_iso(), "msg": msg, "status": r.status_code})
        return False
    except Exception as e:
        if error_log is not None:
            error_log.append({"time": _now_iso(), "msg": f"DELETE {url} raised {type(e).__name__}: {e}"})
        return False


def cancel_stale_open_orders(state, max_age_min=120, crypto_max_age_min=15,
                             error_log=None):
    """Cancel lingering OPEN/unfilled orders so they don't pile up. Crypto
    orders fill in seconds, so a crypto order still open after
    `crypto_max_age_min` (default 15) is cancelled fast; stocks keep the
    longer `max_age_min` window (they legitimately wait for market hours).

    Returns (cancelled_list, open_symbols_set) where open_symbols_set are the
    symbols that STILL have a live open order AFTER this pass — the executor
    uses it to avoid stacking a duplicate order on a name that's already
    working. Paper-safe: only unfilled OPEN orders are touched.
    """
    headers = _get_headers()
    if not headers:
        return [], set()
    open_orders = _api_get(f"{_BASE_URL}/v2/orders?status=open&limit=500", headers, error_log)
    if not isinstance(open_orders, list) or not open_orders:
        return [], set()
    now = datetime.now(timezone.utc)
    cancelled = []
    still_open = set()
    for o in open_orders:
        sym = str(o.get("symbol") or "").upper()
        sub = o.get("submitted_at") or o.get("created_at") or ""
        try:
            age_min = (now - datetime.fromisoformat(str(sub).replace("Z", "+00:00"))).total_seconds() / 60.0
        except Exception:
            age_min = 1e9
        # crypto symbol → fast cancel window; everything else → long window
        _is_crypto = ("/" in sym) or sym.endswith("USD")
        _limit = crypto_max_age_min if _is_crypto else max_age_min
        if age_min >= _limit:
            oid = o.get("id")
            if oid and _api_delete(f"{_BASE_URL}/v2/orders/{oid}", headers, error_log):
                cancelled.append({"symbol": o.get("symbol"), "id": oid,
                                  "side": o.get("side"), "qty": o.get("qty"),
                                  "type": o.get("type"), "age_min": round(age_min)})
            else:
                still_open.add(sym)  # couldn't cancel → still working
        else:
            still_open.add(sym)  # not stale yet → still working
    if cancelled:
        state.setdefault("stale_orders_cancelled", [])
        state["stale_orders_cancelled"] = (state["stale_orders_cancelled"] + cancelled)[-50:]
    state["last_stale_cancel"] = {"at": _now_iso(), "cancelled": len(cancelled),
                                  "open_seen": len(open_orders)}
    return cancelled, still_open


def _load_state(path):
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            pass
    return {
        "version": "6.0", "enabled": False, "account": {},
        "principal_target": 10000, "savings": 0.0,
        "lifetime_realized_wins": 0, "lifetime_realized_losses": 0,
        "position_meta": {}, "tickers_traded_this_cycle": [],
        "recent_alpaca_tickers": [], "orders": [],
        "orders_placed": [], "errors": [],
    }


def _save_state(state, path):
    try:
        from ..analytics.archive import archive_then_trim as _att
        from pathlib import Path as _P
        state["orders"] = _att(_P(state_path).parent,
                               f"orders_{account_id or 'legacy'}",
                               state.get("orders", []), 500)
    except Exception:
        state["orders"] = state.get("orders", [])[-500:]
    state["last_run"] = _now_iso()
    try:
        path.write_text(json.dumps(state, indent=2, default=str))
    except Exception as e:
        print(f"[alpaca] save failed: {e}")


def _prune_recent_tickers(state):
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    recent = []
    for o in state.get("orders", []):
        if o.get("time", "") >= cutoff:
            sym = o.get("symbol")
            if sym and sym not in recent:
                recent.append(sym)
    state["recent_alpaca_tickers"] = recent[:50]


_SAVINGS_VAULT_TICKERS = ("SGOV", "BIL", "SHY", "TFLO", "USFR")


def _extract_savings_vault(positions):
    out = {"holdings": [], "total_market_value": 0.0,
           "primary_symbol": None, "primary_qty": 0.0,
           "primary_market_value": 0.0, "checked_at": _now_iso()}
    if not positions:
        return out
    for pos in positions:
        sym = (pos.get("symbol") or "").upper()
        if sym not in _SAVINGS_VAULT_TICKERS:
            continue
        try:
            qty = float(pos.get("qty", 0) or 0)
            mkt = float(pos.get("market_value", 0) or 0)
            avg = float(pos.get("avg_entry_price", 0) or 0)
            cur = float(pos.get("current_price", 0) or 0)
            upl = float(pos.get("unrealized_pl", 0) or 0)
        except Exception:
            continue
        if abs(qty) < 1e-9:
            continue
        row = {"symbol": sym, "qty": round(qty, 6),
               "market_value": round(mkt, 4),
               "avg_entry_price": round(avg, 4),
               "current_price": round(cur, 4),
               "unrealized_pl": round(upl, 4)}
        out["holdings"].append(row)
        out["total_market_value"] += mkt
        if out["primary_symbol"] is None or sym == "SGOV":
            out["primary_symbol"] = sym
            out["primary_qty"] = round(qty, 6)
            out["primary_market_value"] = round(mkt, 4)
    out["total_market_value"] = round(out["total_market_value"], 4)
    return out


def _build_positions_snapshot(positions, position_meta):
    """Decorate raw Alpaca positions with peak/scale_out_history from meta."""
    out = []
    for p in positions:
        sym = (p.get("symbol") or "").upper()
        if not sym or sym in _RESERVED_VAULT_SYMBOLS:
            continue
        meta = position_meta.get(sym, {}) or {}
        try:
            qty = float(p.get("qty", 0) or 0)
            cur = float(p.get("current_price", 0) or 0)
            avg = float(p.get("avg_entry_price", 0) or 0)
        except Exception:
            continue
        peak = max(meta.get("peak_price", 0) or 0, cur)
        upl = (cur - avg) * qty if qty > 0 else (avg - cur) * abs(qty)
        upl_pct = ((cur - avg) / avg) if avg > 0 else 0.0
        # explicit asset-class tag so crypto vs equity never blur in the
        # data (Alpaca reports crypto positions as BTCUSD-style). Stocks
        # and crypto already live in separate account state files, but the
        # tag makes every row self-describing for clean downstream stats.
        _is_crypto = (sym.endswith("USD") and len(sym) > 3
                      and sym not in ("SGOV",)) or "/" in sym
        out.append({
            "symbol": sym, "ticker": sym,
            "asset_class": "crypto" if _is_crypto else "equity",
            "qty": qty, "current_price": cur,
            "avg_entry_price": avg, "peak_price": peak,
            "market_value": round(qty * cur, 2),
            "unrealized_pl": round(upl, 2),
            "unrealized_plpc": round(upl_pct, 4),
            "first_seen": meta.get("first_seen", ""),
            "scale_out_history": meta.get("scale_out_history") or {},
            "stop_at_break_even": bool(meta.get("stop_at_break_even")),
            "tightened_stop_pct": meta.get("tightened_stop_pct"),
        })
    return out


# ── Wantgot truth v2: per-cycle decision sink ───────────────────────
# Every gate in the entry/exit loops reports through _log_block. During a
# cycle, execute_consensus_signals points this at a fresh list so the cycle's
# decisions can be reconciled (intended vs filled vs held, WITH the reason)
# without touching any individual gate. None outside a cycle.
_CYCLE_DECISION_SINK = None


def _log_block(state_path, _ticker, _category, _reason, account_id, **_detail):
    global _CYCLE_DECISION_SINK
    if _CYCLE_DECISION_SINK is not None:
        try:
            _CYCLE_DECISION_SINK.append({
                "ticker": str(_ticker or "").upper(),
                "category": str(_category),
                "reason": str(_reason)[:160],
            })
        except Exception:
            pass
    try:
        from silmaril.portfolios.explainability import log_decision as _ld
        _ld(Path(state_path).parent, category=_category, ticker=_ticker,
            reason=_reason, account_id=account_id, detail=_detail or {})
    except Exception:
        pass


def _wordsmith_filter(plans, debate_rows, min_conv=0.45):
    """PROJECT WORDSMITH: keep only candidates the word-engine itself wants.
    A name qualifies when its debate contains a FABLEBOY_5 verdict of BUY or
    STRONG_BUY with conviction >= min_conv. Returns (filtered, kept_info).

    debate_rows must be the FULL debate dicts (each with a `verdicts` list).
    ALPHA 1.0 hardening: a {ticker: signal} dict used to be fed here and every
    row silently failed the per-row try/except — H5 starved for days with no
    symptom. Shape is now checked explicitly and the wrong shape is LOUD."""
    fb = {}
    rows = debate_rows or []
    if isinstance(rows, dict):
        print("[alpaca][wordsmith] WARNING: fed a {ticker: signal} dict, not "
              "debate rows — FABLEBOY_5 verdicts are invisible in that shape. "
              "Pass debate_dicts. Proceeding with ZERO word-engine candidates.")
        rows = []
    fed = 0
    for d in rows:
        if not isinstance(d, dict):
            continue
        fed += 1
        try:
            t = str(d.get("ticker") or "").upper()
            for v in (d.get("verdicts") or []):
                if (str(v.get("agent")) == "FABLEBOY_5"
                        and str(v.get("signal")) in ("BUY", "STRONG_BUY")
                        and float(v.get("conviction") or 0) >= min_conv):
                    fb[t] = {"signal": v.get("signal"),
                             "conviction": float(v.get("conviction") or 0),
                             "why": str(v.get("rationale") or "")[:90]}
        except Exception:
            continue
    print(f"[alpaca][wordsmith] fed {fed} debate row(s); FABLEBOY_5 approves "
          f"{len(fb)} name(s) at conviction >= {min_conv}")
    kept, info = [], []
    for p in (plans or []):
        try:
            t = str((p.get("ticker") if isinstance(p, dict)
                     else getattr(p, "ticker", "")) or "").upper()
        except Exception:
            t = ""
        if t and t in fb:
            kept.append(p)
            info.append({"ticker": t, **fb[t]})
    if not kept and fb:
        # ORIGINATION (Alpha 0.007 fix): a headlines-only book must be able
        # to act on the words even when consensus disagrees — that is the
        # whole experiment. Synthesize minimal plans from the word-engine's
        # own convictions (top 5), flagged WORDSMITH-ORIGINATED.
        top = sorted(fb.items(), key=lambda kv: -kv[1]["conviction"])[:5]
        for t, v in top:
            kept.append({"ticker": t, "score": round(v["conviction"] * 2, 2),
                         "signal": v["signal"], "conviction": v["conviction"],
                         "source": "WORDSMITH-ORIGINATED"})
            info.append({"ticker": t, **v, "originated": True})
        print(f"[alpaca][wordsmith] consensus offered none of the word-engine's "
              f"names — originating {len(kept)} entries from FABLEBOY_5 alone")
    return kept, info


def execute_consensus_signals(
    plans,
    state_path,
    max_position_pct=0.08,
    min_consensus_conviction=0.40,
    max_total_positions=15,
    enable_shorts=True,
    all_debate_signals=None,
    debate_dicts=None,
    profit_take_pct=DEFAULT_PROFIT_TAKE_PCT,
    trailing_stop_pct=DEFAULT_TRAIL_STOP_PCT,
    principal_target=None,
    min_harvest_gain_pct=0.0,
    account_id="LEGACY",
    policy=None,
    contexts_by_ticker=None,
    sector_lookup=None,
    mode="consensus",
):
    state = _load_state(state_path)
    state["account_id"] = account_id
    state["mode"] = mode

    # Wantgot truth v2: fresh decision sink for this cycle. Every gate's
    # _log_block lands here; finalize reconciles it into cycle_intents.
    global _CYCLE_DECISION_SINK
    _CYCLE_DECISION_SINK = _cycle_decisions = []
    if mode == "wordsmith":
        # If the leaned-in router supplied these plans (operator directive,
        # June 16: the hotlist drives HARVEST_5's crypto rotation), the
        # router IS the authority for this book — skip the FABLEBOY_5-only
        # filter so the weighted crypto hotlist actually trades. Otherwise
        # keep the original headlines-only behavior.
        _router_driven = any(
            (isinstance(p, dict) and str(p.get("source", "")).startswith(
                "leaned_in_router"))
            for p in (plans or []))
        if _router_driven:
            print(f"[alpaca][{account_id}] WORDSMITH mode: leaned-in router "
                  f"drives this book — {len(plans or [])} hotlist plan(s), "
                  f"FABLEBOY_5 filter bypassed by operator directive")
            state["wordsmith"] = {
                "candidates": [], "router_driven": True,
                "note": ("leaned-in router supplies this book's plans; "
                         "all safety rails still apply")}
        else:
            # Prefer the full debate rows (per-agent verdicts). Fall back to
            # all_debate_signals ONLY if a caller passed the rows there (old
            # interface) — the filter itself rejects the dict shape loudly.
            _ws_rows = debate_dicts if debate_dicts is not None else all_debate_signals
            plans, _ws_kept = _wordsmith_filter(plans, _ws_rows)
            state["wordsmith"] = {"candidates": _ws_kept,
                                  "fed_debate_rows": (len(_ws_rows)
                                                      if isinstance(_ws_rows, list)
                                                      else 0),
                                  "note": ("headlines-only book: entries require a "
                                           "FABLEBOY_5 BUY/STRONG_BUY; all safety "
                                           "rails unchanged")}
            print(f"[alpaca][{account_id}] WORDSMITH mode: "
                  f"{len(_ws_kept)} word-approved candidate(s) this cycle")

    # ── Pre-cycle hygiene: clear stale unfilled orders so they aren't carried
    # into the open or doubled-up on. Guarded — can never break the cycle.
    _open_order_syms = set()  # symbols with a live open order this cycle
    try:
        _stale, _open_order_syms = cancel_stale_open_orders(
            state, max_age_min=120, crypto_max_age_min=15,
            error_log=state.setdefault("errors", []))
        if _stale:
            print(f"[alpaca] {account_id}: cancelled {len(_stale)} stale open order(s) "
                  f"({', '.join(s['symbol'] for s in _stale if s.get('symbol'))})")
    except Exception as _e:  # noqa: BLE001
        _open_order_syms = set()
        print(f"[alpaca] {account_id}: stale-order cleanup skipped — {_e}")

    # ── Market-hours gate: only submit NEW orders during the regular session,
    # when market orders actually fill. Off-hours we still do all bookkeeping,
    # sweeps and stale-order cleanup — we just don't fire orders that would sit
    # unfilled and loop. This is what stops the EOG/PLD-style canceled churn.
    global _DEFER_ORDER_SUBMIT
    _DEFER_ORDER_SUBMIT = not _market_is_regular_session()
    state["market_session_open"] = not _DEFER_ORDER_SUBMIT
    if _DEFER_ORDER_SUBMIT:
        print(f"[alpaca] {account_id}: market closed — order submission deferred "
              f"to regular hours (bookkeeping/sweeps still run)")

    if policy is None:
        try:
            from silmaril.portfolios.policy_router import load_policy as _load_pol
            policy = _load_pol(Path(state_path).parent)
        except Exception:
            policy = {}
    policy = policy or {}

    # ── Alpha 6.0: pull policy blocks ─────────────────────────────
    _pol_sizing = policy.get("sizing", {}) or {}
    _pol_close = policy.get("close_loop", {}) or {}
    _pol_sweep = policy.get("sweep", {}) or {}
    _pol_halt = bool(policy.get("halt_opens"))
    _pol_force_close = policy.get("force_close") or {}
    _pol_elite = set((policy.get("elite_tickers") or []))
    _pol_blocked = policy.get("blocked_tickers") or {}
    _pol_vulnerable = set(policy.get("vulnerable_tickers") or [])
    # Alpha 6.0 wiring:
    _pol_position_directives = policy.get("position_directives") or []
    _pol_forced_rotations = policy.get("forced_rotations") or []
    _pol_deployment_floor = (policy.get("deployment_floor") or {}).get(account_id, {})
    _pol_orchestrator = policy.get("orchestrator") or {}
    _pol_hard_stops = (policy.get("hard_stops") or {}).get(account_id, {})
    _pol_order_quality = policy.get("order_quality") or {}
    _pol_corr_blocked = set((policy.get("correlation_book") or {}).get("blocked") or [])
    _pol_corr_trim = set((policy.get("correlation_book") or {}).get("trim") or [])
    _pol_cohort_safe_mode = bool((policy.get("hard_stops") or {}).get("cohort_safe_mode"))

    _eff_trail_pct = float(trailing_stop_pct) * float(
        _pol_close.get("trail_tightness", 1.0))
    if _pol_hard_stops.get("tighten_trail"):
        _eff_trail_pct *= float(_pol_hard_stops["tighten_trail"])
    _eff_min_conviction = max(float(min_consensus_conviction),
                              float(_pol_sizing.get("min_conviction_floor", 0.0)))

    state["policy_applied"] = {
        "version": policy.get("version"),
        "market_mode": policy.get("market_mode"),
        "winner_engine": policy.get("winner_engine"),
        "halt_opens": _pol_halt,
        "effective_trail_pct": round(_eff_trail_pct, 4),
        "effective_min_conv": round(_eff_min_conviction, 4),
        "elite_tickers": sorted(_pol_elite),
        "force_close_targets": list(_pol_force_close.keys()),
        "blocked_count": len(_pol_blocked),
        "vulnerable_count": len(_pol_vulnerable),
        # 6.0
        "position_directives_count": len([d for d in _pol_position_directives
                                          if (d.get("owner") or "").upper() == account_id]),
        "forced_rotations_count": len([d for d in _pol_forced_rotations
                                       if (d.get("owner") or "").upper() == account_id]),
        "orch_objective": _pol_orchestrator.get("system_objective_today"),
        "deployment_floor_objective": _pol_deployment_floor.get("objective_today"),
        "max_sweep_today": _pol_deployment_floor.get("max_sweep_today"),
        "hard_stop_halt": bool(_pol_hard_stops.get("halt_opens")),
        "cohort_safe_mode": _pol_cohort_safe_mode,
    }

    cycle_errors = []
    headers = _get_headers()
    if not headers:
        state["enabled"] = False
        state["reason"] = "ALPACA_API_KEY/SECRET not set (or stripped to empty)"
        state.setdefault("errors", []).append({"time": _now_iso(),
                                               "msg": state["reason"]})
        state["errors"] = state["errors"][-20:]
        _save_state(state, state_path)
        return state

    account = _api_get(_ACCOUNT_ENDPOINT, headers, error_log=cycle_errors)
    if not account:
        state["enabled"] = False
        last_err = cycle_errors[-1]["msg"] if cycle_errors else "Account fetch returned None"
        state["reason"] = f"Account fetch failed: {last_err}"
        state.setdefault("errors", []).extend(cycle_errors)
        state["errors"] = state["errors"][-20:]
        _save_state(state, state_path)
        return state

    equity = float(account.get("equity", 0))
    cash_avail = float(account.get("cash", 0))
    state["enabled"] = True
    state["account"] = {"equity": round(equity, 2), "cash": round(cash_avail, 2)}

    if not state.get("genesis_at"):
        state["genesis_at"] = _now_iso()

    if principal_target is not None:
        state["principal_target"] = principal_target
    # SILMARIL baseline is ALWAYS $10,000 per account. Heal any legacy/unset/
    # $100k default to 10000 — never reset principal to current equity (that
    # would mask drawdown and hide real performance vs the fixed baseline).
    if not state.get("principal_target") or float(state["principal_target"]) == 100000:
        state["principal_target"] = 10000.0
    principal = float(state["principal_target"])

    trading_capital = min(equity, principal)
    realized_savings = max(0.0, equity - principal)
    state["trading_capital"] = round(trading_capital, 2)
    state["savings"] = round(realized_savings, 2)
    state["realized_savings"] = round(realized_savings, 2)

    print(f"[alpaca] {account_id} equity ${equity:,.2f} | "
          f"principal ${principal:,.2f} | trading_capital ${trading_capital:,.2f} | "
          f"savings ${realized_savings:,.2f} | cash ${cash_avail:,.2f}")
    if equity < 1.0:
        _save_state(state, state_path)
        return state

    # Build signal maps
    plan_signals, plan_conv, plan_class = {}, {}, {}
    for p in plans:
        t = p.get("ticker", "")
        if not t:
            continue
        plan_signals[t] = p.get("consensus_signal", "HOLD")
        plan_conv[t] = float(p.get("consensus_conviction") or p.get("avg_conviction") or 0)
        plan_class[t] = p.get("asset_class", "equity")
    exit_signals = dict(all_debate_signals or {})
    exit_signals.update(plan_signals)
    # CRYPTO SYMBOL BRIDGE (June 17 — fixes the rotation lock-up): the router
    # emits sells keyed as "DOT-USD", but Alpaca reports the held position as
    # "DOTUSD" (no dash). Without bridging, exit_signals.get("DOTUSD") misses
    # the "DOT-USD" SELL → the position-closer never fires → the account can't
    # sell losers → cash never frees → it can't buy the risers → TOTAL JAM.
    # Mirror every signal across both crypto symbologies so the held position
    # (whatever form Alpaca returns) finds its sell/buy signal.
    for _k, _v in list(exit_signals.items()):
        _ku = str(_k).upper()
        _nodash = _ku.replace("/", "").replace("-", "")
        if _nodash != _ku:
            exit_signals.setdefault(_nodash, _v)          # DOT-USD -> DOTUSD
        if _ku.endswith("-USD"):
            exit_signals.setdefault(_ku.replace("-USD", "USD"), _v)
        elif _ku.endswith("USD") and "-" not in _ku and len(_ku) > 3:
            exit_signals.setdefault(_ku[:-3] + "-USD", _v)  # DOTUSD -> DOT-USD

    existing = _api_get(_POSITIONS_ENDPOINT, headers, error_log=cycle_errors) or []
    if not isinstance(existing, list):
        existing = []
    print(f"[alpaca] {account_id} open positions: {len(existing)}")

    state["savings_vault"] = _extract_savings_vault(existing)
    vault_value = float(state["savings_vault"].get("total_market_value", 0) or 0)
    if vault_value > 0:
        trading_capital = max(0.0, min(equity - vault_value, principal))
        state["trading_capital"] = round(trading_capital, 2)
        cash_above_principal = max(0.0, (equity - vault_value) - principal)
        state["realized_savings"] = round(vault_value + cash_above_principal, 2)
        state["savings"] = state["realized_savings"]
        print(f"[alpaca] {account_id} vault ${vault_value:,.2f} verified | "
              f"trading_capital recalc ${trading_capital:,.2f}")

    position_meta = state.get("position_meta", {})
    tickers_traded = []
    orders_placed = []
    closed = 0
    cycle_harvest_intent = []

    # Persist a positions_snapshot for downstream sidecars (position_manager etc.)
    state["positions_snapshot"] = _build_positions_snapshot(existing, position_meta)

    # ── Alpha 6.0: directive consumption BEFORE the legacy close-loop ──
    directive_orders = []
    directive_touched_symbols = set()
    if _pol_position_directives:
        try:
            from .directive_consumer import consume_position_directives
            positions_snapshot = state["positions_snapshot"]
            directive_orders = consume_position_directives(
                positions_snapshot, _pol_position_directives,
                headers=headers, account_id=account_id,
                position_meta=position_meta,
                contract=_pol_deployment_floor,
                current_cash=cash_avail,
                error_log=cycle_errors,
            )
            for o in directive_orders:
                directive_touched_symbols.add(o.get("symbol"))
                if o.get("submitted") and o.get("action") in (
                        "PROFIT_LOCK", "MOMENTUM_DECAY"):
                    closed += 1
                if o.get("submitted"):
                    tickers_traded.append(o.get("symbol"))
            if directive_orders:
                print(f"[alpaca] {account_id} consumed "
                      f"{len(directive_orders)} position directives")
            orders_placed.extend(directive_orders)
        except Exception as _de:
            print(f"[alpaca] directive_consumer failed: {_de}")
            cycle_errors.append({"time": _now_iso(),
                                 "msg": f"directive_consumer: {_de}"})

    # ── Alpha 6.0: forced rotations ──────────────────────────────────
    rotation_orders = []
    if _pol_forced_rotations:
        try:
            from .directive_consumer import consume_forced_rotations
            positions_snapshot = _build_positions_snapshot(existing, position_meta)
            rotation_orders = consume_forced_rotations(
                positions_snapshot, _pol_forced_rotations, plans,
                headers=headers, account_id=account_id, error_log=cycle_errors,
            )
            for o in rotation_orders:
                directive_touched_symbols.add(o.get("symbol"))
                if o.get("submitted"):
                    closed += 1
                    tickers_traded.append(o.get("symbol"))
            if rotation_orders:
                print(f"[alpaca] {account_id} executed "
                      f"{len(rotation_orders)} forced rotations")
            orders_placed.extend(rotation_orders)
        except Exception as _re:
            print(f"[alpaca] forced_rotation consumer failed: {_re}")
            cycle_errors.append({"time": _now_iso(),
                                 "msg": f"forced_rotation: {_re}"})

    # Reload positions after directives/rotations
    if rotation_orders or directive_orders:
        time.sleep(1.5)
        existing2 = _api_get(_POSITIONS_ENDPOINT, headers,
                             error_log=cycle_errors) or []
        if isinstance(existing2, list):
            existing = existing2

    # ── Legacy close loop ────────────────────────────────────────────
    from .directive_consumer import (
        market_session_now, is_extended_session, build_order_payload,
    )
    _session = market_session_now()
    _is_ext = is_extended_session()

    for pos in existing:
        symbol = pos.get("symbol", "")
        try: qty = float(pos.get("qty", "0"))
        except Exception: qty = 0
        try: current_price = float(pos.get("current_price", 0))
        except Exception: current_price = 0
        try: entry_price = float(pos.get("avg_entry_price", 0))
        except Exception: entry_price = 0

        if not symbol or qty == 0:
            continue
        if symbol.upper() in _RESERVED_VAULT_SYMBOLS:
            continue
        if symbol in directive_touched_symbols:
            continue
        side = "long" if qty > 0 else "short"

        # Hardening: a dead/zero price must never drive an exit decision —
        # comparisons against 0 would fire trailing stops on every position.
        if current_price <= 0:
            state.setdefault("exit_checks_skipped", []).append({
                "symbol": symbol, "reason": "no usable price this cycle",
                "time": _now_iso()})
            continue

        meta = position_meta.get(symbol, {})
        prev_peak = meta.get("peak_price", entry_price or current_price)
        new_peak = max(prev_peak, current_price) if current_price else prev_peak
        prior_snaps = meta.get("snapshots_30m") or []
        position_meta[symbol] = {
            **meta,
            "entry_price": entry_price,
            "peak_price": new_peak,
            "first_seen": meta.get("first_seen", _now_iso()),
            "qty": abs(qty),
            "snapshots_30m": prior_snaps,
        }

        close_reason = None
        pnl_pct = 0.0
        if entry_price > 0 and current_price > 0:
            pnl_pct = (current_price / entry_price - 1.0) * 100
        peak_drop_pct = 0.0
        if new_peak > 0 and current_price > 0:
            peak_drop_pct = (current_price / new_peak - 1.0) * 100

        # ─────────────────────────────────────────────────────────────
        # EXIT LADDER — rewritten 2026-06-20 (Dash to 2.1). ONE sell brain.
        # The 10-min momentum chain is the source of truth for BOTH entry and
        # exit (operator's golden law). Fixed-% rules are now ONLY a fallback
        # for when the chain is blind (no fresh read this cycle).
        #
        # REMOVED this pass (superseded — see READ_ME), because they were the
        # mechanical cause of ~9% edge-capture / "win-rate with nothing to
        # show": every one of them banked or amputated a winner EARLY.
        #   • GROCERY HARVEST tiers — sold 50% of a position at +1.5%, more at
        #     +3%/+6%. On a +27% runner that captures ~3%. Profit-taking is now
        #     the MOMENTUM EXIT's job: ride the winner until ITS fast tape rolls.
        #   • _harvest_clock_gate / CLOCK HARVEST / clock-deferred-exit — old
        #     timing-fingerprint harvest, not part of the new philosophy.
        #   • fixed 5% PROFIT-TAKE fallback — superseded by the momentum exit.
        #   • tight 4% trailing stop as a PRIMARY exit — demoted to a
        #     chain-blind / catastrophe-only backstop so a healthy pullback no
        #     longer amputates a live winner ("sold too early").
        # Order (first match wins): policy -> momentum -> consensus ->
        #   (chain-blind only: tight trail + giveback) -> catastrophe stop ->
        #   break-even -> bleed.
        # ─────────────────────────────────────────────────────────────

        # 0. POLICY FORCE-CLOSE — hard override, always first.
        if not close_reason and symbol in _pol_force_close:
            fc = _pol_force_close[symbol] or {}
            close_reason = (f"POLICY FORCE-CLOSE ({fc.get('engine', 'policy')}): "
                            f"{fc.get('rationale', 'policy requires close')}")

        # 0.5 MEAN-REVERSION EXIT (Alpha 2.11) — PRIMARY for liquid crypto when
        #     MR mode is on. We bought the dip; now bank the bounce (+target),
        #     cut the falling knife (-hard stop, the only thing that kills a
        #     mean-reversion book), or time out if the bounce never came. Takes
        #     precedence over the momentum exit for these names. Fail-safe.
        if not close_reason and side == "long":
            try:
                from .mean_reversion import (MEAN_REVERSION_ENABLED,
                                             mean_reversion_exit, _base, LIQUID_NAMES)
                if (MEAN_REVERSION_ENABLED and _base(symbol) in LIQUID_NAMES
                        and entry_price > 0 and current_price > 0):
                    _fs = position_meta.get(symbol, {}).get("first_seen")
                    _hold = 0.0
                    if _fs:
                        try:
                            _hold = (datetime.now(timezone.utc)
                                     - datetime.fromisoformat(_fs)).total_seconds() / 60.0
                        except Exception:
                            _hold = 0.0
                    _do, _why = mean_reversion_exit(entry_price, current_price, _hold)
                    if _do:
                        close_reason = _why
            except Exception:
                pass

        # 1. MOMENTUM EXIT (PRIMARY — the buy-out brain). Reads the SAME
        #    momentum_chain the router ranks/sizes by, so entry and exit share
        #    one truth. Operator's rule: getting IN takes a small green tick;
        #    getting OUT takes OUR position turning, not a full reversal of the
        #    big weekly trend. Protects winners (exit only when the FAST tape
        #    turns hard AND the hour is red AND fire has collapsed — the run is
        #    genuinely over), cuts losers small. `_chain_available` records
        #    whether we actually had a fresh 10-min read to judge by; the
        #    fixed-% fallbacks below ONLY fire when we did NOT.
        _chain_available = False
        _slr = None
        _h1 = None
        _fire = 0.0
        _pos_pnl_pct = 0.0
        if entry_price > 0 and current_price > 0:
            _pos_pnl_pct = (current_price / entry_price - 1.0) * 100.0
        if not close_reason and side == "long":
            try:
                _mcp = Path(state_path).parent / "momentum_chain.json"
                _mc = (json.loads(_mcp.read_text()) if _mcp.exists() else {}).get("chains") or {}
                _su = str(symbol).upper()
                _c = (_mc.get(_su) or _mc.get(_su.replace("USD", "-USD"))
                      or _mc.get(_su[:-3] + "-USD" if _su.endswith("USD") else _su))
                if _c:
                    _w = _c.get("windows") or {}
                    _slr = _w.get("since_last")
                    _h1 = _w.get("h1")
                    _fire = float(_c.get("fire") or 0.0)
                    if _slr is not None:
                        _chain_available = True
                    _pos_pnl_pct = 0.0
                    if entry_price > 0 and current_price > 0:
                        _pos_pnl_pct = (current_price - entry_price) / entry_price * 100.0
                    if _pos_pnl_pct >= 0.5:
                        # protect a winner — only exit if the run is clearly dead
                        _roll = (_slr is not None and _slr <= -0.8) and \
                                (_h1 is not None and _h1 <= -0.3) and _fire < 0.35
                    elif _pos_pnl_pct <= -0.4:
                        # cut a loser before it grows (asymmetric easy-out)
                        _roll = (_slr is not None and _slr <= -0.4) and \
                                (_h1 is None or _h1 <= 0.0) and _fire < 0.5
                    else:
                        # near flat — exit only on a real fast-tape reversal
                        _roll = (_slr is not None and _slr <= -0.6) and \
                                (_h1 is None or _h1 <= 0.0) and _fire < 0.45
                    if _roll:
                        close_reason = (
                            f"MOMENTUM EXIT: {symbol} fast tape rolled over "
                            f"(pos {_pos_pnl_pct:+.1f}%, since-last "
                            f"{(_slr if _slr is not None else 0):+.2f}%, 1h "
                            f"{(_h1 if _h1 is not None else 0):+.2f}%, fire "
                            f"{_fire:.1f}) — banking/cutting, not churning on noise")
            except Exception:
                pass

        # 2. CONSENSUS FLIP — bearish consensus closes the long, BUT the
        #    operator's golden law is "exit when OUR position turns, not on a
        #    broad reversal signal." A STRONG_SELL consensus must NOT dump a
        #    position whose OWN fast tape is still green and in profit — that
        #    broad-signal dump is exactly what sent #2/#3 to cash all at once
        #    and then into the drawdown halt. So a still-green winner is left to
        #    the momentum exit (it sells when ITS tape actually rolls); a fading
        #    or losing position still honors the consensus sell.
        if not close_reason:
            sig = exit_signals.get(symbol, "HOLD")
            _tape_still_green = (_chain_available and _slr is not None
                                 and _slr >= 0.0 and _fire >= 0.4)
            _protected_winner = _tape_still_green and _pos_pnl_pct >= 0.5
            if side == "long" and sig in ("SELL", "STRONG_SELL"):
                if _protected_winner:
                    state.setdefault("consensus_holds", []).append({
                        "symbol": symbol, "sig": sig,
                        "note": (f"held through {sig}: own tape still green "
                                 f"(since-last {(_slr or 0):+.2f}%, fire "
                                 f"{_fire:.1f}, pos {_pos_pnl_pct:+.1f}%)"),
                        "time": _now_iso()})
                    state["consensus_holds"] = state["consensus_holds"][-50:]
                else:
                    close_reason = f"Consensus turned bearish: {sig}"
            elif side == "short" and sig in ("BUY", "STRONG_BUY"):
                close_reason = f"Consensus turned bullish on short: {sig}"

        # 3. CHAIN-BLIND FALLBACK — tight trail + giveback ONLY when we had no
        #    fresh 10-min read this cycle. With a live chain we TRUST the
        #    momentum exit above and do not let a fixed-% rule amputate a
        #    healthy pullback (that was a major "sold too early" leak). The
        #    giveback trigger is also widened (was +1.2% peak / 40% faded, which
        #    banked +0.4% off a +1.2% peak — itself early) to a real backstop.
        _be_stop = bool(position_meta.get(symbol, {}).get("stop_at_break_even"))
        _tight_pct = position_meta.get(symbol, {}).get("tightened_stop_pct")
        if not close_reason and not _chain_available and side == "long" \
           and new_peak > 0:
            _eff_pct = _eff_trail_pct
            if _tight_pct:
                _eff_pct = min(_eff_pct, float(_tight_pct))
            if current_price <= new_peak * (1.0 - _eff_pct):
                close_reason = (f"TRAILING STOP (chain-blind): {symbol} "
                                f"-{abs(peak_drop_pct):.2f}% from peak "
                                f"${new_peak:.2f} (eff {_eff_pct*100:.2f}%)")
            else:
                _pk_pnl = (new_peak / entry_price - 1.0) * 100.0 if entry_price > 0 else 0.0
                if _pk_pnl >= 3.0 and 0.2 < pnl_pct <= 0.5 * _pk_pnl:
                    close_reason = (f"GIVEBACK GUARD (chain-blind): {symbol} was "
                                    f"+{_pk_pnl:.2f}% at peak, faded to "
                                    f"+{pnl_pct:.2f}% with no fresh read — "
                                    f"banking the rest")

        # 4. CATASTROPHE STOP — disaster backstop that survives EVEN with a live
        #    chain: a collapse too fast for the 10-min read to catch. Wide on
        #    purpose so it never fires on a normal pullback.
        if not close_reason and side == "long" and new_peak > 0 \
           and current_price <= new_peak * (1.0 - CATASTROPHE_DROP_PCT):
            close_reason = (f"CATASTROPHE STOP: {symbol} "
                            f"-{abs(peak_drop_pct):.2f}% from peak ${new_peak:.2f} "
                            f"(> {CATASTROPHE_DROP_PCT*100:.0f}% collapse)")

        # 5. BREAK-EVEN STOP — risk-free exit once armed.
        if not close_reason and _be_stop and side == "long" \
           and entry_price > 0 and current_price <= entry_price * 0.999:
            close_reason = (f"BREAK_EVEN_STOP: {symbol} returned to entry "
                            f"${entry_price:.2f}; risk-free exit")

        # 6. BLEED EXIT — slow-bleed detection (unchanged).
        if not close_reason and side == "long":
            try:
                from silmaril.portfolios.bleed_exit import check_position_for_bleed
                bleed_fired, bleed_reason, bleed_components = check_position_for_bleed(
                    position_meta, symbol, current_price,
                    data_dir=Path(state_path).parent)
                if bleed_fired:
                    close_reason = bleed_reason
                    state.setdefault("bleed_exits_this_cycle", []).append({
                        "symbol": symbol, "reason": bleed_reason,
                        "components": bleed_components, "time": _now_iso(),
                    })
            except Exception as _be_e:
                print(f"[alpaca][bleed] check failed for {symbol}: {_be_e}")

        if close_reason:
            print(f"[alpaca] CLOSE {side} {symbol}: {close_reason}")
            close_side = "sell" if side == "long" else "buy"
            # CRYPTO CLOSE FIX (June 17): a held crypto position reports as
            # "DOTUSD" (no dash). build_order_payload only recognizes crypto
            # by the -USD/​/USD form, so without converting, a crypto CLOSE
            # was built as an equity order and then DEFERRED by the market-
            # closed gate — leaving the account unable to sell crypto losers
            # off-hours (the rotation lock-up). Detect a crypto position via
            # its asset_class tag (or the USD suffix) and hand the dashed
            # form so it submits 24/7 as a market gtc order.
            _close_sym = symbol
            _ac = (position_meta.get(symbol, {}) or {}).get("asset_class", "")
            _su = str(symbol).upper()
            _looks_crypto = (_ac == "crypto") or _su.endswith("-USD") or "/" in _su or (
                _su.endswith("USD") and len(_su) > 3
                and account_id in _VALUABLES_ACCOUNTS)
            if _looks_crypto and _su.endswith("USD") and "-" not in _su and "/" not in _su:
                _close_sym = _su[:-3] + "-USD"   # DOTUSD -> DOT-USD
            payload = build_order_payload(
                symbol=_close_sym, side=close_side, qty=abs(qty),
                current_price=current_price,
            )
            if payload is None:
                print(f"[alpaca]   → close deferred (session/price)")
                continue
            r = _api_post(_ORDERS_ENDPOINT, headers, payload,
                          error_log=cycle_errors)
            if r:
                closed += 1
                tickers_traded.append(symbol)
                # RE-ENTRY COOLDOWN stamp (Dash 2.1): record WHEN we closed this
                # name so the buy path won't immediately re-open it. Keyed
                # canonically so XTZ-USD / XTZUSD / XTZ/USD all match.
                _ck = str(symbol).upper().replace("/", "").replace("-", "")
                state.setdefault("recent_exits", {})[_ck] = _now_iso()
                if side == "long":
                    realized = (current_price - entry_price) * abs(qty)
                else:
                    realized = (entry_price - current_price) * abs(qty)
                if realized > 0:
                    state["savings"] = float(state.get("savings", 0)) + realized
                    state["lifetime_realized_wins"] = state.get(
                        "lifetime_realized_wins", 0) + 1
                    print(f"[alpaca]   → +${realized:.2f} harvested")
                    cycle_harvest_intent.append({
                        "source_ticker": symbol,
                        "realized_cash": round(realized, 4),
                        "close_order_id": r.get("id"),
                        "close_filled_at": _now_iso(),
                        "trigger_reason": close_reason,
                    })
                else:
                    state["lifetime_realized_losses"] = state.get(
                        "lifetime_realized_losses", 0) + 1
                    print(f"[alpaca]   → ${realized:.2f} loss")
                orders_placed.append({
                    "action": "CLOSE", "symbol": symbol, "side": close_side,
                    "qty": abs(qty), "trigger_reason": close_reason,
                    "realized_pnl": round(realized, 2),
                    "entry_price": entry_price, "exit_price": current_price,
                    "order_id": r.get("id"), "time": _now_iso(),
                    "timestamp": _now_iso(),
                    "session": _session, "is_extended": _is_ext,
                })
                position_meta.pop(symbol, None)

    if closed > 0:
        time.sleep(1.5)
        existing = _api_get(_POSITIONS_ENDPOINT, headers,
                            error_log=cycle_errors) or []
        if not isinstance(existing, list):
            existing = []

    # ── SGOV harvest sweep with HARD enforcement of max_sweep_today ──
    sgov_buy_result = {"attempted": False}
    if cycle_harvest_intent:
        try:
            from silmaril.portfolios import verified_harvest as _vh
            from .directive_consumer import compute_enforced_sweep_cap
        except Exception:
            _vh = None
            compute_enforced_sweep_cap = None

        total_cash_to_sweep = round(
            sum(float(h.get("realized_cash") or 0) for h in cycle_harvest_intent), 4)
        SGOV_MIN_SWEEP = 25.00   # Alpha 0.007: below this, cash rolls
                                  # forward — no more micro-dust vault buys

        try:
            _acct_now = _api_get(_ACCOUNT_ENDPOINT, headers,
                                 error_log=cycle_errors)
            _cash_now = float(_acct_now.get("cash", 0)) if _acct_now else cash_avail
        except Exception:
            _cash_now = cash_avail

        original_sweep = total_cash_to_sweep
        cap_reason = None
        if compute_enforced_sweep_cap is not None:
            allowed, cap_reason = compute_enforced_sweep_cap(
                intent_cash=total_cash_to_sweep,
                contract=_pol_deployment_floor,
                current_cash=_cash_now,
                cash_reserve=1.00,
            )
            total_cash_to_sweep = round(allowed, 4)
        else:
            _principal_floor = float(state.get("principal_target", principal))
            max_sweepable = max(0.0, _cash_now - _principal_floor - 1.00)
            total_cash_to_sweep = min(total_cash_to_sweep, max_sweepable)

        if total_cash_to_sweep < original_sweep - 0.01:
            state["sgov_sweep_cap_applied"] = {
                "time": _now_iso(),
                "intended": round(original_sweep, 2),
                "actual": round(total_cash_to_sweep, 2),
                "trimmed": round(original_sweep - total_cash_to_sweep, 2),
                "cash_at_check": round(_cash_now, 2),
                "reason": cap_reason or "",
                "contract_max": _pol_deployment_floor.get("max_sweep_today"),
            }
            print(f"[alpaca][sgov] CAP: intent ${original_sweep:.2f} → "
                  f"${total_cash_to_sweep:.2f} ({cap_reason})")
            try:
                from silmaril.portfolios.explainability import log_decision
                log_decision(Path(state_path).parent,
                             category="sgov_sweep_cap_enforced",
                             ticker="SGOV", reason=cap_reason or "cap enforced",
                             account_id=account_id,
                             detail=state["sgov_sweep_cap_applied"])
            except Exception:
                pass

        intent_row_ids = []
        if _vh:
            data_dir = Path(state_path).parent
            for h in cycle_harvest_intent:
                try:
                    row = _vh.record_intent(
                        data_dir=data_dir, account_id=account_id,
                        amount=h["realized_cash"],
                        source_tickers=[h.get("source_ticker", "")],
                        agent_attribution=[],
                        notes=(f"close {h.get('source_ticker')} "
                               f"+${h['realized_cash']:.2f}"))
                    intent_row_ids.append(row["id"])
                    _vh.transition(data_dir, row["id"], "SELL_FILLED",
                                   sell_order_id=h.get("close_order_id"),
                                   sell_filled_at=h.get("close_filled_at"))
                except Exception as _e:
                    print(f"[alpaca][sgov] intent log failed: {_e}")

        if total_cash_to_sweep < SGOV_MIN_SWEEP:
            print(f"[alpaca][sgov] sweep ${total_cash_to_sweep:.2f} < "
                  f"${SGOV_MIN_SWEEP:.2f} — rolling forward")
            sgov_buy_result = {"attempted": False,
                               "reason": f"below min sweep ${SGOV_MIN_SWEEP:.2f}",
                               "cash_pending": total_cash_to_sweep}
            if _vh:
                for rid in intent_row_ids:
                    try:
                        _vh.transition(Path(state_path).parent, rid, "FAILED",
                                       failure_reason="below min sweep threshold")
                    except Exception:
                        pass
        else:
            sgov_buy_result["attempted"] = True
            print(f"[alpaca][sgov] sweeping ${total_cash_to_sweep:.2f} into SGOV")
            sgov_payload = build_order_payload(
                symbol="SGOV", side="buy",
                notional=round(total_cash_to_sweep, 2),
                current_price=100.0,
            )
            sgov_order = _api_post(_ORDERS_ENDPOINT, headers, sgov_payload,
                                   error_log=cycle_errors)
            if sgov_order:
                sgov_buy_result.update({
                    "order_id": sgov_order.get("id"),
                    "submitted_at": _now_iso(),
                    "notional": total_cash_to_sweep,
                    "status": "queued",
                })
                orders_placed.append({
                    "action": "SGOV_SWEEP", "symbol": "SGOV", "side": "buy",
                    "notional": total_cash_to_sweep,
                    "trigger_reason": (f"Verified harvest sweep · "
                                       f"{len(cycle_harvest_intent)} winners"),
                    "order_id": sgov_order.get("id"),
                    "time": _now_iso(), "timestamp": _now_iso(),
                })
                tickers_traded.append("SGOV")
                if _vh:
                    for rid in intent_row_ids:
                        try:
                            _vh.transition(Path(state_path).parent, rid,
                                           "SGOV_QUEUED",
                                           sgov_order_id=sgov_order.get("id"),
                                           sgov_queued_at=_now_iso())
                        except Exception:
                            pass
            else:
                sgov_buy_result.update({
                    "status": "rejected",
                    "reason": (cycle_errors[-1]["msg"] if cycle_errors
                               else "unknown"),
                })
                if _vh:
                    for rid in intent_row_ids:
                        try:
                            _vh.transition(Path(state_path).parent, rid, "FAILED",
                                           failure_reason=sgov_buy_result["reason"])
                        except Exception:
                            pass

        state["sgov_sweep_last_cycle"] = sgov_buy_result
        state["sgov_intent_row_ids"] = state.get("sgov_intent_row_ids", []) + intent_row_ids
        state["sgov_intent_row_ids"] = state["sgov_intent_row_ids"][-200:]

    if cycle_harvest_intent and sgov_buy_result.get("status") == "queued":
        time.sleep(2.0)
        positions_after_sgov = _api_get(_POSITIONS_ENDPOINT, headers,
                                        error_log=cycle_errors) or []
        if isinstance(positions_after_sgov, list):
            state["savings_vault"] = _extract_savings_vault(positions_after_sgov)
            sgov_held = any(
                (p.get("symbol") or "").upper() == "SGOV"
                and float(p.get("qty", 0) or 0) > 0
                for p in positions_after_sgov
            )
            if sgov_held and intent_row_ids:
                try:
                    from silmaril.portfolios import verified_harvest as _vh2
                    data_dir = Path(state_path).parent
                    for rid in intent_row_ids:
                        _vh2.transition(data_dir, rid, "SGOV_FILLED",
                                        sgov_filled_at=_now_iso())
                        _vh2.transition(data_dir, rid, "VERIFIED",
                                        verified_at=_now_iso())
                except Exception as _ve:
                    print(f"[alpaca][sgov] verify failed: {_ve}")

    # ── REDEPLOY from SGOV when contract demands it ─────────────────
    from .directive_consumer import must_redeploy_from_sgov
    _need_redeploy, _redeploy_amount = must_redeploy_from_sgov(_pol_deployment_floor)
    if _need_redeploy and vault_value > 0:
        sgov_pos = next((p for p in (existing or [])
                         if (p.get("symbol") or "").upper() == "SGOV"), None)
        if sgov_pos:
            try:
                sgov_qty = float(sgov_pos.get("qty") or 0)
                sgov_px = float(sgov_pos.get("current_price") or 0)
                if sgov_qty > 0 and sgov_px > 0:
                    redeploy_qty = min(sgov_qty, _redeploy_amount / sgov_px)
                    redeploy_qty = round(redeploy_qty, 4)
                    if redeploy_qty * sgov_px >= 5.0:
                        payload = build_order_payload(
                            symbol="SGOV", side="sell", qty=redeploy_qty,
                            current_price=sgov_px,
                        )
                        if payload:
                            r = _api_post(_ORDERS_ENDPOINT, headers, payload,
                                          error_log=cycle_errors)
                            if r:
                                print(f"[alpaca] {account_id} REDEPLOY_FROM_SGOV "
                                      f"sold {redeploy_qty} SGOV "
                                      f"(~${redeploy_qty * sgov_px:.2f})")
                                orders_placed.append({
                                    "action": "REDEPLOY_FROM_SGOV",
                                    "symbol": "SGOV", "side": "sell",
                                    "qty": redeploy_qty,
                                    "notional": round(redeploy_qty * sgov_px, 2),
                                    "trigger_reason": (
                                        f"deployment_floor demands redeploy: "
                                        f"equity below base by ${_redeploy_amount:.2f}"),
                                    "order_id": r.get("id"),
                                    "time": _now_iso(),
                                    "timestamp": _now_iso(),
                                })
                                tickers_traded.append("SGOV")
            except Exception as _re:
                print(f"[alpaca] SGOV redeploy failed: {_re}")
                cycle_errors.append({"time": _now_iso(),
                                     "msg": f"SGOV redeploy: {_re}"})

    open_symbols = {p.get("symbol") for p in existing}
    open_count = len(existing)
    opened = 0

    # ── composite halt (Dash 2.1 DEADLOCK FIX) ──────────────────────────────
    # A pure DRAWDOWN halt used to set plans_to_iterate = [] and block ALL
    # opens. But once the book is in cash, equity is static, so it can never
    # rebound the +1.5%/+2.5% needed to UN-halt — the engine deadlocks in cash
    # for the rest of the day. That is exactly what stopped #2/#3 after the
    # consensus sell-off: down -3.3%, halted, flat in cash, permanently stuck.
    # For a 24/7 paper RESEARCH engine whose orchestrator objective is literally
    # RECOVER_FROM_DRAWDOWN, a permanent stop is the wrong tool. So we split it:
    #   • CATASTROPHE (cohort -4% safe-mode, or an explicit policy kill-switch)
    #     -> FULL block. Systemic; hands-off.
    #   • DRAWDOWN-ONLY (this account's own daily/weekly hard-stop) -> RECOVERY
    #     MODE: keep trading, but ONLY a few of the strongest fresh-GREEN names
    #     (recovery probes), so the account can move and rebound and the halt
    #     can actually lift. The fresh gate guarantees we never probe a falling
    #     name; the probe cap bounds the exposure.
    _catastrophe_halt = bool(_pol_halt) or bool(_pol_cohort_safe_mode)
    _drawdown_halt = (bool(_pol_hard_stops.get("halt_opens"))
                      and not _catastrophe_halt)
    composite_halt = _catastrophe_halt   # only a catastrophe fully blocks opens
    _recovery_mode = _drawdown_halt
    RECOVERY_PROBE_CAP = 3

    if composite_halt:
        halt_reasons = list(policy.get("halt_opens_reasons") or [])
        if _pol_cohort_safe_mode:
            halt_reasons.append("cohort_safe_mode")
        _log_block(state_path, "*", "blocked_composite_halt",
                   "Halt: " + "; ".join(halt_reasons),
                   account_id, halt_reasons=halt_reasons)
        print(f"[alpaca] {account_id} OPEN halted ({len(halt_reasons)} reasons)")
        plans_to_iterate = []
    else:
        _urgency_order = policy.get("urgency_priority_order") or []
        if _urgency_order:
            _by_ticker = {(p.get("ticker") or "").upper(): p for p in plans}
            _ordered = []
            _seen = set()
            for t in _urgency_order:
                if t in _by_ticker and t not in _seen:
                    _ordered.append(_by_ticker[t])
                    _seen.add(t)
            for p in plans:
                t = (p.get("ticker") or "").upper()
                if t and t not in _seen:
                    _ordered.append(p)
                    _seen.add(t)
            plans_to_iterate = _ordered
        else:
            plans_to_iterate = plans

        if _recovery_mode:
            # Drawdown recovery: keep ONLY the strongest fresh-green probes so
            # the account can attempt a rebound (and thereby lift its own halt)
            # instead of sitting dead in cash. Never probes a falling name.
            try:
                from .fresh_gate import _chain_entry_for
                _mcp_rm = Path(state_path).parent / "momentum_chain.json"
                _rchain = ((json.loads(_mcp_rm.read_text()).get("chains") or {})
                           if _mcp_rm.exists() else {})

                def _probe_strength(p):
                    ce = _chain_entry_for(_rchain, (p.get("ticker") or ""))
                    if not ce:
                        return -1.0
                    slr = (ce.get("windows") or {}).get("since_last")
                    if slr is None or slr < 0.10:   # must be solidly rising NOW
                        return -1.0
                    return float(ce.get("fire") or 0.0) + float(slr)

                _ranked = sorted(plans_to_iterate, key=_probe_strength,
                                 reverse=True)
                _ranked = [p for p in _ranked
                           if _probe_strength(p) > 0][:RECOVERY_PROBE_CAP]
                _hb = _pol_hard_stops.get("rationale", "")
                _log_block(state_path, "*", "recovery_mode_probe",
                           f"drawdown halt ({_hb}) — probing "
                           f"{len(_ranked)} strongest fresh-green name(s) to "
                           f"attempt rebound instead of deadlocking in cash",
                           account_id)
                print(f"[alpaca] {account_id} RECOVERY MODE: {len(_ranked)} "
                      f"probe(s) (drawdown halt, not a full stop)")
                plans_to_iterate = _ranked
            except Exception as _rm_e:
                print(f"[alpaca] recovery-mode filter failed, holding: {_rm_e}")
                plans_to_iterate = []

    # CRYPTO SECTORING (June 16 fix): crypto has no equity sector, so every
    # coin collapses into "Unknown" and trips the max-per-sector / max-sector-
    # book-pct concentration caps — which silently blocks NEW crypto buys once
    # ~3 are held, even with cash free. For the valuables account, give each
    # crypto its OWN sector (its ticker) so coins don't pile into one bucket.
    # The concentration code expects a DICT (ticker -> sector), so we build a
    # dict covering every held + planned crypto name. Equities keep their real
    # sector lookup untouched.
    _sector_lookup = sector_lookup
    if account_id in _VALUABLES_ACCOUNTS:
        _merged = dict(sector_lookup) if isinstance(sector_lookup, dict) else {}
        _names = set()
        for _p in (existing or []):
            _names.add(str(_p.get("symbol") or _p.get("ticker") or "").upper())
        for _p in (plans or []):
            _names.add(str(_p.get("ticker") or "").upper())
        for _n in _names:
            if _n and (_n.endswith("-USD") or _n.endswith("USD") or "/" in _n):
                # cover both symbologies: router uses BTC-USD, Alpaca
                # positions report BTCUSD. Key both to the same sector.
                _base = _n.replace("/", "").replace("-", "")
                _merged[_n] = f"crypto:{_base}"
                _merged[_base] = f"crypto:{_base}"
                if _base.endswith("USD") and len(_base) > 3:
                    _merged[_base[:-3] + "-USD"] = f"crypto:{_base}"
        _sector_lookup = _merged

    try:
        from silmaril.portfolios.correlation_control import (
            build_concentration_snapshot as _build_conc,
            can_open as _can_open,
        )
        concentration_snapshot = _build_conc(
            existing, sector_lookup=_sector_lookup,
            trading_capital=trading_capital,
        )
    except Exception as _ce:
        concentration_snapshot = {"sectors": {}, "asset_classes": {},
                                  "trading_capital": trading_capital}
        _can_open = None
        print(f"[alpaca] concentration snapshot failed: {_ce}")

    # Alpha 6.0 pre-OPEN guards
    from .directive_consumer import can_open_position

    for p in plans_to_iterate:
        ticker = p.get("ticker", "")
        signal = p.get("consensus_signal", "HOLD")
        conviction = plan_conv.get(ticker, 0.0)
        asset_class = plan_class.get(ticker, "equity")
        if not ticker:
            continue
        if signal not in ("BUY", "STRONG_BUY"):
            _log_block(state_path, ticker, "blocked_signal_not_buy",
                       f"signal {signal} is not BUY/STRONG_BUY",
                       account_id, signal=signal, conviction=conviction)
            continue
        # FRESH-WINDOW ENTRY GATE (Dash 2.1, belt-and-suspenders). The router
        # already drops falling names, but ANY buy path that reaches here must
        # also obey the rule: never open a name that is dropping on the freshest
        # 10-min read, no matter how strong its daily/weekly windows are. This
        # is what stops nosedive entries (XTZ/XRP/BONK bought while falling).
        try:
            from .fresh_gate import passes_fresh_entry_gate, _chain_entry_for
            _fg_chain = (json.loads((Path(state_path).parent /
                         "momentum_chain.json").read_text()).get("chains") or {}) \
                        if (Path(state_path).parent / "momentum_chain.json").exists() else {}
            _fg_ok, _fg_reason, _fg_detail = passes_fresh_entry_gate(
                _chain_entry_for(_fg_chain, ticker))
            if not _fg_ok:
                _log_block(state_path, ticker, "blocked_fresh_gate",
                           _fg_reason, account_id, **_fg_detail)
                continue
        except Exception as _fg_e:
            print(f"[alpaca][fresh-gate] check skipped for {ticker}: {_fg_e}")
        # RE-ENTRY COOLDOWN (Dash 2.1): refuse to re-open a name we closed within
        # the cooldown window. THIS is the fix for the same-coin churn the
        # operator watched — buy XTZ, sell XTZ, re-buy XTZ next run, lose again.
        try:
            _ck = ticker.upper().replace("/", "").replace("-", "")
            _last_exit = (state.get("recent_exits") or {}).get(_ck)
            if _last_exit:
                _mins = (datetime.now(timezone.utc)
                         - datetime.fromisoformat(_last_exit)).total_seconds() / 60.0
                if 0 <= _mins < REENTRY_COOLDOWN_MIN:
                    _log_block(state_path, ticker, "blocked_reentry_cooldown",
                               f"closed {_mins:.0f} min ago; {REENTRY_COOLDOWN_MIN:.0f}-min "
                               f"cooldown — not re-buying what we just sold",
                               account_id, minutes_since_exit=round(_mins, 1))
                    continue
        except Exception as _cd_e:
            print(f"[alpaca][cooldown] check skipped for {ticker}: {_cd_e}")
        if conviction < _eff_min_conviction:
            _log_block(state_path, ticker, "blocked_low_conviction",
                       f"conviction {conviction:.2f} < floor "
                       f"{_eff_min_conviction:.2f}",
                       account_id, conviction=conviction)
            continue
        if ticker.upper() in _pol_blocked:
            _log_block(state_path, ticker, "blocked_by_policy",
                       f"policy: {_pol_blocked[ticker.upper()]}", account_id)
            continue
        if ticker.upper() in _pol_corr_blocked:
            _log_block(state_path, ticker, "blocked_correlation_book",
                       "correlation cluster HIGH severity", account_id)
            continue
        if ticker in open_symbols:
            _log_block(state_path, ticker, "blocked_already_held",
                       f"{ticker} already held", account_id)
            continue
        # DUPLICATE-ORDER GUARD (June 17): if this name already has a live
        # UNFILLED order working at the broker, don't stack another one on
        # top — that's what produced the pile of un-filled LDO orders. Wait
        # for the working order to fill or get cancelled by the stale sweep.
        _tk_norm = str(ticker).upper().replace("/", "").replace("-", "")
        if (str(ticker).upper() in _open_order_syms
                or _tk_norm in _open_order_syms
                or (_tk_norm + "").replace("USD", "/USD") in _open_order_syms):
            _log_block(state_path, ticker, "blocked_order_already_open",
                       f"{ticker} already has a working unfilled order — "
                       f"not stacking a duplicate", account_id)
            continue
        if asset_class in _SKIP_ASSET_CLASSES and not (
                asset_class == "crypto"
                and account_id in _VALUABLES_ACCOUNTS):
            # crypto/token are skippable EVERYWHERE except the valuables
            # account (HARVEST_5), which is built to trade them (June 16).
            _log_block(state_path, ticker, "blocked_asset_class",
                       f"{asset_class} not tradeable in {account_id}",
                       account_id)
            continue
        # MISSION GATE (account-aware, June 16): stocks tradeable in every
        # account; crypto/-USD tradeable ONLY in the valuables account
        # (HARVEST_5). The two stock books remain strictly equity-only.
        # asset_class defaults to "equity" for unknown names, so this
        # structural check is the belt-and-suspenders guarantee.
        if not _can_hold_asset(ticker, account_id):
            _log_block(state_path, ticker, "blocked_not_equity_mission",
                       f"{ticker} not permitted in {account_id} — crypto "
                       f"trades only in the valuables account, stocks "
                       f"trade in the equity accounts",
                       account_id)
            continue
        if ticker.upper() in _RESERVED_VAULT_SYMBOLS:
            _log_block(state_path, ticker, "blocked_vault_reserved",
                       f"{ticker} reserved vault", account_id)
            continue
        if open_count >= max_total_positions:
            _log_block(state_path, ticker, "blocked_position_cap",
                       f"max_total_positions={max_total_positions}",
                       account_id)
            break

        # Alpha 0.007: conviction decides the dollars. Plan score (0..2)
        # scales the base slice — score 2.0 -> 1.35x, ~1.07 -> 1.0x,
        # 0 -> 0.6x. Caps and cash gates still rule above this.
        try:
            _sc = float((p.get("score") if isinstance(p, dict)
                         else getattr(p, "score", 0)) or 0)
        except Exception:
            _sc = 0.0
        _conv_mult = max(0.6, min(1.35, 0.6 + 0.375 * _sc))
        proposed_notional = trading_capital * max_position_pct * _conv_mult
        ok_open, reason_open = can_open_position(
            account, _pol_deployment_floor,
            proposed_notional=proposed_notional)
        if not ok_open:
            _log_block(state_path, ticker, "blocked_negative_cash",
                       reason_open, account_id, cash=cash_avail)
            continue

        if _can_open is not None:
            _ok, _reason, _detail = _can_open(
                ticker, concentration=concentration_snapshot,
                proposed_notional=proposed_notional,
                sector_lookup=_sector_lookup,
                limits=(_pol_sizing.get("concentration_limits") or {}),
            )
            if not _ok:
                _log_block(state_path, ticker, "blocked_concentration",
                           f"correlation_control: {_reason}",
                           account_id, **_detail)
                continue

        # Order quality consultation
        oq_row = (_pol_order_quality.get("tickers") or {}).get(ticker.upper())
        if oq_row and oq_row.get("defer_to_next_cycle"):
            _log_block(state_path, ticker, "deferred_order_quality",
                       oq_row.get("rationale", "deferred by order quality"),
                       account_id)
            continue
        use_limit = bool(oq_row and oq_row.get("use_limit_order"))
        limit_bps = int((oq_row or {}).get("limit_buffer_bps", 30))

        # Dynamic sizing
        try:
            from silmaril.portfolios.dynamic_sizer import size_position as _size_pos
            _urgency_card = (policy.get("urgency_by_ticker") or {}).get(ticker.upper())
            _ctx = (contexts_by_ticker or {}).get(ticker.upper())
            _atr = getattr(_ctx, "atr_14", None) if _ctx is not None else None
            _price = getattr(_ctx, "price", None) if _ctx is not None else None
            _sector = sector_lookup.get(ticker.upper()) if sector_lookup else "Unknown"
            _sec_pct = (concentration_snapshot.get("sectors", {}).get(_sector)
                        or {}).get("pct", 0.0)
            _max_sec_pct = float((_pol_sizing.get("concentration_limits") or {})
                                  .get("max_sector_book_pct", 0.30))
            _size_result = _size_pos(
                ticker=ticker, plan=p, trading_capital=trading_capital,
                base_max_position_pct=max_position_pct,
                market_state_knobs=_pol_sizing,
                urgency=_urgency_card,
                elite_tickers=list(_pol_elite),
                sector_pct=float(_sec_pct), max_sector_pct=_max_sec_pct,
                atr_14=_atr, current_price=_price,
                available_cash=trading_capital,
            )
            notional = _size_result["notional"]
            is_elite = _size_result["elite"]
            sizing_rationale = _size_result["rationale"]
        except Exception as _se:
            print(f"[alpaca] dynamic sizing failed for {ticker}: {_se}")
            notional = round(trading_capital * max_position_pct, 2)
            is_elite = ticker.upper() in _pol_elite
            sizing_rationale = "legacy fallback"

        if notional < 1.0:
            _log_block(state_path, ticker, "blocked_notional_too_small",
                       f"notional ${notional:.2f} < $1", account_id,
                       notional=notional)
            continue

        # Build payload — session-aware + order-quality-aware
        cur_px = getattr((contexts_by_ticker or {}).get(ticker.upper(), None),
                          "price", None) or 0.0
        # CRYPTO 24/7 GUARD (June 18 — THE fix for orders stuck pending_new):
        # crypto has NO pre-market/extended session. The stock clock was
        # marking crypto buys as "pre-market"/extended, routing them through
        # the extended path (qty-market with no fill) → stuck pending_new
        # forever, money never spent. Crypto must ALWAYS be a plain notional
        # market order regardless of the stock-market clock.
        _tk_u = str(ticker).upper()
        _is_crypto_buy = (_tk_u.endswith("-USD") or _tk_u.endswith("USDT")
                          or "/" in _tk_u
                          or (_tk_u.endswith("USD") and len(_tk_u) > 4
                              and account_id in _VALUABLES_ACCOUNTS))
        if _is_crypto_buy:
            payload = build_order_payload(
                symbol=ticker, side="buy",
                notional=notional, current_price=cur_px or None,
            )
        elif use_limit or _is_ext:
            # Use limit; need a price.
            if cur_px and cur_px > 0:
                qty_calc = notional / float(cur_px)
                payload = build_order_payload(
                    symbol=ticker, side="buy", qty=qty_calc,
                    current_price=cur_px,
                    limit_buffer_bps=limit_bps,
                    force_extended=_is_ext,
                )
            else:
                # No price — fall back to notional market during regular session
                payload = build_order_payload(
                    symbol=ticker, side="buy",
                    notional=notional, current_price=None,
                )
        else:
            payload = build_order_payload(
                symbol=ticker, side="buy",
                notional=notional, current_price=cur_px or None,
            )

        if payload is None:
            _log_block(state_path, ticker, "blocked_no_session_match",
                       "no usable session for order", account_id)
            continue

        _tag = "ELITE " if is_elite else ""
        print(f"[alpaca] OPEN {_tag}{signal} {ticker} ${notional:.2f} "
              f"(c={conviction:.2f}) — {sizing_rationale}")
        _n_err_before = len(cycle_errors)
        r = _api_post(_ORDERS_ENDPOINT, headers, payload,
                      error_log=cycle_errors)
        if r:
            opened += 1
            open_count += 1
            open_symbols.add(ticker)
            tickers_traded.append(ticker)
            orders_placed.append({
                "action": ("OPEN_ELITE" if is_elite else "OPEN"),
                "symbol": ticker, "side": "buy",
                "notional": notional, "conviction": conviction,
                "signal": signal, "order_id": r.get("id"),
                # Capture Alpaca's actual response so the log reflects reality,
                # not just the attempt. (Market fills settle async, so this is
                # usually 'accepted'/'new' at submit; positions_snapshot is the
                # source of truth for what actually filled and is held.)
                "status": r.get("status"),
                "order_type": r.get("type"),
                "submitted_qty": r.get("qty"),
                "filled_qty": r.get("filled_qty"),
                "filled_avg_price": r.get("filled_avg_price"),
                "limit_price": r.get("limit_price"),
                "elite": is_elite, "use_limit": use_limit,
                "limit_buffer_bps": limit_bps if use_limit else None,
                "session": _session, "is_extended": _is_ext,
                "sizing_rationale": sizing_rationale,
                "synthetic_from_rotation": p.get("from_rotation"),
                "submitted_at": r.get("submitted_at") or _now_iso(),
                "time": _now_iso(), "timestamp": _now_iso(),
            })
        else:
            # Truth in labeling: _api_post returns None BOTH for real broker
            # rejections (which append to cycle_errors) AND for its internal
            # market-closed submit-defer gate (which does not). Calling the
            # latter "Alpaca rejected" hid days of silent deferrals.
            if len(cycle_errors) > _n_err_before:
                _log_block(state_path, ticker, "blocked_alpaca_rejected",
                           "Alpaca rejected OPEN", account_id,
                           last_error=cycle_errors[-1])
            else:
                _log_block(state_path, ticker, "deferred_submit_market_closed",
                           "submission deferred by market-closed gate "
                           "(will retry during regular hours)", account_id)

    # Open shorts (only when no halt active)
    if enable_shorts and not composite_halt:
        for p in plans_to_iterate:
            ticker = p.get("ticker", "")
            signal = p.get("consensus_signal", "HOLD")
            conviction = plan_conv.get(ticker, 0.0)
            asset_class = plan_class.get(ticker, "equity")
            if signal not in ("SELL", "STRONG_SELL"):
                _log_block(state_path, ticker, "blocked_signal_not_sell",
                           f"signal {signal} is not SELL/STRONG_SELL",
                           account_id, signal=signal, conviction=conviction)
                continue
            if conviction < _eff_min_conviction:
                _log_block(state_path, ticker, "blocked_low_conviction",
                           f"short conviction {conviction:.2f} < floor "
                           f"{_eff_min_conviction:.2f}", account_id)
                continue
            if ticker in open_symbols:
                _log_block(state_path, ticker, "blocked_already_held",
                           f"{ticker} already held", account_id)
                continue
            if asset_class in _SKIP_ASSET_CLASSES:
                _log_block(state_path, ticker, "blocked_asset_class",
                           f"short asset_class {asset_class} not tradeable",
                           account_id)
                continue
            if not _is_equity_mission(ticker):
                _log_block(state_path, ticker, "blocked_not_equity_mission",
                           f"short {ticker}: not a traditional equity",
                           account_id)
                continue
            if ticker.upper() in _RESERVED_VAULT_SYMBOLS:
                continue
            if open_count >= max_total_positions:
                break

            proposed_notional = trading_capital * max_position_pct
            ok_open, reason_open = can_open_position(
                account, _pol_deployment_floor,
                proposed_notional=proposed_notional)
            if not ok_open:
                _log_block(state_path, ticker, "blocked_negative_cash",
                           reason_open, account_id)
                continue

            notional = round(trading_capital * max_position_pct, 2)
            if notional < 1.0:
                continue

            cur_px = getattr((contexts_by_ticker or {}).get(ticker.upper(), None),
                              "price", None) or 0.0
            payload = build_order_payload(
                symbol=ticker, side="sell",
                notional=notional if not _is_ext else None,
                qty=(notional / cur_px) if (_is_ext and cur_px > 0) else None,
                current_price=cur_px or None,
            )
            if payload is None:
                continue

            print(f"[alpaca] SHORT {ticker} ${notional:.2f}")
            r = _api_post(_ORDERS_ENDPOINT, headers, payload,
                          error_log=cycle_errors)
            if r:
                opened += 1
                open_count += 1
                open_symbols.add(ticker)
                tickers_traded.append(ticker)
                orders_placed.append({
                    "action": "SHORT", "symbol": ticker, "side": "sell",
                    "notional": notional, "conviction": conviction,
                    "signal": signal, "order_id": r.get("id"),
                    "session": _session, "is_extended": _is_ext,
                    "time": _now_iso(), "timestamp": _now_iso(),
                })

    # ── Finalize ────────────────────────────────────────────────────
    state["orders"] = state.get("orders", []) + orders_placed
    state["orders_placed"] = orders_placed
    state["position_meta"] = position_meta
    state["tickers_traded_this_cycle"] = list(set(tickers_traded))
    if cycle_errors:
        state.setdefault("errors", []).extend(cycle_errors)
        state["errors"] = state["errors"][-20:]
    _prune_recent_tickers(state)

    # Refresh positions_snapshot after all trades for downstream sidecars,
    # and SYNC position_meta to the broker's actual holdings. position_meta is
    # only ever pruned on the sell path (position_meta.pop), so positions closed
    # any OTHER way (manual flatten, off-path close, prior-schema leftovers)
    # lingered as phantom memos — dashboards read positions_snapshot (correct)
    # but the memo dict drifted (e.g. 43/48/3 entries vs real 1/4/0 holdings),
    # and the phantom names also polluted the exit/short evaluation logs. We
    # prune meta to the symbols the broker actually returns, but ONLY when the
    # positions fetch clearly succeeded (no new error appended this call), so a
    # transient API failure can never wipe the memos for genuinely-held names.
    try:
        _err_before = len(cycle_errors)
        post_positions = _api_get(_POSITIONS_ENDPOINT, headers,
                                   error_log=cycle_errors) or []
        _fetch_ok = (len(cycle_errors) == _err_before)
        if isinstance(post_positions, list):
            state["positions_snapshot"] = _build_positions_snapshot(
                post_positions, position_meta)
            if _fetch_ok:
                _held = {str(p.get("symbol") or "").upper()
                         for p in post_positions if isinstance(p, dict)}
                _held.discard("")
                _before_n = len(position_meta)
                position_meta = {k: v for k, v in position_meta.items()
                                 if str(k).upper() in _held}
                state["position_meta"] = position_meta
                _pruned_n = _before_n - len(position_meta)
                if _pruned_n:
                    state["meta_pruned_last_cycle"] = {
                        "count": _pruned_n,
                        "at": _now_iso(),
                        "held": sorted(_held),
                    }
                    print(f"[alpaca] {account_id} synced position_meta to broker: "
                          f"pruned {_pruned_n} phantom memo(s); {len(_held)} held")
    except Exception:
        pass

    # POST-TRADE BALANCE REFRESH (June 18): the account balance was captured
    # at the START of the cycle (pre-trade), but positions_snapshot is
    # refreshed at the END — so the dashboard showed cash≈equity while also
    # listing positions (the books didn't add up). Re-fetch the balance now so
    # cash/equity reflect what was actually spent and match the holdings.
    try:
        _acct2 = _api_get(_ACCOUNT_ENDPOINT, headers, error_log=None)
        if isinstance(_acct2, dict) and _acct2.get("equity") is not None:
            _eq2 = float(_acct2.get("equity") or 0)
            _csh2 = float(_acct2.get("cash") or 0)
            if _eq2 > 0:
                state["account"] = {"equity": round(_eq2, 2),
                                    "cash": round(_csh2, 2)}
                equity = _eq2
    except Exception:
        pass

    # ORDER-STATUS RECONCILIATION (June 18 — fixes stale 'pending_new' in the
    # dashboard): orders were recorded at SUBMIT time with their initial status
    # ('pending_new'/'accepted') and never updated, so the order sheet looked
    # like nothing ever filled even when it did. Re-fetch the recent orders
    # from Alpaca and patch the saved statuses to their REAL current value
    # (filled/canceled/etc.), keyed by order_id. Read-only; never places.
    try:
        _recent = _api_get(f"{_BASE_URL}/v2/orders?status=all&limit=200&direction=desc",
                           headers, error_log=None)
        if isinstance(_recent, list) and _recent:
            _by_id = {str(o.get("id")): o for o in _recent if o.get("id")}
            _patched = 0
            for _o in state.get("orders", []):
                _oid = str(_o.get("order_id") or "")
                _live = _by_id.get(_oid)
                if _live:
                    _ns = _live.get("status")
                    if _ns and _ns != _o.get("status"):
                        _o["status"] = _ns
                        _patched += 1
                    if _live.get("filled_qty") is not None:
                        _o["filled_qty"] = _live.get("filled_qty")
                    if _live.get("filled_avg_price") is not None:
                        _o["filled_avg_price"] = _live.get("filled_avg_price")
            if _patched:
                state["orders_reconciled"] = {"at": _now_iso(), "patched": _patched}
    except Exception:
        pass

    total_value = equity + state.get("savings", 0)
    _bleed_exits = state.get("bleed_exits_this_cycle", []) or []
    _sgov_cap = state.get("sgov_sweep_cap_applied")
    state["last_cycle_summary"] = {
        "time": _now_iso(), "timestamp": _now_iso(),
        "closed": closed, "opened": opened,
        "open_after": open_count, "equity": equity,
        "savings": round(state.get("savings", 0), 2),
        "total_value": round(total_value, 2),
        "tickers_traded": list(set(tickers_traded)),
        "bleed_exits_count": len(_bleed_exits),
        "bleed_exits": _bleed_exits[-5:],
        "sgov_sweep_cap_applied": bool(_sgov_cap),
        "sgov_sweep_cap_detail": _sgov_cap if _sgov_cap else None,
        # Alpha 6.0
        "directives_consumed": len(directive_orders),
        "rotations_executed": len(rotation_orders),
        "composite_halt": composite_halt,
        "session": _session,
        "is_extended": _is_ext,
    }
    state["bleed_exits_this_cycle"] = []

    # ── Wantgot truth v2: record THIS cycle's intent ledger ─────────
    # Intended = every BUY/STRONG_BUY plan the book received this cycle
    # (for the wordsmith book, plans are already the word-engine's own
    # list — including originated entries — so intent means exactly what
    # the book WANTED). Each intent resolves to submitted (with the exact
    # notional + broker status) or to the FIRST gate that stopped it.
    # The wantgot analytics joins this against fills and held positions.
    try:
        _first_block = {}
        _non_entry = {"blocked_signal_not_buy", "harvest_below_fee_floor",
                      "blocked_vault_reserved"}
        for _drow in _cycle_decisions:
            _t = _drow.get("ticker") or ""
            if (_t and _t != "*" and _t not in _first_block
                    and _drow.get("category") not in _non_entry):
                _first_block[_t] = _drow
        _halt_row = next((d for d in _cycle_decisions
                          if d.get("ticker") == "*"), None)
        _submitted = {}
        for _o in orders_placed:
            if str(_o.get("action", "")).startswith(("OPEN", "SHORT")):
                _submitted[str(_o.get("symbol") or "").upper()] = _o
        _intents = []
        for _p in (plans_to_iterate or []):
            _t = str((_p.get("ticker") if isinstance(_p, dict) else "")
                     or "").upper()
            _sig = (_p.get("consensus_signal") or _p.get("signal") or "HOLD"
                    ) if isinstance(_p, dict) else "HOLD"
            if not _t or _sig not in ("BUY", "STRONG_BUY"):
                continue
            _row = {"ticker": _t, "signal": _sig,
                    "conviction": round(float(
                        plan_conv.get(_t)
                        or (_p.get("conviction") if isinstance(_p, dict) else 0)
                        or 0.0), 4),
                    "originated": (_p.get("source") == "WORDSMITH-ORIGINATED"
                                   if isinstance(_p, dict) else False)}
            _ord = _submitted.get(_t)
            if _ord:
                _row.update({
                    "outcome": "submitted",
                    "intended_notional": _ord.get("notional"),
                    "order_id": _ord.get("order_id"),
                    "order_status": _ord.get("status"),
                    "filled_qty": _ord.get("filled_qty"),
                })
            else:
                _blk = _first_block.get(_t)
                _row.update({
                    "outcome": (_blk or {}).get("category", "not_reached"),
                    "intended_notional": round(
                        trading_capital * max_position_pct, 2),
                    "reason": (_blk or {}).get(
                        "reason", "loop ended before this name "
                        "(position cap or halt)"),
                })
            _intents.append(_row)
        state["cycle_intents"] = {
            "at": _now_iso(),
            "session": _session,
            "session_open": not _DEFER_ORDER_SUBMIT,
            "composite_halt": composite_halt,
            "halt_reason": (_halt_row or {}).get("reason"),
            "plans_offered": len(plans_to_iterate or []),
            "buy_intents": _intents,
            "decisions_this_cycle": _cycle_decisions[-200:],
        }
    except Exception as _wge:  # never break a cycle for bookkeeping
        print(f"[alpaca] {account_id}: cycle_intents capture failed — {_wge}")
    finally:
        _CYCLE_DECISION_SINK = None

    _save_state(state, state_path)
    print(f"[alpaca] {account_id} cycle: closed={closed} opened={opened} "
          f"directives={len(directive_orders)} rotations={len(rotation_orders)} "
          f"session={_session} | savings ${state.get('savings', 0):.2f} | "
          f"total ${total_value:.2f}")
    return state
