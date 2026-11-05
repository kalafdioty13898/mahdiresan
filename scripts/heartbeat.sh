#!/usr/bin/env bash
# Daily heartbeat commit: keeps the scheduled backup trigger alive (60-day inactivity rule)
set -u
cd "$GITHUB_WORKSPACE" || exit 0
TODAY=$(date -u +%F)
if [ -f .github/heartbeat.txt ] && [ "$(cat .github/heartbeat.txt 2>/dev/null)" = "$TODAY" ]; then
  echo "heartbeat already sent today"
  exit 0
fi
mkdir -p .github
echo "$TODAY" > .github/heartbeat.txt
git config user.name "bot-keeper"
git config user.email "actions@users.noreply.github.com"
git add .github/heartbeat.txt
git commit -q -m "[skip ci] heartbeat $TODAY" || { echo "nothing to commit"; exit 0; }
git pull --rebase -q origin main 2>/dev/null || true
if git push -q origin HEAD:main 2>/dev/null; then
  echo "heartbeat pushed: $TODAY"
else
  echo "heartbeat push failed (non-fatal)"
fi
