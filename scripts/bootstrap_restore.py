#!/usr/bin/env python3
"""Restore bot state on the runner.

Priority:
1. repository_dispatch 'bootstrap-bot' client_payload.state_b64  (private, one-time)
2. BOT_STATE environment variable (base64 tar.gz)                (manual fallback secret)
Writes only safe members: config.json, data.json, instances/*/config.json|data.json
Never prints payload content.
"""
import base64
import io
import json
import os
import sys
import tarfile

SAFE_ROOTS = ("config.json", "data.json")


def safe_member(name: str) -> bool:
    if name in SAFE_ROOTS:
        return True
    if name.startswith("instances/") and (
        name.endswith("/config.json") or name.endswith("/data.json")
    ):
        return True
    return False


def extract(payload_b64: str) -> int:
    raw = base64.b64decode(payload_b64)
    count = 0
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as tf:
        members = [m for m in tf.getmembers() if safe_member(m.name) and m.isfile()]
        tf.extractall(".", members=members)
        count = len(members)
    return count


def main() -> None:
    payload = ""
    ev_path = os.environ.get("GITHUB_EVENT_PATH")
    if ev_path and os.path.exists(ev_path):
        try:
            with open(ev_path, encoding="utf-8") as f:
                ev = json.load(f)
            if ev.get("action") == "bootstrap-bot":
                payload = (ev.get("client_payload") or {}).get("state_b64") or ""
        except Exception as e:
            print(f"event parse skipped: {type(e).__name__}")
    if not payload:
        payload = (os.environ.get("BOT_STATE") or "").strip()
    if not payload:
        print("no bootstrap payload / secret -> relying on cache restore")
        return
    try:
        n = extract(payload)
        print(f"bootstrap ok: {n} files restored")
    except Exception as e:
        print(f"::error::bootstrap failed: {type(e).__name__}")
        sys.exit(1)


if __name__ == "__main__":
    main()
