# 交給 Claude Code 的安裝 / 驗證指令包

> 用途：把「AI 著作權訴訟每日快訊」從 Cowork 排程搬到本機 launchd + Claude Code headless。
> 使用方式：在 Mac 終端機 `cd` 到 repo 後開啟 Claude Code，把「交給 Claude Code 的指令」那一段複製貼上即可。

---

## 背景（Cowork 已預先準備好的檔案）

Cowork 端已經在 repo 內產出以下 4 個檔案，**內容完整、不需要 Claude Code 再寫**：

```
/Users/jesuisjane/ClaudeProjects/AI Copyright Lawsuits Worldwide/
├── com.tyj.ai-copyright-brief.plist        ← launchd 定義（每日 07:07 觸發）
└── scripts/
    ├── daily-brief.sh                       ← bash wrapper（呼叫 claude -p headless）
    ├── daily-brief-prompt.md                ← 給 Claude 的任務指令（搜尋 + 更新 dashboard）
    └── install.sh                           ← 管理腳本（install / uninstall / status / test / kick）
```

`.gitignore` 已加入 `.daily-brief.state` 與 `*.log`（原本就有）規則。

架構設計：兩個 launchd agent 各司其職
- `com.tyj.ai-copyright-brief`（新）：每天 07:07 跑 `claude -p`，搜尋新聞 + 改 `dashboard.html`
- `com.tyj.dashboard-autopush`（舊，不動）：監視 `dashboard.html`，自動 commit/push

---

## 交給 Claude Code 的指令（複製以下整段貼進 Claude Code）

```
請幫我完成以下動作，任何一步失敗就停下來告訴我原因：

1. 確認 claude CLI 已安裝並已登入。跑 `claude --version` 看版本。

2. 確認 4 個檔案存在且可執行：
   - ls -la "/Users/jesuisjane/ClaudeProjects/AI Copyright Lawsuits Worldwide/com.tyj.ai-copyright-brief.plist"
   - ls -la "/Users/jesuisjane/ClaudeProjects/AI Copyright Lawsuits Worldwide/scripts/"
   daily-brief.sh 與 install.sh 需要有 x 權限；若沒有，執行 chmod +x。

3. 先做試跑（dry run），不安裝 launchd：
   cd "/Users/jesuisjane/ClaudeProjects/AI Copyright Lawsuits Worldwide"
   ./scripts/install.sh test

   這會直接執行 daily-brief.sh 一次，走完整流程。跑完後請：
   - 把 .daily-brief.log 的最後 30 行秀給我看
   - 用 `git status` 確認 dashboard.html 有被改（或說明「今日無新動態」）
   - 若 dashboard.html 有改，現有的 com.tyj.dashboard-autopush agent 應該會自動 commit/push；
     請等 30 秒後看 .auto-push.log 末 10 行確認 push 結果

4. 如果試跑成功，正式安裝 launchd agent：
   ./scripts/install.sh install

   然後跑 ./scripts/install.sh status 確認 agent 已載入，
   輸出 launchctl list 那行應該看到 com.tyj.ai-copyright-brief。

5. 提交新增的檔案到 git（但先問我要不要做）：
   git status --short
   應該看到新增的 com.tyj.ai-copyright-brief.plist、scripts/、以及修改過的 .gitignore。
   如果我同意，請用這個 commit message：
     Add launchd-based daily AI copyright brief (migrated from Cowork)

6. 最後提醒我：去 Cowork 介面把原本的 `ai-copyright-daily-brief` 排程任務停用或刪掉，
   避免與本機 launchd 任務雙跑。

==== 重要限制 ====
- 不要修改 scripts/ 底下任何檔案的內容；只做「跑、驗證、安裝」。
- 若 ./scripts/install.sh test 那步 claude CLI 報錯，
  把錯誤訊息原文貼給我，不要自己改 flag。常見問題：
    - "unknown option --dangerously-skip-permissions"
      → 代表 claude CLI 版本太舊，請 brew upgrade claude-code
    - "Not authenticated"
      → 請先跑一次互動式 `claude` 登入
- 若 ./scripts/install.sh install 報 launchctl 權限錯，
  改用：launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.tyj.ai-copyright-brief.plist
```

---

## 安裝完成後的日常管理

```bash
cd "/Users/jesuisjane/ClaudeProjects/AI Copyright Lawsuits Worldwide"

./scripts/install.sh status     # 看 agent 有沒有掛載、最近 log
./scripts/install.sh test       # 不經 launchd，立刻手動跑一次
./scripts/install.sh kick       # 透過 launchctl kickstart 立刻跑一次（走真正排程路徑）
./scripts/install.sh uninstall  # 關閉每日自動任務

tail -f .daily-brief.log        # 即時看任務執行過程
tail -f .auto-push.log          # 看 git push 結果
```

---

## 故障排除

| 症狀 | 檢查點 |
| --- | --- |
| 07:07 沒跑 | `launchctl list com.tyj.ai-copyright-brief` 有沒有；Mac 當時有沒有開機（launchd 會在下次開機補跑一次） |
| 跑了但 dashboard 沒改 | `.daily-brief.log` 有沒有 `No changes to dashboard.html today`（代表今天真的沒新動態，這是正常行為） |
| dashboard 改了但沒 push | `.auto-push.log` 是不是停在 `fatal: cannot lock ref` 之類的錯；SSH key 有沒有加到 Keychain（`ssh-add --apple-use-keychain`） |
| claude CLI 報「Not authenticated」 | 在終端機跑一次 `claude` 互動式登入；launchd 會讀同一份 credentials |
| 重複條目塞進 newsItems | prompt 內的比對邏輯是字串相似度；如需強化，可在 `daily-brief-prompt.md` 第 21-28 行加上更嚴格的去重規則 |

---

## 之後要微調 prompt

直接改 `scripts/daily-brief-prompt.md`，不用動 bash 腳本或 plist。launchd 下次觸發就會用新版。
