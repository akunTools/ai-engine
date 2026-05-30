"""
auto_generate.py
Pilih keyword PENDING terbaik → rakit prompt via Worker /brief
→ generate HTML (pass 1) + critique (pass 2) via OpenRouter DeepSeek V4 Flash
→ upload ke staging.

ALUR (identik dengan manual BriefActivity dua fase):
  Pass 1: main prompt → DECISIONS block + HTML draft
  Pass 2: critique prompt → DECISIONS slug/title + refined HTML
  Fase 1: register slug ke keyword_stock.json (/update_keyword)
  Fase 2: upload HTML ke staging (/upload_staging)

CATATAN PENTING:
  - extract_html_from_response() membuang DECISIONS block,
    mengambil HANYA isi code block HTML.
  - Prompt menginstruksikan quadruple backticks (````html...````).
  - Fungsi ini handle keduanya: quadruple dan triple backticks.
"""
import os
import re
import sys
import json
import base64
import urllib.request
import urllib.error
import urllib.parse

WORKER_URL     = os.environ.get("WORKER_URL", "").rstrip("/") + "/"
BRIEF_TOKEN    = os.environ.get("BRIEF_TOKEN", "")
OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY", "")
TASK_TYPE      = os.environ.get("TASK_TYPE", "article")
SITE_BASE_URL  = os.environ.get("SITE_BASE_URL", "https://saastools.corenk.com")

MODEL      = "deepseek/deepseek-v4-flash:free"
OR_URL     = "https://openrouter.ai/api/v1/chat/completions"
MAX_TOKENS = 8192


# ─── HTTP helpers ──────────────────────────────────────────────────────────────

def worker_get(path: str) -> str:
    url = WORKER_URL + path.lstrip("/")
    req = urllib.request.Request(
        url,
        headers={"X-Brief-Token": BRIEF_TOKEN, "User-Agent": "ai-engine"},
        method="GET"
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8")


def worker_post(path: str, data: dict) -> str:
    url  = WORKER_URL + path.lstrip("/")
    body = urllib.parse.urlencode(data).encode("utf-8")
    req  = urllib.request.Request(
        url,
        data=body,
        headers={
            "X-Brief-Token": BRIEF_TOKEN,
            "Content-Type":  "application/x-www-form-urlencoded",
            "User-Agent":    "ai-engine"
        },
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8")


# ─── Slug (identik dengan Worker JS) ──────────────────────────────────────────

def keyword_to_slug(keyword: str) -> str:
    """
    Identik dengan Worker:
    keyword.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '')
    """
    slug = keyword.lower()
    slug = re.sub(r'[^a-z0-9]+', '-', slug)
    slug = slug.strip('-')
    return slug


# ─── Keyword selection ─────────────────────────────────────────────────────────

def parse_score(score_str: str) -> int:
    """Parse angka dari format '83 (D:64 O:100 M:60)' → 83."""
    try:
        return int(score_str.split()[0])
    except (ValueError, IndexError, AttributeError):
        return 0


def pick_best_keyword(stock: dict, is_article: bool) -> dict | None:
    """
    Pilih keyword PENDING terbaik sesuai task type.
    Urutan prioritas: EASY > MEDIUM, lalu score tertinggi.
    """
    candidates = []
    for kw in stock.get("keywords", []):
        if kw.get("status") != "PENDING":
            continue
        verdict = kw.get("verdict", "")
        if verdict not in ("EASY", "MEDIUM"):
            continue
        intent = kw.get("intent", "")
        if is_article and intent == "TOOL":
            continue
        if not is_article and intent != "TOOL":
            continue
        candidates.append((
            kw,
            0 if verdict == "EASY" else 1,
            -parse_score(kw.get("score", "0"))
        ))

    if not candidates:
        return None

    candidates.sort(key=lambda x: (x[1], x[2]))
    return candidates[0][0]


# ─── Staging dedup check ───────────────────────────────────────────────────────

def get_staged_slugs(is_article: bool) -> set:
    """
    Ambil slug yang sudah ada di staging via /get_memory.
    Mencegah generate ulang keyword yang sudah di-stage tapi belum publish.
    """
    try:
        memory = json.loads(worker_get("get_memory"))
        key    = "staged_articles" if is_article else "staged_tools"
        return {item["slug"] for item in memory.get(key, [])}
    except Exception as e:
        print(f"Warning: Gagal cek staged slugs (non-fatal): {e}")
        return set()


# ─── Brief ────────────────────────────────────────────────────────────────────

def call_brief(kw: dict, content_type: str) -> dict:
    """
    Panggil Worker /brief.
    Parameter identik dengan BriefActivity.
    Return: { prompt, critique, meta }
    """
    resp = worker_post("brief", {
        "keyword":     kw["keyword"],
        "intent":      kw.get("intent", "ARTICLE"),
        "verdict":     kw.get("verdict", "EASY"),
        "gap":         kw.get("gap", "NO"),
        "recommended": kw.get("recommended", ""),
        "score":       kw.get("score", ""),
        "type":        content_type,
    })
    return json.loads(resp)


# ─── OpenRouter ───────────────────────────────────────────────────────────────

def call_openrouter(messages: list, label: str = "") -> str:
    """
    Kirim messages ke OpenRouter DeepSeek V4 Flash.
    Menerima list messages (mendukung multi-turn untuk critique pass).
    Return: raw response text (belum di-extract HTML-nya).
    Raise Exception jika gagal — tidak ada fallback ke model lain.
    """
    payload = json.dumps({
        "model":      MODEL,
        "messages":   messages,
        "max_tokens": MAX_TOKENS,
    }).encode("utf-8")

    req = urllib.request.Request(
        OR_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {OPENROUTER_KEY}",
            "Content-Type":  "application/json",
            "HTTP-Referer":  SITE_BASE_URL,
            "X-Title":       "SaaS Tools Content Engine",
            "User-Agent":    "ai-engine",
        },
        method="POST"
    )
    tag = f" ({label})" if label else ""
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            data = json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        raise Exception(f"OpenRouter HTTP {e.code}{tag}: {body[:400]}")

    try:
        content = data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError) as e:
        raise Exception(
            f"OpenRouter response format tidak terduga{tag}: {e}. "
            f"Response: {str(data)[:300]}"
        )

    if not content:
        raise Exception(f"OpenRouter mengembalikan konten kosong{tag}.")

    return content


# ─── HTML extraction ──────────────────────────────────────────────────────────

def extract_html_from_response(response: str) -> str:
    """
    Ekstrak HTML dari dalam code block di response AI.

    AI diinstruksikan output dalam dua blok:
      1. DECISIONS block (plain text — dibuang)
      2. HTML dalam satu code block: ````html ... ````

    Fungsi ini mengambil HANYA isi code block.
    Mendukung: quadruple (````) dan triple (```) backticks.

    Fallback: jika tidak ada code block, cari dari tag <meta cluster>.
    """
    # Quadruple backticks dengan 'html' (format yang diinstruksikan)
    match = re.search(r'````html\s*\n(.*?)\n````', response, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()

    # Quadruple backticks tanpa 'html'
    match = re.search(r'````\s*\n(.*?)\n````', response, re.DOTALL)
    if match:
        content = match.group(1).strip()
        if "<" in content:
            return content

    # Triple backticks dengan 'html'
    match = re.search(r'```html\s*\n(.*?)\n```', response, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()

    # Triple backticks tanpa 'html'
    match = re.search(r'```\s*\n(.*?)\n```', response, re.DOTALL)
    if match:
        content = match.group(1).strip()
        if "<" in content:
            return content

    # Fallback: ekstrak dari <meta name="cluster"> sampai akhir
    # Terjadi jika AI tidak menggunakan code block sama sekali
    meta_match = re.search(
        r'(<meta\s+name=["\']cluster["\'].*)',
        response, re.DOTALL | re.IGNORECASE
    )
    if meta_match:
        print("Warning: Tidak ada code block. Fallback ekstraksi dari <meta cluster>.")
        return meta_match.group(1).strip()

    # Last resort: return as-is, biar validation catch
    print("Warning: Tidak bisa ekstrak HTML. Returning raw response.")
    return response.strip()


# ─── Validasi & post-process ──────────────────────────────────────────────────

def validate_html(html: str, keyword: str) -> None:
    """
    Validasi minimum sebelum upload ke staging.
    Jika gagal → sys.exit(1). Konten jelek tidak masuk staging.
    """
    if "<h1" not in html.lower():
        raise Exception(
            f"Konten tidak memiliki <h1>. "
            f"AI gagal mengikuti format. Keyword: '{keyword}'"
        )
    word_count = len(html.split())
    if word_count < 400:
        raise Exception(
            f"Konten terlalu pendek: {word_count} kata "
            f"(minimum 400). Keyword: '{keyword}'"
        )


def ensure_cluster_meta(html: str, kw: dict) -> str:
    """
    Pastikan HTML memiliki meta cluster tag.
    Jika AI sudah include, tidak diubah.
    Jika tidak ada, injeksi berdasarkan keyword matching.
    """
    if 'name="cluster"' in html or "name='cluster'" in html:
        return html

    kw_lower = kw["keyword"].lower()
    cluster_map = {
        "saas-churn-retention":    ["churn", "retention", "nrr"],
        "saas-unit-economics":     ["ltv", "cac", "payback", "arpu",
                                    "unit economics", "acquisition cost"],
        "saas-financial-planning": ["runway", "burn rate", "break even", "cash flow",
                                    "default alive", "financial forecast",
                                    "financial planning"],
        "saas-growth-funnel":      ["free trial", "conversion", "onboarding",
                                    "activation", "funnel", "product led growth"],
        "saas-revenue-pricing":    ["pricing", "mrr", "arr", "revenue", "billing",
                                    "profit margin", "monthly vs annual"],
        "saas-bootstrapper-core":  ["micro saas", "bootstrapping",
                                    "solo founder", "side project"],
        "saas-hosting-infra":      ["hosting", "vps", "server cost",
                                    "infrastructure", "cloudways", "managed hosting"],
        "saas-valuation-exit":     ["valuation", "acquisition", "exit",
                                    "multiple", "business worth"],
        "saas-plg":                ["freemium", "landing page", "a/b testing",
                                    "product market fit", "trial conversion"],
        "saas-marketing":          ["content marketing", "seo strategy",
                                    "marketing budget", "google ads",
                                    "organic growth", "cac by channel"],
        "saas-hiring-ops":         ["hiring", "revenue per employee",
                                    "contractor", "headcount", "founder salary"],
        "saas-micro-saas":         ["micro saas revenue", "micro saas pricing",
                                    "micro saas validation", "income goal",
                                    "solo saas"],
    }
    cluster_id = ""
    for cid, keywords in cluster_map.items():
        if any(k in kw_lower for k in keywords):
            cluster_id = cid
            break

    if cluster_id:
        print(f"    Injeksi cluster meta: {cluster_id}")
        return f'<meta name="cluster" content="{cluster_id}">\n' + html

    print("    Warning: Cluster tidak terdeteksi, meta cluster tidak diinjeksi.")
    return html


# ─── Main ─────────────────────────────────────────────────────────────────────

def run() -> None:
    missing = []
    if not WORKER_URL or WORKER_URL == "/":
        missing.append("WORKER_URL")
    if not BRIEF_TOKEN:
        missing.append("BRIEF_TOKEN")
    if not OPENROUTER_KEY:
        missing.append("OPENROUTER_API_KEY")
    if missing:
        print(f"FATAL: Environment variable tidak di-set: {', '.join(missing)}")
        sys.exit(1)

    is_article   = (TASK_TYPE == "article")
    content_type = "article" if is_article else "tool"
    type_label   = "artikel" if is_article else "tool"

    print(f"=== auto_generate.py | task: {type_label} | model: {MODEL} ===")

    # 1. Ambil keyword stock
    print("1/8 Mengambil keyword stock...")
    try:
        stock = json.loads(worker_get("list_keywords"))
    except Exception as e:
        print(f"FATAL: Gagal ambil keyword stock: {e}")
        sys.exit(1)
    total_pending = sum(
        1 for k in stock.get("keywords", []) if k.get("status") == "PENDING"
    )
    print(f"    Total PENDING: {total_pending} keyword.")

    # 2. Pilih keyword terbaik
    print(f"2/8 Memilih keyword terbaik untuk {type_label}...")
    kw = pick_best_keyword(stock, is_article)
    if not kw:
        print(f"SKIP: Tidak ada keyword PENDING (EASY/MEDIUM) untuk {type_label}.")
        print("Pipeline tetap berjalan untuk publish dari staging yang ada.")
        sys.exit(0)
    print(
        f"    Terpilih: '{kw['keyword']}' "
        f"[{kw.get('verdict')} | score {kw.get('score')} | intent {kw.get('intent')}]"
    )

    # 3. Cek duplikasi staging
    print("3/8 Mengecek staging (cegah duplikasi)...")
    slug         = keyword_to_slug(kw["keyword"])
    staged_slugs = get_staged_slugs(is_article)
    if slug in staged_slugs:
        print(f"SKIP: '{slug}' sudah ada di staging, menunggu giliran publish.")
        print("Pipeline tetap berjalan untuk publish dari staging yang ada.")
        sys.exit(0)
    print(f"    Slug '{slug}' belum di staging, lanjut generate.")

    # 4. Rakit prompt via Worker /brief
    print("4/8 Merakit prompt via Worker /brief...")
    try:
        brief    = call_brief(kw, content_type)
        prompt   = brief["prompt"]
        critique = brief.get("critique", "")
    except Exception as e:
        print(f"FATAL: Gagal panggil /brief: {e}")
        sys.exit(1)
    print(f"    Prompt siap ({len(prompt):,} karakter).")
    if critique:
        print(f"    Critique prompt tersedia ({len(critique):,} karakter).")
    else:
        print("    Warning: Critique prompt tidak tersedia, hanya 1 pass.")

    # 5. Pass 1: Generate draft
    print(f"5/8 Pass 1 — Generate draft ({MODEL})...")
    messages_pass1 = [{"role": "user", "content": prompt}]
    try:
        response_pass1 = call_openrouter(messages_pass1, label="pass1")
    except Exception as e:
        print(f"FATAL: Gagal generate pass 1: {e}")
        sys.exit(1)

    html_draft = extract_html_from_response(response_pass1)
    print(f"    Draft: {len(html_draft.split()):,} kata.")

    # 6. Pass 2: Critique (jika tersedia)
    # Kirim full conversation context: user → assistant (pass1) → user (critique)
    # AI critique membaca DECISIONS block + HTML dari pass1 sebagai konteks
    if critique:
        print("6/8 Pass 2 — Critique & refinement...")
        messages_pass2 = [
            {"role": "user",      "content": prompt},
            {"role": "assistant", "content": response_pass1},
            {"role": "user",      "content": critique},
        ]
        try:
            response_pass2 = call_openrouter(messages_pass2, label="pass2")
            html_final     = extract_html_from_response(response_pass2)
            print(f"    Final: {len(html_final.split()):,} kata.")
        except Exception as e:
            print(f"    Warning: Critique pass gagal ({e}). Fallback ke draft pass 1.")
            html_final = html_draft
    else:
        print("6/8 Pass 2 — Dilewati (critique tidak tersedia).")
        html_final = html_draft

    # Validasi final — jika gagal, sys.exit(1) sebelum upload
    try:
        validate_html(html_final, kw["keyword"])
    except Exception as e:
        print(f"FATAL: Validasi konten gagal: {e}")
        sys.exit(1)
    print(f"    Validasi OK: {len(html_final.split()):,} kata.")

    # Post-process: pastikan cluster meta ada
    html_final = ensure_cluster_meta(html_final, kw)

    # 7. Fase 1: Register slug ke keyword_stock.json
    #    Identik dengan tombol UPDATE MEMORY di BriefActivity
    print("7/8 Mendaftarkan slug ke keyword stock (Fase 1)...")
    try:
        worker_get(
            "update_keyword?"
            + urllib.parse.urlencode({"keyword": kw["keyword"], "slug": slug})
        )
        print(f"    Slug '{slug}' terdaftar.")
    except Exception as e:
        print(f"    Warning: Gagal daftarkan slug (non-fatal, sync_check sebagai fallback): {e}")

    # 8. Fase 2: Upload ke staging
    #    Identik dengan tombol UPLOAD STAGING di BriefActivity
    print(f"8/8 Upload ke staging/{content_type}s/ready/{slug}.html (Fase 2)...")
    content_b64 = base64.b64encode(html_final.encode("utf-8")).decode("utf-8")
    try:
        result = worker_post("upload_staging", {
            "slug":    slug,
            "type":    content_type,
            "content": content_b64,
        })
    except Exception as e:
        print(f"FATAL: Gagal upload ke staging: {e}")
        sys.exit(1)

    if result != "OK":
        print(f"WARNING: Response upload tidak expected: '{result}'")
    else:
        print("    Upload berhasil.")

    print(
        f"\n✓ Selesai: {type_label} '{kw['keyword']}'"
        f" → staging/{content_type}s/ready/{slug}.html"
    )
    print("  Akan dipublish sesuai jadwal berikutnya.")


if __name__ == "__main__":
    run()
