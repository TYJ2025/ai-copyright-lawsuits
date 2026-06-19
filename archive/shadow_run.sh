#!/bin/bash
# shadow_run.sh — Phase 5 shadow-run post-process for daily-brief.
#
# Runs AFTER daily-brief.sh has finished its claude -p edit of dashboard.html.
# Verifies the new (data/*.json → build.py → dashboard.html.shadow) pipeline
# would have produced the SAME content as the live dashboard.html.
#
# Non-destructive: writes only to shadow-run.log. Working tree changes to
# data/*.json are reverted at end (unless check fails — kept for inspection).
# Failure is logged but DOES NOT propagate — daily-brief's exit code is the
# canonical signal for production health.
#
# Cutover criterion: 7 consecutive days of [✓ PASS] before we switch
# daily-brief to use the new pipeline as primary.

set -uo pipefail  # intentionally NOT set -e

REPO_DIR="/Users/jesuisjane/ClaudeProjects/AI Copyright Lawsuits Worldwide"
LOG="$REPO_DIR/shadow-run.log"

cd "$REPO_DIR" || exit 0

ts() { date '+%Y/%m/%d %H:%M:%S'; }
log() { echo "$(ts) | $*" >> "$LOG"; }
log_block() { sed 's/^/      /' >> "$LOG"; }

# Log rotation: cap at ~1000 lines
if [ -f "$LOG" ]; then
    LINES=$(wc -l < "$LOG" 2>/dev/null | tr -d ' ')
    if [ -n "$LINES" ] && [ "$LINES" -gt 1000 ]; then
        tail -n 500 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
        log "Log rotated."
    fi
fi

log "===== shadow run start ====="

# Step 1: re-extract data/ from dashboard.html (just edited by daily-brief).
# This is a real migrate run that writes to data/*.json (working tree).
log "[1/3] migrate_html_to_json.py …"
MIGRATE_OUT=$(/usr/bin/env python3 scripts/migrate_html_to_json.py 2>&1)
MIGRATE_RC=$?
if [ $MIGRATE_RC -ne 0 ]; then
    log "  ✗ migrate failed (rc=$MIGRATE_RC):"
    echo "$MIGRATE_OUT" | log_block
    log "===== shadow run done (failed at migrate) ====="
    exit 0
fi
log "  ✓ data/*.json refreshed from current dashboard.html"

# Step 2: build.py --diff produces dashboard.html.new. Diff command inside
# returns non-zero when differences exist (normal!); that's not an error
# for our purposes — we run our own semantic check below.
log "[2/3] build.py --diff …"
BUILD_OUT=$(/usr/bin/env python3 scripts/build.py --diff 2>&1)
BUILD_RC=$?
if [ ! -f dashboard.html.new ]; then
    log "  ✗ build did not produce dashboard.html.new (rc=$BUILD_RC):"
    echo "$BUILD_OUT" | log_block
    log "===== shadow run done (failed at build) ====="
    git checkout HEAD -- data/ 2>/dev/null
    exit 0
fi
log "  ✓ dashboard.html.new produced ($(wc -c < dashboard.html.new) bytes)"

# Step 3: semantic equivalence check — the real test
log "[3/3] semantic equivalence check:"
CHECK_OUT=$(
    /usr/bin/env python3 <<'PY'
import sys
sys.path.insert(0, "scripts")
from migrate_html_to_json import find_const_body, js_literal_to_python

CONSTS = ["cases", "caseSources", "fairUseCases", "officialReports",
          "newsItems", "newsArchive", "timelineEvents"]

orig = open("dashboard.html", encoding="utf-8").read()
new  = open("dashboard.html.new", encoding="utf-8").read()

all_ok = True
results = []
for name in CONSTS:
    try:
        _, _, b1 = find_const_body(orig, name)
        _, _, b2 = find_const_body(new,  name)
        same = js_literal_to_python(b1) == js_literal_to_python(b2)
        if not same:
            all_ok = False
        results.append(("✓" if same else "✗", name))
    except Exception as e:
        all_ok = False
        results.append(("✗", f"{name} ({type(e).__name__}: {e})"))

for sym, name in results:
    print(f"{sym} {name}")
print("PASS" if all_ok else "FAIL")
sys.exit(0 if all_ok else 1)
PY
)
CHECK_RC=$?
echo "$CHECK_OUT" | log_block

# Cleanup .new (gitignored anyway, but keep working tree tidy)
rm -f dashboard.html.new build-diff.txt

# Revert data/ working changes when check passed (keep tree clean during
# the dual-run week). When check failed, KEEP data/ dirty so the next
# manual inspection can see what migrate produced.
if [ $CHECK_RC -eq 0 ]; then
    git checkout HEAD -- data/ 2>/dev/null
    log "[✓ PASS] data/ reverted (clean working tree)"
else
    log "[✗ FAIL] data/ left dirty for inspection (run 'git diff data/' to see)"
fi

log "===== shadow run done ====="
log ""
exit 0
