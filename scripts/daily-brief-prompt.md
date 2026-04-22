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

若結果與 AI 著作權訴訟無關，請排除。

## 更新 dashboard.html 流程
1. 先用 `Grep` 找 `const newsItems = [` 所在行（約第 7163 行附近）。
2. 用 `Read` 讀取該陣列整塊，取得既有條目供比對避免重複。
3. 對每則新聞判斷：
   - 若已存在相同/極度相似條目，跳過
   - 若為新資訊，格式化為：
     ```
     { "text": "【YYYY/M/D】案件名或主題：重點摘要（30-60 字）", "url": "來源 URL" }
     ```
     YYYY/M/D 為今日台北時間日期。
4. 使用 `Edit` 工具，**將新條目 prepend 至 newsItems 陣列最上方**（新的在上）。
5. 若陣列超過 8 條，同時移除最末端舊條目，僅保留最新 8 條。
6. 若當日查無任何新資訊，則**不修改 dashboard.html**，靜默結束。

## 成功標準
- dashboard.html 若有新動態則新增條目，且不重複
- 無新動態時不動 dashboard.html，避免製造無意義 commit
- 最後以簡短文字輸出（會進 log）：今日新增幾則、條目摘要

## 硬性限制
- **不要寄 email / 建立 Gmail 草稿**（Gmail 步驟已停用）
- **不要下 git commit / push**（auto-push.sh 會處理）
- **不要提問** — 全程自動化執行，有不確定就做合理判斷並在輸出註明
- 時區以台北（UTC+8）為準
