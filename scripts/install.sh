#!/bin/bash
# 安裝 / 解除安裝 com.tyj.ai-copyright-brief launchd agent
# 用法：
#   ./scripts/install.sh install    # 安裝並啟用
#   ./scripts/install.sh uninstall  # 停用並移除
#   ./scripts/install.sh status     # 查詢狀態
#   ./scripts/install.sh test       # 立即手動執行一次（不等 07:07）

set -euo pipefail

REPO_DIR="/Users/jesuisjane/ClaudeProjects/AI Copyright Lawsuits Worldwide"
PLIST_NAME="com.tyj.ai-copyright-brief.plist"
PLIST_SRC="$REPO_DIR/$PLIST_NAME"
PLIST_DST="$HOME/Library/LaunchAgents/$PLIST_NAME"
LABEL="com.tyj.ai-copyright-brief"
SCRIPT_PATH="$REPO_DIR/scripts/daily-brief.sh"

cmd=${1:-status}

case "$cmd" in
    install)
        echo "→ 確認 daily-brief.sh 可執行..."
        chmod +x "$SCRIPT_PATH"
        echo "→ 複製 plist 到 ~/Library/LaunchAgents/ ..."
        cp "$PLIST_SRC" "$PLIST_DST"
        # plist 不能是 700，必須 644
        chmod 644 "$PLIST_DST"
        echo "→ 若先前已載入，先卸載..."
        launchctl unload "$PLIST_DST" 2>/dev/null || true
        echo "→ 載入 launchd agent..."
        launchctl load -w "$PLIST_DST"
        echo "✅ 已安裝：每日 07:07 自動執行"
        echo "   狀態：launchctl list | grep $LABEL"
        ;;
    uninstall)
        if [ -f "$PLIST_DST" ]; then
            launchctl unload "$PLIST_DST" 2>/dev/null || true
            rm -f "$PLIST_DST"
            echo "✅ 已移除 launchd agent"
        else
            echo "（$PLIST_DST 不存在，不用移除）"
        fi
        ;;
    status)
        echo "=== launchctl list ==="
        launchctl list | grep "$LABEL" || echo "（agent 未載入）"
        echo ""
        echo "=== plist 檔案 ==="
        ls -la "$PLIST_DST" 2>/dev/null || echo "（$PLIST_DST 不存在）"
        echo ""
        echo "=== 最近 20 行 daily-brief log ==="
        tail -20 "$REPO_DIR/.daily-brief.log" 2>/dev/null || echo "（尚無 log）"
        ;;
    test)
        echo "→ 立即手動觸發 daily-brief（不經 launchd）..."
        bash "$SCRIPT_PATH"
        echo ""
        echo "=== 最近 30 行 daily-brief log ==="
        tail -30 "$REPO_DIR/.daily-brief.log" 2>/dev/null
        ;;
    kick)
        echo "→ 透過 launchctl 立即啟動一次..."
        launchctl kickstart -k "gui/$(id -u)/$LABEL"
        echo "✅ 已觸發；查看 log："
        echo "   tail -f \"$REPO_DIR/.daily-brief.log\""
        ;;
    *)
        echo "用法：$0 {install|uninstall|status|test|kick}"
        exit 1
        ;;
esac
