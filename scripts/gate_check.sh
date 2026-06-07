#!/bin/bash
# gate_check.sh — Phase 6 cutover GATE 檢查（本機跑，因 shadow-run.log 是 gitignored）
#
# 判斷 shadow-run.log 是否已連續 N 天（預設 7）[✓ PASS] 且零 FAIL。
# 通過 → exit 0 並提示可依 REFACTOR-CUTOVER-PLAN.md 執行 Phase 6。
# 未通過 → exit 1 並說明還差幾天 / 哪天 FAIL。
#
# 用法：
#   bash scripts/gate_check.sh          # 預設門檻 7 天
#   bash scripts/gate_check.sh 5        # 自訂門檻

set -uo pipefail

REPO_DIR="/Users/jesuisjane/ClaudeProjects/AI Copyright Lawsuits Worldwide"
LOG="$REPO_DIR/shadow-run.log"
THRESHOLD="${1:-7}"

if [ ! -f "$LOG" ]; then
    echo "✗ 找不到 $LOG — 影子執行可能還沒跑過。"
    exit 1
fi

/usr/bin/env python3 - "$LOG" "$THRESHOLD" <<'PY'
import sys, re
from collections import OrderedDict

log_path, threshold = sys.argv[1], int(sys.argv[2])

# 每次影子執行的結論行： "YYYY/MM/DD HH:MM:SS | [✓ PASS] ..." 或 "[✗ FAIL] ..."
verdict_re = re.compile(r'^(\d{4}/\d{2}/\d{2}).*\[(✓ PASS|✗ FAIL)\]')

# 每天保留最後一次結論（同日多跑以最後為準）
by_day = OrderedDict()
with open(log_path, encoding="utf-8") as f:
    for line in f:
        m = verdict_re.match(line.strip())
        if m:
            day, v = m.group(1), m.group(2)
            by_day[day] = "PASS" if "PASS" in v else "FAIL"

days = list(by_day.items())
if not days:
    print("✗ shadow-run.log 內找不到任何 PASS/FAIL 結論行。")
    sys.exit(1)

# 從最近往回數，連續 PASS 幾天（遇 FAIL 中斷）
trailing = 0
first_fail = None
for day, v in reversed(days):
    if v == "PASS":
        trailing += 1
    else:
        first_fail = day
        break

total_pass = sum(1 for _, v in days if v == "PASS")
total_fail = sum(1 for _, v in days if v == "FAIL")
span = f"{days[0][0]} → {days[-1][0]}"

print(f"影子執行紀錄：{len(days)} 個執行日（{span}）")
print(f"  PASS={total_pass}  FAIL={total_fail}")
print(f"  最近連續 PASS：{trailing} 天（門檻 {threshold}）")
if first_fail:
    print(f"  ⚠ 連續 PASS 在 {first_fail} 被 FAIL 中斷")
print()

if trailing >= threshold and total_fail == 0:
    print(f"✅ GATE 通過：連續 {trailing} 天 PASS、零 FAIL。")
    print("   可依 REFACTOR-CUTOVER-PLAN.md 執行 Phase 6 切換（先修 footer placeholder）。")
    sys.exit(0)
elif trailing >= threshold and total_fail > 0:
    print(f"✅ 最近連續 {trailing} 天 PASS 已達門檻，但歷史曾有 {total_fail} 次 FAIL。")
    print("   建議人工確認那些 FAIL 是早期除錯殘留還是真問題，再決定切換。")
    sys.exit(0)
else:
    need = threshold - trailing
    print(f"⏳ GATE 未達標：還差 {need} 天連續 PASS。不要切換，繼續觀察。")
    sys.exit(1)
PY
