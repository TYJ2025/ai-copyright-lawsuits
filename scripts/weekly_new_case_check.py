#!/usr/bin/env python3
from __future__ import annotations  # PEP 563 — defer type-hint eval so PEP 604 `X | None` works on Python 3.9 (macOS system Python)
"""
weekly_new_case_check.py

每週主動查 CourtListener，找「過去 N 天內新立案、與 AI 相關、著作權類」的訴訟，
比對 dashboard.html 既有 const cases 陣列，輸出尚未列載的新案件清單到
  cases/_weekly_new_cases_YYYY-MM-DD.md

這個腳本是 daily-brief 「漏案偵測（Missing-Case Detector）」的補強版——
daily-brief 靠新聞驅動，這個靠 CourtListener docket 直接驅動，不依賴媒體報導。

用法：
  export COURTLISTENER_TOKEN=xxx
  python3 scripts/weekly_new_case_check.py           # 預設過去 7 天
  python3 scripts/weekly_new_case_check.py --days 14
  python3 scripts/weekly_new_case_check.py --dry-run # 只跑邏輯不打 API（吃 fixtures）
  python3 scripts/weekly_new_case_check.py --verbose

排程：建議由 launchd com.tyj.weekly-new-cases 每週一 08:00 觸發。

API endpoint:
  GET /api/rest/v4/search/?type=r&q=<query>&filed_after=<date>
  CourtListener Search API v4 — RECAP 聯邦法院案件搜尋
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

API_BASE = "https://www.courtlistener.com/api/rest/v4"
REPO_ROOT = Path(__file__).resolve().parent.parent
DASHBOARD = REPO_ROOT / "dashboard.html"
CASES_DIR = REPO_ROOT / "cases"

# ─────────────────────────────────────────────────────────────────────────────
# 關鍵字清單 ── 廣撒網式，目的是「不漏」，後面再人工篩
# ─────────────────────────────────────────────────────────────────────────────
AI_PARTIES = [
    # Frontier labs / 模型提供者
    "OpenAI", "Anthropic", "Cohere", "Mistral", "DeepSeek", "xAI",
    # Big Tech 玩家
    "Meta Platforms", "Mark Zuckerberg",
    "Google", "Alphabet", "Microsoft", "Apple", "Amazon", "AWS",
    "NVIDIA", "Adobe", "Samsung", "Reddit",
    # 圖像 / 影片 / 音樂 AI
    "Midjourney", "Stability AI", "Runway",
    "Suno", "Udio",
    "MiniMax", "Hailuo",
    "ElevenLabs", "Eleven Labs", "Lovo", "Resemble",
    # 搜尋 / RAG
    "Perplexity",
    # 通用平台
    "Hugging Face",
    # 著名產品名（涵蓋以產品名作為被告者）
    "ChatGPT", "Claude", "Gemini", "Llama", "Sora",
]

COPYRIGHT_TERMS = [
    "copyright", "infringement", "fair use", "DMCA",
    "training data", "generative", "LLM",
]

# 美國聯邦民事 nature_of_suit 820 = Copyright。
# CourtListener Search API (type=r) 的欄位名是 `suitNature`（非 `nature_of_suit`，
# 後者查無結果——2026-06-12 實測修正，bug 導致 5/27 起三次週掃全部誤報 0 件）。
NOS_FILTER_COPYRIGHT = "suitNature:copyright"


def build_query() -> str:
    """組合 Lucene-style query：(AI party A OR B OR ...) AND (copyright OR ...)。"""
    def or_join(items: list[str]) -> str:
        # 包雙引號處理多字片語
        return " OR ".join(f'"{x}"' if " " in x else x for x in items)
    parties = or_join(AI_PARTIES)
    terms = or_join(COPYRIGHT_TERMS)
    return f"({parties}) AND ({terms})"


# ─────────────────────────────────────────────────────────────────────────────
# Dashboard cases 陣列解析
# ─────────────────────────────────────────────────────────────────────────────
NAME_RE = re.compile(r'"name"\s*:\s*"([^"]+)"')


def normalize(s: str) -> str:
    """把案名標準化以便比對：lowercase、移除標點、合併空白。"""
    s = s.lower()
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def load_existing_case_names(dashboard_path: Path) -> set[str]:
    """從 dashboard.html 抽出 const cases 陣列裡的所有 "name" 欄。"""
    if not dashboard_path.exists():
        return set()
    text = dashboard_path.read_text(encoding="utf-8", errors="ignore")
    # 抓 const cases = [ ... ]; 區塊
    m = re.search(r"const cases\s*=\s*\[(.*?)\n\];", text, re.DOTALL)
    if not m:
        return set()
    block = m.group(1)
    names = set(normalize(x) for x in NAME_RE.findall(block))
    return names


STOP_TOKENS = {"the", "inc", "llc", "ltd", "pbc", "corp", "company", "co",
               "and", "et", "al", "plc", "group", "holdings", "platforms"}


def split_plaintiff_defendant(name_norm: str) -> tuple[str, str]:
    """把已 normalize 的案名拆成 (原告字串, 被告字串)。
    'wixen music publishing inc v meta platforms inc' →
        ('wixen music publishing inc', 'meta platforms inc')
    """
    # normalize 之後 'v.' 變 'v ' 或單獨 'v'
    parts = re.split(r"\bv\b|\bvs\b", name_norm, maxsplit=1)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    return name_norm.strip(), ""


def signature_tokens(side: str) -> set[str]:
    """取「能識別」的 token：長度 > 3、非停用字（公司型態詞）。"""
    return {t for t in side.split() if len(t) > 3 and t not in STOP_TOKENS}


def is_already_tracked(new_name: str, existing: set[str]) -> bool:
    """判斷 new_name 是否已在 existing 中。

    比對策略（由嚴到鬆）：
      1. 整串 normalize 後 substring 雙向命中 → 視為已收
      2. 原告側與被告側「各自至少一個 signature token 重疊」→ 視為已收
         （避免單側共享的被告——例：很多案件都告 Meta——被誤判為同案）
    """
    n = normalize(new_name)
    if not n:
        return False
    n_pl, n_de = split_plaintiff_defendant(n)
    n_pl_tok = signature_tokens(n_pl)
    n_de_tok = signature_tokens(n_de)

    for e in existing:
        if n in e or e in n:
            return True
        e_pl, e_de = split_plaintiff_defendant(e)
        e_pl_tok = signature_tokens(e_pl)
        e_de_tok = signature_tokens(e_de)
        # 兩側都要各有重疊才算同案
        if (n_pl_tok & e_pl_tok) and (n_de_tok & e_de_tok):
            return True
    return False


# ─────────────────────────────────────────────────────────────────────────────
# CourtListener Search API
# ─────────────────────────────────────────────────────────────────────────────
def search_courtlistener(
    token: str,
    days: int,
    *,
    nos_filter: bool = True,
    page_size: int = 50,
    max_pages: int = 5,
    verbose: bool = False,
) -> list[dict]:
    """打 CourtListener Search API v4，回傳結果清單。"""
    since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    q = build_query()
    if nos_filter:
        q = f"({q}) AND {NOS_FILTER_COPYRIGHT}"
    params = {
        "type": "r",          # RECAP 聯邦法院 docket
        "q": q,
        "filed_after": since,
        "order_by": "dateFiled desc",
    }
    url = f"{API_BASE}/search/?{urlencode(params)}"
    headers = {
        "Authorization": f"Token {token}",
        "Accept": "application/json",
    }

    results: list[dict] = []
    next_url: str | None = url
    page = 0
    while next_url and page < max_pages:
        page += 1
        if verbose:
            print(f"[page {page}] GET {next_url}", file=sys.stderr)
        req = Request(next_url, headers=headers)
        try:
            with urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8", errors="ignore")[:500]
            except Exception:
                pass
            print(f"HTTP {e.code} from CourtListener: {e.reason}\n{body}", file=sys.stderr)
            sys.exit(2)
        except URLError as e:
            print(f"Network error: {e.reason}", file=sys.stderr)
            sys.exit(3)
        results.extend(data.get("results", []))
        next_url = data.get("next")
    return results


# ─────────────────────────────────────────────────────────────────────────────
# Output
# ─────────────────────────────────────────────────────────────────────────────
def case_url(c: dict) -> str:
    """CourtListener 網頁 URL。必須用 API 給的 docket_absolute_url（含 slug）——
    網頁路由是 /docket/<id>/<slug>/，自己用 id 拼的無 slug 形式會 404。"""
    path = c.get("docket_absolute_url") or ""
    if path:
        return f"https://www.courtlistener.com{path}"
    cl_id = c.get("docket_id") or c.get("id") or ""
    return f"https://www.courtlistener.com/docket/{cl_id}/" if cl_id else ""


def case_summary(c: dict) -> str:
    """從 search API 欄位組一行人工審核用摘要：法官／訴因／陪審／代理律所。"""
    parts = []
    if c.get("assignedTo"):
        parts.append(f"法官 {c['assignedTo']}")
    if c.get("cause"):
        parts.append(c["cause"])
    if c.get("juryDemand") and c["juryDemand"] not in ("", "None"):
        parts.append(f"陪審: {c['juryDemand']}")
    firms = [f for f in (c.get("firm") or []) if f][:2]
    if firms:
        parts.append(f"代理: {'、'.join(firms)}")
    return "｜".join(parts)


def format_case_md(c: dict) -> str:
    """單一案件的 markdown 區塊。"""
    name = c.get("caseName") or c.get("case_name") or "(無案名)"
    court = c.get("court") or c.get("court_id") or "?"
    docket = c.get("docketNumber") or c.get("docket_number") or "?"
    date_filed = c.get("dateFiled") or c.get("date_filed") or "?"
    url = case_url(c)
    summary = case_summary(c)

    lines = [
        f"### {name}",
        f"- **Court / Docket**: {court} · {docket}",
        f"- **Date Filed**: {date_filed}",
    ]
    if summary:
        lines.append(f"- **Summary**: {summary}")
    if url:
        lines.append(f"- **CourtListener**: {url}")
    return "\n".join(lines)


def write_report(
    candidates: list[dict],
    already_tracked: list[dict],
    out_path: Path,
    days: int,
) -> None:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    parts = [
        f"# Weekly New Case Check — {today}",
        "",
        f"_過去 {days} 天 CourtListener 新立案掃描。AI × 著作權關鍵字 + nature_of_suit 820。_",
        f"_腳本：`scripts/weekly_new_case_check.py`_",
        "",
        "---",
        "",
        f"## 🆕 待人工審核新案件（{len(candidates)} 件）",
        "",
    ]
    if candidates:
        parts.extend([format_case_md(c) + "\n" for c in candidates])
    else:
        parts.append("_本週無待補新案件。_\n")
    parts.extend([
        "",
        "---",
        "",
        f"## 已列載案件（過濾掉 {len(already_tracked)} 件 — 僅供參考）",
        "",
    ])
    for c in already_tracked[:30]:  # 至多 30 件避免太長
        name = c.get("caseName") or "?"
        date_filed = c.get("dateFiled") or "?"
        parts.append(f"- {name} ({date_filed})")
    if len(already_tracked) > 30:
        parts.append(f"- ⋯ 共 {len(already_tracked)} 件，僅顯示前 30")

    out_path.write_text("\n".join(parts) + "\n", encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser(description="每週 CourtListener AI 著作權新案掃描")
    ap.add_argument("--days", type=int, default=7, help="回看天數（預設 7）")
    ap.add_argument("--dry-run", action="store_true", help="不打 API；用 fixtures 驗證去重邏輯")
    ap.add_argument("--no-nos-filter", action="store_true", help="不加 nature_of_suit:820 過濾（除錯用）")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    # 1. 載入既有案件名清單
    existing = load_existing_case_names(DASHBOARD)
    if args.verbose:
        print(f"既有 dashboard cases: {len(existing)} 件", file=sys.stderr)
    if not existing:
        print("⚠️  從 dashboard.html 抽不到 const cases 陣列；去重將失效。", file=sys.stderr)

    # 2. 取得搜尋結果
    if args.dry_run:
        # 用 fixtures 模擬，便於離線驗證
        results = [
            {"caseName": "Wixen Music Publishing Inc. v. Meta Platforms Inc.",
             "court": "cacd", "docketNumber": "2:26-cv-00752",
             "dateFiled": "2026-04-30", "docket_id": "70999001"},
            {"caseName": "Poseidon Wave Media LLC v. Suno Inc.",
             "court": "nysd", "docketNumber": "1:26-cv-04123",
             "dateFiled": "2026-05-12", "docket_id": "70999002"},
            {"caseName": "Bartz v. Anthropic PBC",  # 已存在
             "court": "cand", "docketNumber": "3:24-cv-05417",
             "dateFiled": "2024-08-19", "docket_id": "69058235"},
            {"caseName": "Doe v. NewAILab Inc.",  # 假新案
             "court": "nysd", "docketNumber": "1:26-cv-99999",
             "dateFiled": "2026-05-20", "docket_id": "70999003"},
        ]
        print("[dry-run] 使用內建 fixture 資料", file=sys.stderr)
    else:
        token = os.environ.get("COURTLISTENER_TOKEN", "").strip()
        if not token:
            print("錯誤：請先 export COURTLISTENER_TOKEN=<your-token>", file=sys.stderr)
            print("從 https://www.courtlistener.com/profile/api/ 重生 token", file=sys.stderr)
            return 1
        results = search_courtlistener(
            token, args.days,
            nos_filter=not args.no_nos_filter,
            verbose=args.verbose,
        )
        if args.verbose:
            print(f"CourtListener 回傳 {len(results)} 件", file=sys.stderr)

    # 3. 去重
    candidates: list[dict] = []
    already_tracked: list[dict] = []
    for c in results:
        name = c.get("caseName") or c.get("case_name") or ""
        if is_already_tracked(name, existing):
            already_tracked.append(c)
        else:
            candidates.append(c)

    # 4. 寫報告
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out = CASES_DIR / f"_weekly_new_cases_{today}.md"
    write_report(candidates, already_tracked, out, args.days)
    print(f"✓ 報告已寫至 {out.relative_to(REPO_ROOT)}", file=sys.stderr)
    print(f"  新案：{len(candidates)} 件  ｜  已列載：{len(already_tracked)} 件", file=sys.stderr)

    # 5. 寫 .pending-review.json (main-board 慣例檔)
    # 這個檔讓 main-board.vercel.app 的 update.sh 掃到，
    # 把「N 件新案件待審核」顯示在 main-board AI Copyright 卡片上。
    # ── dry-run 不寫，避免 fixture 假資料污染 repo
    if not args.dry_run:
        write_pending_review(candidates, args.days)
    else:
        print(f"[dry-run] 跳過寫 .pending-review.json（避免污染 repo）", file=sys.stderr)

    # 6. 把待審核新案件清單 print 到 stdout（給 launchd 的 log）
    if candidates:
        print(f"\n🆕 待人工審核新案件（{len(candidates)}）：")
        for c in candidates:
            print(f"  - {c.get('caseName', '?')} | {c.get('court', '?')} · {c.get('docketNumber', '?')} | {c.get('dateFiled', '?')}")
    else:
        print("\n本週無待補新案件。")

    return 0


def write_pending_review(candidates: list[dict], days: int) -> None:
    """寫 .pending-review.json 到 repo root，供 main-board 讀取顯示。

    格式約定（main-board update.sh 認得）：
      {
        "label": "...",
        "count": N,
        "items": [{"title", "subtitle", "url"}, ...],
        "updated": "...",
        "source": "scripts/weekly_new_case_check.py",
        "url": "..."   # 點擊 banner 跳到哪
      }
    """
    items = []
    for c in candidates[:20]:  # 最多 20 件，避免 main-board 卡片過長
        court = c.get("court") or c.get("court_id") or "?"
        docket = c.get("docketNumber") or c.get("docket_number") or "?"
        date_filed = c.get("dateFiled") or c.get("date_filed") or "?"
        items.append({
            "title": c.get("caseName") or c.get("case_name") or "(無案名)",
            "subtitle": f"{court} · {docket} · filed {date_filed}",
            "desc": case_summary(c),
            "url": case_url(c),
        })
    # 改經 add_pending.py 的多區段合併機制寫入：只整段替換 new-cases 區段，
    # 不會覆蓋其他 producer（如 daily-brief 時間軸候選）的區段。
    import subprocess
    r = subprocess.run(
        [sys.executable, str(Path(__file__).parent / "add_pending.py"),
         "--section", "new-cases", "--label", "新案件待人工審核", "--replace-stdin"],
        input=json.dumps(items, ensure_ascii=False),
        capture_output=True, text=True,
    )
    if r.returncode == 0:
        print(f"✓ .pending-review.json new-cases 區段已更新（count={len(items)}）", file=sys.stderr)
    else:
        print(f"✗ add_pending.py 失敗：{r.stderr.strip()}", file=sys.stderr)


if __name__ == "__main__":
    sys.exit(main())
