"""silmaril.execution.edge_surface — 7.0 THE CELL TABLE (where the edge actually lives).

Direction is never 90/10; CONDITIONAL EXPECTANCY can be. Every closed trade lands in
a cell — class × entry-regime × fit-state — and each cell carries n, win Wilson-lo,
mean net, and a t-CI on expectancy. Only a cell whose CI_lower > 0 is a proven room.

mode 'observe' (default): publish + stamp; the entry gate stands down honestly.
SELF-ARMING (a 7.0 ACTIVATION checkmark): the moment ≥1 cell reaches min_cell_n with
CI_lower > 0, this module flips its own knob to 'gate' — evidence promotes itself,
no code change, and the flip is written down. Emits EDGE_SURFACE.json.
"""
from __future__ import annotations
import json, math, statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from .atomic_io import write_json_atomic


def _load(out: Path, name: str, default=None):
    try:
        return json.loads((out / name).read_text())
    except Exception:
        return default if default is not None else {}


def _wilson_lo(k, n, z=1.96):
    if n <= 0:
        return None
    ph = k / n
    den = 1 + z * z / n
    return max(0.0, (ph + z * z / (2 * n) - z * math.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n))) / den)


def build_edge_surface(out_dir) -> Dict[str, Any]:
    out = Path(out_dir)
    cat = _load(out, "PARAM_CATALOG.json")
    kb = cat.get("edge_surface") or {}
    min_n = int(kb.get("min_cell_n", 20))
    cells: Dict[str, List[float]] = {}
    for bk in ("crypto", "stock", "metal", "energy", "aggressive"):
        buys = {}
        for t in (_load(out, f"paper_book_{bk}.json").get("trades") or []):
            if t.get("side") == "BUY":
                buys[t.get("sym")] = t
                continue
            if t.get("side") != "SELL":
                continue
            b0 = buys.get(t.get("sym")) or {}
            reg = (b0.get("regime") or b0.get("entry_regime") or "NA")
            fit = "FIT" if (b0.get("fit") or t.get("fit")) else "VOL"
            key = f"{bk}|{reg}|{fit}"
            cells.setdefault(key, []).append(float(t.get("realized_pct") or 0.0))
    rows = []
    armed_candidates = 0
    for key, nets in sorted(cells.items()):
        n = len(nets)
        wins = sum(1 for x in nets if x > 0)
        mean = statistics.fmean(nets)
        sd = statistics.pstdev(nets) if n > 1 else 0.0
        half = 1.96 * sd / math.sqrt(n) if n > 1 else None
        ci_lo = (mean - half) if half is not None else None
        proven = (n >= min_n and ci_lo is not None and ci_lo > 0)
        if proven:
            armed_candidates += 1
        rows.append({"cell": key, "n": n, "win_wilson_lo": _wilson_lo(wins, n),
                     "mean_net_pct": round(mean, 3),
                     "ci_lower_pct": round(ci_lo, 3) if ci_lo is not None else None,
                     "status": ("PROVEN" if proven else
                                ("NEGATIVE" if (ci_lo is not None and n >= min_n) else "OBSERVING"))})
    # ── SELF-ARMING: evidence promotes itself (the activation checkmark) ──────
    flipped = False
    if str(kb.get("mode", "observe")) == "observe" and armed_candidates >= 1:
        try:
            cat["edge_surface"]["mode"] = "gate"
            cat["edge_surface"]["_armed_at"] = datetime.now(timezone.utc).isoformat()
            (out / "PARAM_CATALOG.json").write_text(json.dumps(cat, indent=1))
            flipped = True
        except Exception:
            pass
    payload = {"generated_at": datetime.now(timezone.utc).isoformat(),
               "mode": ("gate" if (flipped or kb.get("mode") == "gate") else "observe"),
               "min_cell_n": min_n, "cells": rows,
               "proven_cells": armed_candidates, "self_armed_this_cycle": flipped,
               "what": ("conditional expectancy with confidence intervals — the only place a "
                        "90/10 honestly exists. Self-arms to 'gate' on the first PROVEN cell; "
                        "the flip is a data event, not a code change (7.0 activation).")}
    write_json_atomic(out / "EDGE_SURFACE.json", payload)
    return {"summary": f"edge surface: {len(rows)} cells · proven {armed_candidates} · mode "
                       f"{payload['mode']}" + (" · SELF-ARMED ⚡" if flipped else "")}
