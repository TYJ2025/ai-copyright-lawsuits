#!/usr/bin/env python3
"""
batch_update_dashboard_judges.py

讀 cases/*.md 內 CourtListener 「Judge Assigned」欄位，與 dashboard.html / index.html
的 case 卡片 "judge": 欄位比對，若不符就更新成 CourtListener 值。

安全規則：
- 跳過 CourtListener 端為「—」或空字串的（如上訴法院 panel）
- 跳過 dashboard 已含明確補充說明的（包含「現審」「原審」「panel」「Magistrate」）
- 永遠跳過 case 1, 6, 7（這 3 件已手動精雕細琢過）
- 寫入前先 dry-run 列出將改的條目；--apply 才實際寫檔
"""
import argparse
import re
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
CASES_DIR = PROJECT / "cases"
DASHBOARD = PROJECT / "dashboard.html"
INDEX = PROJECT / "index.html"

# 已手動精雕、不要覆蓋
SKIP_CASES = {1, 6, 7}
# dashboard judge 欄位內若含這些字眼也跳過（已是精細描述）
PRESERVE_KEYWORDS = ["現審", "原審", "panel", "Magistrate", "／", "/"]


def parse_case_md(md_path):
    """Parse a case .md file. Return dict with case_id, cl_judge, cl_court_short."""
    text = md_path.read_text()
    m = re.search(r"^# Case (\d+) — ", text, re.M)
    if not m:
        return None
    cid = int(m.group(1))
    # Find Judge Assigned in metadata table
    jm = re.search(r"\| Judge Assigned \| ([^|]+?) \|", text)
    judge = jm.group(1).strip() if jm else ""
    if judge in ("—", "-"):
        judge = ""
    return {"case_id": cid, "cl_judge": judge, "md": md_path.name}


def update_html_judge(html_path, updates):
    """
    For each (case_id, old_judge, new_judge), find:
        "id": N,
        "name": "...",
        "court": "...",
        "judge": "<old_judge>",
    in html_path, and replace judge value with new_judge.
    Returns count of edits made.
    """
    text = html_path.read_text()
    edits = 0
    for cid, old_j, new_j in updates:
        # Pattern: capture surrounding to ensure we hit the right case
        pat = re.compile(
            r'("id":\s*' + str(cid) + r'\s*,\s*'
            r'"name":\s*"[^"]*"\s*,\s*'
            r'"court":\s*"[^"]*"\s*,\s*'
            r'"judge":\s*)"' + re.escape(old_j) + r'"',
            re.DOTALL
        )
        new_text, n = pat.subn(lambda m: m.group(1) + f'"{new_j}"', text, count=1)
        if n > 0:
            edits += 1
            text = new_text
    if edits > 0:
        html_path.write_text(text)
    return edits


def get_dashboard_judge(html_text, case_id):
    pat = re.compile(
        r'"id":\s*' + str(case_id) + r'\s*,\s*'
        r'"name":\s*"[^"]*"\s*,\s*'
        r'"court":\s*"[^"]*"\s*,\s*'
        r'"judge":\s*"([^"]*)"',
        re.DOTALL
    )
    m = pat.search(html_text)
    return m.group(1) if m else None


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="實際寫檔（預設 dry-run）")
    args = ap.parse_args()

    dashboard_text = DASHBOARD.read_text()
    cases_data = []
    for md in sorted(CASES_DIR.glob("case-*.md")):
        info = parse_case_md(md)
        if info:
            cases_data.append(info)

    print(f"[+] Loaded {len(cases_data)} case .md files")

    updates = []
    skipped = []
    for c in cases_data:
        cid = c["case_id"]
        cl_judge = c["cl_judge"]
        if not cl_judge:
            skipped.append((cid, "(CL judge empty)", ""))
            continue
        if cid in SKIP_CASES:
            skipped.append((cid, "(in SKIP_CASES — manual)", ""))
            continue
        dash_judge = get_dashboard_judge(dashboard_text, cid)
        if dash_judge is None:
            skipped.append((cid, "(case not found in dashboard)", ""))
            continue
        if dash_judge.strip() == cl_judge.strip():
            continue  # already match
        # If dashboard has descriptive content already, preserve
        if any(kw in dash_judge for kw in PRESERVE_KEYWORDS):
            skipped.append((cid, f"(preserved descriptive: {dash_judge[:30]})", cl_judge))
            continue
        updates.append((cid, dash_judge, cl_judge))

    print(f"\n[+] Will update {len(updates)} cases:")
    for cid, old, new in updates:
        print(f"  case {cid:3d}: 「{old}」 → 「{new}」")

    if skipped:
        print(f"\n[i] Skipped {len(skipped)} cases (sample):")
        for cid, reason, _ in skipped[:8]:
            print(f"  case {cid:3d}: {reason}")

    if not args.apply:
        print("\n[dry-run] 未實際寫入。加 --apply 寫入 dashboard.html 與 index.html。")
        return

    print(f"\n[+] Applying to dashboard.html ...")
    n1 = update_html_judge(DASHBOARD, updates)
    print(f"    Edited {n1} entries")

    print(f"[+] Applying to index.html ...")
    n2 = update_html_judge(INDEX, updates)
    print(f"    Edited {n2} entries")

    print(f"\n[✓] Done.")


if __name__ == "__main__":
    main()
