"""steward.util — atomic writes, dates, the ledger. Nothing clever."""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def today_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def month_of(date_str: str) -> str:
    return str(date_str)[:7]                       # "YYYY-MM"


def write_json_atomic(path: Path, payload: Any) -> None:
    """tmp + rename so a crash mid-write can never leave a half file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=1)
        os.replace(tmp, str(path))
    except Exception:
        try:
            os.unlink(tmp)
        except Exception:
            pass
        raise


def read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default


def ledger_append(data_dir: Path, book: str, event: str, detail: dict) -> None:
    """Append-only record of every action, with its reason. The ledger is never edited."""
    from .config import LEDGER_FILE
    row = {"t": now_iso(), "book": book, "event": event, **detail}
    p = Path(data_dir) / LEDGER_FILE
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")
