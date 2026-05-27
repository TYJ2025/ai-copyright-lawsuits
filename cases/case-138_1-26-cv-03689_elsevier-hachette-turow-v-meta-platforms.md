# Case 138 — Elsevier / Hachette / Macmillan / McGraw Hill / Cengage + Scott Turow v. Meta Platforms

> 最後更新：2026-05-27（手動補錄；由 daily-brief 漏案偵測連續多週提示後補入）

---

## 1. Docket Metadata

| 欄位 | 值 |
|---|---|
| Case Name（CourtListener caption） | Elsevier Inc. v. Meta Platforms, Inc. |
| 完整原告 | Elsevier、Hachette、Macmillan、McGraw Hill、Cengage（5 大教育／學術出版商）+ Scott Turow（個人作家代表） |
| Docket No. | `1:26-cv-03689` |
| Court | S.D.N.Y.（紐約南區聯邦地方法院） |
| Judge Assigned | District Judge P. Kevin Castel |
| Magistrate Judge | Robyn F. Tarnofsky |
| Date Filed | 2026-05-05 |
| Cause | 17 U.S.C. §101 Copyright Infringement |
| Defendants | Meta Platforms, Inc.；**Mark Zuckerberg（個人被告）** |
| Class Action | FRCP 23 集體訴訟（集體界定：擁有 ISBN／DOI／ISSN 之著作權人） |
| CourtListener URL | <https://www.courtlistener.com/docket/73294740/elsevier-inc-v-meta-platforms-inc/> |

## 2. 案件爭點（Issues）

本案為 **Bartz v. Anthropic 後第二件由出版商主導之 AI 著作權巨型集體訴訟**，亦為**首件將 Mark Zuckerberg 列為個人被告**之 AI 訓練侵權案。

核心指控：

1. **shadow library 抓取**——指 Meta 自 **LibGen、Anna's Archive** 等盜版站抓取**數百萬本書與學術期刊**訓練 Llama 系列模型。
2. **Zuckerberg 個人授權之證據**——原告主張 2023/4 Meta 內部文件顯示 **Zuckerberg 親自指示**放棄與出版商之授權談判，轉採盜版捷徑；引述內部 email 與 Meta 揭露之 **267TB 訓練資料規模**。
3. **集體定義之爭議**——以「擁有 **ISBN／DOI／ISSN** 之著作權人」為集體界定，涵蓋學術期刊作者、Open Access 出版商、CC 授權作者；**Authors Alliance 已對此集體代表性提出質疑**（出版商與 OA 作者立場長期對立）。
4. **原告陣容之意義**——5 大教育／學術出版商 + 暢銷律政小說家 Scott Turow（個人作家代表）；caption 以 Elsevier 為首位原告。涵蓋學術期刊、教科書、商業小說等多元出版模式。

**核心爭點**：

- Zuckerberg **個人責任**之 piercing 是否成立？（CEO 在 AI 訓練決策上之直接介入是否足以擊穿公司法人面紗？）
- 集體代表性（Authors Alliance 質疑）是否影響 class certification？
- **合理使用**——對照 Bartz v. Anthropic 已和解、Kadrey v. Meta 仍續審之並行案件，本案之 shadow library 主張是否強化「故意侵權」認定？

## 3. 訴訟進展（Progress）

- **2026/5/5** 出版商聯盟（Elsevier、Hachette、Macmillan、McGraw Hill、Cengage）+ Scott Turow 於 S.D.N.Y. 起訴 Meta 與 Zuckerberg，案號 `1:26-cv-03689`。
- **2026/5/5** 案件分案 P. Kevin Castel 法官、Robyn F. Tarnofsky 治安法官。
- **2026/5/7** Castel 法官核可 Jeffrey Gould 之 pro hac vice 申請。
- **2026/5/12** Castel 法官核可 Benjamin Blystad Gould、Samuel Lev Rubinstein、Chris Nathaniel Ryder 等多位原告律師之 pro hac vice 申請（顯示原告律師團規模龐大）。

**後續預期關鍵節點**：Meta 提出 Motion to Dismiss（爭點預期聚焦 Zuckerberg 個人責任之 piercing、集體代表性、合理使用）、Class certification 階段、可能與 Kadrey v. Meta（N.D. Cal.）合併之 MDL 程序。

**本案與 Kadrey v. Meta 之區別**：
- Kadrey：N.D. Cal.，個別作家集體（Sarah Silverman、Ta-Nehisi Coates 等），無 Zuckerberg 個人被告。
- 本案：S.D.N.Y.，出版商集體 + Scott Turow，**加入 Zuckerberg 個人被告**。
- 兩案管轄、集體界定、首席原告、被告陣容皆不同，**非同案**。

## 4. 對台灣之啟示（Taiwan Implications）

1. **CEO 個人責任之先例**——將 Zuckerberg 列為個人被告為 AI 訓練侵權案首例。台灣大型科技公司 CEO（聯發科蔡力行、台灣大鄭俊卿、中華電信郭水義）若在 AI 訓練決策上有可證實之直接介入（書面授權、email 指示），未來在台灣亦可能面臨個人民事責任主張，呼應**公司法第 23 條之忠實義務**與**民法第 184 條之共同侵權**。

2. **學術出版與 Open Access 衝突**——本案集體定義以 ISBN／DOI／ISSN 為界，將 Open Access 期刊作者、CC 授權作者一併綁入，惟代表此集體之 Elsevier 等出版商與 OA 作者立場長期對立。台灣科技部、國家圖書館、TAOA（Taiwan Open Access）社群應關注此案 **class certification 階段之裁定**，將影響國內學術文獻之 AI 訓練合法性爭議。

3. **shadow library 議題之合規盤點**——LibGen、Z-Library、OceanofPDF 等於台灣亦廣為人知。本案如形成判決將強化「使用盜版庫訓練 = 故意侵權」之認定，國內 AI 業者（聯發科、台達電、中華電信、台灣大、各大學 AI 中心）應**立即盤點訓練資料來源是否含上述盜版庫**，並建立**資料來源驗證（data provenance）流程**。

4. **267TB 規模證據之揭示意義**——本案引述 Meta 揭露之 267TB 訓練資料規模，為 AI 訓練資料量化之首件法庭可見數字，提供台灣損害賠償計算之參考量級（對比：Bartz v. Anthropic 為 91.3% 認領率、約 440,490 件適格著作）。

5. **集體訴訟之國際協調**——本案、Kadrey v. Meta、Bartz v. Anthropic 之 opt-out 機制與集體界定模式，將影響跨國作家／出版商（包含台灣作家透過國際出版社授權之作品）是否能進入美國集體訴訟之保障範圍。台灣文化部、出版商業同業公會、台灣文學發展基金會應協助本國作家評估 opt-in／opt-out 之利弊。

## 5. 媒體與資料來源

- NPR, *"Scott Turow, Macmillan, McGraw Hill sue Meta for AI copyright infringement"*（2026/5/5）
- Variety, *"Mark Zuckerberg 'Personally Authorized' Meta's Massive Copyright Infringement"*（2026/5/5）
- Hachette Book Group, *"Publishers and Authors File Class Action Lawsuit Against Meta and Zuckerberg"*（2026/5/5）
- Deadline, *"Publishers & Author Scott Turow Sue Meta Over AI Training"*（2026/5/5）
- Authors Alliance 評論（2026/5）—— 對集體代表性質疑（5/6 列入 daily-brief）
- CourtListener docket: <https://www.courtlistener.com/docket/73294740/>
