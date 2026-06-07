# Refactor Cutover Plan — Phase 6 (切換) + Phase 7 (清理)

> 重構：單檔 `dashboard.html`（內嵌 7 個 JS const）→ `data/*.json` + `build.py` + `templates/dashboard.template.html` 產生 pipeline。
> 含行號 + 實際程式碼。供 06/10 滿 7 天影子 PASS 後照表執行。撰於 2026-06-07。

---

## Step 0 — GATE（切換前提）

切換前 **必須** 確認 `shadow-run.log` 連續 7 天 `[✓ PASS]`，零 FAIL。

```bash
cd "/Users/jesuisjane/ClaudeProjects/AI Copyright Lawsuits Worldwide"
grep -E "shadow run start|PASS|FAIL" shadow-run.log | tail -20
```

截至 2026-06-07 已連續 PASS：06/04、06/05、06/06、06/07（4 個自動日）。預估達標日 ≈ **2026-06-10**。
任何 FAIL → 不切換，`git diff data/` 查 migrate 落差，修正後重新計天。

---

## Step 1 — 先修 footer 陷阱（最關鍵，不修會倒退）

**問題**：`dashboard.html:1873` 的 `每日快訊最近更新: YYYY-MM-DD` 由 `daily-brief.sh:128` 的 `sed` 每天動態蓋；
`templates/dashboard.template.html:1873` 同一行卻寫死舊日期（產 template 當天凍結，目前 `2026-06-02`）。
`build.py` 用 template 產出 → footer 會倒退。`shadow_run.sh` 只比對 7 個 const 陣列、**看不到 footer**，所以影子驗證照不到這個落差。

**改法（placeholder 化）：**

① `templates/dashboard.template.html:1873`：
```
每日快訊最近更新: 2026-06-02   →   每日快訊最近更新: {{FOOTER_DATE}}
```

② `scripts/build.py` — 在 `build()` 的 substitution 迴圈跑完、`leftover = [...]` 檢查之前插入：
```python
from datetime import date
template = template.replace("{{FOOTER_DATE}}", date.today().isoformat(), 1)
```

③ 驗證：跑 `python3 scripts/build.py` 後 `grep "每日快訊最近更新" dashboard.html` 必須是今天日期。

---

## Step 2 — 改 `scripts/daily-brief-prompt.md`（資料寫入路徑）

把「Claude 用 Edit 直接改 dashboard.html 陣列」整段換成「呼叫 `add_news.py`」。
`add_news.py` 已內建去重 + 自動歸檔（>3 天搬 archive），prompt 可大幅簡化。

**替換 §「更新 dashboard.html 流程」Step 1–3（prompt 第 59–84 行）為：**

```markdown
## 更新資料流程（Phase 6+：寫 data/news.json，不直接改 dashboard.html）

### Step 1 — 比對既有條目避免重複
1. 用 `Read` 讀 `data/news.json`，看 `data.items` 與 `data.archive`（兩個都要比對）。

### Step 2 — 新增今日快訊
對每則新資訊，若 items/archive 都無相同或極相似條目，執行：
    python3 scripts/add_news.py --added-at <今日台北 YYYY-MM-DD> \
      --text "【YYYY/M/D】案件名：重點摘要（30-60 字）" --url "<來源URL>"
- add_news.py 自動去重、自動把 >3 天條目搬到 archive，不需手動搬 archive。
- 多則就多次呼叫。

### Step 3 — 收尾
- 不要自己跑 build.py、不要 Edit dashboard.html、不要 git commit（daily-brief.sh 與 auto-push 處理）。
- 若無任何新資訊，不呼叫 add_news.py，靜默結束（heartbeat 由 build.py footer 處理）。
```

**漏案偵測段（prompt 第 86 行起）**：把 `Grep dashboard.html const cases` 改成讀 `data/cases.json` 的 `"name"` 欄位，其餘不變。
**§目標 第 2 點（第 9 行）**：措辭改為「更新 `data/news.json`」。

---

## Step 3 — 改 `scripts/daily-brief.sh`

**① 內容變更偵測（第 119–124 行）→ 改偵測 news.json：**
```bash
if git diff --quiet HEAD -- data/news.json 2>/dev/null; then
    HAD_CONTENT_CHANGE=0
else
    HAD_CONTENT_CHANGE=1
    CHANGE_LINES=$(git diff --stat HEAD -- data/news.json 2>/dev/null | tail -1)
fi
```

**② footer sed（第 126–129 行）→ 換成 build.py：**
```bash
# --- 用 build.py 從 data/ 重生 dashboard.html（footer 日期由 build.py 蓋）---
log "Rebuilding dashboard.html from data/ via build.py …"
if /usr/bin/env python3 "$REPO_DIR/scripts/build.py" >> "$LOG_FILE" 2>&1; then
    log "build.py OK — dashboard.html regenerated"
else
    log "FATAL: build.py failed — dashboard.html NOT regenerated"
    echo "$(date '+%Y/%m/%d')|fail|build.py" > "$STATE_FILE"
    exit 3
fi
```
> heartbeat 仍成立：build.py 每天跑、footer 蓋今天 → dashboard.html 至少 footer 變 → auto-push 照常 commit。

**③ shadow-run 區塊（第 142–151 行）**：Phase 6 **先留著**；切換後語意反轉（驗證沒人手改髒產出），觀察 3 天後 Phase 7 再刪。

---

## Step 4 — Phase 6 驗證（手動全流程乾跑）

```bash
cd "/Users/jesuisjane/ClaudeProjects/AI Copyright Lawsuits Worldwide"
python3 scripts/add_news.py --dry-run --added-at "$(date +%F)" --text "【測試】cutover dry run" --url ""
python3 scripts/build.py --diff          # 看差異是否如預期
python3 scripts/build.py                  # 正式產出
grep "每日快訊最近更新" dashboard.html    # 必須是今天日期 ← footer 修對沒
git diff --stat                           # 應只有 dashboard.html (+ index.html mirror)
git checkout -- dashboard.html data/      # 乾跑後復原
launchctl kickstart -k gui/$(id -u)/com.tyj.ai-copyright-brief   # 真跑一次
tail -40 .daily-brief.log                 # 確認 build.py OK、無 FATAL
```

通過後 commit Phase 6 變更（訊息含 `cutover` 字樣方便回滾定位）。

---

## Step 5 — 觀察 3 天（約 06/10→06/13）

每天確認：daily-brief 自動跑無 FATAL、dashboard footer 日期正確、auto-push 有 commit、新聞正常進 `data/news.json`。

---

## Phase 7 — 清理（觀察穩定後）

- [ ] 刪 `daily-brief.sh` 第 142–151 行 shadow-run 區塊
- [ ] `git rm scripts/shadow_run.sh`（或移 `archive/`）
- [ ] `scripts/migrate_html_to_json.py` 加註「one-shot 反向工具，已脫離每日流程」
- [ ] 更新 `CLAUDE.md`：標明 **dashboard.html 是 build 產物、勿手改；真實資料源是 `data/*.json`，改資料要改 json + 跑 build.py**
- [ ] 確認 `auto-push.sh` 仍把 dashboard.html mirror 到 index.html
- [ ] `.gitignore` 的 `shadow-run.log` / `dashboard.html.new` / `build-diff.txt` 條目可留（無害）

---

## 回滾（Rollback）

```bash
cd "/Users/jesuisjane/ClaudeProjects/AI Copyright Lawsuits Worldwide"
git log --oneline | grep -i cutover
git revert <cutover-commit>     # 或 git checkout <prev> -- scripts/daily-brief.sh scripts/daily-brief-prompt.md scripts/build.py templates/dashboard.template.html
```
新舊流程不共用狀態，回滾乾淨；dashboard.html 內容不受影響。

---

## 一句話總結

GATE 過（7 天 PASS）→ **先修 footer placeholder** → 改 prompt 用 add_news.py + daily-brief.sh 加 build.py → 乾跑驗證 → 觀察 3 天 → Phase 7 刪 shadow + 更新文件。
