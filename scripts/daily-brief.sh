#!/bin/bash
# AI 著作權訴訟每日快訊 — Claude Code 執行腳本
# 由 launchd (com.tyj.ai-copyright-brief) 每日 07:07 觸發
# 流程：
#   1. 呼叫 claude -p 跑 daily-brief-prompt.md
#   2. Claude 使用 WebSearch + Edit 更新 dashboard.html
#   3. dashboard.html 一旦被改，另一個 launchd agent
#      (com.tyj.dashboard-autopush) 會自動 commit/push 到 GitHub Pages
#
# 本腳本不直接 commit/push，保持單一職責。

set -u

REPO_DIR="/Users/jesuisjane/ClaudeProjects/AI Copyright Lawsuits Worldwide"
PROMPT_FILE="$REPO_DIR/scripts/daily-brief-prompt.md"
LOG_FILE="$REPO_DIR/.daily-brief.log"
STATE_FILE="$REPO_DIR/.daily-brief.state"

# 確保 PATH 涵蓋 claude CLI 可能安裝位置（Homebrew / 使用者安裝）
NVM_NODE_BIN="$(ls -dt "$HOME"/.nvm/versions/node/*/bin 2>/dev/null | head -1)"
export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:$HOME/.claude/local:${NVM_NODE_BIN:+$NVM_NODE_BIN:}/usr/bin:/bin:/usr/sbin:/sbin"

log() {
    echo "$(date '+%Y/%m/%d %H:%M:%S') — $*" >> "$LOG_FILE" 2>/dev/null
}

# --- Log rotation: 超過 1000 行時裁切到最後 500 行 ---
if [ -f "$LOG_FILE" ]; then
    LINES=$(wc -l < "$LOG_FILE" 2>/dev/null | tr -d ' ')
    if [ -n "$LINES" ] && [ "$LINES" -gt 1000 ]; then
        tail -n 500 "$LOG_FILE" > "$LOG_FILE.tmp" && mv "$LOG_FILE.tmp" "$LOG_FILE"
        log "Log rotated (kept last 500 lines)."
    fi
fi

log "===== Daily brief start ====="

cd "$REPO_DIR" || { log "Cannot cd to $REPO_DIR"; exit 1; }

# --- 定位 claude CLI ---
CLAUDE_BIN="$(command -v claude 2>/dev/null || true)"
if [ -z "$CLAUDE_BIN" ]; then
    for candidate in \
        "/opt/homebrew/bin/claude" \
        "/usr/local/bin/claude" \
        "$HOME/.claude/local/claude" \
        "$HOME/.local/bin/claude" \
        "$HOME"/.nvm/versions/node/*/bin/claude; do
        if [ -x "$candidate" ]; then CLAUDE_BIN="$candidate"; break; fi
    done
fi
if [ -z "$CLAUDE_BIN" ] || [ ! -x "$CLAUDE_BIN" ]; then
    log "FATAL: claude CLI not found in PATH — aborting."
    exit 127
fi
log "Using claude CLI: $CLAUDE_BIN"

if [ ! -f "$PROMPT_FILE" ]; then
    log "FATAL: prompt file missing: $PROMPT_FILE"
    exit 2
fi

# --- 呼叫 claude headless ---
# -p / --print                       : 非互動 headless 模式
# --dangerously-skip-permissions     : 自動接受所有工具使用（launchd 無法互動應答，
#                                      所以必須 skip；風險由 prompt 內硬性限制約束）
# --add-dir                          : 明確允許工作目錄
#
# 若要改用白名單制，可移除 --dangerously-skip-permissions，改加：
#   --permission-mode acceptEdits
#   --allowed-tools "Read,Edit,Glob,Grep,WebSearch,WebFetch,Bash"
# 但不同版本的 Claude Code flag 名稱略有差異；skip-permissions 最穩定。

PROMPT_CONTENT=$(cat "$PROMPT_FILE")

log "Invoking claude (headless)..."
# 注意：
# 1) 移除 --add-dir：claude 2.1.117 在 `--add-dir <path>` 後面接 prompt 會把
#    prompt 當成路徑，導致卡住等 stdin。--dangerously-skip-permissions 已
#    允許任意目錄存取，--add-dir 非必要。
# 2) 加 </dev/null：保證 stdin 為空，避免 CLI 誤判成互動模式。
# 3) 偵測 timeout / gtimeout：macOS 預設無 timeout 指令，Homebrew coreutils
#    會裝成 gtimeout；兩者都沒有就裸執行（claude 自己有 timeout 機制）。
TIMEOUT_BIN=""
if command -v timeout >/dev/null 2>&1; then
    TIMEOUT_BIN="$(command -v timeout) 600"
elif command -v gtimeout >/dev/null 2>&1; then
    TIMEOUT_BIN="$(command -v gtimeout) 600"
fi

CLAUDE_OUTPUT=$(
    cd "$REPO_DIR" && $TIMEOUT_BIN "$CLAUDE_BIN" \
        --print \
        --dangerously-skip-permissions \
        "$PROMPT_CONTENT" </dev/null 2>&1
)
RC=$?

# 輸出長度夾取，避免 log 爆掉
if [ ${#CLAUDE_OUTPUT} -gt 20000 ]; then
    CLAUDE_OUTPUT="${CLAUDE_OUTPUT:0:10000}
...[truncated]...
${CLAUDE_OUTPUT: -5000}"
fi

{
    echo "----- claude output (rc=$RC) -----"
    echo "$CLAUDE_OUTPUT"
    echo "----- end output -----"
} >> "$LOG_FILE" 2>/dev/null

if [ $RC -ne 0 ]; then
    log "claude exited with rc=$RC"
    echo "$(date '+%Y/%m/%d')|fail|rc=$RC" > "$STATE_FILE"
    exit $RC
fi

# --- 偵測 Claude 是否真有改到內容（必須在 sed 之前判斷） ---
if git diff --quiet HEAD -- dashboard.html 2>/dev/null; then
    HAD_CONTENT_CHANGE=0
else
    HAD_CONTENT_CHANGE=1
    CHANGE_LINES=$(git diff --stat HEAD -- dashboard.html 2>/dev/null | tail -1)
fi

# --- 永遠戳 footer 日期，當作 cron heartbeat（證明今天有跑過） ---
TODAY=$(date '+%Y-%m-%d')
/usr/bin/sed -i '' "s/每日快訊最近更新: [0-9-]*/每日快訊最近更新: $TODAY/" "$REPO_DIR/dashboard.html"
log "Footer date stamped to $TODAY"

if [ "$HAD_CONTENT_CHANGE" -eq 1 ]; then
    log "dashboard.html updated: $CHANGE_LINES"
    echo "$(date '+%Y/%m/%d')|updated|$CHANGE_LINES" > "$STATE_FILE"
else
    log "No new cases today; footer date bumped as heartbeat."
    echo "$(date '+%Y/%m/%d')|heartbeat" > "$STATE_FILE"
fi
log "auto-push.sh will pick it up via WatchPaths."

log "===== Daily brief done ====="
exit 0
