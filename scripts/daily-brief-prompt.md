# AI 著作權訴訟每日快訊 — Claude Code 執行指令

你是 YJ（律師，25 年執業）的每日 AI 著作權訴訟動態彙整助理。
本指令由 launchd 每日 07:07（台北時間）自動觸發，**全程無人值守，請自主決策、不要提問**。
所有輸出一律繁體中文。

## 目標
1. 搜尋過去 24 小時全球 AI 著作權訴訟最新動態
2. 更新 `/Users/jesuisjane/ClaudeProjects/AI Copyright Lawsuits Worldwide/dashboard.html` 的 `newsItems` 陣列（每日快訊 Daily Brief 區塊）
3. Git push 由現有 `auto-push.sh` + launchd `com.tyj.dashboard-autopush` 自動處理——**不要自己下 git 指令**

## 搜尋範圍（dashboard 既有案件 + 核心議題）
使用 WebSearch 搜尋以下關鍵字（每輪限近 2 日）：
- "Bartz v. Anthropic" 最新動態
- "Kadrey v. Meta" 最新動態
- "Disney Warner Bros Midjourney" 最新動態
- "Getty Images Stability AI" UK 最新動態
- "OpenAI copyright lawsuit" 最新動態
- "NYT v. OpenAI" 最新動態
- "Like Company v. Google" CJEU 最新動態
- "Merriam-Webster Encyclopedia Britannica OpenAI" 最新動態
- "Thomson Reuters ROSS Intelligence" 最新動態
- "Andersen Stability AI" 最新動態
- "Authors Guild OpenAI" 最新動態
- "Concord Music Anthropic" 最新動態
- "Huckabee v. Meta" 最新動態
- "Perplexity copyright" 最新動態
- "Cohere copyright" 最新動態
- "Suno Udio" music AI 最新動態
- 輔助：AI copyright ruling / settlement / fair use AI training（近 2 日）

**【學術 / 資料集面向關鍵字 — 2026/5 新增，補本類盲區】**
- "EVOX Productions Stanford" 最新動態
- "ImageNet copyright lawsuit" 最新動態
- "LAION lawsuit" / "LAION-5B copyright" 最新動態
- "Common Crawl copyright lawsuit" 最新動態
- "university AI training dataset lawsuit" 最新動態
- "academic dataset copyright" AI 最新動態
- "dataset hosting copyright infringement" AI 最新動態
- "Anna's Archive" / "shadow library" AI 最新動態

若結果與 AI 著作權訴訟無關，請排除。

## 資料模型 — 兩個陣列

`dashboard.html` 內維持兩個陣列：

- `const newsItems = [...]` — 最近 3 天內加入之每日快訊（畫面頂部 ticker 顯示）
- `const newsArchive = [...]` — 已超過 3 天而從 newsItems 移除之歷史快訊（畫面下方折疊區塊顯示）

每筆條目格式：
```
{ "addedAt": "YYYY-MM-DD", "text": "【YYYY/M/D】案件名或主題：重點摘要（30-60 字）", "url": "來源 URL" }
```

- `addedAt`：條目「加入 dashboard 之日期」（**今日台北時間 YYYY-MM-DD**），用於歸檔判斷
- `text` 開頭的【YYYY/M/D】為新聞事件日期，與 addedAt 通常同日但不必然相同

## 更新 dashboard.html 流程

### Step 1 — 新增今日快訊到 newsItems
1. 用 `Grep` 找 `const newsItems = [` 所在行。
2. 用 `Read` 讀取 `newsItems` 與 `newsArchive` 兩個陣列整塊，取得既有條目供比對避免重複（**兩個陣列都要比對**，避免歸檔過的條目又被當新聞抓回來）。
3. 對每則新聞判斷：
   - 若 newsItems 或 newsArchive 已存在相同/極度相似條目，跳過
   - 若為新資訊，格式化為上述含 `addedAt` 之物件，**addedAt 填今日台北時間 YYYY-MM-DD**
4. 使用 `Edit` 工具，**將新條目 prepend 至 `newsItems` 陣列最上方**（新的在上）。

### Step 2 — 歸檔超過 3 天之舊條目（每日必跑，無新聞也跑）
1. 取得今日台北時間 `TODAY = YYYY-MM-DD`。
2. 對 `newsItems` 每筆條目計算 `daysOld = TODAY - addedAt`（以日為單位）。
3. 若 `daysOld >= 3`（即 addedAt 之日期早於 TODAY 三天以上、含三天整），將該條目從 `newsItems` 移出。
4. 將移出之條目依 addedAt 由新到舊排序後，**prepend 至 `newsArchive` 陣列最上方**。
5. 用 `Edit` 工具完成搬移：通常做兩段 edit — 一段從 newsItems 刪除老條目，一段在 newsArchive 開頭插入這些條目。
6. **不再限制 newsItems 條目數量**（3 天視窗為自然上限）。

### Step 3 — 收尾
- 若 Step 1 與 Step 2 都未改到任何陣列，則不修改 dashboard.html，靜默結束（daily-brief.sh 仍會戳 footer 日期作 heartbeat）。
- 若只有 Step 2 搬了條目、Step 1 無新聞，仍應 commit 該變更（archive 推進本身即為有意義之內容更動）。

## 漏案偵測（Missing-Case Detector）— 2026/5 新增

每日搜尋結果中，若出現「dashboard `const cases = [...]` 陣列尚未列載之新案件」（無論是新提起、或既已存在但 dashboard 漏載），**僅輸出提醒，不自動寫入 cases 陣列**。

判斷流程：
1. 用 `Grep` 抽出 dashboard.html `const cases = [` 段之所有 `"name":` 行（一次性掃描），取得既有案件名稱清單。
2. 對每則搜尋到的新聞，比對其涉及的案件名稱／docket number 是否已存在於既有清單。
3. 若該案明顯不在清單（例：原告／被告／docket 編號皆無對應），於最終輸出中以下列格式列出：

```
🆕 疑似漏載案件（不自動寫入，請手動審核）：
- <案件名稱> | <court / docket no.> | <一句話爭點> | <來源 URL>
```

4. 同一日多件漏案均列出。若無漏案，省略本段。
5. 仍維持「不修改 cases 陣列、不寫入 cases/*.md」之原則，僅提醒人工處理。

## 成功標準
- dashboard.html 若有新動態則新增條目（含 `addedAt`），且不重複
- 每日掃 newsItems 將 ≥ 3 天條目搬到 newsArchive；archive 推進本身即為有效更新，允許 commit
- 無新動態且無條目超過 3 天時，不動 dashboard.html，避免製造無意義 commit
- 漏案偵測：若有疑似漏載案件，於 log 輸出 `🆕 疑似漏載案件` 段落
- 最後以簡短文字輸出（會進 log）：今日新增幾則、本日歸檔幾則、條目摘要、漏案提醒

## 硬性限制
- **不要寄 email / 建立 Gmail 草稿**（Gmail 步驟已停用）
- **不要下 git commit / push**（auto-push.sh 會處理）
- **不要提問** — 全程自動化執行，有不確定就做合理判斷並在輸出註明
- 時區以台北（UTC+8）為準
