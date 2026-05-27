#!/bin/bash
# install-weekly-check.sh
# 一行部署 com.tyj.weekly-new-cases launchd agent
#
# 用法：
#   export COURTLISTENER_TOKEN=<your-token-here>
#   bash scripts/install-weekly-check.sh
#
# 做的事：
#   1. 驗證 token 已設定
#   2. 從 repo 內的 com.tyj.weekly-new-cases.plist 複製一份到 ~/Library/LaunchAgents/
#   3. 把 COURTLISTENER_TOKEN 注入到複製出來的 plist 的 EnvironmentVariables
#   4. 卸載舊版（若已 load）→ load 新版
#   5. 立刻觸發一次測試運行（kickstart），dry-run 不會打 API、跑真實設定才會
#
# 注意：
#   - 不在 repo 內的 plist 加 token（避免 commit 進 git）
#   - ~/Library/LaunchAgents/ 那份才是被 launchctl 載入的 canonical 版

set -u  # 不用 -e（launchctl 即使成功也回非零 exit code）

REPO_DIR="/Users/jesuisjane/ClaudeProjects/AI Copyright Lawsuits Worldwide"
PLIST_SRC="$REPO_DIR/com.tyj.weekly-new-cases.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.tyj.weekly-new-cases.plist"
LABEL="com.tyj.weekly-new-cases"

# 顏色（terminal-friendly）
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m'

ok()    { echo -e "${GREEN}✓${NC} $*"; }
warn()  { echo -e "${YELLOW}⚠${NC} $*"; }
fail()  { echo -e "${RED}✗${NC} $*"; exit 1; }

# ── 1. 驗證 token ───────────────────────────────────────────────
if [ -z "${COURTLISTENER_TOKEN:-}" ]; then
    fail "請先 export COURTLISTENER_TOKEN=<token>，再執行本腳本。
   token 從 https://www.courtlistener.com/profile/api/ 取得。"
fi
# 簡單防呆：CL token 看起來是 40 字元 hex
if ! echo "$COURTLISTENER_TOKEN" | grep -qE '^[a-f0-9]{30,80}$'; then
    warn "TOKEN 格式不像 CourtListener token (預期 40 字元 hex)，但仍會繼續。"
fi
ok "Token 已偵測（前 8 字元：${COURTLISTENER_TOKEN:0:8}...）"

# ── 2. 確認 plist 來源存在 ────────────────────────────────────────
[ -f "$PLIST_SRC" ] || fail "找不到 plist 來源：$PLIST_SRC"
ok "找到 plist 來源"

# ── 3. 確保 LaunchAgents 目錄存在 ─────────────────────────────────
mkdir -p "$HOME/Library/LaunchAgents"

# ── 4. 複製 plist 到目的地，注入 token ────────────────────────────
# 把 plist 內 EnvironmentVariables dict 末尾插入 COURTLISTENER_TOKEN 條目
# （原 plist 已預留 placeholder，用 awk 注入避免破壞 XML 結構）

# 先 dump 原檔（不含 token 註解）
TMP_PLIST=$(mktemp)
cat "$PLIST_SRC" > "$TMP_PLIST"

# 把 COURTLISTENER_TOKEN 插在 </dict> 之前（EnvironmentVariables 內的最後一個 </dict>）
# 用 python 處理 XML 比 sed 安全得多
python3 - "$TMP_PLIST" "$COURTLISTENER_TOKEN" <<'PYEOF'
import plistlib, sys
path, token = sys.argv[1], sys.argv[2]
with open(path, 'rb') as f:
    data = plistlib.load(f)
data.setdefault('EnvironmentVariables', {})['COURTLISTENER_TOKEN'] = token
with open(path, 'wb') as f:
    plistlib.dump(data, f)
PYEOF

if [ $? -ne 0 ]; then
    rm -f "$TMP_PLIST"
    fail "Token 注入失敗（plistlib 寫入錯誤）"
fi

mv "$TMP_PLIST" "$PLIST_DST"
chmod 600 "$PLIST_DST"  # 內含 token，限制權限
ok "plist 已寫入 ${PLIST_DST} (含 token, 權限 600)"

# ── 5. 卸載舊版（若已 load）──────────────────────────────────────
if launchctl list 2>/dev/null | grep -q "$LABEL"; then
    launchctl unload "$PLIST_DST" 2>/dev/null
    ok "舊版 agent 已 unload"
fi

# ── 6. Load 新版 ───────────────────────────────────────────────
launchctl load "$PLIST_DST"
# launchctl load 即使成功也可能回非零，不能用 $? 判斷；改檢查是否 listed
sleep 1
if launchctl list 2>/dev/null | grep -q "$LABEL"; then
    ok "Agent 已 load：$LABEL"
else
    fail "Agent 未出現在 launchctl list；檢查 plist 語法。"
fi

# ── 7. 立刻測試觸發一次（會打真實 API）──────────────────────────
echo
read -p "要不要現在立刻觸發一次測試運行？（會打真實 CourtListener API）[y/N] " yn
if [[ "$yn" =~ ^[Yy]$ ]]; then
    launchctl kickstart -k "gui/$(id -u)/$LABEL"
    echo
    ok "已 kickstart。等 30 秒讓它跑..."
    sleep 30
    echo
    echo "── stdout log（最後 30 行）──"
    tail -30 "$REPO_DIR/.weekly-new-cases.stdout.log" 2>/dev/null || warn "log 還沒生出來"
    echo
    echo "── 報告檔 ──"
    LATEST=$(ls -t "$REPO_DIR/cases/_weekly_new_cases_"*.md 2>/dev/null | head -1)
    if [ -n "$LATEST" ]; then
        ok "已生出：$LATEST"
        echo "  $ head -20 \"$LATEST\""
    else
        warn "報告檔還沒產出；可能還在跑、或 API 出錯"
    fi
else
    echo "好，等下週一 08:00 自動跑。"
fi

echo
echo "完成。"
echo "  • 排程：每週一 08:00 自動執行"
echo "  • 手動觸發：launchctl kickstart -k gui/\$(id -u)/$LABEL"
echo "  • 看 log：    tail -50 \"$REPO_DIR/.weekly-new-cases.stdout.log\""
echo "  • 移除排程：  launchctl unload \"$PLIST_DST\" && rm \"$PLIST_DST\""
