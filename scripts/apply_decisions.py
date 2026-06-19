#!/usr/bin/env python3
"""
apply_decisions.py — 消化 main-board 審核決定（.pending-decisions.json）。

審核迴圈：
  1. weekly_new_case_check.py → .pending-review.json（待審新案件）
  2. main-board.vercel.app 待審核總覽：YJ 按 ✓ 通過 / ✕ 退回 / ⏳ 稍後（存 Upstash）
  3. main-board 的 `./update.sh --sync-decisions` → 本 repo 根目錄 .pending-decisions.json
  4. 本腳本消化決定：
     - rejected（退回）：自 .pending-review.json 移除 + 記入 scripts/rejected_cases.json
       （weekly 掃描會跳過 ledger 裡的 URL，退回案件不再重現）
     - approved（通過）：自 .pending-review.json 移除 + 記入 scripts/approved_queue.json
       （intake 佇列；正式列載仍走人工流程：cases_manifest.json → fetch docket → build）
     - deferred（稍後）：原地保留，main-board 上維持 ⏳ 標記

用法：
  python3 scripts/apply_decisions.py            # dry-run：只印計劃，不寫檔
  python3 scripts/apply_decisions.py --apply    # 實際寫檔

不做 git commit/push（repo 紅線：自動化不碰 git，交給 auto-push watcher）。
"""
from __future__ import annotations
import argparse
import json
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import add_pending  # noqa: E402  (load / flatten_and_write 共用同一套 sections 邏輯)

REPO_ROOT = Path(__file__).resolve().parent.parent
DECISIONS_FILE = REPO_ROOT / ".pending-decisions.json"
REJECTED_LEDGER = Path(__file__).resolve().parent / "rejected_cases.json"
APPROVED_QUEUE = Path(__file__).resolve().parent / "approved_queue.json"
MANIFEST = Path(__file__).resolve().parent / "cases_manifest.json"
TPE = timezone(timedelta(hours=8))

DOCKET_ID_RE = re.compile(r"courtlistener\.com/docket/(\d+)/")
TITLE_PREFIX_RE = re.compile(r"^【[^】]*】\s*")


def norm_title(t: str) -> str:
    """退回舊版【…】前綴後的比對用標題。"""
    return TITLE_PREFIX_RE.sub("", (t or "").strip())


def load_json(path: Path, default):
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        sys.exit(f"✗ {path.name} 讀取失敗：{e}")


def write_json(path: Path, obj) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    tmp.replace(path)


def find_item(sections: dict, decision: dict):
    """以 URL（首選）或標題比對，回傳 (section_key, index, item) 或 None。"""
    d_url = (decision.get("url") or "").strip()
    d_title = norm_title(decision.get("title") or "")
    for sec_key, sec in sections.items():
        for idx, item in enumerate(sec.get("items", [])):
            if d_url and (item.get("url") or "").strip() == d_url:
                return sec_key, idx, item
            if d_title and norm_title(item.get("title")) == d_title:
                return sec_key, idx, item
    return None


def intake_hint(item: dict, decision: dict, next_case_id: int) -> str:
    m = DOCKET_ID_RE.search(decision.get("url") or item.get("url") or "")
    docket = m.group(1) if m else "<docket-id>"
    return (f"      → intake：python3 scripts/fetch_courtlistener_docket.py "
            f"--case-id {next_case_id} --docket-id {docket}\n"
            f"        （先在 cases_manifest.json 補 case_id={next_case_id} 條目，再跑 fetch + build）")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="實際寫檔（預設 dry-run）")
    args = ap.parse_args()

    doc = load_json(DECISIONS_FILE, None)
    if doc is None:
        print("（沒有 .pending-decisions.json — 先在 main-board 跑 ./update.sh --sync-decisions）")
        return 0
    decisions = doc.get("decisions") or []
    if not decisions:
        print("（.pending-decisions.json 沒有任何決定）")
        return 0

    pending_doc = add_pending.load()
    sections = pending_doc.setdefault("sections", {})
    ledger = load_json(REJECTED_LEDGER, [])
    queue = load_json(APPROVED_QUEUE, [])
    ledger_urls = {e.get("url") for e in ledger}
    queue_urls = {e.get("url") for e in queue}
    manifest = load_json(MANIFEST, [])
    next_case_id = max((c.get("case_id", 0) for c in manifest), default=0) + 1

    now = datetime.now(TPE).isoformat(timespec="seconds")
    removed_total = 0
    plan = {"approved": 0, "rejected": 0, "deferred": 0, "missing": 0}

    print(f"{'[dry-run] ' if not args.apply else ''}消化 {len(decisions)} 件決定"
          f"（{doc.get('updated', '?')} 同步）：\n")
    for d in sorted(decisions, key=lambda x: x.get("at") or ""):
        verb = d.get("decision")
        title = norm_title(d.get("title") or "(無標題)")
        note = f"｜備註：{d['note']}" if d.get("note") else ""
        hit = find_item(sections, d)

        if verb == "deferred":
            plan["deferred"] += 1
            print(f"  ⏳ 稍後　{title}{note}（保留待審）")
            continue

        if hit is None:
            # 已被前次 apply 移除、或來源已換週重寫 — 決定仍記錄進 ledger/queue 以防漏。
            if verb == "rejected" and d.get("url") and d["url"] not in ledger_urls:
                pass  # 還是要進 ledger，往下走
            elif verb == "approved" and d.get("url") and d["url"] not in queue_urls:
                pass  # 還是要進 queue，往下走
            else:
                plan["missing"] += 1
                print(f"  ↺ 略過　{title}（待審清單找不到，且已記錄過）")
                continue

        record = {
            "title": title,
            "url": d.get("url") or (hit[2].get("url") if hit else ""),
            "subtitle": (hit[2].get("subtitle") if hit else "") or "",
            "note": d.get("note") or "",
            "decidedAt": d.get("at") or "",
            "appliedAt": now,
        }

        if verb == "rejected":
            plan["rejected"] += 1
            print(f"  ✕ 退回　{title}{note}")
            if record["url"] not in ledger_urls:
                ledger.append(record)
                ledger_urls.add(record["url"])
        elif verb == "approved":
            plan["approved"] += 1
            print(f"  ✓ 通過　{title}{note}")
            if record["url"] not in queue_urls:
                queue.append(record)
                queue_urls.add(record["url"])
                print(intake_hint(hit[2] if hit else record, d, next_case_id))
                next_case_id += 1
        else:
            plan["missing"] += 1
            print(f"  ? 未知決定 {verb!r}：{title}")
            continue

        if hit is not None:
            sec_key, idx, _ = hit
            del sections[sec_key]["items"][idx]
            removed_total += 1

    print(f"\n小結：通過 {plan['approved']}、退回 {plan['rejected']}、"
          f"稍後 {plan['deferred']}、略過 {plan['missing']}；"
          f"自待審清單移除 {removed_total} 件")

    if not args.apply:
        print("\n[dry-run] 未寫任何檔案。加 --apply 實際執行。")
        return 0

    write_json(REJECTED_LEDGER, ledger)
    write_json(APPROVED_QUEUE, queue)
    add_pending.flatten_and_write(pending_doc)
    print(f"  ✓ {REJECTED_LEDGER.name}：{len(ledger)} 件退回紀錄")
    print(f"  ✓ {APPROVED_QUEUE.name}：{len(queue)} 件待 intake")
    print("\n下一步：approved 案件照 CLAUDE.md 的 intake 流程列載；"
          "main-board 下次 update.sh 會反映新的待審數。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
