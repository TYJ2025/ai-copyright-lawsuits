#!/bin/bash
# 每月刷新 cases/ 子系統（launchd: com.tyj.refresh-cases）
#
# 流程：sync manifest（自 cases.json）→ batch_refresh 全部案件 → 重生 _index.md
# git 交給 auto-push.sh（已納入 cases/），本檔不下 git 指令。
# 注意：不要用 set -e —— launchctl 相關指令即使成功也會回非零 exit code。

PROJECT_DIR="$HOME/ClaudeProjects/AI Copyright Lawsuits Worldwide"
LOG_FILE="$PROJECT_DIR/.refresh-cases.log"

cd "$PROJECT_DIR" || exit 1

echo "" >> "$LOG_FILE"
echo "========================================" >> "$LOG_FILE"
echo "$(date '+%Y/%m/%d %H:%M') — refresh-cases 開始" >> "$LOG_FILE"

if [ -z "$COURTLISTENER_TOKEN" ]; then
  echo "✗ 未設定 COURTLISTENER_TOKEN，中止。請在 plist 的 EnvironmentVariables 補上。" >> "$LOG_FILE"
  exit 1
fi

# 1. manifest 與 cases.json 對齊（新案自動納入、已刪案件自動移除）
python3 scripts/sync_cases_manifest.py --apply >> "$LOG_FILE" 2>&1

# 2. 批次抓 docket（--delay 1 秒保護 API；CL 上限 5,000 req/hr，119 件約 300 次呼叫）
python3 scripts/batch_refresh.py --all --delay 1.0 >> "$LOG_FILE" 2>&1
rc=$?
if [ $rc -ne 0 ]; then
  echo "✗ batch_refresh.py 失敗 rc=$rc（後續步驟仍執行，以免 _index 停留在舊狀態）" >> "$LOG_FILE"
fi

# 3. 重生比對索引
python3 scripts/rebuild_case_index.py >> "$LOG_FILE" 2>&1

echo "$(date '+%Y/%m/%d %H:%M') — refresh-cases 完成（git 由 auto-push.sh 處理）" >> "$LOG_FILE"
