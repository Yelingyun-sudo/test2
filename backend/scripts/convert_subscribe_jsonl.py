#!/usr/bin/env python3
"""
Convert backend/resources/subscribe.jsonl from pseudo-JSON (single quotes,
list-per-line) into proper JSONL (one JSON object per line).
"""

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "resources" / "subscribe.jsonl"
DST = ROOT / "resources" / "subscribe_clean.jsonl"


def parse_chunk(line: str, line_no: int):
    """Parse a single line that may end with a trailing comma."""
    trimmed = line.strip()
    if not trimmed:
        return []
    if trimmed.endswith(","):
        trimmed = trimmed[:-1]
    try:
        chunk = ast.literal_eval(trimmed)
    except Exception as exc:  # pragma: no cover
        raise SystemExit(f"Line {line_no}: failed to parse: {exc}") from exc
    return chunk if isinstance(chunk, list) else [chunk]


def main():
    if not SRC.exists():
        raise SystemExit(f"Source file not found: {SRC}")

    records = []
    seen = set()
    for idx, line in enumerate(SRC.read_text(encoding="utf-8").splitlines(), 1):
        for record in parse_chunk(line, idx):
            key = (record.get("url"), record.get("account"), record.get("password"))
            if key in seen:
                continue
            seen.add(key)
            records.append(record)

    DST.parent.mkdir(parents=True, exist_ok=True)
    with DST.open("w", encoding="utf-8") as f:
        for record in records:
            json.dump(record, f, ensure_ascii=False)
            f.write("\n")

    print(f"Wrote {len(records)} records to {DST.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
