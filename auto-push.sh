#!/bin/bash
# Auto-push dashboard updates to GitHub
# Runs daily via launchd

REPO_DIR="$HOME/Desktop/AI_Lawsuits/AI Copyright Lawsuits Worldwide"
LOG_FILE="$REPO_DIR/.auto-push.log"

cd "$REPO_DIR" || exit 1

# Remove stale lock files left by sandbox or crashed git processes
for lockfile in .git/index.lock .git/config.lock; do
    if [ -f "$lockfile" ]; then
        echo "$(date '+%Y/%m/%d %H:%M') — Removing stale $lockfile" >> "$LOG_FILE"
        rm -f "$lockfile"
    fi
done

# Check if there are any changes to push
if git diff --quiet HEAD -- dashboard.html 2>/dev/null && git diff --cached --quiet HEAD -- dashboard.html 2>/dev/null; then
    echo "$(date '+%Y/%m/%d %H:%M') — No changes to push." >> "$LOG_FILE"
    exit 0
fi

# Stage, commit, and push
git add dashboard.html
git commit -m "Daily update: $(date '+%Y/%m/%d')"
git push origin main >> "$LOG_FILE" 2>&1

if [ $? -eq 0 ]; then
    echo "$(date '+%Y/%m/%d %H:%M') — Push successful." >> "$LOG_FILE"
else
    echo "$(date '+%Y/%m/%d %H:%M') — Push FAILED." >> "$LOG_FILE"
fi
