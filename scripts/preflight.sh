#!/bin/bash
# preflight.sh — push 前模擬 GitHub Actions 驗證，抓出「本機通過但 CI 失敗」
#
# 2026-08-08 踩過的坑：templates/dashboard.template.html 漏 commit，本機工作區有
# {{CLAIMS_VOCAB_JSON}} 佔位符所以測起來正常，但 CI 從 HEAD checkout 就找不到，
# build.py --check 直接失敗。本腳本從 HEAD 解出乾淨副本再驗，與 CI 行為一致。
#
# 用法：
#   ./scripts/preflight.sh          # 驗 HEAD（已 commit 的內容）
#   ./scripts/preflight.sh --staged # 驗 HEAD + 已 git add 但未 commit 者
#
# 注意：不要用 set -e —— 要自己收 exit code 才能完整報告每一項結果。

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR" || exit 1

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# 殘留的 index.lock 會讓 git write-tree / git add 全部失敗，先明確檢查
if [ -f .git/index.lock ]; then
  echo "✗ 偵測到殘留的 .git/index.lock（多為前次 git 程序異常結束）"
  echo "  確認沒有其他 git 程序在跑之後，執行（用 /bin/rm 繞過可能的 rm 別名）："
  echo "    /bin/rm -f .git/index.lock .git/HEAD.lock"
  echo "    find .git/objects -name 'tmp_obj_*' -delete"
  echo "  刪完用 ls .git/index.lock 確認真的不見了（某些 rm 別名不吃 -f，會靜默失敗）"
  exit 1
fi

if [ "$1" = "--staged" ]; then
  SRC="已 git add 的暫存內容"
  TREE=$(git write-tree 2>&1)
  if [ $? -ne 0 ] || [ -z "$TREE" ]; then
    echo "✗ git write-tree 失敗：$TREE"
    exit 1
  fi
  git archive "$TREE" | tar -x -C "$TMP" || { echo "✗ 無法匯出暫存內容"; exit 1; }
else
  SRC="HEAD（$(git rev-parse --short HEAD)）"
  git archive HEAD | tar -x -C "$TMP" || { echo "✗ 無法匯出 HEAD"; exit 1; }
fi

# 解出來的副本必須有東西，否則後面的檢查會以「檔案不存在」的形式假失敗
if [ ! -f "$TMP/scripts/validate_data.py" ] || [ ! -f "$TMP/scripts/build.py" ]; then
  echo "✗ 匯出的副本不完整（$TMP 內找不到 scripts/），請確認 git 狀態正常"
  exit 1
fi

echo "════════════════════════════════════════"
echo "preflight：模擬 CI 驗證 $SRC"
echo "════════════════════════════════════════"

fail=0

echo ""
echo "▸ 1/3  validate_data.py（資料一致性與 claims 受控用語）"
(cd "$TMP" && python3 scripts/validate_data.py)
rc=$?
[ $rc -ne 0 ] && { echo "  ✗ 失敗 rc=$rc"; fail=1; }

echo ""
echo "▸ 2/3  build.py --check（資料可載入、佔位符齊全）"
(cd "$TMP" && python3 scripts/build.py --check)
rc=$?
[ $rc -ne 0 ] && { echo "  ✗ 失敗 rc=$rc"; fail=1; }

echo ""
echo "▸ 3/3  未 commit 的檔案（CI 看不到這些）"
dirty=$(git status --porcelain -- data/ templates/ scripts/ .github/ 2>/dev/null)
# 已追蹤檔案被改動 = 真風險（CI 拿到的是舊版），未追蹤新檔 = 提醒即可
modified=$(echo "$dirty" | grep -v '^??' | grep -v '^$')
untracked=$(echo "$dirty" | grep '^??')

if [ -n "$modified" ]; then
  echo "$modified" | sed 's/^/    /'
  echo "  ✗ 上列已追蹤檔案有未 commit 的修改，CI 會拿到舊版"
  [ "$1" != "--staged" ] && fail=1
fi
if [ -n "$untracked" ]; then
  echo "$untracked" | sed 's/^/    /'
  echo "  ⚠ 上列為未追蹤新檔（若其他已 commit 檔案會用到它，記得一起 git add）"
fi
[ -z "$modified" ] && [ -z "$untracked" ] && echo "    （無）"

echo ""
echo "════════════════════════════════════════"
if [ $fail -eq 0 ]; then
  echo "✅ preflight 通過，可以 push"
else
  echo "❌ preflight 未通過 —— 直接 push 的話 CI 會紅"
fi
echo "════════════════════════════════════════"
exit $fail
