#!/bin/bash
# 🔐 ذخیره ماندگار state (config + data همه instanceها) به صورت رمزنگاری‌شده در ریپو
set -e
cd "$(dirname "$0")"

tar czf state.tgz config.json data.json instances/*/config.json instances/*/data.json 2>/dev/null \
  || tar czf state.tgz config.json data.json

openssl enc -aes-256-cbc -pbkdf2 -salt -in state.tgz -out state.enc -pass env:STATE_KEY
rm -f state.tgz

git config user.name "mahdiresan-bot"
git config user.email "bot@users.noreply.github.com"
git add state.enc

if git diff --cached --quiet; then
  echo "no state changes"
  exit 0
fi

git commit -m "🔁 state backup $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
git pull --rebase origin main || true
git push origin HEAD:main
echo "state pushed ✅"
