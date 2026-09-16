#!/bin/sh
# Run full DB backup at 00:00 local time (TZ), then sleep until next midnight.
set -eu

BACKUP_SCRIPT="${BACKUP_SCRIPT:-/scripts/docker_backup.sh}"

seconds_until_midnight() {
  # Portable: GNU date (Debian postgres image).
  now="$(date +%s)"
  tomorrow="$(date -d 'tomorrow 00:00:00' +%s)"
  echo $((tomorrow - now))
}

echo "[backup-cron] TZ=${TZ:-UTC} starting; first run at next 00:00"
while true; do
  wait_s="$(seconds_until_midnight)"
  echo "[backup-cron] sleeping ${wait_s}s until midnight ($(date -d "@$(( $(date +%s) + wait_s ))" -Iseconds 2>/dev/null || true))"
  sleep "$wait_s"
  if ! sh "$BACKUP_SCRIPT"; then
    echo "[backup-cron] backup failed" >&2
  fi
  # Avoid double-fire if dump finishes in <1s before clock rolls.
  sleep 2
done
