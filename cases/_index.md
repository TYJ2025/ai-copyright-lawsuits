# Cases Verification Index

> 由 `scripts/rebuild_case_index.py` 自動重生於 2026-08-08 12:39。**不要手改**。

- cases.json 案件數：**159**
- 已有 case .md 之案件：**112**（合計 6339 筆 docket entries）
- 有差異需人工確認：**70**
- fetch 日期早於本月者：**106**

比對規則：Judge 取姓氏比對、Court 取代碼交集、docket id 逐字比對、並檢查 CourtListener 最後書狀日是否晚於 cases.json 的 updatedAt。

| id | 案件 | 上次 fetch | 差異 |
|---:|---|---|---|
| 1 | Thomson Reuters v. ROSS Intelligence | 2026-04-27 | ⚠️ Judge 不符：dashboard「Bibas（D. Del. 原審）／3d Cir. panel: Restrepo、Montgomery-Reeves、Bove」／CL「—」；Court 待確認：dashboard「D. Del. 1:20-cv-00613 → 3d Cir. 25-2153（merits appeal）」／CL「Court of Appeals for the Third Circuit (`ca3`)」（無法正規化，需人工看）；docket id 不符：cases.json 17131648／case .md 70622297 |
| 2 | Getty Images v. Stability AI (US) | 2026-04-27 | ✅ 一致 |
| 3 | Andersen v. Stability AI (Artists Class Acti | 2026-04-27 | ✅ 一致 |
| 4 | In re Google Generative AI Copyright Litigat | 2026-04-27 | ✅ 一致 |
| 5 | Kadrey v. Meta Platforms (LLaMA Training) | 2026-04-27 | ✅ 一致 |
| 6 | Bartz v. Anthropic (Claude AI — $1.5B Settle | 2026-04-27 | ✅ 一致 |
| 7 | Concord Music v. Anthropic (AI Lyrics) | 2026-04-27 | ✅ 一致 |
| 8 | Authors Guild v. OpenAI (Authors Action — MD | 2026-04-27 | ✅ 一致 |
| 9 | New York Times v. Microsoft / OpenAI (Newspa | 2026-04-27 | ✅ 一致 |
| 10 | In re OpenAI Copyright Infringement Litigati | 2026-04-27 | ✅ 一致 |
| 11 | Disney v. Midjourney | 2026-04-27 | ✅ 一致 |
| 12 | UMG Recordings v. Suno | 2026-04-27 | ✅ 一致 |
| 13 | Doe v. GitHub (Copilot Litigation) | 2026-04-27 | ✅ 一致 |
| 14 | Raw Story Media v. OpenAI (DMCA CMI — Second | 2026-04-27 | ⚠️ Judge 不符：dashboard「McMahon / Second Circuit」／CL「Sidney H. Stein」 |
| 15 | New York Times v. Perplexity AI | 2026-04-27 | ✅ 一致 |
| 16 | Alcon Entertainment v. Tesla | 2026-04-27 | ✅ 一致 |
| 17 | Strike 3 Holdings v. Meta | 2026-04-27 | ✅ 一致 |
| 18 | Huckabee v. Meta Platforms | 2026-04-27 | ⚠️ Court 不符：dashboard「N.D. Cal.」（cand）／CL「District Court, S.D. New York (`nysd`)」（nysd） |
| 19 | Reddit v. SerpAPI, Perplexity | 2026-04-27 | ✅ 一致 |
| 20 | Lehrman v. Lovo, Inc. (AI Voice) | 2026-04-27 | ✅ 一致 |
| 21 | Vacker v. Eleven Labs (AI Voice — SETTLED) | 2026-04-27 | ✅ 一致 |
| 22 | In re Mosaic LLM Litigation (Databricks) | 2026-04-27 | ✅ 一致 |
| 23 | Dow Jones (WSJ/NY Post) v. Perplexity AI | 2026-04-27 | ✅ 一致 |
| 24 | James v. Snowflake Inc. | 2026-04-27 | ✅ 一致 |
| 25 | Advance Local Media v. Cohere | 2026-04-27 | ✅ 一致 |
| 26 | Woulard v. Suno | 2026-06-14 | ✅ 一致 |
| 27 | Entrepreneur Media v. Meta | 2026-04-27 | ✅ 一致 |
| 28 | Hendrix v. Apple | 2026-04-27 | ✅ 一致 |
| 29 | Tanzer v. Salesforce | 2026-04-27 | ✅ 一致 |
| 30 | Disney v. MiniMax | 2026-04-27 | ✅ 一致 |
| 31 | Ted Entertainment v. NVIDIA (DGX Cloud) | 2026-04-27 | ✅ 一致 |
| 32 | Pierce v. Photobucket (AI Image Training) | 2026-04-27 | ✅ 一致 |
| 33 | Chicago Tribune v. Perplexity AI | 2026-04-27 | ✅ 一致 |
| 34 | Encyclopaedia Britannica v. Perplexity AI | 2026-04-27 | ✅ 一致 |
| 35 | Intercept Media v. OpenAI | 2026-04-27 | ✅ 一致 |
| 36 | Justice v. Suno | 2026-04-27 | ✅ 一致 |
| 37 | Justice v. Uncharted Labs (Udio) | 2026-04-27 | ✅ 一致 |
| 38 | Nazemian v. NVIDIA Corp. | 2026-04-27 | ✅ 一致 |
| 39 | Warner Bros. v. Midjourney | 2026-04-27 | ✅ 一致 |
| 41 | Daily News v. Microsoft/OpenAI | 2026-04-27 | ✅ 一致 |
| 42 | Ziff Davis v. OpenAI | 2026-04-27 | ⚠️ Court 不符：dashboard「MDL Before Judge Stein (Originally D. Del.)」（ded）／CL「District Court, S.D. New York (`nysd`)」（nysd） |
| 43 | U.S. News & World Report v. OpenAI | 2026-04-27 | ✅ 一致 |
| 44 | BMG Rights Management v. Anthropic | 2026-04-27 | ⚠️ Judge 不符：dashboard「Alex G. Tse (Magistrate Judge)」／CL「Eumi K. Lee」 |
| 45 | Huckabee v. Bloomberg | 2026-04-27 | ✅ 一致 |
| 46 | UMG Recordings v. Uncharted Labs (Udio) — SD | 2026-04-27 | ✅ 一致 |
| 47 | Denial v. OpenAI | 2026-04-27 | ⚠️ Court 不符：dashboard「MDL Before Judge Stein (Originally N.D. Cal.)」（cand）／CL「District Court, S.D. New York (`nysd`)」（nysd） |
| 48 | Ted Entertainment v. Apple | 2026-04-27 | ⚠️ Court 不符：dashboard「C.D. Cal.」（cacd）／CL「District Court, N.D. California (`cand`)」（cand） |
| 49 | Ted Entertainment v. OpenAI | 2026-04-27 | ⚠️ Court 不符：dashboard「C.D. Cal.」（cacd）／CL「District Court, N.D. California (`cand`)」（cand） |
| 50 | Ted Entertainment v. Amazon | 2026-04-27 | ⚠️ Court 不符：dashboard「C.D. Cal.」（cacd）／CL「District Court, N.D. California (`cand`)」（cand） |
| 51 | Ted Entertainment v. Bytedance (TikTok) | 2026-04-27 | ⚠️ Court 不符：dashboard「C.D. Cal.」（cacd）／CL「District Court, N.D. California (`cand`)」（cand） |
| 52 | Concord Music v. Anthropic II (Torrenting Cl | 2026-04-27 | ✅ 一致 |
| 53 | Encyclopaedia Britannica v. OpenAI | 2026-04-27 | ✅ 一致 |
| 54 | Merriam-Webster v. OpenAI | 2026-04-27 | ✅ 一致 |
| 55 | Gracenote Media v. OpenAI | 2026-04-27 | ✅ 一致 |
| 56 | Cambronne (Carreyrou) v. Anthropic | 2026-04-27 | ✅ 一致 |
| 57 | case-057_3-25-cv-10897_carreyrou-v-anthropic | 2026-04-27 | ⚠️ case .md 存在但 cases.json 無此 id（案件已刪除？） |
| 58 | Chicken Soup for the Soul v. Multiple AI Com | 2026-04-27 | ✅ 一致 |
| 59 | Amazon.com Services v. Perplexity AI | 2026-04-27 | ⚠️ Court 不符：dashboard「W.D. Wash.」（wawd）／CL「District Court, N.D. California (`cand`)」（cand） |
| 60 | Getty Images v. Stability AI (N.D. Cal.) | 2026-04-27 | ⚠️ Court 不符：dashboard「N.D. Cal.」（cand）／CL「District Court, D. Delaware (`ded`)」（ded） |
| 61 | Anders v. Stability AI | 2026-04-27 | ✅ 一致 |
| 62 | Lyon v. Adobe | 2026-04-27 | ✅ 一致 |
| 63 | Kleiner v. Adobe | 2026-04-27 | ✅ 一致 |
| 64 | James v. Together Compute | 2026-04-27 | ✅ 一致 |
| 65 | James v. Cerebras Systems | 2026-04-27 | ✅ 一致 |
| 66 | David Greene v. Google | 2026-04-27 | ✅ 一致 |
| 67 | Carreyrou v. OpenAI | 2026-04-27 | ✅ 一致 |
| 68 | Millette v. Google | 2026-04-27 | ✅ 一致 |
| 69 | Millette v. NVIDIA | 2026-04-27 | ✅ 一致 |
| 70 | Millette v. OpenAI | 2026-04-27 | ⚠️ Judge 不符：dashboard「Davila/Stein」／CL「Sidney H. Stein」；Court 不符：dashboard「N.D. Cal. (MDL)」（cand）／CL「District Court, S.D. New York (`nysd`)」（nysd） |
| 71 | Basbanes v. Microsoft | 2026-04-27 | ✅ 一致 |
| 72 | Center for Investigative Reporting v. OpenAI | 2026-04-27 | ✅ 一致 |
| 73 | Bird v. Microsoft | 2026-04-27 | ✅ 一致 |
| 74 | California Newspaper Partnership v. Microsof | 2026-04-27 | ✅ 一致 |
| 75 | Apress Media v. Anna's Archive | 2026-04-27 | ✅ 一致 |
| 76 | Kogon v. Google | 2026-04-27 | ⚠️ Court 不符：dashboard「N.D. Ill.」（ilnd）／CL「District Court, N.D. California (`cand`)」（cand） |
| 77 | Businessing v. Runway AI | 2026-04-27 | ⚠️ Court 不符：dashboard「SDNY」（nysd）／CL「District Court, C.D. California (`cacd`)」（cacd） |
| 78 | Gardner v. Runway AI | 2026-04-27 | ⚠️ Court 不符：dashboard「N.D. Cal.」（cand）／CL「District Court, C.D. California (`cacd`)」（cacd） |
| 79 | Ted Entertainment v. Snap | 2026-04-27 | ✅ 一致 |
| 80 | Chmura v. Snap | 2026-04-27 | ⚠️ Court 不符：dashboard「C.D. Cal.」（cacd）／CL「District Court, N.D. California (`cand`)」（cand） |
| 81 | Google v. SerpApi | 2026-04-27 | ✅ 一致 |
| 82 | Ted Entertainment v. Meta | 2026-04-27 | ✅ 一致 |
| 83 | Youngblood v. Meta | 2026-04-27 | ✅ 一致 |
| 84 | Youngblood v. NVIDIA | 2026-04-27 | ✅ 一致 |
| 85 | Atlantic Recording Corp. v. Anna's Archive | 2026-04-27 | ✅ 一致 |
| 86 | Beaulier v. NVIDIA Corporation (3D Models) | 2026-04-27 | ✅ 一致 |
| 87 | Beaulier v. Meta Platforms (3D Models) | 2026-04-27 | ✅ 一致 |
| 88 | Beaulier v. Roblox (3D Models) | 2026-04-27 | ✅ 一致 |
| 89 | Beaulier v. Microsoft (3D Models) | 2026-04-27 | ⚠️ Court 不符：dashboard「W.D. Wash.」（wawd）／CL「District Court, N.D. California (`cand`)」（cand） |
| 90 | Martinez-Conde v. Apple (split from consolid | 2026-04-27 | ✅ 一致 |
| 91 | Alexander v. Apple (split from consolidated  | 2026-04-27 | ✅ 一致 |
| 92 | Alexander v. Salesforce (split from In re Sa | 2026-04-27 | ✅ 一致 |
| 93 | Zhang v. Google (split from In re Google Gen | 2026-04-27 | ✅ 一致 |
| 94 | Leovy v. Google (split from In re Google Gen | 2026-04-27 | ✅ 一致 |
| 95 | Chabon v. Meta Platforms (split from Kadrey  | 2026-04-27 | ✅ 一致 |
| 96 | Farnsworth v. Meta Platforms (split from Kad | 2026-04-27 | ✅ 一致 |
| 97 | Dubus v. NVIDIA Corp. (split from Nazemian v | 2026-04-27 | ⚠️ Court 不符：dashboard「N.D. Cal.」（cand）／CL「District Court, C.D. California (`cacd`)」（cacd） |
| 98 | Makkai v. Databricks (split from In re Mosai | 2026-04-27 | ⚠️ Court 不符：dashboard「N.D. Cal.」（cand）／CL「District Court, S.D. New York (`nysd`)」（nysd） |
| 99 | Alter v. OpenAI / Microsoft (split from Auth | 2026-04-27 | ✅ 一致 |
| 100 | Ace Cam v. Runway AI (split from Businessing | 2026-04-27 | ✅ 一致 |
| 101 | Getty Images v. Stability AI (UK) | — | ⚠️ 無 case .md（尚未 fetch） |
| 102 | GEMA v. OpenAI | — | ⚠️ 無 case .md（尚未 fetch） |
| 103 | Canadian News Publishers v. OpenAI | — | ⚠️ 無 case .md（尚未 fetch） |
| 104 | Canadian Authors Association v. OpenAI | — | ⚠️ 無 case .md（尚未 fetch） |
| 105 | ANI Media Pvt Ltd v. OpenAI | — | ⚠️ 無 case .md（尚未 fetch） |
| 106 | Syndicat national de l'édition et al. v. Met | — | ⚠️ 無 case .md（尚未 fetch） |
| 107 | Like Company v. Google Ireland | — | ⚠️ 無 case .md（尚未 fetch） |
| 108 | French Competition Authority v. Google | — | ⚠️ 無 case .md（尚未 fetch） |
| 109 | GEMA v. Suno AI | — | ⚠️ 無 case .md（尚未 fetch） |
| 110 | Carreyrou v. xAI et al. (Multiple Authors) | 2026-04-27 | ✅ 一致 |
| 111 | Like Company v. Google (CJEU) | — | ⚠️ 無 case .md（尚未 fetch） |
| 112 | Thaler v. Perlmutter (Supreme Court Cert Den | 2026-04-27 | ✅ 一致 |
| 113 | Kneschke v. LAION e.V. | — | ⚠️ 無 case .md（尚未 fetch） |
| 114 | DPCMO v. OpenAI (Danish Publishers) | — | ⚠️ 無 case .md（尚未 fetch） |
| 115 | KBS, MBC, SBS v. OpenAI (Korean Broadcasters | — | ⚠️ 無 case .md（尚未 fetch） |
| 116 | Li Yunkai v. Liu Yuanchun (李昀鍇 v. 劉元春) | — | ⚠️ 無 case .md（尚未 fetch） |
| 117 | Tsuburaya (SCLA / 新創華) v. AI Company (廣州奧特曼案 | — | ⚠️ 無 case .md（尚未 fetch） |
| 118 | Illustrators v. Xiaohongshu / Trik AI (插畫家 v | — | ⚠️ 無 case .md（尚未 fetch） |
| 119 | 読売新聞 v. Perplexity AI（日本） | — | ⚠️ 無 case .md（尚未 fetch） |
| 120 | 日本経済新聞・朝日新聞 v. Perplexity AI（日本） | — | ⚠️ 無 case .md（尚未 fetch） |
| 121 | CODA 等日本出版商 v. OpenAI（Sora2 著作權申訴） | — | ⚠️ 無 case .md（尚未 fetch） |
| 122 | Folha de S.Paulo v. OpenAI（巴西） | — | ⚠️ 無 case .md（尚未 fetch） |
| 123 | Barkley Associates v. Quizlet (AI 教育內容) | — | ⚠️ 無 case .md（尚未 fetch） |
| 124 | Attack the Sound v. Kunlun Tech Co. (Mureka  | — | ⚠️ 無 case .md（尚未 fetch） |
| 125 | Chegg v. Google (AI Overviews 反壟斷/著作權) | — | ⚠️ 無 case .md（尚未 fetch） |
| 126 | Koda v. Suno（丹麥） | — | ⚠️ 無 case .md（尚未 fetch） |
| 127 | RTI & Medusa Film v. Perplexity AI（義大利） | — | ⚠️ 無 case .md（尚未 fetch） |
| 128 | Penguin Random House v. OpenAI（德國 — 小火龍椰子案） | — | ⚠️ 無 case .md（尚未 fetch） |
| 129 | DPG Media v. HowardsHome（荷蘭 — TDM 退出機制） | — | ⚠️ 無 case .md（尚未 fetch） |
| 130 | Klein v. Snap (YouTubers AI Training Class A | — | ⚠️ 無 case .md（尚未 fetch） |
| 131 | Tsuburaya (SCLA / 新創華) v. 杭州某智能科技公司（觸手 AI）(杭 | — | ⚠️ 無 case .md（尚未 fetch） |
| 132 | Brave Software v. News Corp. | — | ⚠️ 無 case .md（尚未 fetch） |
| 133 | EVOX Productions v. The Leland Stanford Juni | — | ✅ 一致 |
| 134 | Reddit, Inc. v. Anthropic PBC | — | ✅ 一致 |
| 135 | Cruz v. Anthropic PBC（Bartz 和解 opt-out 28 作者 | — | ⚠️ Court 不符：dashboard「N.D. Cal.（案號待 PACER 確認，3:26-cv-XXXXX）」（cand）／CL「U.S. District Court, Northern District of California」（cad） |
| 136 | Wixen Music Publishing v. Meta Platforms | — | ✅ 一致 |
| 137 | Poseidon Wave Media v. Suno | — | ✅ 一致 |
| 138 | Elsevier / Hachette / Macmillan / McGraw Hil | — | ✅ 一致 |
| 139 | CNN v. Perplexity AI | — | ⚠️ 無 case .md（尚未 fetch） |
| 140 | Hobbs v. Meta Platforms | — | ⚠️ 無 case .md（尚未 fetch） |
| 141 | Kwon v. Anthropic | 2026-06-12 | ✅ 一致 |
| 142 | Gilbert v. Anthropic | 2026-06-12 | ✅ 一致 |
| 143 | Cambronne, Inc. v. Google | 2026-06-12 | ✅ 一致 |
| 144 | Tanzer v. Adobe | 2026-06-12 | ✅ 一致 |
| 145 | Woulard v. Uncharted Labs (Udio) | 2026-06-14 | ✅ 一致 |
| 146 | Shakespeare v. Anthropic PBC | — | ⚠️ 無 case .md（尚未 fetch） |
| 147 | SCI SPARK LLC v. Schedule A | — | ⚠️ 無 case .md（尚未 fetch） |
| 148 | Will-Burn Recordings & Publishing Co. v. UMG | — | ⚠️ 無 case .md（尚未 fetch） |
| 149 | Richner Communications v. Microsoft / OpenAI | — | ⚠️ 無 case .md（尚未 fetch） |
| 150 | Hachette Book Group v. Google | — | ⚠️ 無 case .md（尚未 fetch） |
| 151 | Sullivan v. Meta Platforms & Zuckerberg | — | ⚠️ 無 case .md（尚未 fetch） |
| 152 | EVOX Productions v. Stability AI, Runway, De | — | ⚠️ 無 case .md（尚未 fetch） |
| 153 | SEIU Pension Plan Master Trust v. Adobe（股東代位 | — | ⚠️ 無 case .md（尚未 fetch） |
| 154 | Hirschberger v. Narayen（Adobe 股東代位） | — | ⚠️ 無 case .md（尚未 fetch） |
| 155 | City of St. Clair Shores Police & Fire Retir | — | ⚠️ 無 case .md（尚未 fetch） |
| 156 | Anderson v. Nadella（Microsoft 股東代位） | — | ⚠️ 無 case .md（尚未 fetch） |
| 157 | American Federation of Musicians v. Warner M | — | ⚠️ 無 case .md（尚未 fetch） |
| 158 | S.A. Jamendo v. NVIDIA Corporation | — | ⚠️ 無 case .md（尚未 fetch） |
| 159 | S.A. Jamendo v. Suno, Inc. | — | ⚠️ 無 case .md（尚未 fetch） |
| 160 | AAP 13 家出版商 v. WeLib（盜版影子圖書館） | — | ⚠️ 無 case .md（尚未 fetch） |
| 162 | Sony Music Entertainment v. Uncharted Labs ( | — | ⚠️ 無 case .md（尚未 fetch） |

