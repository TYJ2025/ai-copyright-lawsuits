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

## 3. dashboard.html 資料結構

兩個關鍵 JS 陣列：

```js
const newsItems = [...]    // 最近 3 天加入的快訊，畫面頂部 ticker
const newsArchive = [...]  // > 3 天的歷史快訊，畫面下方折疊區
```

每筆 entry 格式：
```js
{ "addedAt": "YYYY-MM-DD", "text": "【YYYY/M/D】案件名：重點摘要 30-60 字", "url": "來源 URL" }
```

- `addedAt` = **今日台北時間** (該則進 dashboard 的日期；用來決定何時搬到 archive)
- `text` 開頭 `【YYYY/M/D】` = 新聞事件日期（通常同 addedAt，但若補錄過去新聞會不同）

**Daily-brief 自動化邏輯**：執行時把 `addedAt` 距今 > 3 天的從 `newsItems` 搬到 `newsArchive`，再 append 今日新搜到的 entries。

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
| `cases_manifest.json` | 100 案 case_id ↔ docket_id mapping |
| `install.sh` | 一次性安裝（plist 部署到 LaunchAgents） |
| `HANDOVER.md` | 早期交接文件，內容已被本檔取代 |

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
