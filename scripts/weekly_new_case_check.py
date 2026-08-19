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
import time
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
               "and", "et", "al", "plc", "group", "holdings", "platforms",
               # ── 產業通用詞：本身不具識別力，兩造同業時會造成假性同案 ──
               # 2026-08-19：Round Hill *Music* v. Anthropic 曾因與 Concord *Music*
               # v. Anthropic 共享 token "music"（原告側）與 "anthropic"（被告側）
               # 而被誤判為已列載，靜默漏掉一件全新訴訟。AI 著作權訴訟原告高度集中
               # 於音樂／出版／媒體業，這類詞必須排除。
               "music", "musical", "media", "publishing", "publishers", "publisher",
               "records", "recordings", "recording", "entertainment", "news",
               "press", "books", "book", "studios", "studio", "productions",
               "pictures", "association", "associates", "partners", "partnership",
               "fund", "royalty", "royalties"}


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
def raise_alert(title: str, desc: str) -> None:
    """把掃描失敗寫進 .pending-review.json 的 scan-alert 區段，讓 main-board
    橘色 banner 看得見。

    2026-08-19 記：token 失效時本腳本只是 sys.exit(2)，退出碼沒人看、報告檔
    靜默不產生，主動層連死三週（8/3、8/10、8/17）都沒被察覺，期間漏掉
    Round Hill Music v. Anthropic / v. Suno 兩件新訴訟。失敗必須出聲。
    """
    import subprocess
    from datetime import datetime
    item = [{
        "title": f"⚠ {title}",
        "subtitle": f"weekly_new_case_check.py · {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "desc": desc,
        "url": "https://www.courtlistener.com/profile/api/",
    }]
    try:
        subprocess.run(
            [sys.executable, str(Path(__file__).parent / "add_pending.py"),
             "--section", "scan-alert", "--label", "自動掃描異常", "--replace-stdin"],
            input=json.dumps(item, ensure_ascii=False),
            capture_output=True, text=True, timeout=30,
        )
        print("⚠ 已寫入 .pending-review.json scan-alert 區段", file=sys.stderr)
    except Exception as exc:                      # 告警本身失敗不得掩蓋原錯誤
        print(f"（告警寫入失敗：{exc}）", file=sys.stderr)


def clear_alert() -> None:
    """掃描成功時清掉舊告警，避免 banner 長期掛著已解決的錯誤。"""
    import subprocess
    try:
        subprocess.run(
            [sys.executable, str(Path(__file__).parent / "add_pending.py"),
             "--clear-section", "scan-alert"],
            capture_output=True, text=True, timeout=30,
        )
    except Exception:
        pass


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
        # 排程在 08:00 觸發時 Mac 可能剛喚醒、WiFi 尚未連上，DNS 會失敗
        # （2026-08-03 即因 [Errno 8] nodename nor servname 而 exit 3）。
        # 故網路類錯誤重試 4 次、間隔遞增，仍失敗才放棄。
        data = None
        for attempt in range(4):
            try:
                with urlopen(req, timeout=45) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                break
            except HTTPError as e:
                body = ""
                try:
                    body = e.read().decode("utf-8", errors="ignore")[:500]
                except Exception:
                    pass
                print(f"HTTP {e.code} from CourtListener: {e.reason}\n{body}",
                      file=sys.stderr)
                hint = ("COURTLISTENER_TOKEN 失效或過期，請至 "
                        "https://www.courtlistener.com/profile/api/ 重新產生後，"
                        "以 PlistBuddy 寫入 ~/Library/LaunchAgents/ 之 plist 並重載 agent"
                        if e.code in (401, 403) else
                        f"CourtListener API 回傳 HTTP {e.code}")
                raise_alert(f"新案掃描失敗（HTTP {e.code}）", hint)
                sys.exit(2)
            except URLError as e:
                wait = 15 * (attempt + 1)
                if attempt == 3:
                    print(f"Network error（重試 4 次仍失敗）：{e.reason}", file=sys.stderr)
                    raise_alert("新案掃描失敗（連線錯誤）",
                                f"重試 4 次仍無法連上 CourtListener：{e.reason}")
                    sys.exit(3)
                print(f"Network error：{e.reason}；{wait} 秒後重試"
                      f"（{attempt + 1}/3）", file=sys.stderr)
                time.sleep(wait)
        if data is None:
            sys.exit(3)
        results.extend(data.get("results", []))
        next_url = data.get("next")
    clear_alert()        # 查詢成功 → 撤下先前的異常告警
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


def load_rejected_urls() -> set[str]:
    """scripts/rejected_cases.json — main-board 審核退回的案件 ledger
    （apply_decisions.py 維護），掃描時跳過，退回案件不會每週重現。"""
    p = Path(__file__).resolve().parent / "rejected_cases.json"
    if not p.is_file():
        return set()
    try:
        entries = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    return {e.get("url") for e in entries if isinstance(e, dict) and e.get("url")}


# ─────────────────────────────────────────────────────────────────────────────
# 自動分流（auto-triage）：抓起訴狀全文，機器判斷是否 AI 相關著作權案
# （YJ 2026-06-13 指示：能機器判的不要進人工審核清單）
# ─────────────────────────────────────────────────────────────────────────────
# 純 AI 業者：當事人名單直接命中即視為 AI 案（不需讀起訴狀）。
# 刻意不含 Google / Amazon / Apple / Microsoft / Meta / Adobe 等大廠——
# 它們也常被告與 AI 無關的著作權案，須以起訴狀內文判斷。
AI_PURE_PLAY = [
    "OpenAI", "Anthropic", "Cohere", "Mistral", "DeepSeek", "xAI",
    "Midjourney", "Stability AI", "Runway", "Suno", "Udio",
    "MiniMax", "Hailuo", "ElevenLabs", "Eleven Labs", "Lovo", "Resemble",
    "Perplexity", "Hugging Face",
]

# 起訴狀內文 AI 關鍵詞（lowercase 比對）。命中任一即視為 AI 相關。
AI_COMPLAINT_TERMS = [
    "artificial intelligence", "machine learning", "deep learning",
    "generative", "large language model", "foundation model",
    "neural network", "training data", "training dataset",
    "ai model", "ai system", "ai training", "ai-generated",
    "chatbot", "chatgpt", "stable diffusion", "midjourney",
    "text-to-image", "text-to-video", "diffusion model",
]

COPYRIGHT_COMPLAINT_TERMS = ["copyright", "17 u.s.c"]

SCRIPTS_DIR = Path(__file__).resolve().parent


def fetch_complaint_text(token: str, docket_id, verbose: bool = False) -> str | None:
    """抓 docket entry #1（起訴狀／移送聲請）的 RECAP plain_text。

    回 None = 文件不可得（未進 RECAP、尚未 OCR、或 API 失敗）。
    非致命：呼叫端 fallback 到人工審核。
    """
    if not docket_id:
        return None
    params = {
        "docket_entry__docket": docket_id,
        "docket_entry__entry_number": 1,
        "fields": "plain_text,is_available",
        "page_size": 3,
    }
    url = f"{API_BASE}/recap-documents/?{urlencode(params)}"
    req = Request(url, headers={"Authorization": f"Token {token}",
                                "Accept": "application/json"})
    try:
        with urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    # OSError 涵蓋 socket.timeout（Python 3.9 它還不是 TimeoutError 子類）、
    # URLError、連線重置等——單筆失敗一律當「不可得」，留人工，不炸整個掃描。
    except (OSError, json.JSONDecodeError) as e:
        if verbose:
            print(f"  (complaint fetch failed, docket {docket_id}: {e})", file=sys.stderr)
        return None
    for doc in data.get("results", []):
        text = (doc.get("plain_text") or "").strip()
        if len(text) > 200:
            return text
    return None


def classify_candidate(c: dict, token: str, verbose: bool = False) -> tuple[str, str]:
    """機器分流。回 (verdict, reason)，verdict ∈ {"ai", "not_ai", "unknown"}。

    判準：
      1. 當事人含純 AI 業者 → ai（免讀起訴狀）
      2. 起訴狀全文可得：含著作權字樣且含任一 AI 關鍵詞 → ai；
         可得但無 AI 關鍵詞（或未提著作權）→ not_ai（自動退回）
      3. 全文不可得 → unknown（唯一留給人工的情形）
    """
    # word-boundary 比對——子字串會誤殺（實測 "Udio" ⊂ "Studio"、"Suno" ⊂ 人名）
    parties = " | ".join(p or "" for p in (c.get("party") or []))
    for name in AI_PURE_PLAY:
        if re.search(rf"\b{re.escape(name)}\b", parties, re.IGNORECASE):
            return "ai", f"當事人含 AI 業者：{name}"
    text = fetch_complaint_text(token, c.get("docket_id"), verbose)
    if text is None:
        return "unknown", "起訴狀全文不可得（RECAP 無文件），留待人工"
    tl = text.lower()
    has_copyright = any(t in tl for t in COPYRIGHT_COMPLAINT_TERMS)
    ai_hits = [t for t in AI_COMPLAINT_TERMS if t in tl]
    if has_copyright and ai_hits:
        return "ai", f"起訴狀含 AI 關鍵詞：{'、'.join(ai_hits[:4])}"
    if not has_copyright:
        return "not_ai", "起訴狀全文未提及著作權"
    return "not_ai", "起訴狀全文無任何 AI 關鍵詞（非 AI 案）"


def append_ledger(path: Path, records: list[dict]) -> int:
    """分流結果記入 ledger / queue（與 apply_decisions.py 同格式、以 url 去重）。"""
    try:
        existing = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else []
    except (OSError, json.JSONDecodeError):
        existing = []
    urls = {e.get("url") for e in existing}
    added = 0
    for r in records:
        if r.get("url") and r["url"] in urls:
            continue
        existing.append(r)
        urls.add(r.get("url"))
        added += 1
    if added:
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(existing, ensure_ascii=False, indent=2) + "\n",
                       encoding="utf-8")
        tmp.replace(path)
    return added


def triage_record(c: dict, now_iso: str) -> dict:
    court = c.get("court") or c.get("court_id") or "?"
    docket = c.get("docketNumber") or c.get("docket_number") or "?"
    date_filed = c.get("dateFiled") or c.get("date_filed") or "?"
    return {
        "title": c.get("caseName") or c.get("case_name") or "(無案名)",
        "url": case_url(c),
        "subtitle": f"{court} · {docket} · filed {date_filed}",
        "note": f"自動分流：{c.get('_triage', '')}",
        "decidedAt": now_iso,
        "appliedAt": now_iso,
        "decidedBy": "auto-triage",
    }


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
    auto_ai: list[dict] | None = None,
    auto_rejected: list[dict] | None = None,
) -> None:
    auto_ai = auto_ai or []
    auto_rejected = auto_rejected or []
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    parts = [
        f"# Weekly New Case Check — {today}",
        "",
        f"_過去 {days} 天 CourtListener 新立案掃描。AI × 著作權關鍵字 + nature_of_suit 820；"
        f"起訴狀全文自動分流（人工只審全文不可得者）。_",
        f"_腳本：`scripts/weekly_new_case_check.py`_",
        "",
        "---",
        "",
        f"## ✓ 自動通過（{len(auto_ai)} 件）— 已進 approved_queue.json",
        "",
    ]
    for c in auto_ai:
        parts.append(format_case_md(c))
        parts.append(f"- **Triage**: {c.get('_triage', '')}\n")
    if not auto_ai:
        parts.append("_無。_\n")
    parts.extend([
        "",
        "---",
        "",
        f"## 🆕 待人工審核（{len(candidates)} 件）— 起訴狀全文不可得，機器判不了",
        "",
    ])
    if candidates:
        parts.extend([format_case_md(c) + "\n" for c in candidates])
    else:
        parts.append("_本週無待補新案件。_\n")
    parts.extend([
        "",
        "---",
        "",
        f"## ✕ 自動退回（{len(auto_rejected)} 件）— 起訴狀無 AI 內容，已進 rejected_cases.json",
        "",
    ])
    for c in auto_rejected:
        name = c.get("caseName") or "?"
        parts.append(f"- {name}（{c.get('_triage', '')}）")
    if not auto_rejected:
        parts.append("_無。_")
    parts.append("")
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
    ap.add_argument("--no-triage", action="store_true",
                    help="跳過起訴狀自動分流，全部進人工審核清單（除錯用）")
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

    # 3. 去重（dashboard 已列載 + main-board 已退回的都不再列為候選）
    rejected_urls = load_rejected_urls()
    candidates: list[dict] = []
    already_tracked: list[dict] = []
    rejected_skipped: list[dict] = []
    for c in results:
        name = c.get("caseName") or c.get("case_name") or ""
        if is_already_tracked(name, existing):
            already_tracked.append(c)
        elif case_url(c) in rejected_urls:
            rejected_skipped.append(c)
        else:
            candidates.append(c)
    if rejected_skipped:
        print(f"  ↺ {len(rejected_skipped)} 件曾退回（rejected_cases.json），不再列入待審",
              file=sys.stderr)

    # 3.5 自動分流：抓起訴狀全文機器判斷，人工只審 unknown
    auto_ai: list[dict] = []
    auto_rejected: list[dict] = []
    needs_review: list[dict] = []
    if args.dry_run or args.no_triage:
        needs_review = candidates
    else:
        print(f"  ⚙ 自動分流 {len(candidates)} 件（抓起訴狀全文）…", file=sys.stderr)
        now_iso = datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")
        for c in candidates:
            verdict, reason = classify_candidate(c, token, args.verbose)
            c["_triage"] = reason
            {"ai": auto_ai, "not_ai": auto_rejected, "unknown": needs_review}[verdict].append(c)
        if auto_ai:
            n = append_ledger(SCRIPTS_DIR / "approved_queue.json",
                              [triage_record(c, now_iso) for c in auto_ai])
            print(f"  ✓ 自動通過 {len(auto_ai)} 件 → approved_queue.json（新進 {n} 件）",
                  file=sys.stderr)
        if auto_rejected:
            n = append_ledger(SCRIPTS_DIR / "rejected_cases.json",
                              [triage_record(c, now_iso) for c in auto_rejected])
            print(f"  ✕ 自動退回 {len(auto_rejected)} 件 → rejected_cases.json（新進 {n} 件，"
                  f"之後掃描跳過）", file=sys.stderr)

    # 4. 寫報告
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out = CASES_DIR / f"_weekly_new_cases_{today}.md"
    write_report(needs_review, already_tracked, out, args.days,
                 auto_ai=auto_ai, auto_rejected=auto_rejected)
    print(f"✓ 報告已寫至 {out.relative_to(REPO_ROOT)}", file=sys.stderr)
    print(f"  自動通過：{len(auto_ai)}  ｜  自動退回：{len(auto_rejected)}  ｜  "
          f"留人工：{len(needs_review)}  ｜  已列載：{len(already_tracked)}", file=sys.stderr)

    # 5. 寫 .pending-review.json (main-board 慣例檔) — 只放機器判不了的
    if not args.dry_run:
        write_pending_review(needs_review, args.days)
    else:
        print(f"[dry-run] 跳過寫 .pending-review.json（避免污染 repo）", file=sys.stderr)

    # 6. stdout 摘要（給 launchd 的 log）
    if auto_ai:
        print(f"\n✓ 自動通過（{len(auto_ai)}）— 已進 approved_queue.json 待列載：")
        for c in auto_ai:
            print(f"  - {c.get('caseName', '?')} | {c.get('_triage', '')}")
    if needs_review:
        print(f"\n🆕 待人工審核（{len(needs_review)}）— 起訴狀不可得，機器判不了：")
        for c in needs_review:
            print(f"  - {c.get('caseName', '?')} | {c.get('court', '?')} · {c.get('docketNumber', '?')} | {c.get('dateFiled', '?')}")
    if not auto_ai and not needs_review:
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
        item = {
            "title": c.get("caseName") or c.get("case_name") or "(無案名)",
            "subtitle": f"{court} · {docket} · filed {date_filed}",
            "desc": case_summary(c),
            "url": case_url(c),
        }
        # 穩定 id：main-board 審核決定以「專案名|id」為 key，帶 docket id
        # 讓同一案件跨週重掃時決定不會對不上（無 id 時 main-board 退回 hash(url)）。
        cl_id = c.get("docket_id") or c.get("id")
        if cl_id:
            item["id"] = str(cl_id)
        items.append(item)
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
