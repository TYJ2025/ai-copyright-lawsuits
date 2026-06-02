#!/usr/bin/env python3
"""
generate_template.py — One-shot helper for Phase 4 of refactor.

Reads current dashboard.html, finds the 7 inline `const X = ...;` blocks
that have already been migrated to data/*.json, and replaces each one
with `const X = {{PLACEHOLDER}};`.

Writes to templates/dashboard.template.html.

After running once, the template can be hand-edited (HTML/CSS/non-data JS
changes) without re-running this. Only re-run if a new const is added
to the data layer.
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
DASHBOARD = PROJECT_DIR / "dashboard.html"
TEMPLATE_DIR = PROJECT_DIR / "templates"
TEMPLATE = TEMPLATE_DIR / "dashboard.template.html"

# const name → placeholder token
CONST_TO_PLACEHOLDER = {
    "cases":           "{{CASES_JSON}}",
    "caseSources":     "{{CASE_SOURCES_JSON}}",
    "fairUseCases":    "{{FAIR_USE_CASES_JSON}}",
    "officialReports": "{{OFFICIAL_REPORTS_JSON}}",
    "newsItems":       "{{NEWS_ITEMS_JSON}}",
    "newsArchive":     "{{NEWS_ARCHIVE_JSON}}",
    "timelineEvents":  "{{TIMELINE_EVENTS_JSON}}",
}


def find_const_block(html: str, name: str) -> tuple[int, int]:
    """Locate full `const <name> = [...];` or `const <name> = {...};` span,
    INCLUDING the leading `const <name> = ` keyword and trailing `;` if any.
    Returns (start_offset, end_offset) byte offsets in html (exclusive end)."""
    pat = re.compile(rf'const\s+{re.escape(name)}\s*=\s*([\[\{{])')
    m = pat.search(html)
    if not m:
        raise KeyError(f"const {name} not found")
    open_ch = m.group(1)
    close_ch = ']' if open_ch == '[' else '}'

    # Re-use the migrator's bracket-walker logic (state machine for strings + comments).
    start = m.start()  # at the `const` keyword
    body_start = m.end() - 1  # at the bracket itself
    depth = 0
    i = body_start
    in_string = False
    string_ch = ""
    in_line_comment = False
    in_block_comment = False
    while i < len(html):
        c = html[i]
        nxt = html[i+1] if i+1 < len(html) else ""

        if in_line_comment:
            if c == '\n':
                in_line_comment = False
        elif in_block_comment:
            if c == '*' and nxt == '/':
                in_block_comment = False
                i += 1
        elif in_string:
            if c == '\\':
                i += 1
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
                    # Found closing bracket. Now include trailing ';' if present.
                    j = i + 1
                    while j < len(html) and html[j] in ' \t':
                        j += 1
                    if j < len(html) and html[j] == ';':
                        j += 1
                    return start, j
        i += 1
    raise ValueError(f"unmatched {open_ch} for const {name}")


def main():
    if not DASHBOARD.is_file():
        sys.exit(f"✗ dashboard.html not at {DASHBOARD}")
    print(f"[+] Reading {DASHBOARD}")
    html = DASHBOARD.read_text(encoding="utf-8")

    # Find all const blocks in REVERSE order of file position, so replacements
    # don't shift earlier offsets.
    blocks = []
    for name, placeholder in CONST_TO_PLACEHOLDER.items():
        try:
            start, end = find_const_block(html, name)
            blocks.append((start, end, name, placeholder))
            print(f"  ✓ {name:20s} bytes {start:>7,}…{end:>7,} ({end-start:>6,} chars)")
        except Exception as e:
            print(f"  ✗ {name:20s} FAILED: {e}", file=sys.stderr)
            sys.exit(1)

    blocks.sort(key=lambda b: -b[0])  # reverse position

    template = html
    for start, end, name, placeholder in blocks:
        replacement = f"const {name} = {placeholder};"
        template = template[:start] + replacement + template[end:]

    TEMPLATE_DIR.mkdir(exist_ok=True)
    TEMPLATE.write_text(template, encoding="utf-8")
    saved_kb = len(template) / 1024
    orig_kb = len(html) / 1024
    print()
    print(f"[✓] Wrote {TEMPLATE}")
    print(f"    template: {saved_kb:.1f} KB  vs original dashboard.html: {orig_kb:.1f} KB")
    print(f"    saved {orig_kb - saved_kb:.1f} KB (data portion now in data/*.json)")

    # Sanity: 7 placeholders present
    missing = [p for _, _, _, p in blocks if p not in template]
    if missing:
        sys.exit(f"✗ placeholder not in template: {missing}")
    print(f"    7 placeholders verified ✓")


if __name__ == "__main__":
    main()
