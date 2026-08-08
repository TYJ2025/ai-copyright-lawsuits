#!/usr/bin/env python3
"""
add_news.py — append a news item to data/news.json (Phase 5+ pipeline).

Reads data/news.json (envelope: {"$schema":"news.v1","data":{"items":[],"archive":[]}}),
prepends the new entry to data.items, rotates items older than N days
(default 3) to data.archive, writes back atomically.

After Phase 7 cutover, daily-brief calls this directly instead of regex-editing
dashboard.html. Until then it's available for unit testing.

Usage:
  python3 scripts/add_news.py --added-at 2026-06-03 --text "【2026/6/2】XXX：..." --url https://...
  echo '{"addedAt":"...","text":"...","url":"..."}' | python3 scripts/add_news.py --stdin
"""
from __future__ import annotations
import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
DATA_FILE = PROJECT_DIR / "data" / "news.json"
ARCHIVE_THRESHOLD_DAYS = 3
# 頂部跑馬燈至少保留幾則。滿 3 天本應歸檔，但若近日無新快訊會只剩 1 則、版面過空，
# 故以 MIN_ITEMS 保底：不足時自 archive 回補最新者。
MIN_ITEMS = 3


def parse_date(s: str) -> date:
    return date.fromisoformat(s)


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter,
    )
    ap.add_argument("--added-at", help="YYYY-MM-DD (today in Asia/Taipei)")
    ap.add_argument("--text", help="news text (Traditional Chinese)")
    ap.add_argument("--url", default="", help="source URL (optional)")
    ap.add_argument("--stdin", action="store_true",
                    help='read JSON {"addedAt","text","url"} from stdin')
    ap.add_argument("--archive-threshold-days", type=int,
                    default=ARCHIVE_THRESHOLD_DAYS,
                    help=f"items older than this go to archive (default {ARCHIVE_THRESHOLD_DAYS})")
    ap.add_argument("--min-items", type=int, default=MIN_ITEMS,
                    help=f"ticker 至少保留幾則，不足時自 archive 回補 (default {MIN_ITEMS})")
    ap.add_argument("--rebalance", action="store_true",
                    help="不新增條目，只依 threshold 與 min-items 重整 items/archive")
    ap.add_argument("--dry-run", action="store_true",
                    help="print resulting state but do not write")
    args = ap.parse_args()

    # Get entry
    entry = None
    if args.rebalance:
        pass
    elif args.stdin:
        try:
            entry = json.load(sys.stdin)
        except json.JSONDecodeError as e:
            sys.exit(f"✗ invalid JSON from stdin: {e}")
    else:
        if not args.added_at or not args.text:
            ap.error("--added-at and --text required (unless --stdin)")
        entry = {"addedAt": args.added_at, "text": args.text, "url": args.url}

    # Validate
    if entry is not None:
        try:
            parse_date(entry["addedAt"])
        except (KeyError, ValueError) as e:
            sys.exit(f"✗ invalid addedAt (need YYYY-MM-DD): {e}")
        if not entry.get("text", "").strip():
            sys.exit("✗ text is empty")
        entry.setdefault("url", "")

    # Load
    if not DATA_FILE.is_file():
        sys.exit(f"✗ {DATA_FILE} missing — run migrate_html_to_json.py first")
    doc = json.load(open(DATA_FILE, encoding="utf-8"))
    if doc.get("$schema", "").split(".")[0] != "news":
        sys.exit(f"✗ unexpected schema: {doc.get('$schema')}")
    data = doc.setdefault("data", {})
    items = data.setdefault("items", [])
    archive = data.setdefault("archive", [])

    if entry is not None:
        # Dedupe (same addedAt + text)
        for existing in items + archive:
            if (existing.get("addedAt") == entry["addedAt"]
                    and existing.get("text") == entry["text"]):
                print(f"  ↺ already present (addedAt={entry['addedAt']}); no change")
                return
        # Prepend
        items.insert(0, entry)

    # Rotate（items 由新至舊；archive 亦維持新者在前）
    cutoff = date.today() - timedelta(days=args.archive_threshold_days)
    stay, to_rotate = [], []
    for it in items:
        try:
            d = parse_date(it["addedAt"])
        except (KeyError, ValueError):
            stay.append(it)
            continue
        (to_rotate if d <= cutoff else stay).append(it)

    # 保底：items 不足 MIN_ITEMS 時，先留下本該歸檔者，再自 archive 回補最新者
    pulled_back = 0
    while len(stay) < args.min_items and to_rotate:
        stay.append(to_rotate.pop(0))
    while len(stay) < args.min_items and archive:
        # archive 的排序未必嚴格，取 addedAt 最新者回補而非取 index 0
        newest = max(range(len(archive)),
                     key=lambda i: archive[i].get("addedAt", ""))
        stay.append(archive.pop(newest))
        pulled_back += 1

    # to_rotate 為新至舊，反向 prepend 才能維持 archive 新者在前
    for it in reversed(to_rotate):
        archive.insert(0, it)
    rotated = len(to_rotate)

    data["items"] = stay
    data["archive"] = archive

    # Provenance
    doc["lastUpdatedBy"] = "add_news.py"
    doc["lastUpdatedAt"] = datetime.now().astimezone().isoformat()

    if args.dry_run:
        print(json.dumps(doc, ensure_ascii=False, indent=2)[:2000])
        print(f"\n  [dry-run] items={len(stay)}  archive={len(archive)}  "
              f"rotated={rotated}  pulled_back={pulled_back}")
        return

    # Atomic write
    tmp = DATA_FILE.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, DATA_FILE)

    if entry is not None:
        print(f"  ✓ added news item dated {entry['addedAt']}")
    else:
        print("  ✓ rebalanced (no new entry)")
    if rotated:
        print(f"  ↺ rotated {rotated} item(s) older than {args.archive_threshold_days}d → archive")
    if pulled_back:
        print(f"  ↩ pulled back {pulled_back} item(s) from archive to keep items ≥ {args.min_items}")
    print(f"  state: items={len(stay)}  archive={len(archive)}")


if __name__ == "__main__":
    main()
