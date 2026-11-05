#!/usr/bin/env bash
# Run the bot for N minutes; restart it if it dies; mark .bot_ok once it stayed up >= 60s
set -u
MINUTES="${1:-55}"
cd "$(dirname "$0")/.." || exit 1
END=$(( $(date +%s) + MINUTES * 60 ))
FAILS=0
rm -f instances/*.pid 2>/dev/null
while :; do
  NOW=$(date +%s)
  [ "$NOW" -ge "$END" ] && break
  python3 bot.py >> run.log 2>&1 &
  BOT_PID=$!
  echo "[chunk] bot started pid=$BOT_PID ($(date -u '+%H:%M:%S'))"
  ALIVE_START=$NOW
  while kill -0 "$BOT_PID" 2>/dev/null; do
    sleep 15
    NOW=$(date +%s)
    if [ $(( NOW - ALIVE_START )) -ge 60 ]; then
      touch .bot_ok
    fi
    [ "$NOW" -ge "$END" ] && break
  done
  if [ "$NOW" -ge "$END" ]; then
    kill "$BOT_PID" 2>/dev/null || true
    sleep 5
    break
  fi
  FAILS=$((FAILS+1))
  echo "[chunk] bot exited; restart #$FAILS in 15s"
  if [ "$FAILS" -ge 5 ]; then sleep 120; else sleep 15; fi
done
pkill -f "bot.py --instance" 2>/dev/null || true
rm -f instances/*.pid 2>/dev/null
echo "[chunk] done (${MINUTES}min)"
