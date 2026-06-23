"""
silmaril.execution.tradability — self-correcting Alpaca asset registry.

THE BUG THIS FIXES: the expanded crypto universe included coins that exist on
CoinGecko/Coinbase but Alpaca does NOT list (WLD, DYDX, GALA, JTO, SAND, MANA,
AXS, ...). The chain ranked them #1 (genuinely on fire), the router booked
them, the executor submitted them — and Alpaca returned HTTP 422 "asset not
found". The order failed, the cash sat idle, and only the few on-fire coins
Alpaca actually supports (AAVE, SOL) filled. That is exactly why it "only
buys SOL/AAVE while MANA etc. are ignored."

Rather than hardcode a list that drifts as Alpaca adds/removes pairs, this is
SELF-CORRECTING (the reviewer's philosophy): when a symbol returns 422
"not found", we record it here permanently. The router then skips any
blocklisted symbol BEFORE booking it, so capital flows only to names Alpaca
can actually trade. The list adapts automatically to whatever Alpaca supports.

Persisted to docs/data/untradeable_assets.json.
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Set

FILE_NAME = "untradeable_assets.json"


def _now():
    return datetime.now(timezone.utc).isoformat()


def _norm(sym: str) -> str:
    """Normalize to a canonical key (strip slash/dash, upper)."""
    return str(sym).upper().replace("/", "").replace("-", "")


def _path(out_dir) -> Path:
    return Path(out_dir) / FILE_NAME


def load_blocklist(out_dir) -> Set[str]:
    """Return the set of normalized symbols Alpaca has rejected as not found."""
    try:
        data = json.loads(_path(out_dir).read_text())
        return set(data.get("untradeable", []))
    except Exception:
        return set()


def is_blocked(out_dir, symbol: str) -> bool:
    return _norm(symbol) in load_blocklist(out_dir)


def record_untradeable(out_dir, symbol: str, reason: str = "asset not found") -> None:
    """Add a symbol to the persistent blocklist (idempotent)."""
    out = Path(out_dir)
    p = _path(out)
    try:
        data = json.loads(p.read_text())
    except Exception:
        data = {"untradeable": [], "detail": {}}
    if "untradeable" not in data:
        data["untradeable"] = []
    if "detail" not in data:
        data["detail"] = {}
    key = _norm(symbol)
    if key not in data["untradeable"]:
        data["untradeable"].append(key)
        data["detail"][key] = {"symbol": symbol, "reason": reason,
                               "first_seen": _now()}
        data["updated_at"] = _now()
        # atomic write
        fd, tmp = tempfile.mkstemp(dir=str(out), suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(data, f, separators=(",", ":"))
            os.replace(tmp, str(p))
        finally:
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    pass
        print(f"[tradability] {symbol} marked UNTRADEABLE on Alpaca "
              f"({reason}); will be skipped going forward")


# Module-level pointer so _api_post (which doesn't know out_dir) can record.
# cli/executor sets this once per run.
_ACTIVE_OUT_DIR = None


def set_active_out_dir(out_dir) -> None:
    global _ACTIVE_OUT_DIR
    _ACTIVE_OUT_DIR = out_dir


def record_if_not_found(symbol: str, http_status: int, body: str) -> None:
    """Called from the order POST path: if Alpaca says 422/not found OR
    422/not active, learn it so the router stops re-submitting it every cycle.

    Alpaca returns two distinct 422s for symbols we can't trade:
      • 42210000 "asset ... not found"      (never on Alpaca)
      • 40010001 "asset ... is not active"  (listed but not tradable for us)
    Both mean the order will NEVER fill, so both must be learned — otherwise
    'not active' coins (MKR, TRX, ALGO ...) get re-picked every cycle, waste the
    open budget, and can starve recovery-mode probes so the book never fills.
    """
    if _ACTIVE_OUT_DIR is None:
        return
    b = (body or "").lower()
    if http_status == 422 and (
        "not found" in b or "not_found" in b or "42210000" in b
        or "not tradable" in b or "not tradeable" in b
        or "not active" in b or "not_active" in b or "40010001" in b
    ):
        _reason = ("alpaca 422 not active" if ("not active" in b or "40010001" in b)
                   else "alpaca 422 not found")
        record_untradeable(_ACTIVE_OUT_DIR, symbol, _reason)
