#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""لایه پشتیبان نوتیف خاموشی: اگر پروسه بات هنگ کرده بود و نتوانست خودش به ادمین خبر بدهد،
workflow این اسکریپت را صدا می‌زند. برای هر config.json، پیام را به ادمینِ همان بات می‌فرستد.

مصرف:
    python3 scripts/notify_admin.py config.json
    python3 scripts/notify_admin.py instances/NAME/config.json [پیام دلخواه]
"""
import json
import sys
from urllib.request import Request, urlopen

MSG = "⚙️ ربات درحال خالی سازی فضای رم تا چند دقیقه دیگر ربات روشن میشود"

def main():
    if len(sys.argv) < 2:
        print("usage: notify_admin.py <path/to/config.json> [message]")
        sys.exit(2)
    path = sys.argv[1]
    text = sys.argv[2] if len(sys.argv) > 2 else MSG
    try:
        with open(path, encoding="utf-8") as f:
            cfg = json.load(f)
        token, admin = cfg["token"], int(cfg["admin_id"])
    except Exception as e:
        print(f"notify_admin: cannot read {path}: {e}")
        sys.exit(1)
    try:
        req = Request(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=json.dumps({"chat_id": admin, "text": text}).encode("utf-8"),
            headers={"Content-Type": "application/json"})
        with urlopen(req, timeout=10) as r:
            j = json.loads(r.read().decode("utf-8"))
        print(f"notify_admin: {path} -> admin {admin}: ok={j.get('ok')}")
    except Exception as e:
        print(f"notify_admin: send failed for {path}: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
