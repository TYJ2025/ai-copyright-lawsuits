# Case 133 — EVOX Productions, LLC v. The Leland Stanford Junior University et al.

> 最後更新：2026-05-15（手動補錄；本案先前漏載於 dashboard）

---

## 1. Docket Metadata

| 欄位 | 值 |
|---|---|
| Case Name | EVOX Productions, LLC v. The Leland Stanford Junior University et al. |
| Docket Number | `5:24-cv-09521`（N.D. Cal., San Jose Division） |
| Court | U.S. District Court, Northern District of California (`cand`) |
| Judge Assigned | Jacqueline Scott Corley |
| Date Filed | 2024-12-31 |
| Cause | 17 U.S.C. §501（直接侵害、貢獻侵害） |
| Nature of Suit | 820 Copyright |
| Jury Demand | Plaintiff |
| 共同被告（已先後駁回） | University of Michigan、William Marsh Rice University、Baylor College of Medicine |
| 現存唯一被告 | The Leland Stanford Junior University |

## 2. 案件爭點（Issues）

EVOX Productions（汽車攝影圖庫）主張：

1. 2020 年起，被告大學教職員以「Consortium」形式合作，將 EVOX 圖庫中近 8,000 張受著作權保護之汽車攝影作品，未經授權納入由 Stanford 主導之 AI 訓練資料集（與 ImageNet 系列研究有關）。
2. 模型訓練完成後，Consortium 將該等圖像託管於 Stanford 網站，作為「免費可下載 AI 訓練資料」對外公開散布。
3. 2023 年，研究團隊再公開上傳第二批訓練資料集（225 張），同樣未取得 EVOX 授權。
4. 主張兩種責任態樣：**直接侵害**（直接重製與散布）與**貢獻侵害**（明知第三人會以該資料集進行 AI 訓練、複製、散布）。

法律核心爭點：

- 學術／非營利機構整理、託管並再散布受著作權保護圖像作為 AI 訓練資料集，能否主張合理使用（17 U.S.C. §107）？
- 「資料集託管」與「AI 模型訓練」是否屬於同一行為鏈中可分割評價之獨立利用行為？
- 學術用途之合理使用抗辯，於再散布行為（redistribution）部分能否成立？

## 3. 訴訟進展（Progress）

- **2024/12/31** EVOX 向 N.D. Cal. 提起本訴，列 Stanford、Michigan、Rice、Baylor College of Medicine 為共同被告。
- **2025** 法院就 Michigan、Rice、Baylor 部分准予駁回（主要係屬人管轄及無共同侵害事實之認定），訴訟僅就 Stanford 繼續進行。
- **2025–2026** Stanford 提出駁回動議；法院駁回 Stanford 之 motion to dismiss，本案得以進入實體階段。
- **2026/4** 法院發布案件管理命令（case-management order），訂定事證開示、專家證人、處置動議及審判期日。陪審審判預定於 **2027 年 5 月**進行（若未先和解或經處置動議終結）。

## 4. 對台灣之啟示（Taiwan Implications）

1. **學術機構建置訓練資料集之法律風險**：本案係少見以「學術／非營利大學」為被告之 AI 訓練資料集著作權訴訟。台灣國科會、教育部及各大學 AI 研究中心若建置、釋出大型訓練資料集（含 ImageNet 衍生集、CC-licensed 以外之圖像集），應特別注意：(a) 圖像來源之授權盤點；(b) 「重製＋公開傳輸＋再散布」之分層責任；(c) 著作權法第 65 條合理使用四要件中「對市場潛在價值之影響」於商業圖庫之認定。
2. **資料集託管行為與模型訓練行為之分割評價**：本案原告策略上將「託管供下載」與「實際訓練 AI」拆解為兩個獨立侵害行為，並就前者主張直接侵害、就後者主張貢獻侵害。此分割方法可供台灣著作權人未來對學研機構或開源平台提起訴訟時參考（對應台灣著作權法第 22 條重製權、第 26 條之 1 公開傳輸權、第 87 條視為侵害之解構）。
3. **「教育研究合理使用」抗辯之邊界**：台灣著作權法第 46 條（學校授課必要之重製）及第 65 條第 2 項，傳統上對學術重製給予較寬解釋空間。本案 Stanford 動議駁回未果，預示美國法院對「學術機構免費再散布商業圖像作 AI 訓練」之合理使用抗辯採嚴格立場；台灣智財法院於未來類案中亦可比較法參考。
4. **與其他資料集案件之比較**：本案應與 LAION-5B 相關之 Andersen v. Stability AI（Case 3）、Kadrey v. Meta（Case 5，Books3/LibGen）並列觀察，三者共同形塑「訓練資料集本身（不論最終模型）作為侵害物件」之訴訟趨勢。

## 5. 媒體與資料來源

- Bloomberg Law：[Stanford, Michigan, Others Hit With Photo Set Copyright Suit](https://news.bloomberglaw.com/ip-law/stanford-michigan-others-hit-with-photo-set-copyright-suit)
- ChatGPT Is Eating The World：[Stanford University sued for copyright infringement based on ImageNet dataset](https://chatgptiseatingtheworld.substack.com/p/stanford-university-sued-for-copyright)
- p4sc4l Substack：[The Stanford/EVOX lawsuit and "dataset debt"](https://p4sc4l.substack.com/p/the-stanfordevox-lawsuit-shows-that)
- BYU Copyright Blog：[Train Photos? No, Train-ing Photos—of Cars!](https://copyright.byu.edu/blog/train-photos-no-train-ing-photos-of-cars)
- Law360 案件頁：<https://www.law360.com/cases/6774513b27cdad2c3044c40a>
- PacerMonitor 案件頁：<https://www.pacermonitor.com/public/case/56358691/EVOX_Productions,_LLC_v_The_Leland_Stanford_Junior_University_et_al>
