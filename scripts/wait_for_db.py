#!/usr/bin/env python3
"""Wait until Postgres accepts connections (interviewer / local setup helper)."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.db import connect


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--once", action="store_true", help="Single attempt, no retry")
    args = parser.parse_args()

    attempts = 1 if args.once else max(1, args.timeout)
    last_error = None
    for _ in range(attempts):
        try:
            conn = connect()
            conn.close()
            print("warehouse is accepting connections")
            return 0
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if args.once:
                break
            time.sleep(1)
    print(f"warehouse is not reachable: {last_error}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
