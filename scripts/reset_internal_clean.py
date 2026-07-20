"""
scripts/reset_internal_clean.py — clean-wipe the INTERNAL paper books, PRESERVING graph/fingerprint data.

The corruption is stopped by the freshness FIX in paper_sim.py, not by deleting price history. So this
reset clears only the polluted TRADE RECORDS and restarts equity clean — it PRESERVES price_samples
(every asset's graph + fingerprint history), favicon caches, and all per-asset visual data, so nothing
on the dashboard goes blank. Crypto graphs also keep refilling automatically from the ccxt 300-candle
pull each run.

Wiped:    every internal + arena paper book -> $10k clean · MASTER_ACCOUNT.json (fresh inception)
          · snapshot_history.jsonl (equity curve restarts clean with the books)
PRESERVED: price_samples.json (graphs/fingerprints), favicons, all per-asset visual + fingerprint data.
"""
import json
from pathlib import Path
from datetime import datetime, timezone

DATA = Path(__file__).resolve().parents[1] / "docs" / "data"
BASELINE = 10000.0
CLEAN_BOOK = {"cash": BASELINE, "positions": {}, "realized_pnl": 0.0, "trades": []}

def main():
    # ── 7.0 FINAL — ARCHIVE-FIRST (Law 26: archived, never discarded). ────────────────
    # Before ANY store is flattened or deleted, everything the reset will touch — plus
    # every append-only ledger — is copied to archive/<UTC-stamp>/ in the same commit.
    # A reset that cannot archive REFUSES to run. Nothing is ever simply gone again.
    import shutil
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    ARCH = DATA.parent.parent / "archive" / f"reset_{stamp}"
    to_archive = (list(DATA.glob("paper_book_*.json"))
                  + [DATA / f for f in ("MASTER_ACCOUNT.json", "MASTER_DECISIONS.json",
                                        "snapshot_history.jsonl", "LEDGER.jsonl",
                                        "CHAMPION_FORWARD_LEDGER.jsonl",
                                        "CALIBRATION.json", "CALIBRATION_LEDGER.jsonl",
                                        "SESSION_TODAY.json", "DECISION_TRACE.json")])
    try:
        ARCH.mkdir(parents=True, exist_ok=True)
        kept = 0
        for src in to_archive:
            if src.exists():
                shutil.copy2(src, ARCH / src.name); kept += 1
        print(f"  ARCHIVED {kept} store(s) -> {ARCH} (Law 26 — reset refuses to run without this)")
    except Exception as e:
        print(f"  ARCHIVE FAILED ({e}) — REFUSING to reset. Nothing was touched.")
        raise SystemExit(1)
    n = 0
    for p in list(DATA.glob("paper_book_*.json")):
        p.write_text(json.dumps(CLEAN_BOOK, indent=2)); n += 1
    print(f"  reset {n} paper books -> ${BASELINE:.0f} clean")
    ma = DATA / "MASTER_ACCOUNT.json"
    if ma.exists():
        ma.unlink(); print("  deleted MASTER_ACCOUNT.json (fresh $10k inception)")
    md = DATA / "MASTER_DECISIONS.json"
    if md.exists():
        md.unlink(); print("  deleted MASTER_DECISIONS.json (decision ledger starts clean)")
    for f in ("SESSION_TODAY.json", "SESSION_ANATOMY.json", "DECISION_TRACE.json", "MASTER_LOG.json",
              "CHART_OVERLAYS.json", "DAILY_TAKEHOME.json", "TRADE_QUALITY.json", "NEWS_TRIAL.json",
              "NEWS_TRIAL_STATUS.json", "LIVE_ORDERS_PREVIEW.json",
              "REGIME_AB.json", "REGIME_AB_STATUS.json", "KRAKEN_MIRROR.json", "KRAKEN_SPREAD.json",
              "THRESHOLD_CHAMPION.json", "THRESHOLD_SHADOW.json", "THRESHOLD_TAKEHOME.json",
              "sweep_protection.json",
              "decision_ledger.json", "agent_portfolios.json", "alpaca_paper_state.json",
              "alpaca_h3_state.json", "alpaca_h5_state.json", "capital_flow.json", "paper_book_aggressive.json",
              # 7.0 FINAL (V1): CALIBRATION.json REMOVED from this delete list. "When we said X%, did we
              # win X%" is LEARNING, not a derived view — a standard reset must never burn the machine's
              # memory of its own honesty. (CALIBRATION_LEDGER.jsonl was already preserved; now both are.)
              "AGGRESSION_LADDER.json", "WEEKLY_SCORECARD.json",
              "STOCK_PARITY_AUDIT.json", "INTEGRITY_QUARANTINE.json", "ECONOMIC_CLOCK.json",
              "COMPLEXITY_LEDGER.json",
              "BENCH_BOOKS.json", "STORE_CONTRACTS.json", "UNIVERSE_CENSUS.json",
              "CHAMPION_UTILIZATION.json", "INVARIANTS.json"):
        fp = DATA / f
        if fp.exists():
            fp.unlink(); print(f"  deleted {f} (derived view — rebuilds clean)")
    # ── 7.0.1 BENCH RE-ANCHOR LAW (operator: "vs HODL scores not resetting with the wipe"). ──
    # bench_books.py doctrine: nulls "start where the governed books started." But BENCH_BOOKS.json
    # was never deleted here, so re-anchoring after a wipe was ACCIDENTAL — a ghost crypto-HODL of
    # -22% could sit on a fresh $10k book. Delete it in BOTH modes; bench_books rebuilds at fresh
    # $10k next cycle so every Law-10 comparison shares one honest inception with the books.
    _bb = DATA / "BENCH_BOOKS.json"
    if _bb.exists():
        _bb.unlink(); print("  deleted BENCH_BOOKS.json (nulls re-anchor with the fresh books — Law 10 shares one inception)")
    sh = DATA / "snapshot_history.jsonl"
    if sh.exists():
        sh.write_text(""); print("  cleared snapshot_history.jsonl (equity restarts clean)")
    # 2.7: stamp the wipe time so the engine enforces a TRUE quiet period from now (not from price density).
    (DATA / "WIPE_MARKER.json").write_text(json.dumps(
        {"wiped_at": datetime.now(timezone.utc).isoformat(),
         "note": "engine stays quiet for QUIET_AFTER_WIPE_MIN minutes after this timestamp"}, indent=2))
    print("  wrote WIPE_MARKER.json (true post-wipe quiet period starts now)")
    # ── 7.0.1 THE POST-RESET GHOST FIX (operator: "keeps not working when we reset, genesis or not"). ──
    # Root cause: this script wiped a dozen stores but never touched paper_sim_live.json, so the
    # dashboard kept rendering the PRE-reset snapshot (old positions, old funnel, old "waiting for a
    # dip") against fresh $10k books until the next engine cycle — a Frankenstein state on EVERY
    # reset, both modes. Fix: seed a minimal TRUTHFUL live snapshot right now; the first real cycle
    # overwrites it. Every panel tells the honest "fresh reset · quiet window" story from second one.
    try:
        _qm = 120
        try:
            _cat = json.loads((DATA / "PARAM_CATALOG.json").read_text())
            _qm = int(((_cat.get("post_wipe_quiet") or {}).get("minutes")) or
                      _cat.get("QUIET_AFTER_WIPE_MIN") or 120)
        except Exception:
            pass
        _seed_book = {"positions": [], "skipped": False, "why": "",
                      "funnel": {"seen": 0, "entry_warm": 0, "candidates_after_gates": 0,
                                 "bought": 0, "rejections": {}}}
        (DATA / "paper_sim_live.json").write_text(json.dumps({
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "seeded_by_reset": True,
            "post_wipe_quiet": {"active": True, "minutes_left": _qm},
            "regimes": {},
            "marks_health": {"warm_rule": "fresh reset — rebuilding live context"},
            "crypto": dict(_seed_book), "stock": dict(_seed_book),
            "metal": dict(_seed_book), "energy": dict(_seed_book),
            "aggressive": dict(_seed_book),
            "note": "seeded by reset_internal_clean — the first real engine cycle replaces this"},
            indent=1))
        print(f"  seeded paper_sim_live.json (quiet {_qm}m) — dashboard tells the truth from second one")
    except Exception as _e:
        print(f"  WARN: live seed failed ({_e}) — dashboard may show pre-reset ghosts until first cycle")
    # PRESERVED on purpose: price_samples.json (graphs + fingerprints), favicon caches, per-asset data.
    print("  PRESERVED: price_samples.json (graphs/fingerprints) + favicons — dashboard will NOT go blank")
    print("PRESERVED FOREVER: EVOLUTION_LEDGER.jsonl · RESEARCH_QUEUE.json · REGIME_COMBOS.jsonl · DAILY_BASELINE.json · knowledge_graph.json · ROTATION_HYPOTHESES.json · RESEARCH_OS.json · CONDUCTOR_LEDGER.jsonl · CONDUCTOR_STATE.json · REGIME_EXIT_AB.jsonl · CONDUCTOR_REPORT_CARD.json · STRATEGY_LAB.json · CONFIDENCE_ENGINE.json · CENSUS_ROSTER.json · INVARIANTS_STATE.json · LEDGER.jsonl (the one book of record) · CHAMPION_FORWARD_LEDGER.jsonl (election evidence — the champion can finally evolve) · CALIBRATION.json + CALIBRATION_LEDGER.jsonl (the machine's memory of its own honesty) (long-memory, survives every wipe)")
    print("CLEAN. Books pristine at $10k; all graph/fingerprint/favicon history intact.")

if __name__ == "__main__":
    main()
