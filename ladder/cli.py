"""ladder.cli — the one entrypoint.

    python -m ladder.cli run       # fetch prices, rebuild the ladder, record, write the page
    python -m ladder.cli offline   # same, from the saved price file (no network)
    python -m ladder.cli verify    # registration hash + file-size guard

The forward record (docs/data/ladder_record.json) is APPEND-ONLY: a day, once recorded,
is never rewritten. Each run recomputes everything and compares it with the record; any
difference larger than a cent is a DRIFT and is shown in red on the page.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import data as DA
from . import engine as EN
from . import report as RP
from .config import REGISTERED, registration_hash

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "docs" / "data"
DOCS = ROOT / "docs"
RECORD = "ladder_record.json"
LEDGER = "ladder_ledger.jsonl"
RESULTS = "ladder_results.json"
MAX_FILE_MB = 25          # GitHub refuses files over 100 MB; we stop far below that


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    tmp.replace(path)


def verify() -> bool:
    ok = True
    reg = (ROOT / "REGISTRATION_9.md")
    h = registration_hash()
    if reg.exists() and ("registration-hash: %s" % h) not in reg.read_text(encoding="utf-8"):
        print("VERIFY FAIL: ladder/config.py hash %s is not the one in REGISTRATION_9.md — "
              "parameters changed without a re-registration" % h)
        ok = False
    for p in DATA.glob("**/*"):
        if p.is_file() and p.stat().st_size > MAX_FILE_MB * 1024 * 1024:
            if p.name.startswith("ladder_"):
                print("VERIFY FAIL: %s is %.1f MB (limit %d MB)" % (p, p.stat().st_size / 1e6, MAX_FILE_MB))
                ok = False
    hreg = ROOT / "REGISTRATION_HEADLINES.md"
    if hreg.exists():
        from .headlines import rules_hash
        if ("headline-rules-hash: %s" % rules_hash()) not in hreg.read_text(encoding="utf-8"):
            print("VERIFY FAIL: ladder/headlines.py rules hash %s is not the one in "
                  "REGISTRATION_HEADLINES.md" % rules_hash())
            ok = False
    if ok:
        print("verify OK — registration %s" % h)
    return ok


def _record_and_check(res: dict) -> dict:
    rec = _read(DATA / RECORD, {"registration_hash": registration_hash(), "days": {}})
    drift = []
    added = 0
    for day, vals in sorted(res["forward_values"].items()):
        old = rec["days"].get(day)
        if old is None:
            rec["days"][day] = dict(vals, recorded_at=_now())
            added += 1
            continue
        for k, v in vals.items():
            ov = old.get(k)
            if ov is not None and abs(ov - v) > 0.01:
                drift.append({"date": day, "book": k, "recorded": ov, "recomputed": v})
    _write(DATA / RECORD, rec)
    return {"days_recorded": len(rec["days"]), "days_added": added, "drift": drift[:50],
            "drift_count": len(drift)}


def cmd_run(offline: bool = False) -> int:
    if not verify():
        print("REFUSING TO RUN — see the failures above.")
        return 1
    if offline:
        saved = DA.load_saved(DATA)
        series, meta = saved.get("series", {}), dict(saved.get("meta", {}), source="saved file")
    else:
        series, meta = DA.refresh(DATA)
    if not series or meta.get("missing"):
        print("price data unavailable for: %s" % meta.get("missing"))
        if not series:
            return 1
    tape = DA.build_tape(series)
    res = EN.build(tape)
    stale = DA.staleness_days(tape)
    res["data"] = dict(meta, newest_close=tape.dates[-1], stale_days=stale,
                       stale=stale > REGISTERED["stale_data_days"])
    res["record"] = _record_and_check(res)
    # the headline test is watch-only; nothing it does or fails at can touch the trading run
    try:
        from . import headlines as HL
        res["headlines"] = HL.run(DATA, tape, REGISTERED["categories"], REGISTERED["cash_symbol"],
                                  fetch_news=not offline)
    except Exception as e:                      # noqa: BLE001
        res["headlines"] = {"error": "%s: %s" % (type(e).__name__, str(e)[:200])}
    res["generated_at"] = _now()
    _write(DATA / RESULTS, res)
    with open(DATA / LEDGER, "a", encoding="utf-8") as f:
        f.write(json.dumps({
            "t": res["generated_at"], "hash": res["registration_hash"],
            "data_through": res["data_through"], "source": meta.get("source"),
            "stale_days": stale, "drift_count": res["record"]["drift_count"],
            "master": res["master"].get("forward_value"),
            "accounts": {c: v["account"].get("forward_value")
                         for c, v in res["categories"].items()},
            "equal_weight_hold": res["benchmarks"]["equal_weight_hold"].get("forward_value"),
        }) + "\n")
    RP.build(res, DOCS)
    m = res["master"]
    print("data through %s (%s, %d days old) · hash %s" % (
        res["data_through"], meta.get("source"), stale, res["registration_hash"]))
    print("replay %s -> : master %s%% · equal-weight %s%% · SPY %s%%" % (
        m["replay_start"], m["replay"]["total_pct"],
        res["benchmarks"]["equal_weight_hold"]["replay"]["total_pct"],
        res["benchmarks"]["spy_hold"]["replay"]["total_pct"]))
    if res["epoch_reached"]:
        print("forward: master $%s · equal-weight $%s · drift %d" % (
            m.get("forward_value"), res["benchmarks"]["equal_weight_hold"].get("forward_value"),
            res["record"]["drift_count"]))
    else:
        print("forward: epoch %s not reached yet" % REGISTERED["epoch_date"])
    return 0


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    if cmd == "run":
        return cmd_run()
    if cmd == "offline":
        return cmd_run(offline=True)
    if cmd == "verify":
        return 0 if verify() else 1
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
