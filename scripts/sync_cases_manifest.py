#!/usr/bin/env python3
"""從 cases.json 重生 scripts/cases_manifest.json。

manifest 是 fetch_courtlistener_docket.py / batch_refresh.py 的 source of truth，
但過去靠人工維護，與 cases.json 逐漸脫鉤（2026-08-05 檢查：manifest 111 筆、
cases.json 有 docket 者 119 筆，10 件新案沒進 manifest、2 件已無 docket 仍留著）。
本 script 讓 manifest 成為 cases.json 的衍生物，每月 refresh 前先跑一次。

只納入有 `docket`（CourtListener docket id）的案件；非美國案件與尚未查號者
自然被排除。既有 manifest 的 secondary_docket_ids 會保留。

用法：
  python3 scripts/sync_cases_manifest.py            # dry-run，列出增減
  python3 scripts/sync_cases_manifest.py --apply
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CASES = ROOT / "data" / "cases.json"
MANIFEST = ROOT / "scripts" / "cases_manifest.json"


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    cases = json.loads(CASES.read_text())["data"]
    old = json.loads(MANIFEST.read_text()) if MANIFEST.is_file() else []
    old_by_id = {x["case_id"]: x for x in old}

    new = []
    for c in cases:
        if not c.get("docket"):
            continue
        prev = old_by_id.get(c["id"], {})
        new.append({
            "case_id": c["id"],
            "name": c["name"],
            "court": c["court"],
            "judge": c.get("judge") or "",
            "status": c["status"],
            "primary_docket_id": c["docket"],
            "secondary_docket_ids": prev.get("secondary_docket_ids", []),
            "progress_excerpt": (c.get("progress") or "")[:600],
        })
    new.sort(key=lambda x: x["case_id"])

    new_ids = {x["case_id"] for x in new}
    old_ids = set(old_by_id)
    added, removed = sorted(new_ids - old_ids), sorted(old_ids - new_ids)
    changed = [i for i in (new_ids & old_ids)
               if old_by_id[i].get("primary_docket_id")
               != next(x for x in new if x["case_id"] == i)["primary_docket_id"]]

    print(f"manifest：{len(old)} → {len(new)} 筆")
    if added:
        print(f"  新增 {len(added)} 件：{added}")
    if removed:
        print(f"  移除 {len(removed)} 件（cases.json 已無 docket 或案件已刪）：{removed}")
    if changed:
        print(f"  docket id 變更 {len(changed)} 件：{changed}")
    if not (added or removed or changed):
        print("  無變更")

    if not args.apply:
        print("\n[dry-run] 加 --apply 實際寫入")
        return
    MANIFEST.write_text(json.dumps(new, ensure_ascii=False, indent=1) + "\n")
    print(f"\n[✓] 已寫入 {MANIFEST.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
