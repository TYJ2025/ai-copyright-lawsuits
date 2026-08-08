#!/usr/bin/env python3
"""以起訴狀為準核對各案 claims 標籤（排程執行）。

規則（2026-08-04 YJ 立）：claims 標籤一律以**起訴狀所載訴因**為準。訴訟中之增刪
（撤回、追加請求權）不動標籤，改寫入 issues（訴訟爭點）。

流程：
  1. 以 cases.json 的 `docket`（CourtListener docket id）向 CourtListener API 取
     docket entries，找出 document_number=1 之起訴狀（COMPLAINT）
  2. 取 RECAP 全文（plain_text；無全文則記為 unavailable）
  3. 以 COUNT / CLAIM FOR RELIEF 標題正則擷取各訴因原文
  4. 依 data/claims_vocab.json 對映 canonical，寫回：
       claims          — canonical 規範用語（僅在與現值不同時提示，預設不覆寫）
       claimsDetail    — [{count, title, canonical}] 起訴狀原文
       claimsVerifiedAt— 核對日期
       claimsSource    — 起訴狀來源 URL

環境變數：
  COURTLISTENER_TOKEN   必要。至 https://www.courtlistener.com/profile/api/ 產生。

用法：
  export COURTLISTENER_TOKEN=xxxx
  python3 scripts/verify_claims.py --case-id 6            # 單案，dry-run
  python3 scripts/verify_claims.py --pending --limit 20   # 只跑尚未核對者
  python3 scripts/verify_claims.py --pending --apply
  python3 scripts/verify_claims.py --status               # 只看核對進度，不打 API
  python3 scripts/verify_claims.py --pending --apply --overwrite-claims
                                    # 併同以起訴狀結果覆寫 claims（預設只提示差異）

未帶 --overwrite-claims 時本 script 不會改動既有 claims，只補 claimsDetail 與
核對日期，並在輸出列出「標籤與起訴狀不一致」清單供人工判斷。
本 script 不碰 git，也不跑 build.py。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CASES = ROOT / "data" / "cases.json"
VOCAB = ROOT / "data" / "claims_vocab.json"
API = "https://www.courtlistener.com/api/rest/v4"
RATE_SLEEP = 1.0  # CourtListener 上限 5,000 req/hr，保守留白

# COUNT I — DIRECT COPYRIGHT INFRINGEMENT (17 U.S.C. § 501)
# FIRST CLAIM FOR RELIEF (Contributory Copyright Infringement)
# RECAP 的 plain_text 由 PDF 抽出，訴因標題常見三種排版：
#   (a) 單行：  COUNT I — DIRECT COPYRIGHT INFRINGEMENT (17 U.S.C. § 501)
#   (b) 兩行：  COUNT I
#               DIRECT COPYRIGHT INFRINGEMENT
#   (c) 序數：  FIRST CLAIM FOR RELIEF
#               (Vicarious Copyright Infringement)
# 故先抓「標記行」，標題不足再往下取 1 至 3 行補齊。
ORDINALS = ("FIRST|SECOND|THIRD|FOURTH|FIFTH|SIXTH|SEVENTH|EIGHTH|NINTH|TENTH|"
            "ELEVENTH|TWELFTH|THIRTEENTH|FOURTEENTH|FIFTEENTH")
# 標記詞須夠明確，否則歌詞、內文會誤中：Concord v. Anthropic 起訴狀所附歌詞
# 「'Cause I am a champion」曾被裸 CAUSE 比對成訴因。故：
#   COUNT 可裸用；CLAIM 須接 FOR RELIEF 或編號；CAUSE 一律須接 OF ACTION。
NUM = r"(?:NO\.?\s*)?(?:[IVXLC]{1,7}|\d{1,2})"
MARKER_RE = re.compile(
    r"^\W{0,4}(?P<marker>"
    r"COUNT\s*(?:" + NUM + r")?(?![A-Za-z])"
    r"|CLAIM\s+FOR\s+RELIEF\s*(?:" + NUM + r")?(?![A-Za-z])"
    r"|CLAIM\s*" + NUM + r"(?![A-Za-z])"
    r"|CAUSE\s+OF\s+ACTION\s*(?:" + NUM + r")?(?![A-Za-z])"
    r"|(?:" + ORDINALS + r")\s+(?:CLAIM|COUNT|CAUSE)"
    r"(?:\s+(?:FOR\s+RELIEF|OF\s+ACTION))?"
    r")\W{0,4}(?P<rest>.*)$",
    re.IGNORECASE)
NUM_IN_MARKER_RE = re.compile(
    r"(?:NO\.?\s*)?\b([IVXLC]{1,7}|\d{1,2})\b\s*$|^\s*(" + ORDINALS + r")\b",
    re.IGNORECASE)
# 目錄頁的引導點（THREE .......... 12）
TOC_RE = re.compile(r"\.{3,}")
# 訴因標題應含之字眼；全大寫者亦視為標題
CLAIMISH_RE = re.compile(
    r"\b(?:infring|violat|breach|misappropriat|unfair|unjust|enrich|"
    r"conversion|negligen|fraud|publicity|defamation|liab|declarat|"
    r"circumvent|removal|falsif|dilut|antitrust|conspiracy|"
    r"u\.?s\.?c|§|section|act\b)", re.IGNORECASE)
# 加州等法院用「編號稿紙」（numbered pleading paper），pdftotext 會把左側 1 至 28
# 的行號一併抽出，每行開頭都是裸數字。須先剝掉，否則標題行永遠比對不到。
# 只剝「數字後沒有句點」者，以免誤剝訴狀段落編號（如「68.  Plaintiffs…」）。
LINENO_RE = re.compile(r"^\s*\d{1,2}(?!\s*\.)\s+")
# 排除內文引述（「as alleged in Count I above」）：標記行必須短
MARKER_MAX_LEN = 160
NOISE_RE = re.compile(r"^\W*(?:page\s+\d|case\s+\d:\d{2}-cv|document\s+\d|filed\s+\d{2}/)",
                      re.IGNORECASE)


def today_taipei() -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=8)).strftime("%Y-%m-%d")


def api_get(path: str, token: str, retries: int = 3, **params):
    """CourtListener 大型 docket 常逾時（NYT、MDL 動輒上千 entry），故自動重試。"""
    url = f"{API}/{path}/?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        "Authorization": f"Token {token}",
        "User-Agent": "ai-copyright-lawsuits/verify_claims",
    })
    last = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError:
            raise
        except Exception as e:                               # noqa: BLE001
            last = e
            time.sleep(2 * (attempt + 1))
    raise last if last else RuntimeError("api_get 失敗")


STORAGE = "https://storage.courtlistener.com/"
COMPLAINT_RE = re.compile(r"\bcomplaint\b", re.IGNORECASE)
NOT_COMPLAINT_RE = re.compile(
    r"\b(?:answer|motion|memorandum|exhibit|summons|civil\s+cover|"
    r"corporate\s+disclosure|certificate|proposed|order)\b", re.IGNORECASE)


def abs_url(doc) -> str:
    u = doc.get("absolute_url") or ""
    return "https://www.courtlistener.com" + u if u.startswith("/") else u


def pdf_to_text(filepath_local: str, token: str):
    """plain_text 為空時，抓 PDF 自行抽文字（需系統有 pdftotext 或 pypdf）。"""
    if not filepath_local:
        return ""
    url = STORAGE + filepath_local.lstrip("/")
    try:
        req = urllib.request.Request(url, headers={
            "Authorization": f"Token {token}",
            "User-Agent": "ai-copyright-lawsuits/verify_claims",
        })
        with urllib.request.urlopen(req, timeout=90) as r:
            blob = r.read()
    except Exception:                                        # noqa: BLE001
        return ""

    import shutil
    import subprocess
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(blob)
        tmp = f.name
    try:
        if shutil.which("pdftotext"):
            out = subprocess.run(["pdftotext", "-layout", tmp, "-"],
                                 capture_output=True, text=True, timeout=120)
            if out.returncode == 0 and out.stdout.strip():
                return out.stdout
        try:
            from pypdf import PdfReader
        except ImportError:
            try:
                from PyPDF2 import PdfReader          # type: ignore
            except ImportError:
                return ""
        reader = PdfReader(tmp)
        return "\n".join((p.extract_text() or "") for p in reader.pages)
    except Exception:                                        # noqa: BLE001
        return ""
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def candidate_docs(docket_id: int, token: str):
    """找出可能是起訴狀的文件，依優先序回傳 [(entry_number, description, doc)]。

    不再死綁 entry 1：MDL 移轉、除去（removal）等情形下 entry 1 常是移轉命令，
    起訴狀可能在其他 entry。故掃前 30 個 entry，以 description 判別。
    """
    try:
        entries = api_get("docket-entries", token, docket=docket_id,
                          page_size=30, order_by="entry_number")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"API {e.code}") from e
    except Exception as e:                                   # noqa: BLE001
        raise RuntimeError(f"API 錯誤 {e}") from e

    scored = []
    for entry in entries.get("results", []):
        num = entry.get("entry_number")
        desc = entry.get("description") or ""
        for doc in entry.get("recap_documents", []):
            d = desc + " " + (doc.get("description") or "")
            if doc.get("attachment_number"):
                continue                       # 附件多為 exhibit
            score = 0
            if COMPLAINT_RE.search(d):
                score += 10
            if NOT_COMPLAINT_RE.search(d):
                score -= 6
            if num == 1:
                score += 4
            if re.search(r"\bamended\b", d, re.I):
                score += 1     # 修正訴狀次優（訴因以最初起訴狀為準，但聊勝於無）
            if score > 0:
                scored.append((score, num or 0, desc.strip()[:70], doc))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [(n, d, doc) for _s, n, d, doc in scored]


def fetch_complaint_text(docket_id: int, token: str):
    """回傳 (全文, 來源URL) 或 (None, 說明)。"""
    try:
        cands = candidate_docs(docket_id, token)
    except RuntimeError as e:
        return None, str(e)
    if not cands:
        return None, "docket 內找不到起訴狀 entry"

    no_text = 0
    no_counts = 0
    fallback = None
    for num, _desc, doc in cands[:8]:
        text = (doc.get("plain_text") or "").strip()
        if len(text) <= 2000:
            no_text += 1
            text = pdf_to_text(doc.get("filepath_local") or "", token).strip()
            time.sleep(RATE_SLEEP)
        if len(text) <= 2000:
            continue
        # 取得文字還不夠：候選裡可能混到通知、和解書等無訴因之文件，
        # 故實際擷取看得出 COUNT 才採用，否則試下一個候選。
        if extract_counts(text):
            return text, abs_url(doc)
        no_counts += 1
        if fallback is None:
            fallback = (text, abs_url(doc))
    if fallback:
        return fallback[0], fallback[1]
    return None, (f"起訴狀候選 {len(cands)} 個：{no_text} 個無 plain_text 且 PDF 抽文失敗、"
                  f"{no_counts} 個取到文字但無 COUNT"
                  f"（若系統無 pdftotext 可 `brew install poppler`）")


def clean(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip(" .:;-—–()[]")


def strip_lineno(s: str) -> str:
    """剝掉編號稿紙左側行號。"""
    return LINENO_RE.sub("", s.strip(), count=1).strip()


def extract_counts(text: str):
    """自起訴狀全文擷取 COUNT / CLAIM 標題。回傳 [(編號, 標題原文)]。"""
    lines = text.splitlines()
    out, seen = [], set()

    for i, raw in enumerate(lines):
        line = strip_lineno(raw)
        if not line or len(line) > MARKER_MAX_LEN or NOISE_RE.match(line):
            continue
        if TOC_RE.search(line):          # 目錄頁引導點
            continue
        m = MARKER_RE.match(line)
        if not m:
            continue

        mk = NUM_IN_MARKER_RE.search(m.group("marker") or "")
        num = ((mk.group(1) or mk.group(2)) if mk else "").upper()
        title = clean(m.group("rest") or "")

        # 標題不在同一行時，往下取 1 至 3 行補齊
        if len(title) < 8:
            picked, j = [], i + 1
            while j < len(lines) and len(picked) < 3:
                nxt = strip_lineno(lines[j])
                j += 1
                if not nxt:
                    if picked:
                        break
                    continue
                if len(nxt) > MARKER_MAX_LEN or NOISE_RE.match(nxt) or TOC_RE.search(nxt):
                    break
                if MARKER_RE.match(nxt):
                    break        # 下一個 COUNT 開始了，不可併入本標題
                picked.append(nxt)
                joined = clean(" ".join(picked))
                # 取到足夠長度且看得出是訴因名稱就停
                if len(joined) >= 12 and (nxt.endswith(")") or nxt.isupper()
                                          or len(joined) >= 30):
                    break
            title = clean(" ".join(picked))

        if len(title) < 8 or len(title) > 160:
            continue
        if not re.search(r"[A-Za-z]{4}", title):
            continue
        # 內文引述常見「…Count I above」「incorporated by reference」
        if re.search(r"\b(?:above|herein|incorporat|realleg|repeat)\b", title, re.I):
            continue
        # 「Against Defendant X」為被告指涉，非訴因名稱，切掉
        title = clean(re.split(r"\bagainst\s+(?:all\s+)?defendants?\b", title, 1,
                               flags=re.IGNORECASE)[0]) or title

        # 須看得出是訴因名稱（含法律字眼，或整行全大寫的標題體例）
        if not CLAIMISH_RE.search(title) and not title.isupper():
            continue

        key = title.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append((num, title))

    return out


def dump_headings(text: str, n: int = 40):
    """除錯用：印出所有含 COUNT / CLAIM / CAUSE 的行及其前後脈絡。"""
    lines = text.splitlines()
    hits = 0
    for i, raw in enumerate(lines):
        if not re.search(r"\b(COUNT|CLAIM|CAUSE OF ACTION)\b", raw, re.I):
            continue
        hits += 1
        if hits > n:
            print(f"  …（另有更多，僅列前 {n} 處）")
            break
        for k in range(i, min(i + 3, len(lines))):
            mark = ">>" if k == i else "  "
            print(f"  {mark} {lines[k].strip()[:120]}")
        print()
    if hits == 0:
        print("  （全文中找不到 COUNT / CLAIM / CAUSE OF ACTION 字樣）")


def map_canonical(title: str, alias: dict, canon: dict):
    """把起訴狀 COUNT 標題對映到 canonical key（先查 alias 完全比對，再關鍵字比對）。"""
    if title in alias:
        return alias[title]
    t = re.sub(r"[-\u2010-\u2015]", " ", title.lower())
    t = re.sub(r"\s+", " ", t)
    rules = [
        ("dmca-1202", ["copyright management information", "copyright-management",
                       "removal of copyright", "false copyright management",
                       "falsif"]),
        ("dmca-1201", ["anti circumvention", "anticircumvention"]),
        ("dmca-1202", ["1202", "copyright management information", "cmi"]),
        ("dmca-1201", ["1201", "circumvent"]),
        ("contributory", ["contributory"]),
        ("vicarious", ["vicarious"]),
        ("inducement", ["induce"]),
        ("pre1972", ["pre-1972", "pre‑1972", "music modernization"]),
        ("lanham", ["lanham", "trademark", "false designation", "dilution"]),
        ("breach-cba", ["collective bargaining", "lmra", "labor management"]),
        ("breach-cc-license", ["creative commons"]),
        ("breach-contract", ["breach of contract"]),
        ("unjust-enrichment", ["unjust enrichment"]),
        ("trespass-chattels", ["trespass to chattel"]),
        ("tortious-interference", ["tortious interference"]),
        ("unfair-competition", ["unfair competition"]),
        ("antitrust", ["sherman", "antitrust", "monopol"]),
        ("bipa", ["biometric"]),
        ("right-of-publicity", ["right of publicity"]),
        ("cfaa", ["computer fraud"]),
        ("securities", ["14(a)", "proxy", "securities exchange act"]),
        ("fiduciary", ["fiduciary"]),
        ("defamation", ["defamation", "libel"]),
        ("conspiracy", ["conspiracy"]),
        ("conversion", ["conversion", "stolen property", "larceny"]),
        ("privacy", ["invasion of privacy", "intrusion upon seclusion"]),
        ("negligence", ["negligen"]),
        ("fraud", ["fraud"]),
        ("state-law", ["consumer privacy act", "deceptive trade practices",
                       "consumer protection", "unfair competition law",
                       "bus. & prof", "business and professions"]),
        ("declaratory-noninfringement", ["declaratory"]),
        ("direct-copyright", ["copyright infringement", "direct copyright",
                              "infringement of copyright"]),
        # DMCA 泛稱（未指明條次）先歸 §1202：AI 訓練案之 DMCA 訴因絕大多數為移除 CMI
        ("dmca-1202", ["digital millennium copyright act",
                       "digital millenium copyright act", "dmca"]),
    ]
    for key, needles in rules:
        if any(n in t for n in needles) and key in canon:
            return key
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--case-id", type=int)
    ap.add_argument("--pending", action="store_true",
                    help="處理所有 claimsVerifiedAt 為 null 且有 docket id 者")
    ap.add_argument("--limit", type=int, default=25)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--overwrite-claims", action="store_true",
                    help="以起訴狀結果覆寫 claims（預設只提示差異）")
    ap.add_argument("--status", action="store_true", help="只印核對進度，不打 API")
    ap.add_argument("--redo", action="store_true",
                    help="連同已核對過的案件一併重跑（改了擷取邏輯後用）")
    ap.add_argument("--diagnose", action="store_true",
                    help="除錯：印出 docket 前 30 個 entry 中的起訴狀候選及其取文狀態")
    ap.add_argument("--dump", action="store_true",
                    help="除錯：印出起訴狀中含 COUNT / CLAIM 字樣之行與擷取結果，不寫檔")
    args = ap.parse_args()

    doc = json.loads(CASES.read_text())
    cases = doc["data"]
    vocab = json.loads(VOCAB.read_text())
    canon, alias = vocab["canonical"], vocab["aliases"]
    label_of = {k: v["label"] for k, v in canon.items()}

    if args.status:
        done = [c for c in cases if c.get("claimsVerifiedAt")]
        pend = [c for c in cases if not c.get("claimsVerifiedAt") and c.get("docket")]
        nodk = [c for c in cases if not c.get("claimsVerifiedAt") and not c.get("docket")]
        print(f"已核對起訴狀：{len(done)} 件")
        print(f"待核對（有 docket id，可自動跑）：{len(pend)} 件")
        print(f"待核對（無 docket id，需先查號）：{len(nodk)} 件")
        return

    token = os.environ.get("COURTLISTENER_TOKEN")
    if not token:
        sys.exit("[✗] 需要環境變數 COURTLISTENER_TOKEN\n"
                 "    到 https://www.courtlistener.com/profile/api/ 產生後：\n"
                 "    export COURTLISTENER_TOKEN=xxxx")

    if args.case_id:
        targets = [c for c in cases if c["id"] == args.case_id]
        if not targets:
            sys.exit(f"[✗] case id {args.case_id} 不存在")
    elif args.pending:
        targets = [c for c in cases
                   if c.get("docket") and (args.redo or not c.get("claimsVerifiedAt"))
                   ][:args.limit]
    else:
        sys.exit("[✗] 需指定 --case-id 或 --pending（或用 --status 看進度）")

    ok = skipped = 0
    mismatches = []
    for c in targets:
        cid, name = c["id"], c["name"][:40]
        if not c.get("docket"):
            print(f"[-] case {cid:5} {name:42} 無 docket id，略過")
            skipped += 1
            continue
        if args.diagnose:
            print(f"\n===== case {cid} {name} （CL docket {c['docket']}）=====")
            try:
                cands = candidate_docs(c["docket"], token)
            except RuntimeError as e:
                print(f"  {e}")
                continue
            if not cands:
                print("  找不到起訴狀候選 entry")
                continue
            for num, desc, doc in cands[:8]:
                pt = len((doc.get("plain_text") or "").strip())
                print(f"  entry {str(num):4} | plain_text {pt:7} 字元 | "
                      f"是否可取得 {doc.get('is_available')} | ocr={doc.get('ocr_status')} | "
                      f"pdf={'有' if doc.get('filepath_local') else '無'}")
                print(f"          {desc[:88]}")
            continue

        text, src = fetch_complaint_text(c["docket"], token)
        time.sleep(RATE_SLEEP)
        if not text:
            print(f"[-] case {cid:5} {name:42} {src}")
            skipped += 1
            continue

        counts = extract_counts(text)
        if args.dump:
            print(f"\n===== case {cid} {name} =====")
            print(f"起訴狀來源：{src}　全文長度：{len(text)} 字元")
            print("\n-- 含 COUNT / CLAIM 字樣之行 --")
            dump_headings(text)
            print("-- extract_counts 擷取結果 --")
            if not counts:
                print("  （無）")
            for num, title in counts:
                key = map_canonical(title, alias, canon)
                print(f"  {num or '-':6} {title[:78]:80} → {key}")
            continue
        detail, canon_keys = [], []
        for num, title in counts:
            key = map_canonical(title, alias, canon)
            detail.append({"count": num, "title": title, "canonical": key})
            if key and key not in canon_keys:
                canon_keys.append(key)

        if not canon_keys:
            print(f"[-] case {cid:5} {name:42} 擷取不到可辨識之 COUNT，略過")
            skipped += 1
            continue

        from_complaint = [label_of[k] for k in canon_keys]
        current = list(c.get("claims") or [])
        if set(from_complaint) != set(current):
            mismatches.append((cid, name, current, from_complaint))

        c["claimsDetail"] = detail
        c["claimsVerifiedAt"] = today_taipei()
        c["claimsSource"] = src
        if args.overwrite_claims and set(from_complaint) != set(current):
            # 保留被取代的舊標籤，覆寫可回溯、不靜默丟失
            c["claimsPrevious"] = current
            c["claims"] = from_complaint
        c["updatedAt"] = today_taipei()
        ok += 1
        print(f"[✓] case {cid:5} {name:42} COUNT {len(detail)} 項 → {from_complaint}")

    if mismatches:
        print("\n⚠ 標籤與起訴狀不一致（未帶 --overwrite-claims 時不自動改）：")
        for cid, name, cur, comp in mismatches:
            print(f"  case {cid} {name}")
            print(f"      現行：{cur}")
            print(f"      起訴狀：{comp}")

    if not args.apply:
        print(f"\n[dry-run] 成功 {ok}、略過 {skipped}（加 --apply 寫入）")
        return

    CASES.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n")
    print(f"\n[✓] 已寫入：核對 {ok} 件、略過 {skipped} 件")


if __name__ == "__main__":
    main()
