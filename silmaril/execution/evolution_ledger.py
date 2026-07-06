"""
EVOLUTION LEDGER (Phase 21) — the permanent memory of improvement. Append-only JSONL that SURVIVES
EVERY WIPE. Not git history — knowledge: why each change was made, what evidence backed it, what
happened after. The substrate a future 4.0 reasons over.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

def record(out_dir, version, reason, hypothesis=None, evidence=None, result="deployed"):
    e = {"t": datetime.now(timezone.utc).isoformat(), "version": version, "reason": reason,
         "hypothesis": hypothesis, "evidence": evidence, "result": result}
    with (Path(out_dir) / "EVOLUTION_LEDGER.jsonl").open("a") as fh:
        fh.write(json.dumps(e) + "\n")
    return e
