#!/bin/bash
# 每週以起訴狀核對 claims 標籤（launchd: com.tyj.verify-claims）
# 注意：不要用 set -e —— launchctl 相關指令即使成功也會回非零 exit code。

PROJECT_DIR="$HOME/ClaudeProjects/AI Copyright Lawsuits Worldwide"
LOG_FILE="$PROJECT_DIR/.verify-claims.log"
BATCH="${VERIFY_CLAIMS_BATCH:-25}"

cd "$PROJECT_DIR" || exit 1

echo "" >> "$LOG_FILE"
echo "========================================" >> "$LOG_FILE"
echo "$(date '+%Y/%m/%d %H:%M') — verify_claims 開始（batch=$BATCH）" >> "$LOG_FILE"

if [ -z "$COURTLISTENER_TOKEN" ]; then
  echo "✗ 未設定 COURTLISTENER_TOKEN，中止。請在 plist 的 EnvironmentVariables 補上。" >> "$LOG_FILE"
  exit 1
fi

# 只跑尚未核對且有 docket id 者。2026-08-05 起依 YJ 指示以起訴狀結果覆寫 claims
# （舊標籤存入 claimsPrevious 可回溯），不一致清單仍會留在 log。
python3 scripts/verify_claims.py --pending --limit "$BATCH" --apply --overwrite-claims >> "$LOG_FILE" 2>&1
rc=$?

if [ $rc -ne 0 ]; then
  echo "✗ verify_claims.py 失敗 rc=$rc" >> "$LOG_FILE"
  exit $rc
fi

# 標籤用語把關（正規化 + 驗證），再重生 dashboard；git 交給 auto-push.sh
python3 scripts/normalize_claims.py --apply >> "$LOG_FILE" 2>&1
python3 scripts/validate_data.py     >> "$LOG_FILE" 2>&1
python3 scripts/build.py             >> "$LOG_FILE" 2>&1

python3 scripts/verify_claims.py --status >> "$LOG_FILE" 2>&1
echo "$(date '+%Y/%m/%d %H:%M') — verify_claims 完成" >> "$LOG_FILE"
