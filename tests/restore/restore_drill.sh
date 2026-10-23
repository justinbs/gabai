#!/usr/bin/env bash
# Restore drill: rebuild GABAI on this laptop from one encrypted nightly backup.
#
#   tests/restore/restore_drill.sh <db-*.dump.age> <uploads-*.tar.gz.age> <age key file> <production counts file>
#
# Run from the repo root in Git Bash, with Docker running and DATA_KEYS exported
# in this terminal (see tests/verification/README.md, part C). Steps R2 to R9 of Table 20C;
# R1 (download from Google Drive) is done by hand first. Everything is logged to
# tests/restore/results/. The decrypted copy is deleted when the script ends.
set -euo pipefail

DB_AGE=$1 UP_AGE=$2 KEY=$3 PROD_COUNTS=$4
ROOT=$(pwd)
DAY=$(date +%Y-%m-%d)
LOG="$ROOT/tests/restore/results/restore-drill-$DAY.txt"
WORK="$HOME/gabai-restore-drill"
PORT_DB=5544 PORT_API=8100
mkdir -p "$(dirname "$LOG")"
exec > >(tee -a "$LOG") 2>&1

[ -n "${DATA_KEYS:-}" ] || { echo "DATA_KEYS is not set in this terminal; see README"; exit 1; }
for f in "$DB_AGE" "$UP_AGE" "$KEY" "$PROD_COUNTS"; do [ -f "$f" ] || { echo "missing: $f"; exit 1; }; done

api_pid=""
# The drill copy links to this laptop's .venv and models. Remove the links before
# any rm -rf, and stop if one is still there, so the real folders are never touched.
remove_links() {
    for d in .venv models; do
        local link="$WORK/app/backend/$d"
        if [ -e "$link" ] || [ -L "$link" ]; then
            powershell -NoProfile -Command "(Get-Item '$(cygpath -w "$link")').Delete()" >/dev/null 2>&1 || true
        fi
        if [ -e "$link" ] || [ -L "$link" ]; then
            echo "Could not remove the link $link; delete it by hand, then $WORK" >&2
            return 1
        fi
    done
}
cleanup() {
    [ -n "$api_pid" ] && kill "$api_pid" 2>/dev/null || true
    docker rm -f -v gabai-restore >/dev/null 2>&1 || true
    if remove_links; then
        rm -rf "$WORK"
        echo "Cleaned up: drill database and its volume removed, decrypted files deleted."
    fi
}
trap cleanup EXIT
step() { echo; echo "== $1"; }
pass() { echo "RESULT $1: PASS"; }
fail() { echo "RESULT $1: FAIL - $2"; exit 1; }

echo "GABAI restore drill, $(date '+%Y-%m-%d %H:%M %z'), on $(hostname)"
echo "Repo commit: $(git rev-parse --short HEAD)"

step "R1 Backup files (downloaded from Google Drive by hand)"
stamp=$(basename "$DB_AGE" | sed -E 's/^db-([0-9T]+Z).*/\1/')
ls -l "$DB_AGE" "$UP_AGE" | awk '{print $5, $NF}'
made=$(date -u -d "$(echo "$stamp" | sed -E 's/(....)(..)(..)T(..)(..)(..)Z/\1-\2-\3 \4:\5:\6 UTC/')" +%s)
echo "Backup made $stamp; age $(( ($(date +%s) - made) / 3600 )) hours"
[ "$(basename "$UP_AGE")" = "uploads-$stamp.tar.gz.age" ] || fail R1 "the two files are from different backups"
pass R1

remove_links || exit 1
rm -rf "$WORK" && mkdir -p "$WORK"
t0=$(date +%s)

step "R2 Decrypt both files with the offline private key"
age -d -i "$KEY" -o "$WORK/db.dump" "$DB_AGE" || fail R2 "database dump did not decrypt"
age -d -i "$KEY" -o "$WORK/uploads.tar.gz" "$UP_AGE" || fail R2 "uploads archive did not decrypt"
tar -tzf "$WORK/uploads.tar.gz" >/dev/null || fail R2 "uploads archive is not readable"
echo "dump $(stat -c %s "$WORK/db.dump") bytes; uploads archive holds $(tar -tzf "$WORK/uploads.tar.gz" | grep -vc '/$') files"
pass R2

step "R3 Empty PostgreSQL 16 database and full pg_restore"
docker rm -f -v gabai-restore >/dev/null 2>&1 || true
docker run -d --name gabai-restore -e POSTGRES_USER=gabai -e POSTGRES_PASSWORD=drill -e POSTGRES_DB=gabai \
    -p 127.0.0.1:$PORT_DB:5432 postgres:16-alpine >/dev/null
until docker exec gabai-restore pg_isready -U gabai -d gabai >/dev/null 2>&1; do sleep 1; done
sleep 2
r0=$(date +%s)
docker exec -i gabai-restore pg_restore -U gabai -d gabai --exit-on-error < "$WORK/db.dump" || fail R3 "pg_restore reported an error"
echo "pg_restore finished with no errors in $(( $(date +%s) - r0 )) s"
pass R3

step "R4 Row counts against production at backup time"
docker exec -i gabai-restore psql -U gabai -d gabai -At < tests/restore/counts.sql > "$WORK/restored-counts.txt"
paste -d'|' <(tr -d '\r' < "$PROD_COUNTS") "$WORK/restored-counts.txt" | awk -F'|' '{printf "%-45s %-45s %s\n", $1, $2, ($1==$2 ? "same" : "DIFFERENT")}'
diff <(tr -d '\r' < "$PROD_COUNTS") "$WORK/restored-counts.txt" >/dev/null || fail R4 "counts differ from production"
pass R4

step "R5 Migration revision and append-only audit log"
head=$(cd backend && .venv/Scripts/python -m alembic heads 2>/dev/null | awk '{print $1}')
rev=$(docker exec gabai-restore psql -U gabai -d gabai -At -c "select version_num from alembic_version")
echo "restored revision $rev; repo head $head"
[ "$rev" = "$head" ] || fail R5 "restored database is not at the final revision"
for sql in "update audit_log_entries set action = action || ' edited' where id = (select min(id) from audit_log_entries)" \
           "delete from audit_log_entries where id = (select min(id) from audit_log_entries)"; do
    if docker exec gabai-restore psql -U gabai -d gabai -v ON_ERROR_STOP=1 -c "$sql" >/dev/null 2>"$WORK/err.txt"; then
        fail R5 "the audit log accepted: $sql"
    fi
    grep -q "append-only" "$WORK/err.txt" || fail R5 "refused for another reason: $(head -1 "$WORK/err.txt")"
    echo "refused as expected: ${sql%% *} -> $(head -1 "$WORK/err.txt")"
done
pass R5

step "R6 Start the application against the restored database"
mkdir -p "$WORK/app"
git archive HEAD | tar -x -C "$WORK/app"
# Junctions to this laptop's Python environment and model files (not in git).
for d in .venv models; do
    powershell -NoProfile -Command "New-Item -ItemType Junction -Path '$(cygpath -w "$WORK/app/backend/$d")' -Target '$(cygpath -w "$ROOT/backend/$d")'" >/dev/null
done
tar -xzf "$WORK/uploads.tar.gz" -C "$WORK/app/backend"
cd "$WORK/app/backend"
export POSTGRES_PORT=$PORT_DB POSTGRES_PASSWORD=drill ENVIRONMENT=development PYTHONPATH=.
.venv/Scripts/python -c "
from app.core.eventloop import use_selector_loop_on_windows
use_selector_loop_on_windows()
import uvicorn
uvicorn.run('app.main:app', host='127.0.0.1', port=$PORT_API, log_level='warning')" > "$WORK/api.log" 2>&1 &
api_pid=$!
for i in $(seq 60); do
    [ "$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:$PORT_API/api/site)" = 200 ] && break
    sleep 2
done
[ "$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:$PORT_API/api/site)" = 200 ] || fail R6 "application did not start"
echo "application answering on http://127.0.0.1:$PORT_API"
pass R6

step "R7 Every encrypted value and file reads back"
.venv/Scripts/python "$ROOT/tests/restore/check_restored.py" || fail R7 "some data could not be read"
t1=$(date +%s)
newest=$(.venv/Scripts/python "$ROOT/tests/restore/check_restored.py" | sed -n 's/^newest attachment: request \([0-9]*\), attachment \([0-9]*\).*/\1 \2/p')
echo
echo "Now sign in with your administrator account. The same attachment is downloaded"
echo "from gabai.help and from the restored copy and the checksums are compared."
read -r -p "Administrator email: " drill_email
read -r -s -p "Password (not shown): " drill_password; echo
DRILL_EMAIL=$drill_email DRILL_PASSWORD=$drill_password     .venv/Scripts/python "$ROOT/tests/restore/compare_download.py" $newest | tee "$WORK/compare.txt"
unset drill_password
grep -q "RESULT PASS" "$WORK/compare.txt" || fail R7 "live and restored downloads differ"
pass R7

step "R8 Negative checks"
env -u DATA_KEYS .venv/Scripts/python -c "import app.main" > "$WORK/r8.txt" 2>&1 && fail R8 "the application started without DATA_KEYS"
grep -q "DATA_KEYS is not set" "$WORK/r8.txt" || fail R8 "failed for another reason: $(tail -1 "$WORK/r8.txt")"
echo "without DATA_KEYS: the application refuses to start (DATA_KEYS is not set)"
DATA_KEYS="1:$(.venv/Scripts/python -c 'import os,base64;print(base64.b64encode(os.urandom(32)).decode())')" \
    .venv/Scripts/python "$ROOT/tests/restore/check_restored.py" > "$WORK/r8.txt" 2>&1 && fail R8 "data read back with a wrong DATA_KEYS"
grep -q "RESULT FAIL" "$WORK/r8.txt" || fail R8 "failed for another reason: $(tail -1 "$WORK/r8.txt")"
echo "with a wrong DATA_KEYS: encrypted data cannot be read ($(grep RESULT "$WORK/r8.txt"))"
cd "$ROOT"
age-keygen -o "$WORK/wrong-key.txt" 2>/dev/null
age -d -i "$WORK/wrong-key.txt" -o /dev/null "$DB_AGE" > "$WORK/r8.txt" 2>&1 && fail R8 "the backup decrypted with a wrong key"
grep -q "no identity matched" "$WORK/r8.txt" || fail R8 "failed for another reason: $(tail -1 "$WORK/r8.txt")"
echo "with a wrong age key: the backup does not decrypt (no identity matched)"
pass R8

step "R9 Time and data-loss window"
echo "From decryption to a running copy whose data all reads back (R2 to R7, before the sign-in): $(( (t1 - t0) / 60 )) min $(( (t1 - t0) % 60 )) s"
echo "Backup age at the start of the drill: $(( (t0 - made) / 3600 )) hours (changes after the backup would be lost)"
echo
echo "All steps passed. Log: $LOG"
