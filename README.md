# AI Copyright Lawsuits Worldwide

全球生成式 AI 著作權訴訟動態追蹤儀表板。每日 07:07（Asia/Taipei）自動透過 WebSearch 抓取最新案件動態，並彙整 100+ 件美國案件的 CourtListener docket metadata。

**🌐 Live dashboard**：https://tyj2025.github.io/ai-copyright-lawsuits/

## 內容

| 系統 | 角色 |
| --- | --- |
| Daily Brief | 每日自動更新 dashboard 的 `newsItems` ticker（過去 24 小時全球 AI 著作權新聞） |
| Cases Tracker | 100+ 件美國案件，每案 1 個 `cases/case-NNN_*.md`，含 CourtListener docket entries + dashboard 卡片 vs CL metadata 比對 |
| Dashboard | 單檔 HTML，部署在 GitHub Pages（`index.html` 是部署檔；`dashboard.html` 是工作檔，由 `auto-push.sh` 自動 mirror） |

## 技術 stack

- HTML + 內嵌 JS（單檔 dashboard，無 build step）
- Python 3 scripts（CourtListener API v4 拉取、batch refresh、metadata 比對）
- macOS launchd（每日 daily-brief + dashboard auto-push watcher）
- GitHub Actions（pages-build-deployment）

## 資料來源

- 每日新聞：WebSearch 多家關鍵字（案件名、AI copyright ruling、settlement 等）
- 案件 docket：[CourtListener REST API v4](https://www.courtlistener.com/api/rest/v4/)（需 `COURTLISTENER_TOKEN` env var）
- Dashboard 卡片內容：人工維護 + script 半自動更新

## 開發者文件

完整架構、自動化流程、red lines、TODO → 見 [CLAUDE.md](./CLAUDE.md)。

## 免責聲明

- 本儀表板提供之資訊僅供學術研究與一般參考之用，不構成任何法律意見。
- 案件 metadata 透過自動化抓取與比對，可能與 CourtListener 官方資料有出入；引用前請以 CourtListener 公告為準。
