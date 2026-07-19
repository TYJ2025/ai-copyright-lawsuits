#!/usr/bin/env python3
from __future__ import annotations  # PEP 563 — let `X | None` hints parse on Python 3.9 (macOS system Python)
"""
backfill_docket_dates.py — 從 CourtListener 回填每件案件的 filedAt / updatedAt。

讀 data/cases.json 內各案的 `docket`（= CourtListener primary_docket_id，由
backfill_case_fields.py 從 cases_manifest.json 帶入），打 /dockets/{id}/：
    date_filed         → filedAt   （立案日）
    date_last_filing   → updatedAt （最後一筆 docket entry 日期；driving「as of」最準）
    （date_last_filing 缺時退而用 date_modified）

寫回 data/cases.json（idempotent，只動有變的值）。回填後：
  - dashboard 每案「目前進度 Current Status (as of …)」會顯示該案自己的 updatedAt，
    取代全站統一的 build 月份。
  - validate_data.py 的「filedAt/updatedAt 尚未回填」警告會隨之減少。

★ 不碰 git（交給 auto-push / 人工 commit）。改完 data/ 後記得跑 build.py 重生 dashboard.html。

用法：
  export COURTLISTENER_TOKEN=xxx          # CourtListener 帳號 → Profile → API token
  python3 scripts/backfill_docket_dates.py --dry-run     # 先看會改什麼，不寫檔
  python3 scripts/backfill_docket_dates.py               # 正式寫回 data/cases.json
  python3 scripts/backfill_docket_dates.py --case-id 6   # 只回填單一案件
  python3 scripts/backfill_docket_dates.py --limit 20    # 只處理前 20 件有 docket 的案件
  python3 scripts/backfill_docket_dates.py --force       # 連已有 filedAt/updatedAt 的也覆蓋更新

注意：updatedAt 每天可能變（新 entry），故定期重跑可保持同步；filedAt 不會變。
"""
import argparse
import json
import os
import sys
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from pathlib import Path

API_BASE = "https://www.courtlistener.com/api/rest/v4"
PROJECT_DIR = Path(__file__).resolve().parent.parent
CASES = PROJECT_DIR / "data" / "cases.json"


def api_get(path: str, token: str, params: dict | None = None):
    """GET CourtListener API. 回傳 (data, error_str)；error_str 為 None 代表成功。"""
    url = f"{API_BASE}{path}"
    if params:
        url = f"{url}?{urlencode(params)}"
    req = Request(url, headers={"Authorization": f"Token {token}", "Accept": "application/json"})
    try:
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8")), None
    except HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:200]
        return None, f"HTTP {e.code}: {body}"
    except URLError as e:
        return None, f"network: {e}"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="只印變更，不寫檔")
    ap.add_argument("--case-id", type=int, default=None, help="只回填單一 case id")
    ap.add_argument("--limit", type=int, default=None, help="最多處理幾件（有 docket 者）")
    ap.add_argument("--force", action="store_true", help="覆蓋已存在的 filedAt/updatedAt")
    ap.add_argument("--sleep", type=float, default=0.3, help="每次 API 呼叫間隔秒數（預設 0.3）")
    args = ap.parse_args()

    token = os.environ.get("COURTLISTENER_TOKEN")
    if not token:
        sys.exit("✗ 未設定 COURTLISTENER_TOKEN。\n"
                 "  到 CourtListener 帳號 → Profile → API，複製 token（純 40 字元，勿含 <>），然後：\n"
                 "  export COURTLISTENER_TOKEN=你的token")

    doc = json.load(open(CASES, encoding="utf-8"))
    cases = doc["data"] if isinstance(doc, dict) and "data" in doc else doc

    # 挑出要處理的案件
    targets = []
    for c in cases:
        if args.case_id is not None and c.get("id") != args.case_id:
            continue
        if not c.get("docket"):
            continue
        if not args.force and c.get("filedAt") and c.get("updatedAt"):
            continue  # 已回填、且非 force → 跳過
        targets.append(c)
    if args.limit:
        targets = targets[:args.limit]

    no_docket = sum(1 for c in cases if not c.get("docket"))
    print(f"待處理 {len(targets)} 件（總 {len(cases)} 件；{no_docket} 件無 docket 無法回填）")
    if not targets:
        print("沒有需要回填的案件。"); return

    changed = filed_set = updated_set = 0
    errors = []
    for i, c in enumerate(targets, 1):
        cid, dock = c["id"], c["docket"]
        data, err = api_get(f"/dockets/{dock}/", token)
        if err:
            errors.append((cid, dock, err))
            print(f"  [{i}/{len(targets)}] id={cid} docket={dock} ✗ {err}")
            if "HTTP 401" in err:
                print("  ← 401 = token 無效。請確認沒把 <> 一起貼進去，或到 Profile 重新產生。中止。")
                break
            time.sleep(args.sleep)
            continue

        filed = (data.get("date_filed") or "")[:10] or None
        updated = (data.get("date_last_filing") or data.get("date_modified") or "")[:10] or None

        before = (c.get("filedAt"), c.get("updatedAt"))
        if filed and c.get("filedAt") != filed:
            c["filedAt"] = filed; filed_set += 1
        if updated and c.get("updatedAt") != updated:
            c["updatedAt"] = updated; updated_set += 1
        after = (c.get("filedAt"), c.get("updatedAt"))
        if before != after:
            changed += 1
            print(f"  [{i}/{len(targets)}] id={cid} docket={dock} → filedAt={c.get('filedAt')} updatedAt={c.get('updatedAt')}")
        else:
            print(f"  [{i}/{len(targets)}] id={cid} docket={dock} = 無變更")
        time.sleep(args.sleep)

    print("=" * 56)
    print(f"異動 {changed} 件（filedAt 設 {filed_set}、updatedAt 設 {updated_set}）；錯誤 {len(errors)} 件")
    still_null = sum(1 for c in cases if not (c.get("filedAt") and c.get("updatedAt")))
    print(f"仍有 {still_null} 件 filedAt/updatedAt 未齊（多為無 docket 者）")

    if args.dry_run:
        print("\n[dry-run] 未寫檔。"); return
    if changed:
        json.dump(doc, open(CASES, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print(f"\n[✓] 已寫回 {CASES}")
        print("    下一步：python3 scripts/build.py  重生 dashboard.html")
    else:
        print("\n無變更，未寫檔。")


if __name__ == "__main__":
    main()
