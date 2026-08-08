#!/usr/bin/env python3
"""重生 cases/_index.md：比對 cases.json 與 cases/case-NNN_*.md 的差異。

背景：舊的 `_index.md` 是 2026-04-27 的一次性報告，標「50 件不符」後來證實是
假警報（比對邏輯過於字面），且沒有任何 script 會重生它，導致長期誤導。本 script
取代之，改以可解釋的規則比對，並在每次 batch_refresh 後自動重生。

比對項目（以 cases.json 為 dashboard 現況、case .md 為 CourtListener 快照）：
  - Judge      姓氏比對（dashboard 常只寫姓，CourtListener 寫全名）
  - Court      法院代碼／簡稱比對（S.D.N.Y. ↔ S.D. New York）
  - Docket id  cases.json 的 docket 是否等於 case .md 的 CourtListener ID
  - 新進度     case .md 的 Date Last Filing 是否晚於 cases.json 的 updatedAt

用法：
  python3 scripts/rebuild_case_index.py                # 寫入 cases/_index.md
  python3 scripts/rebuild_case_index.py --stdout       # 同時印出
  python3 scripts/rebuild_case_index.py --only-issues  # 只列有差異者
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CASES = ROOT / "data" / "cases.json"
CASES_DIR = ROOT / "cases"
OUT = CASES_DIR / "_index.md"

FIELD_RE = {
    "docket_no": re.compile(r"\|\s*Docket Number\s*\|\s*`?([^`|]+)`?\s*\|"),
    "court": re.compile(r"\|\s*Court\s*\|\s*([^|]+)\|"),
    "judge": re.compile(r"\|\s*Judge Assigned\s*\|\s*([^|]+)\|"),
    "last_filing": re.compile(r"\|\s*Date Last Filing\s*\|\s*([\d-]+)\s*\|"),
    "cl_id": re.compile(r"\|\s*CourtListener ID\s*\|\s*`?(\d+)`?\s*\|"),
}
FETCHED_RE = re.compile(r"最後更新（CourtListener fetch）：\s*([\d-]+)")
COURT_TOKEN_RE = re.compile(r"[a-z]+")


def parse_case_md(path: Path) -> dict:
    text = path.read_text(errors="replace")
    out = {"file": path.name}
    m = re.match(r"case-(\d+)_", path.name)
    out["id"] = int(m.group(1)) if m else None
    for key, rx in FIELD_RE.items():
        hit = rx.search(text)
        out[key] = hit.group(1).strip() if hit else None
    hit = FETCHED_RE.search(text)
    out["fetched"] = hit.group(1) if hit else None
    out["entries"] = text.count("### 📄")
    return out


def surname(s: str) -> str:
    """取姓氏小寫，供 dashboard「Stein」對上 CourtListener「Sidney H. Stein」。"""
    if not s:
        return ""
    s = re.sub(r"\(.*?\)|（.*?）", " ", s)
    s = re.split(r"[／/、,]", s)[0]
    parts = [p for p in re.split(r"\s+", s.strip()) if p]
    return parts[-1].lower().strip(".") if parts else ""


# 州名／縮寫 → CourtListener 兩碼州別。舊 _index.md 的 50 件「不符」大多源於
# 拿「S.D.N.Y.」硬比「District Court, S.D. New York (nysd)」的字面差異，
# 故一律先正規化成 CL court code（nysd、cand、ded…）再比。
STATE = {
    "cal": "ca", "california": "ca", "ny": "ny", "newyork": "ny",
    "del": "de", "delaware": "de", "mass": "ma", "massachusetts": "ma",
    "wash": "wa", "washington": "wa", "ill": "il", "illinois": "il",
    "ala": "al", "alabama": "al", "tenn": "tn", "tennessee": "tn",
    "mont": "mt", "montana": "mt", "colo": "co", "colorado": "co",
    "pa": "pa", "pennsylvania": "pa", "nc": "nc", "northcarolina": "nc",
    "tex": "tx", "texas": "tx", "fla": "fl", "florida": "fl",
    "ga": "ga", "georgia": "ga", "nj": "nj", "newjersey": "nj",
}
DIV_RE = re.compile(r"\b([nsewc])\.?\s*d\.?\b|\bdistrict\s+of\b|\bd\.")
CL_CODE_RE = re.compile(r"`([a-z]{2,6})`")


def court_code(s: str) -> str:
    """把法院字串正規化成 CourtListener court code，取不出來回空字串。"""
    if not s:
        return ""
    m = CL_CODE_RE.search(s)          # case .md 直接帶 `nysd`
    if m:
        return m.group(1)
    t = s.lower()
    if "d.d.c" in t or "district of columbia" in t:
        return "dcd"
    if "s.d.n.y" in t or t.startswith("sdny"):
        return "nysd"
    if "e.d.n.y" in t or t.startswith("edny"):
        return "nyed"
    if "w.d.n.c" in t:
        return "ncwd"
    # 一般式：<方位>.D. <州>  例如 N.D. Cal. / W.D. Wash. / D. Mass.
    div = re.search(r"\b([nsewc])\.\s*d\.", t)
    div = div.group(1) if div else "d"
    st = ""
    for token in re.findall(r"[a-z]+", t.replace(" ", "")):
        if token in STATE:
            st = STATE[token]
            break
    if not st:
        for name, code in STATE.items():
            if name in t.replace(" ", ""):
                st = code
                break
    if not st:
        return ""
    return st + ("d" if div == "d" else div + "d")


def court_tokens(s: str) -> set:
    """保留給無法正規化者的粗略比對。"""
    if not s:
        return set()
    s = s.lower().replace(".", "")
    return set(COURT_TOKEN_RE.findall(s)) - {
        "district", "court", "of", "the", "us", "united", "states"}


def compare(case: dict, md: dict) -> list:
    issues = []

    j_dash, j_md = surname(case.get("judge")), surname(md.get("judge"))
    if j_dash and j_md and j_dash != j_md and j_dash not in ("待分派", "待確認", "tba"):
        issues.append(f"Judge 不符：dashboard「{case.get('judge')}」／CL「{md.get('judge')}」")

    c_dash, c_md = court_code(case.get("court")), court_code(md.get("court"))
    if c_dash and c_md:
        if c_dash != c_md:
            issues.append(f"Court 不符：dashboard「{case.get('court')}」（{c_dash}）"
                          f"／CL「{md.get('court')}」（{c_md}）")
    else:
        t_dash, t_md = court_tokens(case.get("court")), court_tokens(md.get("court"))
        if t_dash and t_md and not (t_dash & t_md):
            issues.append(f"Court 待確認：dashboard「{case.get('court')}」"
                          f"／CL「{md.get('court')}」（無法正規化，需人工看）")

    if case.get("docket") and md.get("cl_id") and int(md["cl_id"]) != case["docket"]:
        issues.append(f"docket id 不符：cases.json {case['docket']}／case .md {md['cl_id']}")

    lf, up = md.get("last_filing"), case.get("updatedAt")
    if lf and up and lf > up:
        issues.append(f"CL 有較新書狀（{lf}）而 cases.json 停在 {up}")

    return issues


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--stdout", action="store_true")
    ap.add_argument("--only-issues", action="store_true")
    args = ap.parse_args()

    cases = {c["id"]: c for c in json.loads(CASES.read_text())["data"]}
    mds = {}
    for p in sorted(CASES_DIR.glob("case-*.md")):
        md = parse_case_md(p)
        if md["id"] is not None:
            mds[md["id"]] = md

    rows, issue_count = [], 0
    for cid in sorted(set(cases) | set(mds)):
        case, md = cases.get(cid), mds.get(cid)
        if case and not md:
            rows.append((cid, case["name"], "—", ["無 case .md（尚未 fetch）"]))
            issue_count += 1
            continue
        if md and not case:
            rows.append((cid, md["file"], md.get("fetched") or "—",
                         ["case .md 存在但 cases.json 無此 id（案件已刪除？）"]))
            issue_count += 1
            continue
        issues = compare(case, md)
        if issues:
            issue_count += 1
        if issues or not args.only_issues:
            rows.append((cid, case["name"], md.get("fetched") or "—", issues))

    stale = [m for m in mds.values()
             if m.get("fetched") and m["fetched"] < str(date.today().replace(day=1))]

    lines = [
        "# Cases Verification Index",
        "",
        f"> 由 `scripts/rebuild_case_index.py` 自動重生於 "
        f"{datetime.now().strftime('%Y-%m-%d %H:%M')}。**不要手改**。",
        "",
        f"- cases.json 案件數：**{len(cases)}**",
        f"- 已有 case .md 之案件：**{len(mds)}**（合計 "
        f"{sum(m['entries'] for m in mds.values())} 筆 docket entries）",
        f"- 有差異需人工確認：**{issue_count}**",
        f"- fetch 日期早於本月者：**{len(stale)}**",
        "",
        "比對規則：Judge 取姓氏比對、Court 取代碼交集、docket id 逐字比對、"
        "並檢查 CourtListener 最後書狀日是否晚於 cases.json 的 updatedAt。",
        "",
        "| id | 案件 | 上次 fetch | 差異 |",
        "|---:|---|---|---|",
    ]
    for cid, name, fetched, issues in rows:
        mark = "⚠️ " + "；".join(issues) if issues else "✅ 一致"
        lines.append(f"| {cid} | {name[:44]} | {fetched} | {mark} |")
    lines.append("")

    text = "\n".join(lines) + "\n"
    OUT.write_text(text)
    print(f"[✓] 已重生 {OUT.relative_to(ROOT)}："
          f"{len(rows)} 列、{issue_count} 件有差異、{len(stale)} 件 fetch 過舊")
    if args.stdout:
        print()
        print(text)


if __name__ == "__main__":
    main()
