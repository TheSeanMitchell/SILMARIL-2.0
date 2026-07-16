"""silmaril.execution.venues — 5.3 THE VENUE LAYER (M2).

Real fees, real listings, real constraints — the live-handoff foundation.
DECLARED, never inferred: the fee schedule below is typed in from published
schedules; the noise-floor proxy is DEMOTED to a capped slippage term.

  cost = venue_fee(round-trip) + measured_spread + capped_slippage

Emits VENUE_REALITY.json every cycle:
  · per-venue listing coverage of OUR crypto universe
  · realized-P&L attribution on names the target venues do NOT list
    ("of $X realized, $Y was earned on names you cannot trade") — the
    Universe Truth Test that decides whether history means anything.
  · UNIVERSE GAPS: venue-listed names we are not yet tracking (fed to the
    roster via EXTRA_TICKERS.json so max-capture is real, not aspirational).

Listings ship SEEDED and are refreshed by fetch_listings() on GitHub Actions
(public endpoints, no keys). The 90-day live lock is untouched; this layer
makes the paper economics match the venue you will actually trade.
"""
from __future__ import annotations
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .atomic_io import write_json_atomic

# ── DECLARED FEE SCHEDULES (bps per SIDE unless noted) — typed from published docs ──
VENUES: Dict[str, Dict[str, Any]] = {
    "binanceus": {"label": "Binance.US", "taker_bps": 10.0, "maker_bps": 10.0,
                  "min_notional_usd": 1.0, "note": "0.10% spot flat (Tier 0)"},
    "coinbase":  {"label": "Coinbase One", "taker_bps": 0.0, "maker_bps": 0.0,
                  "min_notional_usd": 1.0, "spread_pad_bps": 15.0,
                  "note": "One subscription: $0 trading fee; spread applies"},
    "robinhood": {"label": "Robinhood Crypto", "taker_bps": 0.0, "maker_bps": 0.0,
                  "min_notional_usd": 1.0, "spread_pad_bps": 25.0,
                  "note": "commission-free; revenue via spread"},
}

# ── SEED LISTINGS (USD pairs) — refreshed live by fetch_listings() on Actions ──
_SEED_BINANCEUS = [
 "BTC","ETH","SOL","XRP","ADA","DOGE","AVAX","LINK","DOT","MATIC","POL","LTC","BCH","UNI","ATOM","ETC",
 "XLM","NEAR","APT","ARB","OP","FIL","ICP","HBAR","VET","ALGO","AAVE","MKR","GRT","SAND","MANA","AXS",
 "EGLD","THETA","XTZ","EOS","FLOW","CHZ","CRV","ENJ","ZIL","1INCH","COMP","SNX","SUSHI","YFI","BAND",
 "KNC","STORJ","ZRX","BAT","REN","LRC","OMG","ANKR","CTSI","SKL","OGN","NKN","IOTX","ONE","ONT","QTUM",
 "ICX","ZEN","DASH","ZEC","WAVES","KAVA","RVN","SC","DGB","HNT","AR","STX","RNDR","RENDER","INJ","SUI",
 "SEI","TIA","JTO","PYTH","JUP","WIF","BONK","PEPE","SHIB","FLOKI","GALA","IMX","APE","LDO","ORCA","RAY",
 "FET","OCEAN","AGIX","ROSE","CELO","MINA","KSM","GLMR","ASTR","ACA","SPELL","DYDX","GMX","BLUR","ENS",
 "MASK","TRB","API3","UMA","BADGER","RARE","AUDIO","HIGH","GTC","POLYX","ILV","YGG","GHST","ALICE","TLM",
 "SLP","C98","DAR","VOXEL","MAGIC","PRIME","BEAM","RON","PIXEL","PORTAL","ACE","NFP","AI","XAI","MANTA",
 "ALT","DYM","STRK","ONDO","ETHFI","ENA","W","TNSR","SAGA","TAO","OM","ZRO","ZK","IO","NOT","TON","ATA",
]
_SEED_COINBASE = _SEED_BINANCEUS + [
 "ADAUP" if False else "AERO","WELL","MORPHO","EIGEN","CBETH","MSOL","JITOSOL","OSMO","AKT","QNT","XCN",
 "AMP","ACH","AGLD","ALEPH","AERGO","ASM","AST","ATH","AURORA","AXL","BICO","BIT","BOBA","BTRST","CGLD",
 "CLV","COVAL","CRO","CTX","CVC","DESO","DIA","DNT","DREP","ELA","ERN","FARM","FIDA","FORT","FORTH","FOX",
 "FX","GAL","GFI","GLM","GNO","GODS","GST","GUSD","HFT","HOPR","IDEX","INDEX","INV","JASMY","KRL","LCX",
 "LIT","LOKA","LPT","LQTY","LSETH","MCO2","MEDIA","METIS","MLN","MNDE","MPL","MSD" if False else "MUSE",
 "NCT","NMR","OXT","PAX","PERP","PLA","PLU","PNG","POLS","POND","POWR","PRO","PRQ","PUNDIX","PYR","QI",
 "QUICK","RAD","RAI","RARI","RBN","REQ","RGT","RLC","RLY","RPL","SHDW","SHPING","SPA","SUKU","SUPER",
 "SWFTC","SYLO","SYN","TIME","TONE" if False else "TRAC","TRIBE","TRU","UNFI","UPI","VARA","VGX","VTHO",
 "WAMPL","WCFG","XYO","ZETA",
]
_SEED_ROBINHOOD = ["BTC","ETH","SOL","XRP","ADA","DOGE","AVAX","LINK","LTC","BCH","UNI","ETC","XLM",
                   "AAVE","COMP","SHIB","PEPE","BONK","WIF","DOT","XTZ","TRUMP" if False else "ONDO",
                   "ARB","OP","SUI","NEAR","RENDER","JUP","POPCAT" if False else "PENGU"]


def _now():
    return datetime.now(timezone.utc).isoformat()


def _usd(syms) -> set:
    return {f"{b}-USD" for b in syms if b and isinstance(b, str)}


def _load(out: Path, name: str, default=None):
    try:
        return json.loads((out / name).read_text())
    except Exception:
        return default if default is not None else {}


def fetch_listings(out_dir) -> Dict[str, Any]:
    """Refresh listed sets from PUBLIC endpoints (runs on Actions; seeds if offline)."""
    out = Path(out_dir)
    store = _load(out, "VENUES.json", {})
    listed = store.get("listed") or {}
    changed = []
    try:
        import requests
        r = requests.get("https://api.binance.us/api/v3/exchangeInfo", timeout=20)
        syms = [s["baseAsset"] for s in r.json().get("symbols", [])
                if s.get("quoteAsset") == "USD" and s.get("status") == "TRADING"]
        if len(syms) >= 40:
            listed["binanceus"] = sorted(_usd(syms)); changed.append("binanceus")
    except Exception:
        pass
    try:
        import requests
        r = requests.get("https://api.exchange.coinbase.com/products", timeout=20)
        syms = [p["base_currency"] for p in r.json()
                if p.get("quote_currency") == "USD" and not p.get("trading_disabled")]
        if len(syms) >= 60:
            listed["coinbase"] = sorted(_usd(syms)); changed.append("coinbase")
    except Exception:
        pass
    listed.setdefault("binanceus", sorted(_usd(_SEED_BINANCEUS)))
    listed.setdefault("coinbase", sorted(_usd(_SEED_COINBASE)))
    listed.setdefault("robinhood", sorted(_usd(_SEED_ROBINHOOD)))
    store.update({"generated_at": _now(), "fees": VENUES, "listed": listed,
                  "refreshed": changed or ["seed"],
                  "what": ("declared venue fees + live listings. cost = fee + spread + capped "
                           "slippage; listings refresh from public endpoints each daily run")})
    write_json_atomic(out / "VENUES.json", store)
    return store


def spread_bps_for(out: Path, sym: str, default_bps: float = 8.0) -> float:
    sp = _load(out, "KRAKEN_SPREAD.json", {}).get("by_symbol") or {}
    v = sp.get(sym, {}).get("spread_bps")
    try:
        return float(v) if v is not None else default_bps
    except Exception:
        return default_bps


def venue_round_trip_cost(out: Path, sym: str, prices: List[float], knob: Dict[str, Any],
                          legacy_cost: float) -> Dict[str, Any]:
    """Total round-trip cost FRACTION under the declared model, with full breakdown."""
    venue = str(knob.get("venue", "binanceus"))
    v = VENUES.get(venue, VENUES["binanceus"])
    side = float(v.get("maker_bps" if str(knob.get("order_type", "maker")) == "maker"
                       else "taker_bps", 10.0))
    fee_bps = 2.0 * side + float(v.get("spread_pad_bps", 0.0))
    spr_bps = spread_bps_for(out, sym, float(knob.get("default_spread_bps", 8.0)))
    cap_bps = float(knob.get("slippage_cap_bps", 20.0))
    slip_bps = min(cap_bps, max(0.0, legacy_cost * 10000.0 - fee_bps))   # noise DEMOTED + CAPPED
    total = (fee_bps + spr_bps + slip_bps) / 10000.0
    return {"total": round(total, 6), "venue": venue,
            "parts_bps": {"fee_rt": round(fee_bps, 2), "spread": round(spr_bps, 2),
                          "slippage_capped": round(slip_bps, 2)}}


def build_venue_reality(out_dir) -> Dict[str, Any]:
    """THE UNIVERSE TRUTH TEST — publishes coverage, unlisted-P&L, and roster gaps."""
    out = Path(out_dir)
    store = fetch_listings(out)
    listed = {k: set(vv) for k, vv in (store.get("listed") or {}).items()}
    union_listed = set().union(*listed.values()) if listed else set()
    cards = (_load(out, "CONFIDENCE_CARDS.json").get("cards") or {})
    ours = {s for s, c in cards.items() if c.get("class") in ("crypto", "aggressive")
            or (s.endswith("-USD") and c.get("class") == "crypto")}
    if not ours:
        ours = {s for s in cards if s.endswith("-USD") or s.endswith("USDT")}
    coverage = {ven: {"listed_n": len(l), "ours_listed": len(ours & l),
                      "ours_unlisted_n": len(ours - l)} for ven, l in listed.items()}
    # realized attribution on venue-unlisted names (all-time, crypto books)
    unl_usd, tot_usd, unl_syms = 0.0, 0.0, {}
    for bk in ("crypto", "aggressive"):
        for t in (_load(out, f"paper_book_{bk}.json").get("trades") or []):
            if t.get("side") != "SELL":
                continue
            pnl = float(t.get("pnl") or 0.0)
            tot_usd += pnl
            if t.get("sym") not in union_listed:
                unl_usd += pnl
                unl_syms[t["sym"]] = round(unl_syms.get(t["sym"], 0.0) + pnl, 2)
    gaps = sorted(union_listed - ours)
    payload = {"generated_at": _now(), "coverage": coverage,
               "union_listed_n": len(union_listed),
               "truth_test": {"realized_total_usd": round(tot_usd, 2),
                              "realized_on_UNLISTED_usd": round(unl_usd, 2),
                              "pct_of_realized_untradable": (round(100 * unl_usd / tot_usd, 1)
                                                             if tot_usd else 0.0),
                              "top_unlisted_earners": sorted(unl_syms.items(),
                                                             key=lambda x: -abs(x[1]))[:10]},
               "universe_gaps": {"venue_listed_but_untracked_n": len(gaps),
                                 "sample": gaps[:40],
                                 "action": "EXTRA_TICKERS.json feeds these into the roster"},
               "what": ("Universe Truth Test: if the edge lives on names your venues do not list, "
                        "the edge is zero. This store decides whether history means anything.")}
    write_json_atomic(out / "VENUE_REALITY.json", payload)
    # feed the roster: venue-listed names we do not track yet
    write_json_atomic(out / "EXTRA_TICKERS.json",
                      {"generated_at": _now(), "crypto": gaps,
                       "what": "venue-listed USD pairs auto-added to the scan roster (max capture)"})
    return {"summary": f"venues: union {len(union_listed)} listed · gaps {len(gaps)} → roster · "
                       f"unlisted realized ${round(unl_usd,2)} of ${round(tot_usd,2)}"}
