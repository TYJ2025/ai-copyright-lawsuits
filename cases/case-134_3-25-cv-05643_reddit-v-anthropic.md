# Case 134 — Reddit, Inc. v. Anthropic PBC

> 最後更新：2026-05-15（手動補錄；經 scan_case_trackers.py 漏案掃描發現後補入）

---

## 1. Docket Metadata

| 欄位 | 值 |
|---|---|
| Case Name | Reddit, Inc. v. Anthropic PBC |
| 州法院案號 | `CGC-25-625892`（San Francisco Superior Court，原始起訴地） |
| 聯邦案號 | `3:25-cv-05643`（N.D. Cal.，Anthropic 移送後） |
| Court | 起訴：San Francisco Superior Court → 移送：N.D. Cal. → **2026/3/30 發回州法院** |
| Judge Assigned | Trina L. Thompson（N.D. Cal., 處理 remand 階段，前期為 Susan Illston）／後續由 San Francisco Superior Court 法官審理 |
| Date Filed | 2025-06-05（州法院起訴） |
| Cause | 州法請求：違約、不當得利、侵入動產（trespass to chattels）、妨害契約、加州不公平競爭法（UCL §17200）。**未提起聯邦著作權請求** |
| Jury Demand | Plaintiff |
| Trial Date | 2028-02-14 至 2028-03-08（San Francisco Superior Court 排定） |
| CourtListener URL | <https://www.courtlistener.com/docket/70704683/reddit-inc-v-anthropic-pbc/> |

## 2. 案件爭點（Issues）

本案係 AI 訓練資料訴訟中**罕見「全部以州法請求權」起訴**之案件，具高度策略意義。

Reddit 主張：

1. **違約**：Anthropic 接入 Reddit 服務（包括以爬蟲抓取公開貼文）時，受 Reddit 使用者協議（User Agreement）拘束；協議明文限制使用者就 Reddit 內容之商業利用，並要求授權方須付費。
2. **不當得利**：Anthropic 未付對價而以 Reddit 平台內容訓練 Claude，取得不當經濟利益。
3. **侵入動產（trespass to chattels）**：Anthropic 持續、自動化抓取 Reddit 伺服器，造成系統負擔，構成對 Reddit 動產之侵入。
4. **妨害契約**：Anthropic 規避 Reddit 對其使用者所設之內容控制機制，導致 Reddit 對使用者之契約義務（隱私、刪除權）受妨礙。
5. **加州不公平競爭法（UCL §17200）**：以上行為構成不法、不公平或詐欺之商業行為。

**核心爭點**：

- 17 U.S.C. §301 著作權法「優先抵觸條款」（preemption）是否吸收上述州法請求？換言之，當資料抓取行為同時涉及著作權利用（重製、衍生）與契約／侵權違反時，州法請求是否被聯邦著作權法排除？
- **訴訟策略意涵**：Reddit 採「契約路徑」而非「著作權路徑」，因為 Reddit 對使用者貼文本身不享有著作權（著作權屬於使用者）；改以「服務條款」作為請求權基礎，此路徑若成功，將為**「平台不擁有內容著作權，但能以服務條款防 AI 抓取」**樹立先例。

## 3. 訴訟進展（Progress）

- **2025/6/5** Reddit 於 San Francisco Superior Court 起訴 Anthropic，案號 CGC-25-625892。
- **2025/7/3** Anthropic 將案件移送（remove）至 N.D. Cal.，案號 3:25-cv-05643；初期分案予 Susan Illston 法官，後改由 Trina L. Thompson 法官審理。
- **2025–2026** 主要爭點為「remand 與否」：Reddit 主張州法請求未被 §301 preempt，應發回州法院；Anthropic 反對。
- **2026/3** Thompson 法官就 remand 動議發布暫時意見（tentative ruling），傾向准予發回。
- **【2026/3/30】Thompson 法官正式裁定准予發回**——認定 §301 對 Reddit 之州法請求**不構成優先抵觸**：
  - 違約請求：使用者協議課予被告之義務（access methods 限制、技術基礎設施保護）與著作權法所保護之權利**質的不同**（quantitatively different），不被吸收。
  - 不當得利、侵入動產、妨害契約、UCL：皆有著作權法之外的獨立要件，不被吸收。
- **2026/4** 案件正式回到 San Francisco Superior Court 續行。
- **2028/2/14–3/8** 預定陪審審判（San Francisco Superior Court）。

## 4. 對台灣之啟示（Taiwan Implications）

1. **「服務條款防 AI 抓取」之路徑**——台灣平台業者（如 Dcard、PTT、痞客邦）若擔憂自身平台內容遭 AI 業者抓取作訓練，可參考 Reddit 之策略：**以使用者協議與服務條款作為請求權基礎**，主張違約、不當得利、UCL 等台灣對應制度，而非單獨依著作權法。此路徑特別適合「平台不擁有 UGC 著作權」之情境。
2. **台灣民法第 184 條（侵權）／第 179 條（不當得利）／第 199 條（契約債務不履行）之援用**——Reddit 案五項州法請求權幾乎皆有台灣法對應：違約對應債務不履行；不當得利對應第 179 條；trespass to chattels 對應第 184 條第 1 項之物權／使用權侵害；UCL 對應公平交易法第 25 條（不公平競爭）或第 21、24 條。
3. **著作權法第 65 條合理使用不再是 AI 訴訟唯一戰場**——本案揭示：即使 AI 業者得在著作權法上主張合理使用，仍可能在契約、侵權、不公平競爭法上敗訴。台灣 AI 業者使用網路爬取資料時，**不應僅檢查著作權合理使用，亦須檢視來源平台之 ToS、robots.txt 與資料庫保護權**。
4. **§301 preemption 之比較**——美國 §301 preemption 制度於台灣無直接對應，台灣著作權法本身亦不排除民法／公平法之競合救濟，故台灣權利人就同一行為**通常可同時主張**著作權、民法侵權、不當得利、公平法等多重請求權，無 preemption 障礙。台灣權利人於起訴時應主動規劃多請求權之競合與順序。
5. **陪審審判時程**——本案排於 2028 年 2–3 月，將是 AI 訓練資料「契約路徑」首件實體審判，若 Reddit 勝訴，將強化平台對 AI 業者之議價地位（已有 Reddit-Google、Reddit-OpenAI 之授權合作為對照）。

## 5. 媒體與資料來源

- CourtListener docket：<https://www.courtlistener.com/docket/70704683/reddit-inc-v-anthropic-pbc/>
- Courthouse News：[Reddit prods judge to move Anthropic case back to state court](https://www.courthousenews.com/reddit-prods-judge-to-move-anthropic-case-back-to-state-court/)
- Crowell & Moring 客戶備忘錄：[Court Holds State Tort and Contract Claims Not Preempted by Federal Copyright Act, Remands Reddit v. Anthropic](https://www.crowell.com/en/insights/client-alerts/northern-district-of-california-court-holds-state-tort-and-contract-claims-not-preempted-by-federal-copyright-act-remands-reddit-v-anthropic-to-state-court)
- Loeb & Loeb 4 月分析：<https://www.loeb.com/en/insights/publications/2026/04/reddit-inc-v-anthropic-pbc>
- MLex：[Reddit's data scraping lawsuit against Anthropic sent back to California state court](https://www.mlex.com/mlex/articles/2459465/reddit-s-data-scraping-lawsuit-against-anthropic-sent-back-to-california-state-court)
- Bloomberg Law：[Anthropic Tries to Keep Reddit Scraping Row in Federal Court](https://news.bloomberglaw.com/ip-law/anthropic-fights-to-keep-reddit-ai-scraping-row-in-federal-court)
- Daily Journal：[Reddit data scraping suit against Anthropic back to state court](https://www.dailyjournal.com/article/390586-reddit-data-scraping-suit-against-anthropic-back-to-state-court)
