#!/usr/bin/env python3
"""更新 data/cases.json 中單一案件的 rulings 結構化欄位（比較功能裁定矩陣的資料源）。

用法：
  python3 scripts/update_rulings.py --case-id 109 \
    --add-ruling "2026-07|慕尼黑地院：Suno 訓練與輸出侵害著作權，命停止" \
    --fair-use na --fair-use-note "適用歐盟 TDM 例外框架" \
    --outcome "一審原告勝訴，Suno 可上訴"

  --add-ruling 可重複，格式 "YYYY-MM|一句話 holding"（以 date+holding 去重，重跑無害）
  --fair-use 僅接受 favorable / unfavorable / partial / pending / na
  未給的參數不會動到既有值。
"""
import argparse
import json
import sys
from pathlib import Path

PATH = Path(__file__).resolve().parent.parent / "data" / "cases.json"
FAIR_USE_VALUES = {"favorable", "unfavorable", "partial", "pending", "na"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--case-id", type=int, required=True)
    ap.add_argument("--fair-use", choices=sorted(FAIR_USE_VALUES))
    ap.add_argument("--fair-use-note")
    ap.add_argument("--add-ruling", action="append", default=[],
                    help='格式 "YYYY-MM|holding"，可重複')
    ap.add_argument("--outcome")
    args = ap.parse_args()

    doc = json.loads(PATH.read_text())
    case = next((c for c in doc["data"] if c["id"] == args.case_id), None)
    if case is None:
        sys.exit(f"[✗] case id {args.case_id} 不存在於 cases.json")

    r = case.setdefault("rulings", {"fairUse": "pending", "keyRulings": []})
    changed = []

    if args.fair_use:
        r["fairUse"] = args.fair_use
        changed.append(f"fairUse={args.fair_use}")
    if args.fair_use_note:
        r["fairUseNote"] = args.fair_use_note
        changed.append("fairUseNote")
    if args.outcome:
        r["outcome"] = args.outcome
        changed.append("outcome")

    existing = {(k["date"], k["holding"]) for k in r.get("keyRulings", [])}
    for item in args.add_ruling:
        if "|" not in item:
            sys.exit(f'[✗] --add-ruling 格式錯誤（缺 "|"）：{item}')
        date, holding = item.split("|", 1)
        date, holding = date.strip(), holding.strip()
        if (date, holding) in existing:
            print(f"[=] 已存在，略過：{date} {holding[:30]}")
            continue
        r.setdefault("keyRulings", []).append({"date": date, "holding": holding})
        existing.add((date, holding))
        changed.append(f"keyRuling {date}")

    if not changed:
        print("[=] 無變更")
        return

    r["keyRulings"].sort(key=lambda k: k["date"])
    PATH.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n")
    print(f"[✓] case {args.case_id}（{case['name'][:40]}）已更新：{', '.join(changed)}")


if __name__ == "__main__":
    main()
