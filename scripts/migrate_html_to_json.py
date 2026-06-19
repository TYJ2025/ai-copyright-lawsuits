#!/usr/bin/env python3
"""
migrate_html_to_json.py — one-shot 反向工具，已脫離每日流程（Phase 7 收尾後）

原為 Phase 3 重構工具（one-shot, idempotent）。Phase 6 切換後 dashboard.html 已是
build 產物，每日流程改走 data/*.json + build.py，本腳本不再參與日常運行，僅供日後
需要從 dashboard.html 反向重建 data/ 時手動使用。

Reads dashboard.html and extracts 7 inline data constants into data/*.json:
  cases             → data/cases.json
  caseSources       → data/case_sources.json
  fairUseCases      → data/fair_use_cases.json
  officialReports   → data/official_reports.json
  newsItems +       ↘
  newsArchive       ↗ data/news.json (combined)
  timelineEvents    → data/timeline.json
  + data/_meta.json

Each output gets:
  {
    "$schema": "<name>.v1",
    "generatedFrom": "dashboard.html",
    "generatedAt": "<ISO timestamp>",
    "lastUpdatedSource": "<git log -1 dashboard.html>",
    "items": [ ... ]  // or appropriate top-level
  }

This script DOES NOT modify dashboard.html. Re-running overwrites data/*.json.
Safe to re-run when daily-brief edits dashboard.html (until Phase 5 switch).
"""
from __future__ import annotations
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
DASHBOARD = PROJECT_DIR / "dashboard.html"
DATA_DIR = PROJECT_DIR / "data"
TPE = timezone(timedelta(hours=8))


# ─────────────────────────────────────────────────────────────────
# Robust JS literal extraction (handles backtick template literals,
# JS comments inside arrays, trailing commas — none of which are
# legal JSON, so we can't just json.loads the slice).
# ─────────────────────────────────────────────────────────────────

def find_const_body(html: str, name: str) -> tuple[int, int, str]:
    """Return (start_offset, end_offset, body_str) for `const <name> = [...]`
    or `const <name> = {...}`. start/end are byte offsets into html for
    the brackets themselves (inclusive of open, exclusive of close)."""
    pat = re.compile(rf'const\s+{re.escape(name)}\s*=\s*([\[\{{])')
    m = pat.search(html)
    if not m:
        raise KeyError(f"const {name} not found")
    open_ch = m.group(1)
    close_ch = ']' if open_ch == '[' else '}'
    start = m.end() - 1  # at the opening bracket
    depth = 0
    i = start
    in_string = False
    string_ch = ""
    in_line_comment = False
    in_block_comment = False
    while i < len(html):
        c = html[i]
        nxt = html[i+1] if i+1 < len(html) else ""

        # state machine to respect strings + comments while scanning brackets
        if in_line_comment:
            if c == '\n':
                in_line_comment = False
        elif in_block_comment:
            if c == '*' and nxt == '/':
                in_block_comment = False
                i += 1
        elif in_string:
            if c == '\\':
                i += 1  # skip escaped char
            elif c == string_ch:
                in_string = False
        else:
            if c == '/' and nxt == '/':
                in_line_comment = True
                i += 1
            elif c == '/' and nxt == '*':
                in_block_comment = True
                i += 1
            elif c in ('"', "'", '`'):
                in_string = True
                string_ch = c
            elif c == open_ch:
                depth += 1
            elif c == close_ch:
                depth -= 1
                if depth == 0:
                    return start, i + 1, html[start:i+1]
        i += 1
    raise ValueError(f"unmatched {open_ch} for const {name}")


def js_literal_to_python(js_body: str) -> object:
    """Convert a JS literal (with backticks, // comments, trailing commas)
    into a Python object. Strategy: normalize to standard JSON, then json.loads.
    """
    s = js_body

    # 1. Strip // line comments (but not inside strings)
    out = []
    i = 0
    in_string = False
    string_ch = ""
    while i < len(s):
        c = s[i]
        nxt = s[i+1] if i+1 < len(s) else ""
        if in_string:
            if c == '\\':
                out.append(s[i:i+2])
                i += 2
                continue
            if c == string_ch:
                in_string = False
            out.append(c)
            i += 1
            continue
        if c == '/' and nxt == '/':
            # Skip to end of line
            while i < len(s) and s[i] != '\n':
                i += 1
            continue
        if c == '/' and nxt == '*':
            i += 2
            while i+1 < len(s) and not (s[i] == '*' and s[i+1] == '/'):
                i += 1
            i += 2  # skip the closing */
            continue
        if c in ('"', "'", '`'):
            in_string = True
            string_ch = c
        out.append(c)
        i += 1
    s = "".join(out)

    # 2. Convert backtick strings to JSON strings.
    #    Backtick allows real newlines + must escape special chars.
    def convert_backtick(match):
        inner = match.group(1)
        # Convert template substitution ${...} → literal placeholder (rare in data)
        # We just preserve them as text since data shouldn't have ${} interpolation.
        inner = inner.replace('\\', '\\\\').replace('"', '\\"')
        inner = inner.replace('\n', '\\n').replace('\r', '').replace('\t', '\\t')
        return '"' + inner + '"'
    s = re.sub(r'`([^`]*)`', convert_backtick, s, flags=re.DOTALL)

    # 3. Convert single-quoted strings to double-quoted (JS allows both).
    #    Be careful: don't touch apostrophes inside double-quoted strings.
    out = []
    i = 0
    in_dq = False
    while i < len(s):
        c = s[i]
        if in_dq:
            if c == '\\':
                out.append(s[i:i+2])
                i += 2
                continue
            if c == '"':
                in_dq = False
            out.append(c)
            i += 1
            continue
        if c == '"':
            in_dq = True
            out.append(c)
            i += 1
            continue
        if c == "'":
            # find matching single quote
            j = i + 1
            buf = []
            while j < len(s):
                cc = s[j]
                if cc == '\\':
                    buf.append(s[j:j+2])
                    j += 2
                    continue
                if cc == "'":
                    break
                buf.append(cc)
                j += 1
            content = "".join(buf)
            # escape double quotes that may be inside
            content = content.replace('\\', '\\\\').replace('"', '\\"')
            # un-escape \' since we no longer need it (it was for JS single-quote)
            content = content.replace("\\'", "'")
            out.append('"' + content + '"')
            i = j + 1
            continue
        out.append(c)
        i += 1
    s = "".join(out)

    # 4. Quote unquoted JS object keys: { id: 1, name: "x" } → { "id": 1, "name": "x" }
    #    Match `<word>:` after `{` or `,` (with possible whitespace).
    s = re.sub(r'([{,]\s*)([A-Za-z_][A-Za-z0-9_]*)\s*:', r'\1"\2":', s)

    # 5. Strip trailing commas: `, ]` → ` ]`  and  `, }` → ` }`
    s = re.sub(r',\s*([\]\}])', r'\1', s)

    # 6. Parse
    try:
        return json.loads(s)
    except json.JSONDecodeError as e:
        # Surface a useful snippet
        ctx_start = max(0, e.pos - 60)
        ctx_end = min(len(s), e.pos + 60)
        print(f"JSON parse error at offset {e.pos}: {e.msg}", file=sys.stderr)
        print(f"  context: ...{s[ctx_start:ctx_end]}...", file=sys.stderr)
        raise


# ─────────────────────────────────────────────────────────────────
# Migration driver
# ─────────────────────────────────────────────────────────────────

def dashboard_last_modified() -> str:
    try:
        r = subprocess.run(
            ["git", "-C", str(PROJECT_DIR), "log", "-1", "--format=%cI", "--", "dashboard.html"],
            capture_output=True, text=True, timeout=5,
        )
        return r.stdout.strip() or "(unknown)"
    except Exception:
        return "(unknown)"


def envelope(schema: str, payload: object, last_updated_src: str) -> dict:
    return {
        "$schema": schema,
        "generatedFrom": "dashboard.html",
        "generatedAt": datetime.now(TPE).isoformat(),
        "lastUpdatedSource": last_updated_src,
        "data": payload,
    }


def write_json(name: str, obj: dict) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    path = DATA_DIR / name
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")
    size_kb = os.path.getsize(path) / 1024
    print(f"  ✓ {name:30s} ({size_kb:6.1f} KB)")


def main():
    if not DASHBOARD.is_file():
        sys.exit(f"✗ dashboard.html not at {DASHBOARD}")
    print(f"[+] Reading {DASHBOARD}")
    html = DASHBOARD.read_text(encoding="utf-8")
    print(f"    size: {len(html):,} bytes / {html.count(chr(10)):,} lines")
    print()

    last_modified = dashboard_last_modified()
    print(f"[+] dashboard.html last git modified: {last_modified}")
    print()

    # Extract each const
    extractions = []
    for name in ["cases", "caseSources", "fairUseCases", "officialReports",
                 "newsItems", "newsArchive", "timelineEvents"]:
        try:
            start, end, body = find_const_body(html, name)
            data = js_literal_to_python(body)
            n = len(data) if isinstance(data, (list, dict)) else "?"
            print(f"  ✓ {name:20s} → {type(data).__name__} of {n}")
            extractions.append((name, data))
        except Exception as e:
            print(f"  ✗ {name:20s} FAILED: {e}", file=sys.stderr)
            extractions.append((name, None))

    extracted = dict(extractions)
    if any(v is None for v in extracted.values()):
        sys.exit("✗ Some extractions failed; aborting.")
    print()

    # Write JSONs (combine newsItems + newsArchive into news.json)
    print("[+] Writing data/*.json")
    write_json("cases.json",           envelope("cases.v1",            extracted["cases"],           last_modified))
    write_json("case_sources.json",    envelope("case_sources.v1",     extracted["caseSources"],     last_modified))
    write_json("fair_use_cases.json",  envelope("fair_use_cases.v1",   extracted["fairUseCases"],    last_modified))
    write_json("official_reports.json",envelope("official_reports.v1", extracted["officialReports"], last_modified))
    write_json("news.json",            envelope("news.v1", {
        "items":   extracted["newsItems"],
        "archive": extracted["newsArchive"],
    }, last_modified))
    write_json("timeline.json",        envelope("timeline.v1",         extracted["timelineEvents"],  last_modified))

    # Meta
    meta = {
        "$schema": "_meta.v1",
        "generatedAt": datetime.now(TPE).isoformat(),
        "dashboardLastModified": last_modified,
        "extractionCounts": {
            "cases":           len(extracted["cases"]),
            "case_sources":    len(extracted["caseSources"]),
            "fair_use_cases":  len(extracted["fairUseCases"]),
            "official_reports":len(extracted["officialReports"]),
            "news_items":      len(extracted["newsItems"]),
            "news_archive":    len(extracted["newsArchive"]),
            "timeline_events": len(extracted["timelineEvents"]),
        },
    }
    write_json("_meta.json", meta)

    print()
    print("[✓] Migration complete. data/ now contains 7 JSON files.")
    print("    dashboard.html untouched.")
    print()
    print(f"  Counts: cases={meta['extractionCounts']['cases']}  "
          f"case_sources={meta['extractionCounts']['case_sources']}  "
          f"fair_use={meta['extractionCounts']['fair_use_cases']}  "
          f"reports={meta['extractionCounts']['official_reports']}  "
          f"news_items={meta['extractionCounts']['news_items']}  "
          f"news_archive={meta['extractionCounts']['news_archive']}  "
          f"timeline={meta['extractionCounts']['timeline_events']}")


if __name__ == "__main__":
    main()
