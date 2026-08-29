#!/usr/bin/env python3
"""Backfill data/cases.json 的 plaintiffs / plaintiffEntities 兩個欄位。

- plaintiffs        : 人類可讀的原告方全稱（對照既有 defendants 欄位）
- plaintiffEntities : 供統計用的正規化「原告企業／團體」名稱陣列。
                      純自然人（作者、藝術家、配音員等集體訴訟）留空陣列，
                      統計時改以 plaintiffType 歸入「個人／集體訴訟」。

用法： python3 apply_plaintiffs.py <seed.json> <cases.json>
"""
import json
import sys
from pathlib import Path

seed_path, cases_path = Path(sys.argv[1]), Path(sys.argv[2])
seed = json.loads(seed_path.read_text(encoding="utf-8"))
doc = json.loads(cases_path.read_text(encoding="utf-8"))
cases = doc["data"]

missing, applied = [], 0
for idx, c in enumerate(cases):
    key = str(c["id"])
    if key not in seed:
        missing.append(key)
        continue
    plaintiffs, entities = seed[key]
    # 插在 defendants 之前，讓兩造欄位相鄰
    rebuilt = {}
    for k, v in c.items():
        if k == "defendants":
            rebuilt["plaintiffs"] = plaintiffs
            rebuilt["plaintiffEntities"] = entities
        if k in ("plaintiffs", "plaintiffEntities"):
            continue
        rebuilt[k] = v
    if "plaintiffs" not in rebuilt:  # 沒有 defendants 欄位時附在最後
        rebuilt["plaintiffs"] = plaintiffs
        rebuilt["plaintiffEntities"] = entities
    cases[idx] = rebuilt
    applied += 1

extra = [k for k in seed if k not in {str(c["id"]) for c in cases}]
print(f"applied={applied}  missing_in_seed={missing}  seed_not_in_cases={extra}")
if missing or extra:
    sys.exit(1)

cases_path.write_text(
    json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
)
print(f"[ok] wrote {cases_path}")
