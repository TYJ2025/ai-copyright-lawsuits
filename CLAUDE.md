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
       → git add index.html $TRACKED_PATHS && git commit && git push
         （TRACKED_PATHS = dashboard.html data/ cases/ scripts/*.json）
       → log 寫到 .auto-push.log
```

**關鍵設計**：daily-brief 跟 auto-push 職責分離。daily-brief 只負責改檔，git 操作交給另一個 watcher。**Claude 在跑 daily-brief 時不要自己下 `git commit/push`**。

### launchctl 常見誤判（2026-08-08 記）

- **`Bootstrap failed: 5: Input/output error` 多半代表「已經載入過」，不是失敗。** 先用
  `launchctl print gui/$(id -u)/<label>` 確認；印得出來就是已註冊。要重載才需先
  `launchctl bootout gui/$(id -u)/<label>`。
- 確認實際狀態一律看 `launchctl list | grep tyj`：第二欄是上次結束碼，`0` 正常、
  非 0 代表該 agent 上次執行失敗；PID 欄為 `-` 是正常的（排程型 agent 平時不常駐）。
- `launchctl list/load/unload/print` 即使成功也可能回非零 exit code，**腳本裡不要配 `set -e`**。

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
  - `items` = 頂部 ticker 快訊，原則最近 3 天、但**至少保留 3 則**（`add_news.py` 的 `MIN_ITEMS`，不足時自 archive 回補最新者；`--rebalance` 可只重整不新增）；`archive` = 已歸檔之歷史快訊（下方折疊區）
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

**Daily-brief 自動化邏輯**：claude -p 呼叫 `add_news.py` 寫 `data/news.json` →（案件型快訊）呼叫 `update_case_progress.py` 回寫 `data/cases.json` 的 progress → daily-brief.sh 跑 `build.py` 重生 dashboard.html → auto-push commit。

**auto-push 納管路徑**（`auto-push.sh` 的 `TRACKED_PATHS`，改動時三處要一致：兩行偵測 + 一行 `git add`）：
`dashboard.html`、`index.html`、`data/`、`cases/`、`scripts/*.json`。

- `scripts/*.json` 於 2026-08-19 納入：`approved_queue.json`、`rejected_cases.json`、`cases_manifest.json`、`missing_cases_report.json` 都是機器產生的 intake ledger，每週掃描會變動，先前不在清單內導致審核狀態長期未提交。
- **只收 `*.json`，不收 `*.py` / `*.sh`**，避免開發中未完成的腳本被自動 commit。
- **`templates/` 刻意不納管**：改版面後若只 commit 了 script 沒 commit template，CI 從 HEAD checkout 會少佔位符而失敗（2026-08-08 踩過）。push 前一律先跑 `./scripts/preflight.sh`，漏 commit 的檔案會立刻現形。

### claims 標籤規則（2026-08-04 立）

**標籤一律以起訴狀所載訴因（causes of action）為準。** 訴訟中之增刪（撤回、追加請求權）**不動標籤**，改寫入 `issues`（訴訟爭點）。

- 受控詞彙表：`data/claims_vocab.json`。canonical 36 種規範用語 + 91 種既有寫法的 alias 對照 + 7 種非訴因項目（陪審團聲請、集體訴訟聲明、故意侵權損賠態樣、合理使用抗辯、銷毀模型請求等）之處置說明。
- `claims` 只放訴因；比較功能的「共同主張 vs 獨有主張」靠這個欄位做集合運算，用語不統一會算錯。
- `claimsDetail` 存起訴狀 COUNT 原文 `[{count, title, canonical}]`，`claimsVerifiedAt` 為核對日期（null = 尚未核對，卡片顯示「待核對起訴狀」）。
- `validate_data.py` 會擋非受控用語；新增案件後跑 `python3 scripts/normalize_claims.py --apply`。
- 每週二 08:30 由 `com.tyj.verify-claims` 批次核對（每次 25 件），**以起訴狀結果覆寫 claims**（2026-08-05 起）；被取代的舊標籤存入 `claimsPrevious` 可回溯，差異清單仍留在 `.verify-claims.log`。
- **上訴中案件的 `docket` 必須指一審卷宗**，否則抓不到起訴狀（上訴卷宗沒有）。案 1 Thomson Reuters v. ROSS 曾誤指 3d Cir. 卷宗（70622297），2026-08-05 改為 D. Del. 17131648；上訴卷宗連結改放 `case_sources.json`，兩審並列。新增上訴中案件時要一併檢查。

### 快訊 ↔ 案件資訊同步規則（2026-08-03 立）

**只要快訊提到已收錄案件的任何進展，就必須回寫該案 `progress`。** 快訊是時間流、案件卡片是案件現況，兩者不同步的話案件資訊會停在舊狀態。2026/5 至 7 曾累積 50 餘則未回寫（154 件中僅 12 件有 `updatedAt`），2026-08-03 人工補齊 52 筆。

- 適用範圍比 `rulings` 寬：裁定、判決、和解、修正訴狀、撤銷之訴、即決判決聲請、排程變更、discovery 攻防、當事人變更、上訴全都要回寫；`rulings` 只收里程碑等級的實質裁定。
- 一律經 `scripts/update_case_progress.py`，不要手改 cases.json。
- 一則快訊涉及多案時每案各跑一次。
- 純產業動態（募資、授權合作、產業報告、政策聲明）找不到對應案件時可略過，但要在輸出列為「無對應案件」。
- 快訊提到的案件不在 cases.json → 走漏案偵測列為疑似漏載，不自行新增。
- 詳細指令寫在 `scripts/daily-brief-prompt.md` 的「案件資訊同步（progress 欄位）」段。

---

## 4. cases/ 子系統（與 daily-brief 獨立）

`cases/case-NNN_<docket>_<slug>.md` — 每案一檔，共 100+ 件。每檔結構：
1. **CourtListener Docket Metadata** 表格
2. **Dashboard 卡片 vs CourtListener 比對**（自動標 ✅ / ⚠️）
3. **Docket Entries**（最新優先，過濾掉 pro hac vice、certificate of service 等程序性 entries）

`cases/_index.md` — 比對結果彙總，由 `rebuild_case_index.py` 自動重生（**不要手改**）。舊版是 2026-04-27 的一次性報告且比對邏輯過於字面（把「S.D.N.Y.」與「District Court, S.D. New York」判為不符），50 件「不符」多為假警報；2026-08-08 改寫後降到真正需要人工看的數量。

`scripts/cases_manifest.json` — 100 件的 case_id ↔ CourtListener docket_id 對照表，是 fetch script 的 source of truth。

**Workflow**：
- `scripts/fetch_courtlistener_docket.py` — 抓單一案件 docket
- `scripts/batch_refresh.py` — 批次刷新所有案件
- `scripts/rebuild_case_index.py` — 比對 cases.json 與 case .md，重生 `cases/_index.md`
- `scripts/sync_cases_manifest.py` — 自 cases.json 重生 `cases_manifest.json`
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
| `scan_case_trackers.py` | 抓外部 case tracker 網頁比對 manifest，找漏案（**不是**產 `_index.md`，CLAUDE.md 舊版寫錯） |
| `weekly_new_case_check.py` | 每週掃 CourtListener 找新立案，輸出待審清單 |
| `add_pending.py` | 多區段合併寫 `.pending-review.json`（main-board 待審 banner 的資料源） |
| `update_rulings.py` | 更新 cases.json 單案 `rulings` 欄位（比較功能裁定矩陣資料源；date+holding 去重，daily-brief 遇實質裁定時呼叫） |
| `update_case_progress.py` | **回寫案件進展到 cases.json 的 `progress`**（每則案件型快訊必跑；【YYYY/M/D】標記去重、依日期插入正確位置，另可帶 status/court/judge/docket；`--find` 可用案名或案號查 case id） |
| `apply_decisions.py` | 消化 main-board 審核決定（`.pending-decisions.json`），見下方審核迴圈 |
| `rejected_cases.json` | 審核退回 ledger（weekly 掃描跳過這些 URL，退回案件不重現）— apply_decisions 維護 |
| `approved_queue.json` | 審核通過的 intake 佇列（待人工列載）— apply_decisions 維護 |
| `normalize_claims.py` | 依 `data/claims_vocab.json` 正規化 claims 標籤（98 種寫法 → 36 種規範用語），非訴因項目移入 issues |
| `verify_claims.py` | **以起訴狀核對 claims**（RECAP 抓 document 1 起訴狀 → 擷取 COUNT → 對映 canonical）；`--status` 看進度、`--pending --apply` 批次跑，需 `COURTLISTENER_TOKEN` |
| `verify-claims-weekly.sh` | launchd `com.tyj.verify-claims` 每週二 08:30 的入口，跑 verify → normalize → validate → build |
| `sync_courtlistener_sources.py` | 把 cases.json 的 `docket` id 補成 case_sources.json 的 CourtListener 連結（`--report` 分類列出仍無連結者）。**注意**：卡片上的 CourtListener 按鈕讀 `case_sources.json`，不是 `cases.json` 的 `docket` 欄位，兩邊各自維護會脫鉤 |
| `rebuild_case_index.py` | 比對 cases.json 與 cases/case-*.md（judge 取姓氏、court 正規化成 CL code、docket id、最後書狀日），重生 `cases/_index.md` |
| `sync_cases_manifest.py` | 自 cases.json 重生 `cases_manifest.json`（只收有 docket 者），讓 manifest 成為衍生物而非人工維護 |
| `refresh-cases-monthly.sh` | launchd `com.tyj.refresh-cases` 每月 1 日 09:00 的入口：sync manifest → batch_refresh --all → rebuild _index |
| `cases_manifest.json` | case_id ↔ docket_id mapping（119 筆，由 sync_cases_manifest.py 產生，**不要手改**） |
| `preflight.sh` | **push 前跑一次**：從 HEAD 解出乾淨副本模擬 CI（validate_data + build --check），並列出 CI 路徑內未 commit 的檔案。`--staged` 可驗已 git add 的內容 |
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

### CI（GitHub Actions）

`.github/workflows/validate.yml` 在 push 到 main 且動到 `data/`、`templates/`、`build.py`、`validate_data.py` 時觸發，跑 `validate_data.py` 與 `build.py --check`；`link-check` job 設 `continue-on-error`，不擋。

**踩過的坑（2026-08-08）**：改了 template 卻只 commit 了 script，本機工作區測得過但 CI 從 HEAD checkout 就少了 `{{CLAIMS_VOCAB_JSON}}` 佔位符而失敗。push 前先跑：

```bash
./scripts/preflight.sh
```

它從 HEAD 解出乾淨副本驗，與 CI 行為一致，漏 commit 的檔案會立刻現形。

---

## 7. 紅線（DO NOT）

- ❌ **不要在 daily-brief 流程裡自己 `git commit/push`** — auto-push.sh 會處理，重複會搞亂。
- ❌ **不要直接編輯 repo 內的 `com.tyj.*.plist`** 然後 `launchctl load` — 那是 stale 備份，會載入錯路徑（舊 iCloud 路徑）。改要編 `~/Library/LaunchAgents/` 那份。
- ❌ **不要把這個 repo 搬進 iCloud Drive**（`~/Documents/` if iCloud sync enabled、任何 iCloud 同步路徑） — `bird` daemon 會鎖 `.git/`、產生 `tmp_obj_*` 殘檔。當前正確位置：`~/ClaudeProjects/AI Copyright Lawsuits Worldwide/`。
- ❌ **不要在腳本開頭寫 `set -e`** 配合 `launchctl` 指令 — `launchctl list/load/unload/print` 即使成功也回非零 exit code，會誤殺後續步驟。
- ❌ **不要刪 cases/case-NNN_*.md 而不同步更新 `cases_manifest.json`** — 兩邊會脫鉤，下次 `batch_refresh.py` 會壞掉。
- ❌ **不要直接手改 `dashboard.html` / `index.html`**（2026-06-12 Phase 6 cutover 後它們是 build 產物）— 改資料動 `data/*.json`（快訊用 `add_news.py`）、改版面動 `templates/dashboard.template.html`，然後跑 `python3 scripts/build.py`。

---

## 7b. daily-brief 登入憑證（2026-06-28 新增）

daily-brief 的 `claude -p` headless 呼叫**靠 CLI 憑證認證**。互動式 Claude Pro `/login` 留下的憑證**對 launchd 背景排程不穩**，會週期性過期或被登出 → brief 在第一步就 rc=1 中止、快訊靜默停更（2026/6/22~28 連續 6 天踩過：6/22~26 報 `401 Invalid authentication credentials`、6/28 報 `Not logged in · Please run /login`）。手動 `/login` 只能治標撐幾天。

**根治（已套用）**：在 `~/Library/LaunchAgents/com.tyj.ai-copyright-brief.plist` 的 `EnvironmentVariables` 放長效 token：
```
<key>CLAUDE_CODE_OAUTH_TOKEN</key>
<string>sk-ant-oat01-...</string>
```
token 用 `claude setup-token` 產生（**效期一年**，2026-06-28 設、2027-06 到期；已設 scheduled task 於 2027-06-14 提醒換發）。寫入用 PlistBuddy（首次 `Add`、續期 `Set`）：
```bash
/usr/libexec/PlistBuddy -c "Set :EnvironmentVariables:CLAUDE_CODE_OAUTH_TOKEN 新TOKEN" ~/Library/LaunchAgents/com.tyj.ai-copyright-brief.plist
launchctl bootout gui/$(id -u)/com.tyj.ai-copyright-brief 2>/dev/null
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.tyj.ai-copyright-brief.plist
launchctl kickstart -k gui/$(id -u)/com.tyj.ai-copyright-brief
```

**排錯口訣**：「快訊沒更新」先 `tail .daily-brief.log`。看到 `Not logged in` 或 `401` → 憑證問題（換 token），**不是腳本邏輯壞掉**，別瞎改 script。

---

## 8. 已知待修 / TODO

**2026-05-17 housekeeping pass — 處理 6 個 TODO 結果：**

- [x] ~~repo 內 `com.tyj.dashboard-autopush.plist` 寫舊 iCloud 路徑~~ → 已同步 live (commit 5f72b48)
- [x] ~~一堆根目錄 audit log 殘留~~ → 已移到 `archive/audit-logs/` (commit 5f72b48)
- [x] ~~`.bak` 備份檔~~ → 已 `git rm` 2 個 tracked、`archive/` 收容 1 個 untracked (commit 5f72b48)
- [x] ~~`index.html` vs `dashboard.html` 不同步~~ → **發現 GH Pages 服務的 index.html 落後 3 週**！已 sync + 改 `auto-push.sh` 之後自動 mirror (commit a0bed3f)
- [x] ~~`cases/_index.md` 50 案不符~~ → 假警報。daily-brief 過去 3 週已把 dashboard 改到位，抽查 11 件全對。`_index.md` 是 2026-04-27 stale 報告，無 script 自動重生，**用時請忽略**或手動重整。
- [x] ~~**`batch_refresh.py` 把 104 個 case .md 拉到最新**~~ → 2026-08-08 改為 `com.tyj.refresh-cases` 每月 1 日 09:00 自動跑（sync manifest → batch_refresh --all → rebuild _index）。原 2026-05-17 暫緩原因：已修 `fetch_courtlistener_docket.py` 的 Python 3.9 type-hint bug（commit `9f840c7`），script 本身可跑。實測時 CL API 回 401 invalid token，2 輪除錯（疑似 `<>` 括號被一起貼進去）後 YJ 決定不繼續。case .md 維持 2026-04-27 fetch 版本，dashboard.html 由 daily-brief 每日自動更新與 case 檔脫鉤無妨。未來想跑：`export COURTLISTENER_TOKEN=<從 CL profile 重生>`，再 `python3 scripts/batch_refresh.py --case 6` 驗證；通了再 `--all`。

**新發現 / 順手做的事：**

- [x] 105 case 檔 + 8 scripts 全進 git（先前 untracked）(commit 88e7a9d)
- [x] `.gitignore` 補 `node_modules/`、`__pycache__/`、`.env*`、`.claude/settings.local.json`、`.claude/worktrees/`
- [x] `batch_update_dashboard_judges.py` 的 Python 3.9 type-hint bug 修掉（`dict | None` → `dict`；本機 macOS Python 3.9 不吃新語法）
- [x] ~~`_index.md` 沒有自動重生機制~~ → 2026-08-08 寫了 `rebuild_case_index.py`，比對 cases.json 與 case .md，court 先正規化成 CL code 再比（消掉 49 件假警報），每月 refresh 後自動重生。
- [ ] `index.html` 跟 `dashboard.html` 兩份檔案重複佔空間（~400KB × 2）。若想徹底去重：刪 `index.html`、改 GH Pages config 服務 `dashboard.html`，或加 1 行 HTML meta-refresh redirect 在 index.html。目前 auto-push.sh 已自動 mirror，無功能差異。

---

## 9. CourtListener API 注意

- API token 用 env var `COURTLISTENER_TOKEN`（不要 commit）
- Rate limit：5,000 req/hour（足夠 batch refresh）
- Docket entries 一次最多回 20 個，要分頁 (`?cursor=...`)
- 程序性 entries（pro hac vice、certificate of service、disclosure statement、notice of appearance / change of address）已在 fetch script 過濾掉

---

_Last updated: 2026-05-17 by Claude（從 codebase 與 settings.local.json 反推）_
