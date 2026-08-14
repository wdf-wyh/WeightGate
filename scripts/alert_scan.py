#!/usr/bin/env python3
"""Trigger control-plane alert scan (Phase 4 ops helper).

  python scripts/alert_scan.py
  python scripts/alert_scan.py --base http://127.0.0.1:8080
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request


def main() -> int:
    p = argparse.ArgumentParser(description="POST /v1/alerts/scan")
    p.add_argument("--base", default="http://127.0.0.1:8080")
    args = p.parse_args()
    url = args.base.rstrip("/") + "/v1/alerts/scan"
    req = urllib.request.Request(url, method="POST", data=b"")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            print(body)
            data = json.loads(body)
            print(f"created={data.get('created')} open_total={data.get('open_total')}")
            return 0
    except urllib.error.URLError as exc:
        print(f"alert_scan failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
