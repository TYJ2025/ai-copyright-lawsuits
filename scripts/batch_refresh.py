#!/usr/bin/env python3
"""
batch_refresh.py — 依 cases_manifest.json 批次跑 fetch_courtlistener_docket.py

用法：
  export COURTLISTENER_TOKEN=xxx

  # 跑全部 US 案件
  python3 scripts/batch_refresh.py --all

  # 只跑指定 case_id
  python3 scripts/batch_refresh.py --case 6,7,1

  # 跑 manifest 內第 N 件到第 M 件（依 case_id 排序）
  python3 scripts/batch_refresh.py --slice 0:10

  # 跑特定 status
  python3 scripts/batch_refresh.py --status active

選項：
  --max-entries N         主 docket 抓多少 raw entries（預設 200）
  --max-secondary N       次 docket 抓多少（預設 50）
  --skip-existing         若 cases/ 已有對應 .md 則跳過（預設覆蓋）
  --dry-run               只列出將執行的 case，不實際 fetch
"""
import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPTS_DIR.parent
MANIFEST = SCRIPTS_DIR / "cases_manifest.json"
CASES_DIR = PROJECT_DIR / "cases"
FETCH_SCRIPT = SCRIPTS_DIR / "fetch_courtlistener_docket.py"


def slugify(text: str) -> str:
    text = re.sub(r"[^\w\s-]", "", text.lower())
    text = re.sub(r"[\s_-]+", "-", text).strip("-")
    return text[:60]  # cap length


def case_filename_pattern(case_id: int) -> str:
    """Return glob pattern matching this case's existing .md file."""
    return f"case-{case_id:03d}_*.md"


def build_dashboard_info(case: dict) -> str:
    """Build the --dashboard-info CLI string from manifest entry."""
    parts = []
    if case.get("court"):
        parts.append(f"Court={case['court']}")
    if case.get("judge"):
        parts.append(f"Judge={case['judge']}")
    if case.get("status"):
        parts.append(f"Status={case['status']}")
    progress = case.get("progress_excerpt", "")
    if progress:
        # Strip newlines, escape pipe, truncate
        progress_clean = progress.replace("\n", " ").replace("|", "／")
        progress_clean = re.sub(r"\s+", " ", progress_clean)[:500]
        parts.append(f"Progress={progress_clean}")
    return "|".join(parts)


def run_one(case: dict, max_entries: int, max_secondary: int, dry_run: bool) -> tuple[bool, str]:
    cid = case["case_id"]
    name = case["name"]
    primary = case["primary_docket_id"]
    secondaries = case.get("secondary_docket_ids", [])
    slug = slugify(name)
    dashboard_info = build_dashboard_info(case)

    cmd = [
        "python3", str(FETCH_SCRIPT),
        "--case-id", str(cid),
        "--docket-id", str(primary),
        "--slug", slug,
        "--max-entries", str(max_entries),
        "--max-secondary-entries", str(max_secondary),
        "--dashboard-info", dashboard_info,
    ]
    for sec in secondaries:
        cmd.extend(["--docket-id", str(sec)])

    if dry_run:
        print(f"[DRY] case {cid:3d}: {name[:60]}")
        print(f"      primary={primary} secondary={secondaries}")
        return True, "dry-run"

    print(f"[+] case {cid:3d}: {name[:60]}", flush=True)
    try:
        result = subprocess.run(cmd, cwd=str(PROJECT_DIR), capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            err = (result.stderr or result.stdout or "").strip()[:300]
            print(f"    ❌ FAILED: {err}", flush=True)
            return False, err
        # extract output filename from script's stdout
        m = re.search(r"\[✓\] Wrote (.+\.md)", result.stdout)
        outfile = m.group(1) if m else "?"
        print(f"    ✓ {outfile}", flush=True)
        return True, outfile
    except subprocess.TimeoutExpired:
        print(f"    ❌ TIMEOUT after 120s", flush=True)
        return False, "timeout"
    except Exception as e:
        print(f"    ❌ EXCEPTION: {e}", flush=True)
        return False, str(e)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--all", action="store_true", help="跑 manifest 內全部案件")
    g.add_argument("--case", type=str, help="只跑指定 case_id（逗號分隔）")
    g.add_argument("--slice", type=str, help="跑 manifest 第 a:b 區間（依 case_id 排序）")
    g.add_argument("--status", type=str, help="跑指定 status 的案件")

    ap.add_argument("--max-entries", type=int, default=200)
    ap.add_argument("--max-secondary", type=int, default=50)
    ap.add_argument("--skip-existing", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--manifest", type=Path, default=MANIFEST)
    ap.add_argument("--delay", type=float, default=1.0, help="案件間延遲（秒）以保護 API")
    args = ap.parse_args()

    if not args.manifest.exists():
        sys.exit(f"manifest 不存在：{args.manifest}")
    cases: list[dict] = json.loads(args.manifest.read_text())
    cases.sort(key=lambda c: c["case_id"])

    # filter
    if args.case:
        wanted = {int(x) for x in args.case.split(",")}
        cases = [c for c in cases if c["case_id"] in wanted]
    elif args.slice:
        a, b = args.slice.split(":")
        cases = cases[int(a):int(b) if b else None]
    elif args.status:
        cases = [c for c in cases if c.get("status") == args.status]

    # skip existing
    if args.skip_existing:
        before = len(cases)
        cases = [
            c for c in cases
            if not list(CASES_DIR.glob(case_filename_pattern(c["case_id"])))
        ]
        print(f"[i] --skip-existing: skipped {before - len(cases)} already-present cases", flush=True)

    if not cases:
        print("[!] 沒有符合條件的案件")
        return

    print(f"[i] 將處理 {len(cases)} 件，max_entries={args.max_entries}, "
          f"max_secondary={args.max_secondary}, delay={args.delay}s\n", flush=True)

    ok_count = 0
    fail_count = 0
    failures = []
    for i, case in enumerate(cases):
        ok, info = run_one(case, args.max_entries, args.max_secondary, args.dry_run)
        if ok:
            ok_count += 1
        else:
            fail_count += 1
            failures.append((case["case_id"], case["name"], info))
        if i + 1 < len(cases) and args.delay > 0 and not args.dry_run:
            time.sleep(args.delay)

    print(f"\n[i] 完成：成功 {ok_count}／失敗 {fail_count}")
    if failures:
        print("\n失敗清單：")
        for cid, name, info in failures:
            print(f"  - case {cid}: {name[:50]} → {info[:100]}")


if __name__ == "__main__":
    main()
