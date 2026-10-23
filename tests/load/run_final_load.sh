#!/usr/bin/env bash
# Guided load tests on the final build (paper Table 20B). Asks for everything it
# needs, runs the three k6 runs in order and waits for you between them.
#
#   tests/load/run_final_load.sh
#
# Run from the repo root in Git Bash.
set -euo pipefail

BASE="${BASE:-https://gabai.help}"
OUT="${RESULTS_DIR:-tests/load/results}"
PHOTO=test-photo-2mb.jpg
trap 'rm -f "$PHOTO"' EXIT
[ -f tests/load/load_test.js ] || { echo "Run this from the GABAI folder: cd ~/Desktop/Personal/GABAI"; exit 1; }
mkdir -p "$OUT"
say() { echo; echo "------------------------------------------------------------"; printf '%s\n' "$@"; echo "------------------------------------------------------------"; }
wait_enter() { read -r -p ">> $1 Then press Enter. " _; }
stamp() { date '+%H:%M:%S'; }
# k6 saves its summary even when a limit is crossed; with no summary, k6 itself failed.
ran() {
    grep -q "http_req_duration" "$1" && return 0
    echo "k6 did not run properly (see the lines above). Nothing more was run; send Claude the file $1."
    exit 1
}

say "STEP 1 OF 6: the two test accounts" \
    "Type each answer and press Enter. Passwords stay hidden while you type."
read -r -p "Staff test account email: " SE
read -r -s -p "Staff test account password: " SP; echo
read -r -p "Resident test account email: " RE
read -r -s -p "Resident test account password: " RP; echo

say "STEP 2 OF 6: checking both accounts sign in"
check() {
    local code jar
    jar=$(mktemp)
    code=$(curl -s -c "$jar" -o /dev/null -w "%{http_code}" "$BASE/api/auth/login" --data-urlencode "username=$1" --data-urlencode "password=$2") || code=000
    if [ "$code" != 204 ]; then
        rm -f "$jar"
        echo "$3 account did NOT sign in (code $code). Nothing was run. Start this script again and retype it."; exit 1
    fi
    # Signed in, but the account must also have accepted the current terms.
    code=$(curl -s -b "$jar" -o /dev/null -w "%{http_code}" "$BASE/api/notifications?limit=1") || code=000
    rm -f "$jar"
    if [ "$code" != 200 ]; then
        echo "$3 account signs in but can't use the site yet (code $code). Sign in to gabai.help with it in a"
        echo "private window, accept the Terms of Use (and change the password if asked), then start this script again."
        exit 1
    fi
    echo "$3 account: OK"
}
check "$SE" "$SP" Staff
check "$RE" "$RP" Resident
# Any Python on this laptop that has Pillow and numpy will do.
for py in ml/.venv/Scripts/python python; do
    "$py" -c "import PIL, numpy" >/dev/null 2>&1 && break
done
"$py" tests/load/make_test_photo.py "$PHOTO" >/dev/null || { echo "Could not make the test photo. Nothing was run."; exit 1; }
# k6 opens files relative to the test script, so pass the full path.
PHOTO_PATH="$(pwd -W)/$PHOTO"
echo "Test photo made: $PHOTO"

say "STEP 3 OF 6: run 1 of 3 (same test as on 4 October, about 2 minutes)"
wait_enter "Open DigitalOcean > your droplet > Graphs in the browser and leave it open."
echo "Run 1 started at $(stamp)"
k6 run -e BASE="$BASE" -e STAFF_EMAIL="$SE" -e STAFF_PASSWORD="$SP" -e RESIDENT_EMAIL="$RE" -e RESIDENT_PASSWORD="$RP" \
    tests/load/load_test.js 2>&1 | tee "$OUT/k6-load-final.txt" || true
ran "$OUT/k6-load-final.txt"
echo "Run 1 finished at $(stamp)"

say "STEP 4 OF 6: run 2 of 3 (same test, each request with a 2 MB photo, about 2 minutes)"
echo "First clean up run 1: in the browser, sign in to gabai.help as staff and close the"
echo "10 requests whose description starts with LOAD TEST (open each, Mark in progress, Mark resolved, Close)."
wait_enter "When all 10 are closed,"
echo "Run 2 started at $(stamp)"
k6 run -e BASE="$BASE" -e STAFF_EMAIL="$SE" -e STAFF_PASSWORD="$SP" -e RESIDENT_EMAIL="$RE" -e RESIDENT_PASSWORD="$RP" \
    -e PHOTO="$PHOTO_PATH" tests/load/load_test.js 2>&1 | tee "$OUT/k6-load-photo-final.txt" || true
ran "$OUT/k6-load-photo-final.txt"
echo "Run 2 finished at $(stamp)"

say "STEP 5 OF 6: run 3 of 3 (stress test, 20 then 40 then 60 sessions, about 5 minutes)"
echo "First clean up run 2 the same way: close the 10 new LOAD TEST requests."
wait_enter "When all 10 are closed,"
echo "Run 3 started at $(stamp)"
k6 run -e BASE="$BASE" -e STAFF_EMAIL="$SE" -e STAFF_PASSWORD="$SP" tests/load/stress_test.js 2>&1 | tee "$OUT/k6-stress-final.txt" || true
ran "$OUT/k6-stress-final.txt"
echo "Run 3 finished at $(stamp)"

unset SP RP
say "STEP 6 OF 6: graphs" \
    "In DigitalOcean > Graphs, take screenshots of CPU and Memory that show the three runs" \
    "(the start and finish times are printed above). Save them in tests/load/results/." \
    "Load tests done. The results are saved in tests/load/results/."
