#!/usr/bin/env python3
"""
scan_case_trackers.py — 漏案掃描器（Missing-case scanner）

用途：
  週期性抓取外部 AI 著作權訴訟「case tracker」頁面，比對 cases_manifest.json，
  找出 dashboard.html 尚未列載之案件，輸出人工審核清單。

來源（可在 SOURCES 內擴充／調整）：
  - BakerHostetler Case Tracker
  - McKool Smith AI Litigation 新聞室
  - ChatGPT Is Eating The World（Substack）

用法：
  python3 scripts/scan_case_trackers.py             # 寫入 scripts/missing_cases_report.md
  python3 scripts/scan_case_trackers.py --stdout    # 也印出至 stdout
  python3 scripts/scan_case_trackers.py --json      # 同時輸出 .json 機器可讀

設計原則（重要）：
  本腳本「只偵測、只報告」，**絕不**自動寫入 dashboard.html 或 cases_manifest.json。
  漏案判斷僅作粗略 name match（大小寫不敏感、移除 v./vs./標點），仍需人工核對。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

try:
    import requests
except ImportError:  # pragma: no cover
    sys.stderr.write("Missing dependency: requests. Install via `pip install --break-system-packages requests`.\n")
    sys.exit(2)

SCRIPTS_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPTS_DIR.parent
MANIFEST = SCRIPTS_DIR / "cases_manifest.json"
DASHBOARD = PROJECT_DIR / "dashboard.html"
REPORT_MD = SCRIPTS_DIR / "missing_cases_report.md"
REPORT_JSON = SCRIPTS_DIR / "missing_cases_report.json"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 "
    "(YJ AI-Copyright Tracker scan_case_trackers/1.0)"
)

SOURCES = [
    {
        "name": "BakerHostetler — Case Tracker: AI, Copyrights and Class Actions",
        "url": "https://www.bakerlaw.com/services/artificial-intelligence-ai/case-tracker-artificial-intelligence-copyrights-and-class-actions/",
    },
    {
        "name": "McKool Smith — AI Litigation Updates",
        "url": "https://www.mckoolsmith.com/newsroom-ailitigation",
    },
    {
        "name": "ChatGPT Is Eating The World — Substack",
        "url": "https://chatgptiseatingtheworld.substack.com/",
    },
]

# 案件名稱常見前綴／後綴雜訊
_NOISE = re.compile(
    r"(?i)\b(llc|inc|corp|corporation|limited|ltd|plc|co\.?|nv|sa|gmbh|"
    r"the\s+leland\s+stanford\s+junior|leland\s+stanford\s+junior|"
    r"platforms|productions|press|media|entertainment|"
    r"holdings|recordings|rights\s+management)\b"
)
_VS = re.compile(r"\bv(?:s)?\.?\b", re.IGNORECASE)
_WS = re.compile(r"\s+")
_PUNC = re.compile(r"[^\w\s]")
# 看起來像「Plaintiff v. Defendant」的字串：A 至 80 字以內，含 v. 或 vs.
_CASENAME_LIKE = re.compile(
    r"([A-Z][A-Za-z0-9&'.,\- ]{1,60}?\s+v(?:s)?\.\s+[A-Z][A-Za-z0-9&'.,\- ]{1,60})"
)

_PAREN = re.compile(r"\([^()]*\)")
_BRACKET = re.compile(r"\[[^\[\]]*\]")

def normalize(name: str) -> str:
    s = name.lower()
    # strip parentheticals like "(LLaMA Training)" / "(Claude AI — $1.5B Settlement)"
    s = _PAREN.sub(" ", s)
    s = _BRACKET.sub(" ", s)
    s = _VS.sub("v", s)
    s = _PUNC.sub(" ", s)
    s = _NOISE.sub(" ", s)
    s = _WS.sub(" ", s).strip()
    return s

def party_tokens(name: str) -> set[str]:
    """Return a set of significant name tokens, dropping short / generic words."""
    SKIP = {
        "v", "the", "of", "and", "a", "an", "co", "in", "re",
        "for", "to", "as", "on", "et", "al", "etal",
    }
    return {t for t in normalize(name).split() if len(t) > 2 and t not in SKIP}

def load_known_cases() -> list[dict]:
    known = []
    if MANIFEST.exists():
        with MANIFEST.open() as fh:
            for item in json.load(fh):
                known.append({"src": "manifest", "name": item.get("name", "")})
    # also scrape dashboard names so we don't double-flag id 113–132 added directly to HTML
    if DASHBOARD.exists():
        text = DASHBOARD.read_text(errors="ignore")
        # cheap extraction: lines like     "name": "...",
        for m in re.finditer(r'^\s*"name":\s*"([^"]+)"', text, re.MULTILINE):
            known.append({"src": "dashboard", "name": m.group(1)})
    return known

def fetch(url: str, timeout: int = 30) -> str:
    headers = {"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"}
    r = requests.get(url, headers=headers, timeout=timeout)
    r.raise_for_status()
    return r.text

def extract_case_names(html: str) -> list[str]:
    """Pull every 'X v. Y' substring out of raw HTML/text."""
    # strip tags first to avoid attribute noise
    text = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.IGNORECASE)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;|&amp;|&#x27;|&#39;|&quot;", " ", text)
    text = _WS.sub(" ", text)
    found = []
    seen = set()
    for m in _CASENAME_LIKE.finditer(text):
        s = m.group(1).strip(" ,.;:")
        key = normalize(s)
        if key and key not in seen:
            seen.add(key)
            found.append(s)
    return found

def is_known(candidate: str, known_tokens_list: list[set[str]]) -> bool:
    cand = party_tokens(candidate)
    if not cand:
        return True  # too short, treat as known to avoid spam
    for known in known_tokens_list:
        if not known:
            continue
        overlap = cand & known
        # match if the *known* case's significant tokens are largely contained in candidate;
        # this handles candidates that include date prefixes / boilerplate around the case name.
        if len(overlap) >= 2 and len(overlap) / max(1, len(known)) >= 0.5:
            return True
        # also: if known has only 2 tokens (typical "Plaintiff v. Defendant") and both appear
        if len(known) == 2 and overlap == known:
            return True
        # candidate is a full subset of known — handles multi-plaintiff cases like
        # "Hendrix / Martinez-Conde / Alexander v. Apple" matched by "Hendrix v. Apple"
        if len(cand) >= 2 and cand.issubset(known):
            return True
        # also keep the symmetric guard for short single-token known cases
        if len(known) == 1 and overlap == known:
            return True
    return False

_DATE_PREFIX = re.compile(
    r"^\s*(?:january|february|march|april|may|june|july|august|september|october|november|december)"
    r"\s+\d{1,2},\s*\d{4}\s*\d{2}\.\d{2}\.\d{4}\s*\d+\.\s*",
    re.IGNORECASE,
)
_TAIL_BOILER = re.compile(
    r"\s*(?:current status|background|major new case alert|new case alert).*$",
    re.IGNORECASE,
)

def clean_candidate(name: str) -> str:
    s = _DATE_PREFIX.sub("", name)
    s = _TAIL_BOILER.sub("", s)
    return s.strip(" -–—:.;")

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stdout", action="store_true", help="也輸出至 stdout")
    ap.add_argument("--json", action="store_true", help="同時輸出 missing_cases_report.json")
    ap.add_argument("--timeout", type=int, default=30)
    args = ap.parse_args()

    known = load_known_cases()
    known_tokens_list = [party_tokens(k["name"]) for k in known if k["name"]]

    report = {
        "generated_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "known_count": len(known),
        "sources": [],
    }

    print(f"[scan] loaded {len(known)} known case names from manifest+dashboard")

    for src in SOURCES:
        entry = {"name": src["name"], "url": src["url"], "missing": [], "error": None}
        print(f"[scan] fetching: {src['name']}")
        try:
            html = fetch(src["url"], timeout=args.timeout)
        except Exception as e:
            entry["error"] = f"{type(e).__name__}: {e}"
            report["sources"].append(entry)
            print(f"  ! error: {entry['error']}")
            continue

        candidates = extract_case_names(html)
        print(f"  found {len(candidates)} candidate case names")
        for cand in candidates:
            cleaned = clean_candidate(cand)
            if not is_known(cleaned, known_tokens_list):
                entry["missing"].append(cleaned)
        # dedupe missing (case-insensitive)
        seen = {}
        for m in entry["missing"]:
            key = normalize(m)
            if key not in seen:
                seen[key] = m
        entry["missing"] = sorted(seen.values(), key=lambda s: s.lower())
        report["sources"].append(entry)
        time.sleep(2)  # be polite

    # write markdown report
    lines = [
        f"# 漏案掃描報告（Missing-Case Scan Report）",
        "",
        f"- Generated: {report['generated_at']} UTC",
        f"- Known cases scanned (manifest + dashboard): {report['known_count']}",
        "",
        "> 本報告僅為「疑似漏載」候選清單，需人工核對。Matching 採party-token 重疊 ≥ 2 且覆蓋率 ≥ 50% 視為已知；其餘列入候選。",
        "",
    ]
    total_missing = 0
    for s in report["sources"]:
        lines.append(f"## {s['name']}")
        lines.append("")
        lines.append(f"- Source: <{s['url']}>")
        if s["error"]:
            lines.append(f"- ⚠️ Error: {s['error']}")
            lines.append("")
            continue
        lines.append(f"- 候選漏案數：{len(s['missing'])}")
        lines.append("")
        if s["missing"]:
            for name in s["missing"]:
                lines.append(f"- [ ] {name}")
            total_missing += len(s["missing"])
        else:
            lines.append("（無）")
        lines.append("")
    lines.append("---")
    lines.append(f"**Total candidate missing across all sources: {total_missing}**")

    out_md = "\n".join(lines) + "\n"
    REPORT_MD.write_text(out_md)
    print(f"[scan] wrote {REPORT_MD}")

    if args.json:
        REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2))
        print(f"[scan] wrote {REPORT_JSON}")

    if args.stdout:
        print()
        print(out_md)

    return 0

if __name__ == "__main__":
    sys.exit(main())
