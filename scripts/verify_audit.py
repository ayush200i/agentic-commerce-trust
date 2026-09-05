"""Verify an exported audit independently of the app database.

Usage: uv run python scripts/verify_audit.py receipt.json --head <separately-saved-head>
"""

import argparse
import hashlib
import json
from pathlib import Path


def verify(document, head=None):
    previous = "0" * 64
    for index, entry in enumerate(document["entries"], start=1):
        payload = {k: v for k, v in entry.items() if k != "hash"}
        calculated = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
        ).hexdigest()
        if (
            entry["sequence"] != index
            or entry["prev_hash"] != previous
            or entry["hash"] != calculated
            or entry["session_id"] != document["session_id"]
        ):
            return False, f"Entry {index} failed verification"
        previous = calculated
    if previous != document["head"] or (head is not None and previous != head):
        return False, "Root hash mismatch (possible truncation or rewrite)"
    return True, f"Verified {len(document['entries'])} entries. Head: {previous}"


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("file", type=Path)
    parser.add_argument("--head", help="A previously saved root hash independent of this export")
    args = parser.parse_args()
    valid, message = verify(json.loads(args.file.read_text(encoding="utf-8")), args.head)
    print(message)
    raise SystemExit(0 if valid else 1)
