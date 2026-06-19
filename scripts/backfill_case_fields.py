#!/usr/bin/env python3
"""
backfill_case_fields.py — 把 dashboard 過去靠 JS 即時「關鍵字推測」的分類，
固化成 data/cases.json 的正式欄位，讓資料成為 source of truth、可人工修正。

新增/更新欄位（每件案件）：
  jurisdiction   us | uk | eu | cn | asia-other | other   ← classifyJurisdiction
  country        國旗+名稱（非美國案）或 "🇺🇸 美國"          ← classifyCountry / isNonUS
  technology     llm | music | image | code | video | search ← classifyTech
  plaintiffType  author | music | artist | media | code | creator | reference ← classifyPlaintiff
  workType       著作類型（圖表用）                          ← classifyWorkType
  isNonUS        bool                                        ← isNonUS
  sourceCount    int（data/case_sources.json 內該案連結數）
  docket         CourtListener primary_docket_id（manifest 有才填，否則 null）
  filedAt        null  ← TODO: 從 CourtListener 回填
  updatedAt      null  ← TODO: 從 CourtListener / daily-brief 回填

★ 規則完全比照 templates/dashboard.template.html 內的同名 JS 函式，確保固化後
  與目前畫面顯示一致（值要對得上 <select> 篩選選項與 chart drill 比較）。
  日後新增案件或修正分類，直接重跑本腳本（idempotent），或手動改 cases.json 後
  保留人工值（見 --preserve-manual）。

用法：
  python3 scripts/backfill_case_fields.py            # 寫回 data/cases.json
  python3 scripts/backfill_case_fields.py --dry-run  # 只印變更摘要，不寫檔
"""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
DATA = PROJECT_DIR / "data"
CASES = DATA / "cases.json"
SOURCES = DATA / "case_sources.json"
MANIFEST = PROJECT_DIR / "scripts" / "cases_manifest.json"

# ── 與 dashboard.template.html 同步的關鍵字表（勿單方面改） ──
NON_US_KEYWORDS = ['CJEU', 'UK High Court', 'European Union', 'Budapest', '歐盟', '加拿大',
    '印度', '德國', '法國', '英國', 'Ontario', 'Delhi', 'German', 'Munich', 'Paris', 'France',
    'Canada', 'Hamburg', '漢堡', '丹麥', 'Copenhagen', 'Denmark', '韓國', 'Seoul', 'South Korea',
    '中國', '北京', '廣州', '杭州', 'Beijing Internet Court', 'Guangzhou Internet Court', 'China',
    '日本', 'Tokyo', 'Japan', '巴西', 'Brazil', '義大利', 'Italy', '荷蘭', 'Netherlands',
    'Amsterdam', 'England', 'London', 'India', 'Germany']

NEW_FIELDS = ["jurisdiction", "country", "technology", "plaintiffType",
              "workType", "isNonUS", "sourceCount", "docket", "filedAt", "updatedAt"]


def is_non_us(court: str) -> bool:
    return any(k in court for k in NON_US_KEYWORDS)


def classify_country(court: str) -> str:
    # 比照 classifyCountry（case-sensitive regex .test）
    rules = [
        (r'UK|英國', '🇬🇧 英國'),
        (r'France|Paris|法國', '🇫🇷 法國'),
        (r'German|Munich|Hamburg|德國|漢堡', '🇩🇪 德國'),
        (r'Canada|Ontario|加拿大', '🇨🇦 加拿大'),
        (r'India|Delhi|印度', '🇮🇳 印度'),
        (r'CJEU|European Union|歐盟', '🇪🇺 歐盟'),
        (r'Denmark|丹麥|Copenhagen', '🇩🇰 丹麥'),
        (r'Korea|韓國|Seoul', '🇰🇷 韓國'),
        (r'China|中國|北京|廣州|杭州|Beijing|Guangzhou', '🇨🇳 中國'),
        (r'Japan|日本|Tokyo', '🇯🇵 日本'),
        (r'Brazil|巴西', '🇧🇷 巴西'),
        (r'Italy|義大利', '🇮🇹 義大利'),
        (r'Netherlands|荷蘭', '🇳🇱 荷蘭'),
    ]
    for pat, label in rules:
        if re.search(pat, court):
            return label
    return '其他'


def classify_jurisdiction(court: str) -> str:
    uk = ['UK High Court', '英國', 'England', 'London']
    eu = ['CJEU', 'European Union', '歐盟', 'Budapest', '德國', '法國', 'German', 'Munich',
          'Paris', 'France', 'Hamburg', '漢堡', '丹麥', 'Copenhagen', 'Denmark', '荷蘭',
          'Netherlands', 'Amsterdam', '義大利', 'Italy']
    cn = ['中國', '北京', '廣州', '杭州', 'Beijing Internet Court', 'Guangzhou Internet Court', 'China']
    asia = ['印度', 'Delhi', 'India', '韓國', 'Seoul', 'South Korea', '日本', 'Tokyo', 'Japan']
    if any(k in court for k in uk): return 'uk'
    if any(k in court for k in eu): return 'eu'
    if any(k in court for k in cn): return 'cn'
    if any(k in court for k in asia): return 'asia-other'
    if any(k in court for k in NON_US_KEYWORDS): return 'other'
    return 'us'


def classify_tech(c: dict) -> str:
    n = (c.get('name', '') + ' ' + c.get('issues', '') + ' ' + c.get('defendants', '')).lower()
    if re.search(r'歌詞|lyric|music|song|umg|concord|bmg|riaa', n): return 'music'
    if re.search(r'圖像|image|illustrat|photo|getty|stability|midjourney|dall-e|art', n): return 'image'
    if re.search(r'程式碼|code|copilot|github', n): return 'code'
    if re.search(r'影片|video|youtube|snap|tiktok|bytedance', n): return 'video'
    if re.search(r'搜尋|search|perplexity|摘要|summar', n): return 'search'
    return 'llm'


def classify_plaintiff(c: dict) -> str:
    n = (c.get('name', '') + ' ' + c.get('issues', '')).lower()
    if re.search(r'音樂|music|lyric|song|umg|concord|bmg|riaa', n): return 'music'
    if re.search(r'藝術家|artist|illustrat|photo|getty|攝影|畫家', n): return 'artist'
    if re.search(r'新聞|news|nyt|times|media|journal|tribune|reuters|cbc|afp', n): return 'media'
    if re.search(r'程式|code|copilot|github|software', n): return 'code'
    if re.search(r'youtube|影片|creator|youtuber|snap', n): return 'creator'
    if re.search(r'百科|encyclop|britannica|dictionary|merriam|webster', n): return 'reference'
    return 'author'


def classify_work_type(c: dict) -> str:
    claims = c.get('claims') or []
    n = (c.get('name', '') + ' ' + c.get('defendants', '') + ' ' + ' '.join(claims)).lower()
    if re.search(r'music|recording|umg|bmg|concord|suno|udio|koda|gema|lyrics|mureka', n): return '音樂 Music'
    if re.search(r'news|times|tribune|journal|post|gazette|daily|intercept|raw story|carreyrou|ani media|folha|dpcmo|publisher|newspaper|chegg|rtl|medusa|dpg', n): return '新聞媒體 News'
    if re.search(r'author|guild|book|penguin|huckabee|cambronne|alter |apress|basbanes|chicken soup|encyclopa|merriam|britannica|denial', n): return '書籍出版 Books'
    if re.search(r'image|getty|photo|pierce|photobucket|stock', n): return '圖片攝影 Images'
    if re.search(r'artist|andersen|disney|warner|midjourney|stability|illustrat|coda|ghibli', n): return '視覺藝術 Visual Art'
    if re.search(r'voice|lovo|eleven|vacker|lehrman', n): return '語音聲紋 Voice'
    if re.search(r'video|film|alcon|strike 3|ted entertain|snap|bytedance|tiktok|runway|ace cam|gardner|businesss', n): return '影視內容 Film/Video'
    if re.search(r'code|github|copilot|doe v', n): return '程式碼 Code'
    if re.search(r'3d|beaulier|roblox', n): return '3D 模型 3D Models'
    if re.search(r'thaler|perlmutter|li yunkai|李昀鍇', n): return 'AI 可著作性 AI Copyrightability'
    if re.search(r'data|snowflake|reddit|serpapi|gracenote|kogon', n): return '資料平台 Data'
    return '其他 Other'


def load_source_counts() -> dict:
    if not SOURCES.is_file():
        return {}
    doc = json.load(open(SOURCES, encoding="utf-8"))
    data = doc.get("data", doc)
    out = {}
    if isinstance(data, dict):
        for k, v in data.items():
            try:
                cid = int(k)
            except (ValueError, TypeError):
                continue
            out[cid] = len(v) if isinstance(v, list) else (1 if v else 0)
    return out


def load_dockets() -> dict:
    if not MANIFEST.is_file():
        return {}
    m = json.load(open(MANIFEST, encoding="utf-8"))
    out = {}
    for row in (m if isinstance(m, list) else []):
        cid = row.get("case_id")
        dock = row.get("primary_docket_id")
        if cid is not None and dock:
            out[int(cid)] = dock
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="只印摘要，不寫檔")
    args = ap.parse_args()

    doc = json.load(open(CASES, encoding="utf-8"))
    cases = doc["data"] if isinstance(doc, dict) and "data" in doc else doc
    src_counts = load_source_counts()
    dockets = load_dockets()

    changed = 0
    for c in cases:
        court = c.get("court", "")
        cid = c.get("id")
        non_us = is_non_us(court)
        new = {
            "jurisdiction": classify_jurisdiction(court),
            "country": classify_country(court) if non_us else "🇺🇸 美國",
            "technology": classify_tech(c),
            "plaintiffType": classify_plaintiff(c),
            "workType": classify_work_type(c),
            "isNonUS": non_us,
            "sourceCount": src_counts.get(cid, 0),
            "docket": dockets.get(cid),  # None if unknown
            "filedAt": c.get("filedAt"),      # 保留既有人工值；預設 None
            "updatedAt": c.get("updatedAt"),  # 保留既有人工值；預設 None
        }
        for k, v in new.items():
            if c.get(k) != v and not (k in ("filedAt", "updatedAt") and c.get(k) is None and v is None):
                changed += 1
            c[k] = v

    # 摘要
    from collections import Counter
    print("固化結果摘要：")
    for f in ("jurisdiction", "country", "technology", "plaintiffType"):
        dist = Counter(c[f] for c in cases)
        print(f"  {f}: " + ", ".join(f"{k}={v}" for k, v in dist.most_common()))
    no_src = [c["id"] for c in cases if c["sourceCount"] == 0]
    no_dock = sum(1 for c in cases if c["docket"] is None)
    print(f"  無來源案件 {len(no_src)} 件: {no_src}")
    print(f"  無 docket(manifest 未涵蓋) {no_dock} 件；filedAt/updatedAt 全為 null（待回填）")
    print(f"  欄位值異動 {changed} 處")

    if args.dry_run:
        print("\n[dry-run] 未寫檔。")
        return
    json.dump(doc, open(CASES, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\n[✓] 已寫回 {CASES}")


if __name__ == "__main__":
    main()
