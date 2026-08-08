#!/usr/bin/env python3
"""依 data/claims_vocab.json 正規化 cases.json 的 claims 標籤。

規則（2026-08-04 YJ 立）：
- claims 標籤以**起訴狀所載訴因**為準，顯示用受控詞彙表的規範用語
- 起訴狀 COUNT 原文另存於 claimsDetail（由 verify_claims.py 自起訴狀擷取）
- 訴訟中之增刪（撤回、追加請求權）**不改標籤**，改寫入 issues（訴訟爭點）
- 非訴因項目（陪審團聲請、集體訴訟聲明、損賠態樣、抗辯、救濟請求）移出 claims，
  併入 issues 末段之「【救濟與程序聲明】」

用法：
  python3 scripts/normalize_claims.py             # dry-run，列出將如何變動
  python3 scripts/normalize_claims.py --apply
  python3 scripts/normalize_claims.py --report    # 只統計，不改檔

重跑無害：已正規化之標籤會原樣通過；issues 末段以標題去重，不會重複附加。
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CASES = ROOT / "data" / "cases.json"
VOCAB = ROOT / "data" / "claims_vocab.json"
PROC_HEADING = "【救濟與程序聲明】"


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()

    vocab = json.loads(VOCAB.read_text())
    canon = vocab["canonical"]
    alias = vocab["aliases"]
    nonclaims = vocab["non_claims"]["map"]
    label_of = {k: v["label"] for k, v in canon.items()}
    canonical_labels = set(label_of.values())

    doc = json.loads(CASES.read_text())
    cases = doc["data"]

    unknown = Counter()
    changed, moved = [], []

    for c in cases:
        old = list(c.get("claims") or [])
        new, procs = [], []
        for raw in old:
            if raw in nonclaims:
                procs.append(nonclaims[raw])
                continue
            key = alias.get(raw)
            if key is None:
                if raw in canonical_labels:      # 已正規化
                    if raw not in new:
                        new.append(raw)
                    continue
                unknown[raw] += 1
                if raw not in new:
                    new.append(raw)              # 保留，等人工處理
                continue
            lab = label_of[key]
            if lab not in new:
                new.append(lab)

        if new != old:
            changed.append((c["id"], c["name"][:38], old, new))
            c["claims"] = new

        if procs:
            issues = c.get("issues") or ""
            line = PROC_HEADING + "；".join(procs) + "。"
            if PROC_HEADING not in issues:
                c["issues"] = issues.rstrip() + ("\n\n" if issues.strip() else "") + line
                moved.append((c["id"], procs))

        # 核對狀態欄位：尚未比對起訴狀者為 null
        c.setdefault("claimsDetail", None)
        c.setdefault("claimsVerifiedAt", None)

    if args.report:
        cnt = Counter()
        for c in cases:
            cnt.update(c["claims"])
        print(f"正規化後標籤種類：{len(cnt)}（原 98 種）\n")
        for lab, n in cnt.most_common():
            print(f"  {n:4}  {lab}")
        print(f"\n已核對起訴狀：{sum(1 for c in cases if c.get('claimsVerifiedAt'))} / {len(cases)}")
        return

    for cid, name, old, new in changed:
        print(f"case {cid:5} {name:40}")
        print(f"        原：{old}")
        print(f"        新：{new}")
    for cid, procs in moved:
        print(f"case {cid:5} 移入 issues：{procs}")
    if unknown:
        print("\n⚠ 詞彙表未收錄（保留原樣，請補進 claims_vocab.json）：")
        for raw, n in unknown.most_common():
            print(f"  {n:3}  {raw}")

    if not args.apply:
        print(f"\n[dry-run] {len(changed)} 件標籤變動、{len(moved)} 件移入 issues（加 --apply 寫入）")
        return

    CASES.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n")
    print(f"\n[✓] 已寫入：{len(changed)} 件標籤變動、{len(moved)} 件移入 issues")


if __name__ == "__main__":
    main()
