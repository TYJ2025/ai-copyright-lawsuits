#!/usr/bin/env python3
"""
build.py — data/ + templates/ → dashboard.html

Reads each data/*.json (unwraps envelope to get the actual payload),
serializes to JSON string, substitutes into templates/dashboard.template.html,
writes dashboard.html.

Usage:
  python3 scripts/build.py              # write dashboard.html
  python3 scripts/build.py --diff       # write to dashboard.html.new and diff vs current
  python3 scripts/build.py --check      # validate data/*.json + placeholder coverage only

Exit codes:
  0  success
  1  data file missing / unreadable
  2  placeholder not in template
  3  output write failed
"""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_DIR / "data"
TEMPLATE = PROJECT_DIR / "templates" / "dashboard.template.html"
OUTPUT = PROJECT_DIR / "dashboard.html"
OUTPUT_NEW = PROJECT_DIR / "dashboard.html.new"

# Each placeholder maps to (filename, dot-path-into-envelope-after-"data")
SUBSTITUTIONS = [
    ("{{CASES_JSON}}",           "cases.json",            ""),
    ("{{CASE_SOURCES_JSON}}",    "case_sources.json",     ""),
    ("{{FAIR_USE_CASES_JSON}}",  "fair_use_cases.json",   ""),
    ("{{OFFICIAL_REPORTS_JSON}}","official_reports.json", ""),
    ("{{NEWS_ITEMS_JSON}}",      "news.json",             "items"),
    ("{{NEWS_ARCHIVE_JSON}}",    "news.json",             "archive"),
    ("{{TIMELINE_EVENTS_JSON}}", "timeline.json",         ""),
    ("{{CLAIMS_VOCAB_JSON}}",    "claims_vocab.json",     "canonical"),
]

# Footer date is stamped from today's date, not a data file.
FOOTER_PLACEHOLDER = "{{FOOTER_DATE}}"
# Progress "as of" month, stamped from today's date (fallback when a case has no updatedAt).
PROGRESS_AS_OF_PLACEHOLDER = "{{PROGRESS_AS_OF}}"


def load_payload(filename: str, subpath: str) -> object:
    path = DATA_DIR / filename
    if not path.is_file():
        sys.exit(f"✗ {path} missing")
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    payload = doc.get("data", doc)
    for key in subpath.split(".") if subpath else []:
        payload = payload[key]
    return payload


def build(check_only: bool = False, output_path: Path = OUTPUT) -> str:
    if not TEMPLATE.is_file():
        sys.exit(f"✗ template missing: {TEMPLATE}")
    template = TEMPLATE.read_text(encoding="utf-8")

    if check_only:
        for placeholder, filename, subpath in SUBSTITUTIONS:
            load_payload(filename, subpath)  # raises if bad
            if placeholder not in template:
                print(f"✗ placeholder {placeholder} not in template", file=sys.stderr)
                sys.exit(2)
        if FOOTER_PLACEHOLDER not in template:
            print(f"✗ placeholder {FOOTER_PLACEHOLDER} not in template", file=sys.stderr)
            sys.exit(2)
        print("[✓] All data files valid + placeholders present.")
        return ""

    for placeholder, filename, subpath in SUBSTITUTIONS:
        payload = load_payload(filename, subpath)
        # 2-space indent matches the migrator output style; deterministic key order
        # (sort_keys=False to preserve input order, since cases is id-ordered).
        js_literal = json.dumps(payload, ensure_ascii=False, indent=2)
        if placeholder not in template:
            print(f"✗ placeholder {placeholder} not in template", file=sys.stderr)
            sys.exit(2)
        template = template.replace(placeholder, js_literal, 1)

    # Footer heartbeat: stamp today's date (Asia/Taipei = system local time).
    # Replaces the sed stamp previously done by daily-brief.sh.
    if FOOTER_PLACEHOLDER not in template:
        sys.exit(f"✗ placeholder {FOOTER_PLACEHOLDER} not in template")
    template = template.replace(FOOTER_PLACEHOLDER, date.today().isoformat(), 1)

    # Progress "as of" build-month stamp, e.g. "June 2026" (English month to match the label).
    if PROGRESS_AS_OF_PLACEHOLDER in template:
        as_of = date.today().strftime("%B %Y")
        template = template.replace(PROGRESS_AS_OF_PLACEHOLDER, as_of)

    leftover = [p for p, _, _ in SUBSTITUTIONS if p in template]
    if leftover:
        sys.exit(f"✗ unsubstituted placeholders: {leftover}")

    try:
        output_path.write_text(template, encoding="utf-8")
    except OSError as e:
        sys.exit(f"✗ write failed: {e}")
    size_kb = len(template) / 1024
    print(f"[✓] Wrote {output_path} ({size_kb:.1f} KB)")
    return template


def diff_with_current() -> int:
    """Build to OUTPUT_NEW, run `diff dashboard.html dashboard.html.new`,
    summarize."""
    build(output_path=OUTPUT_NEW)
    print()
    print(f"[+] Diffing {OUTPUT.name} vs {OUTPUT_NEW.name} ...")
    r = subprocess.run(
        ["diff", "-u", str(OUTPUT), str(OUTPUT_NEW)],
        capture_output=True, text=True,
    )
    if r.returncode == 0:
        print("[✓] Files are byte-identical.")
        return 0
    diff_lines = r.stdout.splitlines()
    add_lines = sum(1 for L in diff_lines if L.startswith("+") and not L.startswith("+++"))
    del_lines = sum(1 for L in diff_lines if L.startswith("-") and not L.startswith("---"))
    print(f"[…] {add_lines} added / {del_lines} removed lines")
    print(f"    Full diff length: {len(diff_lines)} lines")
    # Save full diff for inspection
    diff_path = PROJECT_DIR / "build-diff.txt"
    diff_path.write_text(r.stdout, encoding="utf-8")
    print(f"    Saved full diff → {diff_path}")
    # Show top of diff
    print()
    print("--- diff head (first 50 lines) ---")
    for L in diff_lines[:50]:
        print(L)
    return 1


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--diff", action="store_true",
                    help="Write to dashboard.html.new and diff vs current")
    ap.add_argument("--check", action="store_true",
                    help="Validate data + placeholders only, no output write")
    args = ap.parse_args()

    if args.check:
        build(check_only=True)
        return
    if args.diff:
        sys.exit(diff_with_current())
    build()


if __name__ == "__main__":
    main()
