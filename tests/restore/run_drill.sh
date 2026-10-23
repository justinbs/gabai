#!/usr/bin/env bash
# Guided restore drill (paper Table 20C). Makes a fresh backup on the server,
# tells you which two files to download from Google Drive, then runs
# restore_drill.sh with the keys from ~/GABAI-keys.
#
#   tests/restore/run_drill.sh
#
# Run from the repo root in Git Bash, with Docker Desktop running.
set -euo pipefail

KEYS="$HOME/GABAI-keys"
DRILL="$HOME/Downloads/drill"
[ -f tests/restore/restore_drill.sh ] || { echo "Run this from the GABAI folder: cd ~/Desktop/Personal/GABAI"; exit 1; }
say() { echo; echo "------------------------------------------------------------"; printf '%s\n' "$@"; echo "------------------------------------------------------------"; }
wait_enter() { read -r -p ">> $1 Then press Enter. " _; }

say "STEP 1 OF 4: checking what the drill needs"
docker info >/dev/null 2>&1 || { echo "Docker Desktop is not running. Open it, wait until it says running, and start this script again."; exit 1; }
[ -f "$KEYS/gabai-backup-key.txt" ] || { echo "Missing $KEYS/gabai-backup-key.txt"; exit 1; }
grep -q "^DATA_KEYS=" "$KEYS/server-secrets.txt" || { echo "No DATA_KEYS line in $KEYS/server-secrets.txt"; exit 1; }
echo "Docker is running; the backup key and the data key copy were found in $KEYS."

say "STEP 2 OF 4: a fresh backup on the server (about 1 minute)" \
    "Nobody should be using gabai.help during this step."
trap 'rm -f counts-before.txt drill-counts-production.txt' EXIT
for attempt in 1 2 3; do
    ssh gabai "docker exec -i gabai-db psql -U gabai -d gabai -At" < tests/restore/counts.sql > counts-before.txt
    ssh gabai "cd /srv/gabai && scripts/backup.sh && rclone sync backups gdrive:gabai-backups"
    ssh gabai "docker exec -i gabai-db psql -U gabai -d gabai -At" < tests/restore/counts.sql > drill-counts-production.txt
    if diff -q counts-before.txt drill-counts-production.txt >/dev/null; then
        echo "Backup made, and nothing changed on the site while it ran."
        break
    fi
    echo "Someone used the site during the backup (attempt $attempt of 3); making another one."
    [ "$attempt" = 3 ] && { echo "Try again later, when the site is quiet."; exit 1; }
done
newest=$(ssh gabai "ls -1 /srv/gabai/backups/db-*.dump.age | tail -1 | xargs -n1 basename")
time=${newest#db-}; time=${time%.dump.age}

say "STEP 3 OF 4: download two files from Google Drive"
mkdir -p "$DRILL"
echo "1. In the browser, sign in to the Google account that holds the GABAI backups."
echo "2. Open the folder gabai-backups."
echo "3. Download these two files:"
echo "       db-$time.dump.age"
echo "       uploads-$time.tar.gz.age"
echo "4. Move both into this folder:  $(cygpath -w "$DRILL")"
while true; do
    wait_enter "When both files are in that folder,"
    [ -f "$DRILL/db-$time.dump.age" ] && [ -f "$DRILL/uploads-$time.tar.gz.age" ] && break
    echo "Not found yet. Folder now holds: $(ls "$DRILL" 2>/dev/null | tr '\n' ' ')"
done

say "STEP 4 OF 4: the drill (about 1 minute; it asks for your admin email and password once)"
DATA_KEYS="$(grep '^DATA_KEYS=' "$KEYS/server-secrets.txt" | tail -n 1 | cut -d= -f2- | tr -d '\r' | sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'\$//")"
export DATA_KEYS
status=0
bash tests/restore/restore_drill.sh "$DRILL/db-$time.dump.age" "$DRILL/uploads-$time.tar.gz.age" \
    "$KEYS/gabai-backup-key.txt" drill-counts-production.txt || status=$?
unset DATA_KEYS
rm -rf "$DRILL" counts-before.txt drill-counts-production.txt
if [ "$status" = 0 ]; then
    say "Drill passed. The log is in tests/restore/results/. The downloaded backup files were deleted."
else
    say "Drill stopped at a FAIL (see the line above). Send Claude the log in tests/restore/results/."
fi
