#!/usr/bin/env python3
"""
fetch_courtlistener_docket.py

從 CourtListener API v4 抓取單一案件的 docket metadata 與 entries，
產出 Markdown 檔到 cases/。

用法：
  export COURTLISTENER_TOKEN=xxx
  python3 fetch_courtlistener_docket.py \
      --case-id 6 \
      --docket-id 69058235 \
      --slug bartz-v-anthropic \
      [--max-entries 50] \
      [--dashboard-info "Court=N.D. Cal.|Judge=Alsup|Status=Settled"]

API endpoints used:
  GET /api/rest/v4/dockets/{id}/                    metadata
  GET /api/rest/v4/search/?type=rd&q=docket_id:{id} entries (paginated)
"""
import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, unquote
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

API_BASE = "https://www.courtlistener.com/api/rest/v4"
CASES_DIR = Path(__file__).resolve().parent.parent / "cases"


# ─────────────────────────────────────────────────────────────────────────────
# Procedural noise filter
# ─────────────────────────────────────────────────────────────────────────────
# Patterns matching entries that are purely administrative/clerical and have
# no substantive impact on the case progress. They will be filtered OUT of
# the rendered docket so YJ can focus on substantive developments.
#
# Add new patterns here as you encounter them in real cases.
PROCEDURAL_PATTERNS: list[str] = [
    # Attorney admissions / appearances / changes
    r"(?i)pro\s*hac\s*vice",
    r"(?i)application\s+for\s+admission",
    r"(?i)^notice\s+of\s+appearance",
    r"(?i)^notice\s+of\s+substitution\s+of\s+(counsel|attorney)",
    r"(?i)^notice\s+of\s+(withdrawal|change)\s+of\s+(counsel|attorney)",
    r"(?i)^notice\s+of\s+appearance/substitution/change/withdrawal",
    r"(?i)^notice\s+of\s+change\s+of\s+address",
    r"(?i)^notice\s+of\s+attorney",  # generic attorney updates
    # Service / clerical
    r"(?i)^certificate\s+of\s+service",
    r"(?i)^certificate\s+of\s+interested",  # disclosure of interested entities
    r"(?i)^civil\s+cover\s+sheet",
    r"(?i)^summons\s+(issued|returned)",
    r"(?i)^request\s+for\s+issuance\s+of\s+summons",
    r"(?i)^receipt\s+for",  # filing fee receipts
    r"(?i)^(corporate\s+)?disclosure\s+statement",  # FRCP 7.1 corp disclosures
    r"(?i)^statement\s+of\s+(consent|non-consent)\s+to.*magistrate",  # consent forms
    r"(?i)^magistrate\s+judge\s+jurisdiction",
    # Routine status / scheduling without substance
    r"(?i)^add\s+and\s+terminate\s+attorneys",
    r"(?i)^reset\s+(deadline|hearing)",  # automatic reset notices
    r"(?i)^clerks?\s+notice\s+(setting|of)\s+(initial\s+)?case\s+management",
    r"(?i)^transcript\s+order\s+form",
    r"(?i)^request\s+for\s+(transcript|copies)",
    # Empty entries (no description)
    # — handled separately by checking for empty desc
]


def is_procedural(description: str) -> bool:
    """Return True if the entry description matches a procedural noise pattern."""
    if not description or not description.strip():
        return False  # don't filter empties — let them be visible so YJ can spot odd cases
    for pat in PROCEDURAL_PATTERNS:
        if re.search(pat, description):
            return True
    return False


# ─────────────────────────────────────────────────────────────────────────────
# Court name comparison — handles abbreviations
# ─────────────────────────────────────────────────────────────────────────────
# Map dashboard-style abbreviations to court_id substrings.
# This avoids false-positive "court mismatch" warnings from format differences
# like "N.D. Cal." vs "N.D. California" (same court, different formatting).
COURT_ALIAS_NORMALIZED: dict[str, set[str]] = {
    # district courts
    "n.d. cal.": {"n.d. california", "northern district of california", "cand"},
    "n.d.cal.": {"n.d. california", "northern district of california", "cand"},
    "c.d. cal.": {"c.d. california", "central district of california", "cacd"},
    "s.d. cal.": {"s.d. california", "southern district of california", "casd"},
    "e.d. cal.": {"e.d. california", "eastern district of california", "caed"},
    "s.d.n.y.": {"s.d. new york", "southern district of new york", "nysd"},
    "e.d.n.y.": {"e.d. new york", "eastern district of new york", "nyed"},
    "d. del.": {"d. delaware", "district of delaware", "ded"},
    "d. mass.": {"d. massachusetts", "district of massachusetts", "mad"},
    "d. mont.": {"d. montana", "district of montana", "mtd"},
    "d. colo.": {"d. colorado", "district of colorado", "cod"},
    "n.d. ill.": {"n.d. illinois", "northern district of illinois", "ilnd"},
    "m.d. tenn.": {"m.d. tennessee", "middle district of tennessee", "tnmd"},
    "w.d. wash.": {"w.d. washington", "western district of washington", "wawd"},
    "w.d.n.c.": {"w.d. north carolina", "western district of north carolina", "ncwd"},
    "d.d.c.": {"d. district of columbia", "district of columbia", "dcd"},
}


def _norm(s: str) -> str:
    """Lowercase, strip, collapse multiple spaces."""
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def courts_match(declared: str, cl_full: str, cl_short: str, cl_id: str) -> bool:
    """
    Return True if declared court (e.g. "N.D. Cal.") matches CourtListener
    full/short name (e.g. "District Court, N.D. California" / "N.D. California")
    or court_id ("cand"). Tolerates abbreviation variations.
    """
    d = _norm(declared)
    candidates = {_norm(cl_full), _norm(cl_short), _norm(cl_id)}

    # 1) direct substring match in either direction
    for c in candidates:
        if not c:
            continue
        if d in c or c in d:
            return True

    # 2) alias table lookup
    for alias_key, aliases in COURT_ALIAS_NORMALIZED.items():
        # normalize the dict alias_key for comparison
        if _norm(alias_key) == d.replace(" ", ""):
            # try aliases against each candidate
            for c in candidates:
                if c and any(_norm(a) in c or c in _norm(a) for a in aliases):
                    return True
        # also try a more relaxed key match (e.g. d="n.d. cal." (with spaces))
        if _norm(alias_key) == d:
            for c in candidates:
                if c and any(_norm(a) in c or c in _norm(a) for a in aliases):
                    return True

    return False


def api_get(path: str, params: dict | None = None) -> dict:
    """GET CourtListener API with token auth."""
    token = os.environ.get("COURTLISTENER_TOKEN")
    if not token:
        sys.exit("ERROR: COURTLISTENER_TOKEN env var not set")
    url = f"{API_BASE}{path}"
    if params:
        url = f"{url}?{urlencode(params)}"
    req = Request(url, headers={
        "Authorization": f"Token {token}",
        "Accept": "application/json",
    })
    try:
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:500]
        sys.exit(f"ERROR {e.code} fetching {url}: {body}")
    except URLError as e:
        sys.exit(f"ERROR network {url}: {e}")


def fetch_docket_metadata(docket_id: int) -> dict:
    return api_get(f"/dockets/{docket_id}/")


def fetch_court_metadata(court_url: str) -> dict:
    """court_url is the full URL string from docket['court']."""
    if not court_url:
        return {}
    # path = /api/rest/v4/courts/cand/  → keep tail
    m = re.search(r"/courts/([^/]+)/?$", court_url)
    if not m:
        return {}
    return api_get(f"/courts/{m.group(1)}/")


def fetch_docket_entries(docket_id: int, max_entries: int) -> list[dict]:
    """
    Fetch docket entries via search API (type=rd).
    Each docket entry may have multiple recap_documents (main + attachments);
    we deduplicate by entry_number to keep one row per entry.
    """
    seen_entries: dict[int | str, dict] = {}
    cursor: str | None = None
    fetched = 0

    while fetched < max_entries:
        params = {
            "type": "rd",
            "q": f"docket_id:{docket_id}",
            "order_by": "entry_date_filed desc",
            "page_size": 100,
        }
        if cursor:
            params["cursor"] = cursor
        data = api_get("/search/", params)
        results = data.get("results", [])
        if not results:
            break

        for r in results:
            entry_no = r.get("entry_number") or f"_no_num_{r.get('id')}"
            if entry_no in seen_entries:
                # already saw this entry's main doc — skip the attachment row
                continue
            seen_entries[entry_no] = {
                "entry_number": r.get("entry_number"),
                "entry_date_filed": r.get("entry_date_filed"),
                "description": r.get("description") or "",
                "short_description": r.get("short_description") or "",
                "document_type": r.get("document_type"),
                "page_count": r.get("page_count"),
                "is_available": r.get("is_available"),
                "absolute_url": r.get("absolute_url"),
                "pacer_doc_id": r.get("pacer_doc_id"),
            }
            fetched += 1
            if fetched >= max_entries:
                break

        next_url = data.get("next")
        if not next_url:
            break
        # extract cursor from next url; the value in the URL is already
        # percent-encoded — decode once so urlencode doesn't double-encode it.
        m = re.search(r"[?&]cursor=([^&]+)", next_url)
        if not m:
            break
        cursor = unquote(m.group(1))
        # be polite to the API
        time.sleep(0.3)

    return list(seen_entries.values())


def fmt_date(dt_str: str | None) -> str:
    if not dt_str:
        return "—"
    return dt_str[:10]


def slugify(text: str) -> str:
    text = re.sub(r"[^\w\s-]", "", text.lower())
    text = re.sub(r"[\s_-]+", "-", text).strip("-")
    return text


def safe_docket_number(num: str | None) -> str:
    if not num:
        return "no-docket-number"
    return num.replace(":", "-").replace("/", "-").replace(" ", "")


def _render_entries_section(
    lines: list[str],
    entries: list[dict],
    heading_prefix: str = "",
) -> None:
    """Append entries (substantive first, procedural collapsed) to lines list."""
    if not entries:
        lines.append("（無 entries 資料）")
        lines.append("")
        return

    substantive = [e for e in entries if not is_procedural(e.get("description", ""))]
    procedural = [e for e in entries if is_procedural(e.get("description", ""))]
    substantive.sort(key=lambda e: (e.get("entry_date_filed") or "0000-00-00"), reverse=True)
    procedural.sort(key=lambda e: (e.get("entry_date_filed") or "0000-00-00"), reverse=True)

    lines.append(
        f"**實質性 entries**：{len(substantive)} 筆／**已過濾程序性 entries**：{len(procedural)} 筆"
        f"（pro hac vice、certificate of service、notice of appearance/change of address、disclosure statement 等）"
    )
    lines.append("")
    for e in substantive:
        num = e.get("entry_number")
        num_str = f"#{num}" if num else "#—"
        date = fmt_date(e.get("entry_date_filed"))
        desc = (e.get("description") or e.get("short_description") or "").strip()
        if len(desc) > 1000:
            desc = desc[:1000] + " …(truncated)"
        url = e.get("absolute_url") or ""
        full_url = f"https://www.courtlistener.com{url}" if url else ""
        lines.append(f"### 📄 {heading_prefix}Doc {num_str} — {date}")
        if desc:
            lines.append("")
            lines.append(desc)
        if full_url:
            lines.append("")
            lines.append(f"[CourtListener 連結]({full_url})")
        lines.append("")

    if procedural:
        lines.append("<details>")
        lines.append(f"<summary>已過濾的 {len(procedural)} 筆程序性 entries（點擊展開）</summary>")
        lines.append("")
        for e in procedural:
            num = e.get("entry_number")
            num_str = f"#{num}" if num else "#—"
            date = fmt_date(e.get("entry_date_filed"))
            desc = (e.get("description") or e.get("short_description") or "").strip()
            if len(desc) > 200:
                desc = desc[:200] + "…"
            lines.append(f"- **{heading_prefix}Doc {num_str}** ({date}): {desc}")
        lines.append("")
        lines.append("</details>")
        lines.append("")


def render_markdown(
    case_id: int,
    docket: dict,
    court_meta: dict,
    entries: list[dict],
    dashboard_info: str | None,
    secondary_dockets: list[tuple[dict, dict, list[dict]]] | None = None,
) -> str:
    lines: list[str] = []
    case_name = docket.get("case_name") or docket.get("case_name_full") or "(unknown)"
    docket_number = docket.get("docket_number", "—")
    court_name = court_meta.get("full_name") or court_meta.get("short_name") or docket.get("court_id", "—")
    judge_assigned = docket.get("assigned_to_str") or "—"
    judge_referred = docket.get("referred_to_str") or ""
    date_filed = fmt_date(docket.get("date_filed"))
    date_terminated = fmt_date(docket.get("date_terminated"))
    date_last_filing = fmt_date(docket.get("date_last_filing"))
    cause = docket.get("cause") or "—"
    nature = docket.get("nature_of_suit") or "—"
    cl_id = docket.get("id")
    cl_url = f"https://www.courtlistener.com{docket.get('absolute_url', '')}"

    fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines.append(f"# Case {case_id} — {case_name}")
    lines.append("")
    lines.append(f"> 最後更新（CourtListener fetch）：{fetched_at}")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 1. CourtListener Docket Metadata")
    lines.append("")
    lines.append(f"| 欄位 | 值 |")
    lines.append(f"|---|---|")
    lines.append(f"| Case Name | {case_name} |")
    lines.append(f"| Docket Number | `{docket_number}` |")
    lines.append(f"| Court | {court_name} (`{docket.get('court_id','')}`) |")
    lines.append(f"| Judge Assigned | {judge_assigned} |")
    if judge_referred:
        lines.append(f"| Judge Referred | {judge_referred} |")
    lines.append(f"| Date Filed | {date_filed} |")
    if docket.get("date_terminated"):
        lines.append(f"| Date Terminated | {date_terminated} |")
    lines.append(f"| Date Last Filing | {date_last_filing} |")
    lines.append(f"| Cause | {cause} |")
    lines.append(f"| Nature of Suit | {nature} |")
    lines.append(f"| Jury Demand | {docket.get('jury_demand') or '—'} |")
    lines.append(f"| CourtListener ID | `{cl_id}` |")
    lines.append(f"| CourtListener URL | <{cl_url}> |")
    lines.append("")

    if dashboard_info:
        lines.append("## 2. Dashboard 卡片 vs CourtListener 比對")
        lines.append("")
        lines.append("> Dashboard 卡片宣告：")
        lines.append("")
        for piece in dashboard_info.split("|"):
            piece = piece.strip()
            if not piece:
                continue
            lines.append(f"> - {piece}")
        lines.append("")
        # auto comparison logic
        comparisons = parse_dashboard_compare(dashboard_info, docket, court_meta)
        if comparisons:
            lines.append("**自動比對結果：**")
            lines.append("")
            for c in comparisons:
                lines.append(f"- {c}")
            lines.append("")

    lines.append("## 3. Docket Entries（最新優先，已過濾程序性 entries）")
    lines.append("")
    _render_entries_section(lines, entries, heading_prefix="")

    # Render any secondary dockets (e.g. transferred-from court, appellate docket)
    if secondary_dockets:
        for idx, (sec_docket, sec_court, sec_entries) in enumerate(secondary_dockets, start=1):
            sec_court_name = sec_court.get("full_name") or sec_court.get("short_name") or sec_docket.get("court_id", "—")
            sec_docket_num = sec_docket.get("docket_number", "—")
            sec_cl_id = sec_docket.get("id")
            sec_cl_url = f"https://www.courtlistener.com{sec_docket.get('absolute_url', '')}"
            sec_filed = fmt_date(sec_docket.get("date_filed"))
            sec_terminated = fmt_date(sec_docket.get("date_terminated"))
            sec_judge = sec_docket.get("assigned_to_str") or "—"

            lines.append(f"## {3 + idx}. Secondary Docket #{idx}: {sec_court_name} (`{sec_docket_num}`)")
            lines.append("")
            lines.append(f"| 欄位 | 值 |")
            lines.append(f"|---|---|")
            lines.append(f"| Court | {sec_court_name} (`{sec_docket.get('court_id','')}`) |")
            lines.append(f"| Docket Number | `{sec_docket_num}` |")
            lines.append(f"| Judge Assigned | {sec_judge} |")
            lines.append(f"| Date Filed | {sec_filed} |")
            if sec_docket.get("date_terminated"):
                lines.append(f"| Date Terminated | {sec_terminated} |")
            lines.append(f"| CourtListener ID | `{sec_cl_id}` |")
            lines.append(f"| CourtListener URL | <{sec_cl_url}> |")
            lines.append("")
            lines.append(f"### Secondary Docket #{idx} Entries（最新優先）")
            lines.append("")
            _render_entries_section(lines, sec_entries, heading_prefix=f"S{idx}-")

    lines.append("---")
    lines.append("")
    lines.append(f"*產生時間：{fetched_at} | Script: `scripts/fetch_courtlistener_docket.py`*")
    return "\n".join(lines)


def extract_latest_progress_date(progress_text: str) -> str | None:
    """
    Find the latest 【YYYY/M/D】 or 【YYYY 年 M 月 D 日】 token in dashboard
    progress text; return as YYYY-MM-DD ISO string, or None if none found.
    """
    if not progress_text:
        return None
    candidates: list[str] = []
    # Pattern A: 【2026/4/7】 or 【2026/04/07】
    for m in re.finditer(r"【\s*(\d{4})\s*[/\-．]\s*(\d{1,2})\s*[/\-．]\s*(\d{1,2})", progress_text):
        y, mo, d = m.group(1), m.group(2).zfill(2), m.group(3).zfill(2)
        candidates.append(f"{y}-{mo}-{d}")
    # Pattern B: 【2026 年 4 月 7 日】
    for m in re.finditer(r"【\s*(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日", progress_text):
        y, mo, d = m.group(1), m.group(2).zfill(2), m.group(3).zfill(2)
        candidates.append(f"{y}-{mo}-{d}")
    if not candidates:
        return None
    return max(candidates)  # ISO format → max() == latest


def parse_dashboard_compare(dashboard_info: str, docket: dict, court_meta: dict) -> list[str]:
    """Compare dashboard-claimed values against CourtListener docket data."""
    out: list[str] = []
    declared: dict[str, str] = {}
    for piece in dashboard_info.split("|"):
        piece = piece.strip()
        if not piece or "=" not in piece:
            continue
        k, v = piece.split("=", 1)
        declared[k.strip().lower()] = v.strip()

    # Court comparison with abbreviation whitelist
    cl_court_full = (court_meta.get("full_name") or "").lower()
    cl_court_short = (court_meta.get("short_name") or "").lower()
    cl_court_id = (docket.get("court_id") or "").lower()
    if "court" in declared:
        d_court = declared["court"].strip()
        if courts_match(d_court, cl_court_full, cl_court_short, cl_court_id):
            out.append(f"✅ Court 一致：dashboard 寫「{d_court}」，CourtListener 為「{court_meta.get('short_name') or court_meta.get('full_name') or cl_court_id}」")
        else:
            out.append(f"⚠️ Court 可能不一致：dashboard 寫「{d_court}」，CourtListener 為「{court_meta.get('short_name') or court_meta.get('full_name') or cl_court_id}」")

    # Judge comparison
    cl_judge = docket.get("assigned_to_str") or ""
    if "judge" in declared:
        d_judge = declared["judge"]
        # Match by surname
        d_lower = d_judge.lower()
        cl_lower = cl_judge.lower()
        if d_lower and cl_lower and (d_lower in cl_lower or cl_lower in d_lower or any(part in cl_lower for part in d_lower.split() if len(part) > 2)):
            out.append(f"✅ Judge 一致：dashboard 寫「{d_judge}」，CourtListener 為「{cl_judge}」")
        else:
            out.append(f"⚠️ Judge 可能不一致：dashboard 寫「{d_judge}」，CourtListener 為「{cl_judge}」")

    # Docket number comparison
    if "docket" in declared or "case_number" in declared:
        d_num = declared.get("docket") or declared.get("case_number") or ""
        cl_num = docket.get("docket_number", "")
        if d_num and cl_num and d_num.replace(" ", "") == cl_num.replace(" ", ""):
            out.append(f"✅ Docket Number 一致：`{cl_num}`")
        elif d_num:
            out.append(f"⚠️ Docket Number 可能不一致：dashboard 寫「{d_num}」，CourtListener 為「{cl_num}」")

    # Last progress date vs CourtListener last filing date
    if "progress" in declared:
        progress_text = declared["progress"]
        latest_dashboard_date = extract_latest_progress_date(progress_text)
        cl_last_filing = (docket.get("date_last_filing") or "")[:10]
        if latest_dashboard_date and cl_last_filing:
            try:
                d_dt = datetime.fromisoformat(latest_dashboard_date)
                cl_dt = datetime.fromisoformat(cl_last_filing)
                lag_days = (cl_dt - d_dt).days
                if lag_days <= 0:
                    out.append(
                        f"✅ Dashboard progress 同步：dashboard 最新日期 {latest_dashboard_date}，"
                        f"CourtListener 最後 entry {cl_last_filing}（dashboard 不落後）"
                    )
                elif lag_days <= 30:
                    out.append(
                        f"ℹ️ Dashboard progress 略落後 {lag_days} 天："
                        f"dashboard 最新日期 {latest_dashboard_date}，CourtListener 最後 entry {cl_last_filing}"
                    )
                else:
                    out.append(
                        f"⚠️ Dashboard progress **落後 {lag_days} 天**："
                        f"dashboard 最新日期 {latest_dashboard_date}，CourtListener 最後 entry {cl_last_filing}"
                        f"——建議查看新近 entries 並補充 progress"
                    )
            except ValueError:
                out.append(f"ℹ️ 日期解析失敗：dashboard {latest_dashboard_date}，CL {cl_last_filing}")
        elif cl_last_filing and not latest_dashboard_date:
            out.append(
                f"ℹ️ Dashboard progress 內找不到【YYYY/M/D】格式日期；"
                f"CourtListener 最後 entry: {cl_last_filing}"
            )

    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--case-id", type=int, required=True, help="dashboard 上的 case id")
    ap.add_argument("--docket-id", type=int, required=True, action="append",
                    help="CourtListener docket id（首個為主 docket，可重複此旗標加入次要 docket，例：移轉前舊案、上訴 docket）")
    ap.add_argument("--slug", type=str, default=None, help="檔名 slug（不給則用 docket case name slugify）")
    ap.add_argument("--max-entries", type=int, default=300,
                    help="主 docket fetch 多少 raw entries")
    ap.add_argument("--max-secondary-entries", type=int, default=100,
                    help="次要 docket fetch 多少 raw entries")
    ap.add_argument("--dashboard-info", type=str, default=None,
                    help="dashboard 卡片宣告，格式：Court=...|Judge=...|Docket=...|Status=...")
    ap.add_argument("--out-dir", type=Path, default=CASES_DIR, help="輸出資料夾（預設 cases/）")
    args = ap.parse_args()

    docket_ids: list[int] = args.docket_id  # action=append → list

    print(f"[+] Fetching primary docket metadata for {docket_ids[0]}...")
    primary_docket = fetch_docket_metadata(docket_ids[0])
    primary_court = fetch_court_metadata(primary_docket.get("court", ""))

    print(f"[+] Fetching up to {args.max_entries} entries for primary docket...")
    primary_entries = fetch_docket_entries(docket_ids[0], args.max_entries)
    print(f"[+] Got {len(primary_entries)} unique primary entries.")

    secondary_dockets: list[tuple[dict, dict, list[dict]]] = []
    for sec_id in docket_ids[1:]:
        print(f"[+] Fetching secondary docket {sec_id}...")
        sec_docket = fetch_docket_metadata(sec_id)
        sec_court = fetch_court_metadata(sec_docket.get("court", ""))
        sec_entries = fetch_docket_entries(sec_id, args.max_secondary_entries)
        print(f"[+] Got {len(sec_entries)} secondary entries for docket {sec_id}.")
        secondary_dockets.append((sec_docket, sec_court, sec_entries))

    slug = args.slug or slugify(primary_docket.get("case_name", f"docket-{docket_ids[0]}"))
    docket_num_safe = safe_docket_number(primary_docket.get("docket_number"))
    filename = f"case-{args.case_id:03d}_{docket_num_safe}_{slug}.md"
    out_path = args.out_dir / filename
    args.out_dir.mkdir(parents=True, exist_ok=True)

    md = render_markdown(
        args.case_id, primary_docket, primary_court, primary_entries,
        args.dashboard_info, secondary_dockets,
    )
    out_path.write_text(md, encoding="utf-8")
    print(f"[✓] Wrote {out_path}")
    print(f"    File size: {out_path.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
