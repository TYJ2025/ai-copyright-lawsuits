#!/usr/bin/env python3
"""把「案件進展」回寫到 data/cases.json 的 progress 欄位（daily-brief 每則案件型快訊必跑）。

設計原則與 add_news.py 相同：只認一個入口、自動去重、重跑無害。

用法：
  # 1) 先查案件 id（支援案名 / 案號 / 當事人片段，大小寫不拘）
  python3 scripts/update_case_progress.py --find "Bartz"
  python3 scripts/update_case_progress.py --find "3:24-cv-05417"

  # 2) 回寫進展（date 用新聞事件日，不是今天）
  python3 scripts/update_case_progress.py --case-id 6 \
      --date 2026-07-20 \
      --note "和解終局核准：Martínez-Olguín 法官核准 15 億美元集體和解，律師費砍至約 1.016 億美元" \
      --status settled

  # 3) 只改欄位不加 progress
  python3 scripts/update_case_progress.py --case-id 109 --court "LG München I" --judge "42. Zivilkammer"

去重：progress 內若已存在同一個【YYYY/M/D】標記即略過（--force 可強制附加）。
updatedAt 預設寫入今日（Asia/Taipei），可用 --updated-at 覆寫。
本 script 不碰 git，也不跑 build.py；由呼叫端（daily-brief.sh）負責。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

PATH = Path(__file__).resolve().parent.parent / "data" / "cases.json"
STATUS_VALUES = {"active", "dismissed", "settled", "appeal", "decided", "mdl"}


def today_taipei() -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=8)).strftime("%Y-%m-%d")


def marker(iso_date: str) -> str:
    """2026-07-20 -> 【2026/7/20】（與 news.json / progress 既有慣例一致）"""
    y, m, d = iso_date.split("-")
    return f"【{int(y)}/{int(m)}/{int(d)}】"


BLOCK_RE = re.compile(r"【(\d{4})/(\d{1,2})/(\d{1,2})】")


def block_date(text):
    """取一段文字開頭的【YYYY/M/D】並轉成可排序字串；沒有標記回 None。"""
    m = BLOCK_RE.match(text.strip())
    if not m:
        return None
    return "%s-%02d-%02d" % (m.group(1), int(m.group(2)), int(m.group(3)))


def insert_block(progress, iso_date, new_block):
    """把 new_block 依日期插進 progress 的正確位置（新的在後）。

    無日期標記的敘述段落（多為案件背景）一律留在最前面，不參與排序。
    """
    progress = (progress or "").rstrip()
    if not progress:
        return new_block
    parts = [p for p in progress.split("\n\n") if p.strip()]
    dated = [(block_date(p), p) for p in parts]
    idx = len(parts)
    for i, (d, _) in enumerate(dated):
        if d and d > iso_date:
            idx = i
            break
    parts.insert(idx, new_block)
    return "\n\n".join(parts)


def find_cases(cases, needle):
    n = needle.lower()
    return [c for c in cases if n in json.dumps(c, ensure_ascii=False).lower()]


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    ap.add_argument("--find", help="以關鍵字搜尋案件，列出 id / 案名 / 案號後結束")
    ap.add_argument("--case-id", type=int)
    ap.add_argument("--date", help="新聞事件日 YYYY-MM-DD（progress 標記用）")
    ap.add_argument("--note", help="一句話進展摘要，30 至 120 字")
    ap.add_argument("--status", choices=sorted(STATUS_VALUES))
    ap.add_argument("--court")
    ap.add_argument("--judge")
    ap.add_argument("--docket")
    ap.add_argument("--updated-at", help="預設今日（Asia/Taipei）")
    ap.add_argument("--force", action="store_true", help="即使同日標記已存在也附加")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    doc = json.loads(PATH.read_text())
    cases = doc["data"]

    if args.find:
        hits = find_cases(cases, args.find)
        if not hits:
            print(f"[✗] 查無案件：{args.find}")
            sys.exit(1)
        for c in hits[:25]:
            print(f"{c['id']:5}  {c['name'][:52]:54} {c['court'][:38]:40} status={c['status']}")
        if len(hits) > 25:
            print(f"...（另有 {len(hits) - 25} 筆，請用更精確的關鍵字）")
        return

    if args.case_id is None:
        sys.exit("[✗] 需要 --case-id（或用 --find 先查）")

    case = next((c for c in cases if c["id"] == args.case_id), None)
    if case is None:
        sys.exit(f"[✗] case id {args.case_id} 不存在於 cases.json")

    if args.note and not args.date:
        sys.exit("[✗] --note 必須搭配 --date")

    changed = []

    if args.note:
        mk = marker(args.date)
        progress = case.get("progress") or ""
        if mk in progress and not args.force:
            print(f"[=] case {args.case_id} progress 已有 {mk}，略過（--force 可強制附加）")
        else:
            case["progress"] = insert_block(progress, args.date, mk + args.note.strip())
            changed.append(f"progress {mk}")

    for field, val in (("status", args.status), ("court", args.court),
                       ("judge", args.judge), ("docket", args.docket)):
        if val and case.get(field) != val:
            case[field] = val
            changed.append(f"{field}={val}")

    if changed:
        case["updatedAt"] = args.updated_at or today_taipei()
        changed.append(f"updatedAt={case['updatedAt']}")

    if not changed:
        print("[=] 無變更")
        return

    if args.dry_run:
        print(f"[dry-run] case {args.case_id}（{case['name'][:40]}）將更新：{', '.join(changed)}")
        if args.note:
            print("---- progress 尾段 ----")
            print(case["progress"][-400:])
        return

    PATH.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n")
    print(f"[✓] case {args.case_id}（{case['name'][:40]}）已更新：{', '.join(changed)}")


if __name__ == "__main__":
    main()
