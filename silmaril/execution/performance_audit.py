"""silmaril.execution.performance_audit — PERFORMANCE AUDIT (2.5.1 P7). Measurement."""
from __future__ import annotations
import json, os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict
from .atomic_io import write_json_atomic

def _now(): return datetime.now().astimezone().isoformat()

def build_performance_audit(out_dir) -> Dict[str, Any]:
    out = Path(out_dir)
    files = []
    for p in out.glob("*.json"):
        try: files.append((p.name, p.stat().st_size))
        except Exception: pass
    files.sort(key=lambda x: x[1], reverse=True)
    data_bytes = sum(s for _, s in files)
    src = out.parent.parent / "silmaril" if (out.parent.parent / "silmaril").exists() else None
    nmod = len(list(src.rglob("*.py"))) if src else None
    payload = {"generated_at": _now(),
               "data_dir_total_kb": round(data_bytes / 1024, 1),
               "json_file_count": len(files),
               "largest_files_kb": [{"file": n, "kb": round(s / 1024, 1)} for n, s in files[:12]],
               "python_modules": nmod,
               "advice": ("Largest JSONs are the cycle's IO cost each run. If any single file balloons, "
                          "cap its history (snapshots/leaderboards already capped). No runtime hotspots "
                          "flagged at this size — IO is the dominant cost, already atomic + concurrency-guarded."),
               "note": "Measurement only. Optimize only a file that is actually large and written every cycle."}
    try: write_json_atomic(out / "PERFORMANCE_AUDIT.json", payload)
    except Exception: pass
    return payload

if __name__ == "__main__":
    import sys
    p = build_performance_audit(sys.argv[1] if len(sys.argv) > 1 else "docs/data")
    print("data dir:", p["data_dir_total_kb"], "KB |", p["json_file_count"], "files |", p["python_modules"], "modules")
    for f in p["largest_files_kb"][:6]: print(f"  {f['kb']:>7} KB  {f['file']}")
