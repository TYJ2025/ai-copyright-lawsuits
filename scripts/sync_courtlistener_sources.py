#!/usr/bin/env python3
"""把 cases.json 的 docket id 同步成 case_sources.json 的 CourtListener 連結。

dashboard 卡片上的「CourtListener Docket」按鈕讀的是 `data/case_sources.json`
（模板找 label 含 courtlistener 的項目），不是 cases.json 的 `docket` 欄位。
兩邊各自維護的結果就是「明明有 docket id 卻沒有按鈕」。本 script 補這個落差。

用法：
  python3 scripts/sync_courtlistener_sources.py            # dry-run，列出將補的案件
  python3 scripts/sync_courtlistener_sources.py --apply    # 實際寫入
  python3 scripts/sync_courtlistener_sources.py --report   # 只列出「無連結」清單並分類

CourtListener 的 /docket/<id>/ 會自動導向含 slug 的正式網址，故不需要 slug。
本 script 不碰 git，也不跑 build.py；由呼叫端負責。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CASES = ROOT / "data" / "cases.json"
SOURCES = ROOT / "data" / "case_sources.json"
LABEL = "CourtListener Docket"


def has_cl(entries):
    return any("courtlistener" in (e.get("label", "") + e.get("url", "")).lower()
               for e in entries)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--report", action="store_true",
                    help="列出仍無 CourtListener 連結的案件並分類")
    args = ap.parse_args()

    cases = json.loads(CASES.read_text())["data"]
    sdoc = json.loads(SOURCES.read_text())
    src = sdoc["data"]

    todo, no_docket_us, non_us = [], [], []
    for c in cases:
        entries = src.get(str(c["id"]), [])
        if has_cl(entries):
            continue
        if c.get("docket"):
            todo.append(c)
        elif c.get("isNonUS"):
            non_us.append(c)
        else:
            no_docket_us.append(c)

    if args.report:
        print(f"仍無 CourtListener 連結：{len(todo) + len(no_docket_us) + len(non_us)} 件\n")
        print(f"[可自動補] 有 docket id 但 case_sources 缺連結：{len(todo)} 件")
        for c in todo:
            print(f"  {c['id']:5} {c['name'][:52]:54} docket={c['docket']}")
        print(f"\n[需查號] 美國案件但無 docket id：{len(no_docket_us)} 件")
        for c in no_docket_us:
            print(f"  {c['id']:5} {c['name'][:52]:54} {c['court'][:34]}")
        print(f"\n[不適用] 非美國案件：{len(non_us)} 件")
        return

    if not todo:
        print("[=] 無可補之案件（有 docket id 者皆已有連結）")
        return

    for c in todo:
        url = f"https://www.courtlistener.com/docket/{c['docket']}/"
        entry = {"label": LABEL, "url": url}
        key = str(c["id"])
        src.setdefault(key, []).insert(0, entry)
        print(f"{'[✓]' if args.apply else '[dry-run]'} case {c['id']:5} "
              f"{c['name'][:44]:46} → {url}")

    if not args.apply:
        print(f"\n共 {len(todo)} 件待補（加 --apply 實際寫入）")
        return

    SOURCES.write_text(json.dumps(sdoc, ensure_ascii=False, indent=1) + "\n")
    print(f"\n[✓] 已寫入 {len(todo)} 筆連結到 case_sources.json")


if __name__ == "__main__":
    main()
