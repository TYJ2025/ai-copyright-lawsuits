# CLAUDE.md — AI Copyright Lawsuits Worldwide

> 給下一個 Claude session 的快速上手文件。讀完應該能在 30 秒內知道這個專案在幹嘛、檔案在哪、能改什麼、不能碰什麼。

---

## 1. 專案是什麼

全球生成式 AI 著作權訴訟追蹤儀表板，三個系統合在一起：

| 系統 | 角色 | 關鍵檔 |
| --- | --- | --- |
| **Daily Brief** | 每日 07:07 自動跑，WebSearch 找全球 24 小時內 AI 著作權新聞 → 更新 `dashboard.html` 的 `newsItems` 陣列 | `scripts/daily-brief.sh` · `scripts/daily-brief-prompt.md` |
| **Cases Tracker** | 100+ 件美國案件 metadata（CourtListener docket + dashboard 卡片）逐案存檔，比對差異 | `cases/case-NNN_*.md` · `cases/_index.md` · `scripts/cases_manifest.json` |
| **Dashboard** | 單檔 HTML，公開部署在 GitHub Pages | `dashboard.html`（也作 `index.html` 副本）|

**部署**：https://tyj2025.github.io/ai-copyright-lawsuits/
**Repo**：git@github.com:TYJ2025/ai-copyright-lawsuits.git（**SSH**，不是 HTTPS）

---

## 2. 自動化流程（兩個 launchd agents）

### `com.tyj.ai-copyright-brief` — 每日 07:07
```
launchd → scripts/daily-brief.sh
       → claude -p (依 scripts/daily-brief-prompt.md 指令)
       → WebSearch 各家 AI copyright 案件最新動態
       → Edit dashboard.html 的 newsItems / newsArchive 陣列
       → log 寫到 .daily-brief.log
```

### `com.tyj.dashboard-autopush` — 觸發式 + 6h safety net
```
WatchPaths: dashboard.html 變動 → 立即執行
StartInterval: 每 6h 跑一次（safety net）
RunAtLoad: agent 重新載入時跑一次
ThrottleInterval: 60s（防 editor save 風暴）
       → auto-push.sh
       → git add dashboard.html && git commit && git push
       → log 寫到 .auto-push.log
```

**關鍵設計**：daily-brief 跟 auto-push 職責分離。daily-brief 只負責改檔，git 操作交給另一個 watcher。**Claude 在跑 daily-brief 時不要自己下 `git commit/push`**。

### plist 位置（重要）
- **實際被 launchd 載入的**：`~/Library/LaunchAgents/com.tyj.*.plist` ← canonical
- **repo 內的同名 plist**：是備份，**已知是舊版**（裡面寫舊 iCloud 路徑 `~/Documents/Claude/Projects/...`），**不要拿來 `launchctl load`**。要改排程，編輯 `~/Library/LaunchAgents/` 那份。

---

## 3. 資料架構（2026-06-12 Phase 6 cutover 後）

**`dashboard.html` 是 build 產物，不要手改**（改了下次 build 就被蓋掉）。真實資料源與產生流程：

```
data/*.json  +  templates/dashboard.template.html
            │
            └── python3 scripts/build.py ──► dashboard.html（含 footer 今日日期）
```

- `data/news.json` — 快訊。envelope：`{"$schema":"news.v1","data":{"items":[...],"archive":[...]}}`
  - `items` = 最近 3 天快訊（頂部 ticker）；`archive` = 超過 3 天的歷史快訊（下方折疊區）
  - **新增快訊一律用 `scripts/add_news.py`**（自動去重 + 自動歸檔），不要手改 json
- `data/cases.json`、`case_sources.json`、`fair_use_cases.json`、`official_reports.json`、`timeline.json` — 其餘 dashboard 區塊資料
- 改**版面/視覺** → 編輯 `templates/dashboard.template.html` 後跑 `build.py`
- `scripts/migrate_html_to_json.py` — one-shot 反向工具（dashboard.html → data/），已脫離每日流程

每筆快訊 entry 格式：
```js
{ "addedAt": "YYYY-MM-DD", "text": "【YYYY/M/D】案件名：重點摘要 30-60 字", "url": "來源 URL" }
```

- `addedAt` = **今日台北時間** (該則進 dashboard 的日期；用來決定何時搬到 archive)
- `text` 開頭 `【YYYY/M/D】` = 新聞事件日期（通常同 addedAt，但若補錄過去新聞會不同）

**Daily-brief 自動化邏輯**：claude -p 呼叫 `add_news.py` 寫 `data/news.json` → daily-brief.sh 跑 `build.py` 重生 dashboard.html → auto-push commit（dashboard.html + index.html + data/）。

---

## 4. cases/ 子系統（與 daily-brief 獨立）

`cases/case-NNN_<docket>_<slug>.md` — 每案一檔，共 100+ 件。每檔結構：
1. **CourtListener Docket Metadata** 表格
2. **Dashboard 卡片 vs CourtListener 比對**（自動標 ✅ / ⚠️）
3. **Docket Entries**（最新優先，過濾掉 pro hac vice、certificate of service 等程序性 entries）

`cases/_index.md` — 比對結果彙總，目前 100 件中 50 件被標「不符 ⚠️」（judge / court / docket 不一致、進度落後等）。

`scripts/cases_manifest.json` — 100 件的 case_id ↔ CourtListener docket_id 對照表，是 fetch script 的 source of truth。

**Workflow**：
- `scripts/fetch_courtlistener_docket.py` — 抓單一案件 docket
- `scripts/batch_refresh.py` — 批次刷新所有案件
- `scripts/scan_case_trackers.py` — 重新產生 `_index.md`
- `scripts/batch_update_dashboard_judges.py` — 把 CourtListener 上的 judge 名稱回寫到 dashboard 卡片
- `scripts/weekly_new_case_check.py` — **每週主動掃 CourtListener 找新立案**（不靠新聞）；輸出 `cases/_weekly_new_cases_YYYY-MM-DD.md`

### 新案發現：兩層機制

| 層 | 觸發 | 來源 | 輸出 |
| --- | --- | --- | --- |
| **被動（daily-brief 內建）** | 每日 07:07 | WebSearch 新聞 | `.daily-brief.log` 內 `🆕 疑似漏載案件` 段 |
| **主動（weekly_new_case_check.py）** | launchd 每週一 08:00 | CourtListener Search API (NoS 820 + AI 關鍵字) | `cases/_weekly_new_cases_*.md` |

被動層依賴媒體報導；主動層補上「剛立案、媒體還沒寫」的盲點。兩者去重邏輯都不會自動寫 `const cases` 陣列——僅輸出待人工審核清單。

---

## 5. scripts/ 內檔案一覽

| 檔案 | 用途 |
| --- | --- |
| `daily-brief.sh` | launchd 觸發的 daily-brief 入口 |
| `daily-brief-prompt.md` | 給 `claude -p` 的指令文件 |
| `fetch_courtlistener_docket.py` | 抓單一案件 docket（要 CourtListener API token） |
| `batch_refresh.py` | 批次刷新所有案件 docket |
| `batch_update_dashboard_judges.py` | 比對 dashboard judge 欄位與 CourtListener，回寫 |
| `scan_case_trackers.py` | 掃 `cases/` 重產 `_index.md` |
| `weekly_new_case_check.py` | 每週掃 CourtListener 找新立案，輸出待審清單 |
| `add_pending.py` | 多區段合併寫 `.pending-review.json`（main-board 待審 banner 的資料源） |
| `apply_decisions.py` | 消化 main-board 審核決定（`.pending-decisions.json`），見下方審核迴圈 |
| `rejected_cases.json` | 審核退回 ledger（weekly 掃描跳過這些 URL，退回案件不重現）— apply_decisions 維護 |
| `approved_queue.json` | 審核通過的 intake 佇列（待人工列載）— apply_decisions 維護 |
| `cases_manifest.json` | 100 案 case_id ↔ docket_id mapping |
| `install.sh` | 一次性安裝（plist 部署到 LaunchAgents） |
| `HANDOVER.md` | 早期交接文件，內容已被本檔取代 |

### main-board 審核迴圈（2026-06-12 起）

```
weekly_new_case_check.py（每週一 launchd，--days 7）
  → 自動分流（2026-06-13 起，YJ 指示「能機器判的不進人工清單」）：
      a. 當事人含純 AI 業者（OpenAI/Anthropic/Suno…，word-boundary 比對）→ 自動通過
      b. 起訴狀 RECAP 全文可得：含著作權字樣＋AI 關鍵詞 → 自動通過；
         無 AI 關鍵詞 → 自動退回（進 rejected ledger，永不再現）
      c. 全文不可得 → 才進 .pending-review.json 人工審核
  → .pending-review.json（只剩 unknown；items 帶穩定 id = CL docket id）
  → main-board update.sh 掃進 dashboard → YJ 在 https://main-board.vercel.app
    「待審核總覽」按 ✓通過 / ✕退回 / ⏳稍後（決定存 Upstash，跨裝置）
  → main-board 跑 ./update.sh --sync-decisions → 本 repo .pending-decisions.json
  → python3 scripts/apply_decisions.py（先 dry-run 看計劃，--apply 寫檔）：
      approved → 移出待審 + 進 approved_queue.json（之後照 intake 流程列載）
      rejected → 移出待審 + 進 rejected_cases.json（weekly 掃描永久跳過）
      deferred → 原地保留
```

已知去重盲點：dashboard 案名用縮寫時（例 CNN v. Perplexity AI vs 法院全名
Cable News Network Inc）token 比對會 miss——自動通過後進 approved_queue 的案件，
列載前仍要先確認 dashboard 沒有同案。

apply_decisions.py 以 URL 比對案件（idempotent，重跑不會重複記錄），不碰 git。

---

## 6. 常見任務速查

### 「daily-brief 沒跑」
```bash
# 看最近執行紀錄
tail -50 .daily-brief.log

# 手動觸發測試
launchctl kickstart -k gui/$(id -u)/com.tyj.ai-copyright-brief

# 確認 agent 還 loaded（注意 launchctl 即使成功也回非零 exit code）
launchctl list | grep tyj.ai-copyright-brief
```

### 「dashboard 改了沒 push」
```bash
tail -50 .auto-push.log
launchctl kickstart -k gui/$(id -u)/com.tyj.dashboard-autopush
git status  # 看是不是有 untracked / unstaged
```

### 「新增 / 刷新一件案子」
```bash
# 1. 加進 manifest
vim scripts/cases_manifest.json   # 加 {case_id, name, court, judge, status, primary_docket_id}

# 2. 抓 docket
python3 scripts/fetch_courtlistener_docket.py --case-id <N>

# 3. 重生 _index.md
python3 scripts/scan_case_trackers.py
```

### 「修改 dashboard 視覺 / 互動」
直接編輯 `dashboard.html`（單檔 HTML，CSS / JS 都內嵌）。儲存後 watcher 會自動 commit/push。**改 JS const 要小心 temporal dead zone**——所有 `const`/`let` 必須在引用它的 function call 之前宣告。

---

## 7. 紅線（DO NOT）

- ❌ **不要在 daily-brief 流程裡自己 `git commit/push`** — auto-push.sh 會處理，重複會搞亂。
- ❌ **不要直接編輯 repo 內的 `com.tyj.*.plist`** 然後 `launchctl load` — 那是 stale 備份，會載入錯路徑（舊 iCloud 路徑）。改要編 `~/Library/LaunchAgents/` 那份。
- ❌ **不要把這個 repo 搬進 iCloud Drive**（`~/Documents/` if iCloud sync enabled、任何 iCloud 同步路徑） — `bird` daemon 會鎖 `.git/`、產生 `tmp_obj_*` 殘檔。當前正確位置：`~/ClaudeProjects/AI Copyright Lawsuits Worldwide/`。
- ❌ **不要在腳本開頭寫 `set -e`** 配合 `launchctl` 指令 — `launchctl list/load/unload/print` 即使成功也回非零 exit code，會誤殺後續步驟。
- ❌ **不要刪 cases/case-NNN_*.md 而不同步更新 `cases_manifest.json`** — 兩邊會脫鉤，下次 `batch_refresh.py` 會壞掉。
- ❌ **不要直接手改 `dashboard.html` / `index.html`**（2026-06-12 Phase 6 cutover 後它們是 build 產物）— 改資料動 `data/*.json`（快訊用 `add_news.py`）、改版面動 `templates/dashboard.template.html`，然後跑 `python3 scripts/build.py`。

---

## 8. 已知待修 / TODO

**2026-05-17 housekeeping pass — 處理 6 個 TODO 結果：**

- [x] ~~repo 內 `com.tyj.dashboard-autopush.plist` 寫舊 iCloud 路徑~~ → 已同步 live (commit 5f72b48)
- [x] ~~一堆根目錄 audit log 殘留~~ → 已移到 `archive/audit-logs/` (commit 5f72b48)
- [x] ~~`.bak` 備份檔~~ → 已 `git rm` 2 個 tracked、`archive/` 收容 1 個 untracked (commit 5f72b48)
- [x] ~~`index.html` vs `dashboard.html` 不同步~~ → **發現 GH Pages 服務的 index.html 落後 3 週**！已 sync + 改 `auto-push.sh` 之後自動 mirror (commit a0bed3f)
- [x] ~~`cases/_index.md` 50 案不符~~ → 假警報。daily-brief 過去 3 週已把 dashboard 改到位，抽查 11 件全對。`_index.md` 是 2026-04-27 stale 報告，無 script 自動重生，**用時請忽略**或手動重整。
- [~] **`batch_refresh.py` 把 104 個 case .md 拉到最新** — **2026-05-17 主動暫緩**。已修 `fetch_courtlistener_docket.py` 的 Python 3.9 type-hint bug（commit `9f840c7`），script 本身可跑。實測時 CL API 回 401 invalid token，2 輪除錯（疑似 `<>` 括號被一起貼進去）後 YJ 決定不繼續。case .md 維持 2026-04-27 fetch 版本，dashboard.html 由 daily-brief 每日自動更新與 case 檔脫鉤無妨。未來想跑：`export COURTLISTENER_TOKEN=<從 CL profile 重生>`，再 `python3 scripts/batch_refresh.py --case 6` 驗證；通了再 `--all`。

**新發現 / 順手做的事：**

- [x] 105 case 檔 + 8 scripts 全進 git（先前 untracked）(commit 88e7a9d)
- [x] `.gitignore` 補 `node_modules/`、`__pycache__/`、`.env*`、`.claude/settings.local.json`、`.claude/worktrees/`
- [x] `batch_update_dashboard_judges.py` 的 Python 3.9 type-hint bug 修掉（`dict | None` → `dict`；本機 macOS Python 3.9 不吃新語法）
- [ ] `_index.md` 沒有自動重生機制 → 寫一個 script 比對 `cases/case-*.md` 的 Judge Assigned 與 dashboard.html 的 `"judge"` 欄位，產出真正反映「現況不符」的清單。或者直接刪掉 `_index.md`，避免下次又被它誤導。
- [ ] `index.html` 跟 `dashboard.html` 兩份檔案重複佔空間（~400KB × 2）。若想徹底去重：刪 `index.html`、改 GH Pages config 服務 `dashboard.html`，或加 1 行 HTML meta-refresh redirect 在 index.html。目前 auto-push.sh 已自動 mirror，無功能差異。

---

## 9. CourtListener API 注意

- API token 用 env var `COURTLISTENER_TOKEN`（不要 commit）
- Rate limit：5,000 req/hour（足夠 batch refresh）
- Docket entries 一次最多回 20 個，要分頁 (`?cursor=...`)
- 程序性 entries（pro hac vice、certificate of service、disclosure statement、notice of appearance / change of address）已在 fetch script 過濾掉

---

_Last updated: 2026-05-17 by Claude（從 codebase 與 settings.local.json 反推）_
