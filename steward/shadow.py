"""steward.shadow — hypotheses on trial. Graded daily, funded never.

Three registered shadows, each with its origin, sample size, pass mark and kill
criterion frozen in config.py BEFORE forward data:

  NEWSFADE  — the one honest lead the old system produced (bullish headlines ->
              negative 3-bar return), found IN-SAMPLE at t=-2.51, so it owes the
              data-mining debt: it must replicate out-of-sample at t <= -3.0 over
              n >= 400 non-overlapping flags before anyone believes it.
  FORM4     — insider filing activity (a COUNT PROXY, stated plainly) -> positive
              21-bar excess vs SPY. Externally motivated, so the bar is t >= +2.5.
  CONGRESS  — registered and INACTIVE: the hypothesis predates the data on purpose.

A shadow that passes earns a re-registration conversation. A shadow that hits its
kill is closed in writing. Neither ever places a trade from here.
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Dict, List, Optional

from . import prices as P
from .config import (NEWS_BEAR, NEWS_BULL, REGISTERED, SHADOW_FILE,
                     all_universe_symbols)
from .util import ledger_append, now_iso, read_json, write_json_atomic


def _fresh_state() -> Dict:
    return {
        "newsfade": {"open": [], "graded": []},
        "form4": {"open": [], "graded": []},
        "congress": {"status": "REGISTERED_INACTIVE",
                     "spec": REGISTERED["shadows"]["congress"]},
    }


def load(data_dir: Path) -> Dict:
    return read_json(Path(data_dir) / SHADOW_FILE, None) or _fresh_state()


def save(data_dir: Path, st: Dict) -> None:
    st["generated_at"] = now_iso()
    write_json_atomic(Path(data_dir) / SHADOW_FILE, st)


# ── shared grading math ───────────────────────────────────────────────────────────

def t_stat(vals: List[float]) -> Optional[float]:
    n = len(vals)
    if n < 3:
        return None
    m = sum(vals) / n
    var = sum((v - m) ** 2 for v in vals) / n
    sd = math.sqrt(var)
    return m / (sd / math.sqrt(n)) if sd > 1e-12 else None


def verdict(vals: List[float], spec: Dict, direction: int) -> Dict:
    """direction: -1 means the claim predicts NEGATIVE returns, +1 positive."""
    t = t_stat(vals)
    n = len(vals)
    need_n = 400 if direction < 0 else 200
    out = {"n": n, "need_n": need_n,
           "mean_pct": round(sum(vals) / n * 100, 3) if n else None,
           "t": round(t, 2) if t is not None else None,
           "status": "COLLECTING"}
    if t is None or n < need_n:
        return out
    if direction < 0:
        if t <= -3.0:
            out["status"] = "PASSED"
        elif t >= -1.0:
            out["status"] = "KILLED"
    else:
        if t >= 2.5:
            out["status"] = "PASSED"
        elif t <= 0.5:
            out["status"] = "KILLED"
    return out


# ── NEWSFADE ──────────────────────────────────────────────────────────────────────

def _score_titles(titles: List[str]) -> int:
    score = 0
    for t in titles:
        words = set(str(t).lower().replace("-", " ").replace(",", " ").split())
        bull = bool(words & NEWS_BULL)
        bear = bool(words & NEWS_BEAR)
        score += (1 if bull else 0) - (1 if bear else 0)
    return score


def _fetch_titles(sym: str) -> List[str]:
    try:
        import yfinance as yf
        items = yf.Ticker(sym).news or []
        return [i.get("title") or (i.get("content") or {}).get("title", "")
                for i in items][:20]
    except Exception:
        return []


def run_newsfade(st: Dict, store: Dict, data_dir: Path) -> None:
    sh = st["newsfade"]
    # grade any open flag whose 3rd forward bar now exists
    still = []
    for f in sh["open"]:
        bar = P.bars_after(store, f["sym"], f["flag_bar"], 3)
        if bar is None:
            still.append(f)
            continue
        fwd = bar[1] / f["base_px"] - 1.0
        sh["graded"].append({"sym": f["sym"], "flag_bar": f["flag_bar"],
                             "fwd3": round(fwd, 6)})
        ledger_append(data_dir, "shadow", "NEWSFADE_GRADED",
                      {"sym": f["sym"], "flag_bar": f["flag_bar"],
                       "fwd3_pct": round(fwd * 100, 3)})
    sh["open"] = still
    # raise new flags — one open flag per symbol keeps windows non-overlapping
    open_syms = {f["sym"] for f in sh["open"]}
    for sym in all_universe_symbols():
        if sym in open_syms:
            continue
        lb = P.latest_bar(store, sym)
        if not lb:
            continue
        score = _score_titles(_fetch_titles(sym))
        if score >= 2:
            sh["open"].append({"sym": sym, "flag_bar": lb[0], "base_px": lb[1],
                               "news_score": score, "opened": now_iso()})
            ledger_append(data_dir, "shadow", "NEWSFADE_FLAG",
                          {"sym": sym, "bar": lb[0], "score": score})


# ── FORM4 (ported filing-count proxy — see steward/form4.py) ─────────────────────

def run_form4(st: Dict, store: Dict, data_dir: Path) -> None:
    from .form4 import get_insider_buy_score
    sh = st["form4"]
    still = []
    for f in sh["open"]:
        bar = P.bars_after(store, f["sym"], f["flag_bar"], 21)
        spy = P.bars_after(store, "SPY", f["flag_bar"], 21)
        if bar is None or spy is None:
            still.append(f)
            continue
        spy_base = P.close_on_or_before(store, "SPY", f["flag_bar"])
        if not spy_base:
            continue
        excess = (bar[1] / f["base_px"] - 1.0) - (spy[1] / spy_base - 1.0)
        sh["graded"].append({"sym": f["sym"], "flag_bar": f["flag_bar"],
                             "excess21": round(excess, 6)})
        ledger_append(data_dir, "shadow", "FORM4_GRADED",
                      {"sym": f["sym"], "excess21_pct": round(excess * 100, 3)})
    sh["open"] = still
    open_syms = {f["sym"] for f in sh["open"]}
    for sym in REGISTERED["shadows"]["form4"]["watchlist"]:
        if sym in open_syms:
            continue
        lb = P.latest_bar(store, sym)
        if not lb:
            continue
        score = get_insider_buy_score(sym)
        if score >= 1.5:
            sh["open"].append({"sym": sym, "flag_bar": lb[0], "base_px": lb[1],
                               "insider_score": score, "opened": now_iso()})
            ledger_append(data_dir, "shadow", "FORM4_FLAG",
                          {"sym": sym, "bar": lb[0], "score": score})


# ── the daily pass ────────────────────────────────────────────────────────────────

def run_all(store: Dict, data_dir: Path, fetch_news: bool = True) -> Dict:
    st = load(data_dir)
    if fetch_news:
        try:
            run_newsfade(st, store, data_dir)
        except Exception as e:
            ledger_append(data_dir, "shadow", "NEWSFADE_ERROR", {"err": str(e)[:200]})
        try:
            run_form4(st, store, data_dir)
        except Exception as e:
            ledger_append(data_dir, "shadow", "FORM4_ERROR", {"err": str(e)[:200]})
    st["summary"] = {
        "newsfade": verdict([g["fwd3"] for g in st["newsfade"]["graded"]],
                            REGISTERED["shadows"]["newsfade"], direction=-1),
        "form4": verdict([g["excess21"] for g in st["form4"]["graded"]],
                         REGISTERED["shadows"]["form4"], direction=+1),
        "congress": {"status": "REGISTERED_INACTIVE"},
    }
    save(data_dir, st)
    return st
