#!/bin/bash
# Auto-push dashboard updates to GitHub.
# Triggered by launchd (com.tyj.dashboard-autopush):
#   - WatchPaths:  dashboard.html changes -> run
#   - StartInterval: every 6h as safety net
#   - RunAtLoad:   once on agent load
# See com.tyj.dashboard-autopush.plist

REPO_DIR="/Users/jesuisjane/Documents/Claude/Projects/AI Copyright Lawsuits Worldwide"
LOG_FILE="$REPO_DIR/.auto-push.log"
FAIL_STATE="$REPO_DIR/.auto-push.failstate"

log() { echo "$(date '+%Y/%m/%d %H:%M') — $*" >> "$LOG_FILE" 2>/dev/null; }

# --- Log rotation: cap at ~500 lines ---------------------------------------
if [ -f "$LOG_FILE" ]; then
    LINES=$(wc -l < "$LOG_FILE" 2>/dev/null | tr -d ' ')
    if [ -n "$LINES" ] && [ "$LINES" -gt 500 ]; then
        tail -n 300 "$LOG_FILE" > "$LOG_FILE.tmp" && mv "$LOG_FILE.tmp" "$LOG_FILE"
        log "Log rotated (kept last 300 lines)."
    fi
fi

cd "$REPO_DIR" || { log "Cannot cd to $REPO_DIR"; exit 1; }

# --- Load SSH keys from macOS Keychain -------------------------------------
# Keys must have been added once via: ssh-add --apple-use-keychain <keyfile>
if [ -x /usr/bin/ssh-add ]; then
    /usr/bin/ssh-add --apple-load-keychain >/dev/null 2>&1
fi

# --- Clean stale lock files ------------------------------------------------
for lockfile in .git/index.lock .git/config.lock; do
    if [ -f "$lockfile" ]; then
        log "Removing stale $lockfile"
        rm -f "$lockfile"
    fi
done

# --- Decide whether we need to act -----------------------------------------
NEED_COMMIT=0
NEED_PUSH=0

if ! git diff --quiet HEAD -- dashboard.html 2>/dev/null; then NEED_COMMIT=1; fi
if ! git diff --cached --quiet HEAD -- dashboard.html 2>/dev/null; then NEED_COMMIT=1; fi

# Fetch remote to compare (quiet; don't abort on network failure).
git fetch origin --quiet 2>/dev/null
LOCAL=$(git rev-parse @ 2>/dev/null || echo "")
REMOTE=$(git rev-parse @{u} 2>/dev/null || echo "")
if [ -n "$LOCAL" ] && [ -n "$REMOTE" ] && [ "$LOCAL" != "$REMOTE" ]; then
    AHEAD=$(git rev-list --count "$REMOTE..$LOCAL" 2>/dev/null || echo "0")
    if [ "$AHEAD" != "0" ]; then NEED_PUSH=1; fi
fi

if [ "$NEED_COMMIT" -eq 0 ] && [ "$NEED_PUSH" -eq 0 ]; then
    # Silent no-op. Reset any previous fail state.
    [ -f "$FAIL_STATE" ] && rm -f "$FAIL_STATE"
    exit 0
fi

# --- Commit if needed, then push -------------------------------------------
if [ "$NEED_COMMIT" -eq 1 ]; then
    git add dashboard.html
    git commit -m "Daily update: $(date '+%Y/%m/%d')" >> "$LOG_FILE" 2>&1
fi

git push origin HEAD >> "$LOG_FILE" 2>&1
RC=$?

if [ $RC -eq 0 ]; then
    log "Push successful."
    [ -f "$FAIL_STATE" ] && rm -f "$FAIL_STATE"
    exit 0
fi

# --- Failure handling with throttled logging --------------------------------
# Count consecutive failures; only write to log for the 1st, 3rd, 10th, ... failure.
FAILS=0
if [ -f "$FAIL_STATE" ]; then
    FAILS=$(cat "$FAIL_STATE" 2>/dev/null)
    FAILS=${FAILS:-0}
fi
FAILS=$((FAILS + 1))
echo "$FAILS" > "$FAIL_STATE"

case $FAILS in
    1|3|10|30|100)
        log "Push FAILED (exit $RC, consecutive failures: $FAILS)."
        ;;
    *)
        # silent — avoids log spam on sustained outage
        ;;
esac
exit $RC
