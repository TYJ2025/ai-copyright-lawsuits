#!/usr/bin/env python3
"""
validate_data.py — data/*.json 一致性檢查（CI 與本機共用）。

ERROR（exit 1，會擋 CI）：
  - 任一 data/*.json 無法解析（malformed JSON）
  - 案件 id 重複
  - 缺少必填欄位或必填欄位為空
  - status / jurisdiction / technology / plaintiffType 值不在合法 enum
  - case_sources / 任一案件的 updatedAt 是未來日期或非法 ISO 日期

WARNING（不擋 CI，只提示，給人工 backlog）：
  - 案件 id 不連續（已知缺號，如 40）
  - 案件無任何來源（sourceCount == 0）
  - 案件缺固化欄位（jurisdiction/country/... 尚未 backfill）
  - filedAt / updatedAt 為 null（待回填）

選用：
  --check-links   對所有來源 URL 發 HEAD 請求，列出失效連結（需網路，預設關閉）

用法：
  python3 scripts/validate_data.py
  python3 scripts/validate_data.py --check-links
"""
from __future__ import annotations
import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
DATA = PROJECT_DIR / "data"

REQUIRED_FIELDS = ["id", "name", "court", "judge", "status",
                   "claims", "defendants", "issues", "progress", "taiwan"]
FORMALIZED_FIELDS = ["jurisdiction", "country", "technology", "plaintiffType",
                     "workType", "isNonUS", "sourceCount"]

STATUS_ENUM = {"active", "decided", "settled", "appeal", "dismissed", "mdl"}
JURISDICTION_ENUM = {"us", "uk", "eu", "cn", "asia-other", "other"}
TECH_ENUM = {"llm", "music", "image", "code", "video", "search"}
PLAINTIFF_ENUM = {"author", "music", "artist", "media", "code", "creator", "reference"}

ALL_DATA_FILES = ["cases.json", "case_sources.json", "fair_use_cases.json",
                  "official_reports.json", "news.json", "timeline.json", "_meta.json"]

errors: list[str] = []
warnings: list[str] = []


def err(m): errors.append(m)
def warn(m): warnings.append(m)


def load(name: str):
    path = DATA / name
    if not path.is_file():
        err(f"[{name}] 檔案不存在")
        return None
    try:
        return json.load(open(path, encoding="utf-8"))
    except json.JSONDecodeError as e:
        err(f"[{name}] JSON 解析失敗：{e}")
        return None


def payload(doc):
    return doc["data"] if isinstance(doc, dict) and "data" in doc else doc


def valid_iso(s: str) -> bool:
    try:
        datetime.strptime(s, "%Y-%m-%d")
        return True
    except (ValueError, TypeError):
        return False


def check_cases(check_links: bool):
    doc = load("cases.json")
    if doc is None:
        return
    cases = payload(doc)
    if not isinstance(cases, list):
        err("[cases.json] data 不是陣列")
        return

    ids = [c.get("id") for c in cases]
    # id 唯一
    seen, dups = set(), set()
    for i in ids:
        if i in seen:
            dups.add(i)
        seen.add(i)
    if dups:
        err(f"[cases.json] 重複 id：{sorted(dups)}")
    # id 連續（warn）
    numeric = sorted(i for i in ids if isinstance(i, int))
    if numeric:
        gaps = sorted(set(range(numeric[0], numeric[-1] + 1)) - set(numeric))
        if gaps:
            warn(f"[cases.json] id 不連續，缺號：{gaps}")

    today = date.today()
    no_src, no_formal, no_dates = [], [], []
    for c in cases:
        cid = c.get("id")
        # 必填
        for f in REQUIRED_FIELDS:
            v = c.get(f)
            if v is None or (isinstance(v, str) and not v.strip()) or (isinstance(v, list) and not v):
                err(f"[cases.json] id={cid} 缺必填欄位或為空：{f}")
        # enum
        if c.get("status") not in STATUS_ENUM:
            err(f"[cases.json] id={cid} status 非法：{c.get('status')!r}")
        if "jurisdiction" in c and c["jurisdiction"] not in JURISDICTION_ENUM:
            err(f"[cases.json] id={cid} jurisdiction 非法：{c.get('jurisdiction')!r}")
        if "technology" in c and c["technology"] not in TECH_ENUM:
            err(f"[cases.json] id={cid} technology 非法：{c.get('technology')!r}")
        if "plaintiffType" in c and c["plaintiffType"] not in PLAINTIFF_ENUM:
            err(f"[cases.json] id={cid} plaintiffType 非法：{c.get('plaintiffType')!r}")
        # 固化欄位是否齊全（warn）
        if any(f not in c for f in FORMALIZED_FIELDS):
            no_formal.append(cid)
        # 來源（warn）
        if c.get("sourceCount", 0) == 0:
            no_src.append(cid)
        # 日期合理性
        for f in ("filedAt", "updatedAt"):
            v = c.get(f)
            if v in (None, ""):
                no_dates.append(cid)
            elif not valid_iso(v):
                err(f"[cases.json] id={cid} {f} 非合法 YYYY-MM-DD：{v!r}")
            elif datetime.strptime(v, "%Y-%m-%d").date() > today:
                err(f"[cases.json] id={cid} {f} 是未來日期：{v}")

    if no_formal:
        warn(f"[cases.json] {len(no_formal)} 件缺固化欄位（需跑 backfill_case_fields.py）：{no_formal[:20]}{'…' if len(no_formal)>20 else ''}")
    if no_src:
        warn(f"[cases.json] {len(no_src)} 件無來源（sourceCount=0）：{sorted(set(no_src))}")
    if no_dates:
        warn(f"[cases.json] filedAt/updatedAt 尚未回填（{len(set(no_dates))} 件至少缺一）")

    # 來源檔交叉檢查
    sdoc = load("case_sources.json")
    if sdoc is not None:
        sdata = payload(sdoc)
        if isinstance(sdata, dict):
            case_ids = set(i for i in ids if isinstance(i, int))
            for k in sdata:
                try:
                    if int(k) not in case_ids:
                        err(f"[case_sources.json] 來源指向不存在的案件 id：{k}")
                except (ValueError, TypeError):
                    err(f"[case_sources.json] 非法 case id key：{k!r}")
            if check_links:
                check_source_links(sdata)


def check_source_links(sdata: dict):
    import urllib.request
    import urllib.error
    urls = []
    for v in sdata.values():
        if isinstance(v, list):
            urls += [s.get("url") for s in v if isinstance(s, dict) and s.get("url")]
    print(f"[links] 檢查 {len(urls)} 條來源連結 …")
    dead = []
    for u in urls:
        try:
            req = urllib.request.Request(u, method="HEAD",
                                         headers={"User-Agent": "Mozilla/5.0 (link-check)"})
            urllib.request.urlopen(req, timeout=15)
        except urllib.error.HTTPError as e:
            if e.code >= 400 and e.code not in (403, 405, 999):  # 403/405 常為反爬，非真失效
                dead.append((u, e.code))
        except Exception as e:
            dead.append((u, type(e).__name__))
    if dead:
        warn(f"[links] {len(dead)} 條疑似失效：" + "; ".join(f"{u} ({c})" for u, c in dead[:15]))
    else:
        print("[links] 全部可達。")


def check_other_files():
    # 其餘檔只要能解析即可（add_news.py / 手改可能寫壞）
    for name in ALL_DATA_FILES:
        if name == "cases.json":
            continue
        load(name)  # 解析失敗會自動進 errors


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--check-links", action="store_true", help="HTTP 檢查來源連結（需網路）")
    args = ap.parse_args()

    check_cases(args.check_links)
    check_other_files()

    print("=" * 56)
    if warnings:
        print(f"⚠️  {len(warnings)} 個警告（不擋 CI）：")
        for w in warnings:
            print("   - " + w)
    if errors:
        print(f"❌ {len(errors)} 個錯誤：")
        for e in errors:
            print("   - " + e)
        print("=" * 56)
        sys.exit(1)
    print("✅ 資料驗證通過（無錯誤）。")
    print("=" * 56)


if __name__ == "__main__":
    main()
