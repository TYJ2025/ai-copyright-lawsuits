#!/usr/bin/env python3
"""
add_pending.py — 多區段合併寫入 .pending-review.json（main-board 慣例檔）。

main-board 的 update.sh 讀取頂層 {label, count, items, updated, url} 顯示
橘色待審 banner。本檔在頂層 schema 之外維護 "sections" 字典，讓多個
producer（weekly 新案掃描、daily-brief 時間軸候選…）各管各的區段、
互不覆蓋；頂層 items/count 每次寫入時由所有區段重新攤平合成。

用法：
  # 加一筆（同區段內以 title 去重，重複靜默跳過）
  python3 scripts/add_pending.py --section timeline --label "時間軸候選" \
      --title "Thomson Reuters v. ROSS 第三巡迴口頭辯論" \
      --subtitle "3d Cir. 25-2153 · 2026-06-11" --url "https://..."

  # 整段替換（producer 每次全量重寫自己的區段，如 weekly 掃描）
  echo '[{"title":"...","subtitle":"...","url":"..."}]' | \
      python3 scripts/add_pending.py --section new-cases --label "新案件待人工審核" --replace-stdin

  # 清空區段（人工審核完畢後）
  python3 scripts/add_pending.py --clear-section timeline
"""
from __future__ import annotations
import argparse
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PENDING_FILE = REPO_ROOT / ".pending-review.json"
DASHBOARD_URL = "https://tyj2025.github.io/ai-copyright-lawsuits/"
TPE = timezone(timedelta(hours=8))


def load() -> dict:
    if not PENDING_FILE.is_file():
        return {"sections": {}}
    try:
        doc = json.loads(PENDING_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"sections": {}}
    if "sections" not in doc:
        # 舊版單區段格式 → 遷移為 new-cases 區段
        doc = {
            "sections": {
                "new-cases": {
                    "label": doc.get("label", "新案件待人工審核"),
                    "items": doc.get("items", []),
                }
            }
        }
    return doc


def flatten_and_write(doc: dict) -> None:
    """由 sections 合成 main-board 讀的頂層欄位，原子寫回。"""
    sections = doc.get("sections", {})
    items, labels = [], []
    for sec in sections.values():
        sec_label = sec.get("label", "待審核")
        sec_items = sec.get("items", [])
        if not sec_items:
            continue
        labels.append(f"{sec_label} {len(sec_items)}")
        for it in sec_items:
            items.append({
                "title": f"【{sec_label}】{it.get('title', '')}",
                "subtitle": it.get("subtitle", ""),
                "url": it.get("url", ""),
            })
    out = {
        "label": "、".join(labels) if labels else "待人工審核",
        "count": len(items),
        "items": items,
        "updated": datetime.now(TPE).isoformat(timespec="seconds"),
        "source": "scripts/add_pending.py",
        "url": DASHBOARD_URL,
        "sections": sections,
    }
    tmp = PENDING_FILE.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, PENDING_FILE)
    print(f"  ✓ .pending-review.json：{len(sections)} 區段、共 {len(items)} 件待審")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--section", help="區段 key（如 new-cases / timeline / missing-cases）")
    ap.add_argument("--label", help="區段顯示名稱（首次建立區段時必填）")
    ap.add_argument("--title", help="條目標題")
    ap.add_argument("--subtitle", default="", help="條目副標（法院/日期等）")
    ap.add_argument("--url", default="", help="條目連結")
    ap.add_argument("--replace-stdin", action="store_true",
                    help="自 stdin 讀 JSON array 整段替換 --section")
    ap.add_argument("--clear-section", metavar="SECTION", help="清空指定區段")
    args = ap.parse_args()

    doc = load()
    sections = doc.setdefault("sections", {})

    if args.clear_section:
        removed = sections.pop(args.clear_section, None)
        n = len(removed.get("items", [])) if removed else 0
        print(f"  ✓ 區段 {args.clear_section} 已清空（移除 {n} 件）")
        flatten_and_write(doc)
        return

    if not args.section:
        ap.error("--section 必填（或用 --clear-section）")

    sec = sections.setdefault(args.section, {"label": args.label or "待審核", "items": []})
    if args.label:
        sec["label"] = args.label

    if args.replace_stdin:
        try:
            new_items = json.load(sys.stdin)
        except json.JSONDecodeError as e:
            sys.exit(f"✗ stdin 非合法 JSON array：{e}")
        if not isinstance(new_items, list):
            sys.exit("✗ stdin 須為 JSON array")
        sec["items"] = new_items
        print(f"  ✓ 區段 {args.section} 整段替換為 {len(new_items)} 件")
    else:
        if not args.title:
            ap.error("--title 必填（或用 --replace-stdin / --clear-section）")
        if any(it.get("title") == args.title for it in sec["items"]):
            print(f"  ↺ 已存在（{args.title}），跳過")
            return
        sec["items"].insert(0, {"title": args.title,
                                "subtitle": args.subtitle, "url": args.url})
        print(f"  ✓ 區段 {args.section} 新增：{args.title}")

    flatten_and_write(doc)


if __name__ == "__main__":
    main()
