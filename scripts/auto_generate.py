"""
auto_generate.py
Pilih keyword PENDING terbaik → rakit prompt via Worker /brief
→ generate HTML (pass 1) + critique (pass 2) via OpenRouter / DeepSeek direct
→ upload ke staging.

ALUR (identik dengan manual BriefActivity dua fase):
  Pass 1: main prompt → DECISIONS block + HTML draft
  Pass 2: critique prompt → DECISIONS slug/title + refined HTML
  Fase 1: register slug ke keyword_stock.json (/update_keyword)
  Fase 2: upload HTML ke staging (/upload_staging)

MODEL PRIORITY & ROUTING:

  calculator_tool → deepseek-v4-pro SAJA (wajib, script exit jika key tidak ada)
    Secret wajib: DEEPSEEK_API_KEY (GitHub Actions secret)

  article → free models dulu, paid sebagai last resort:
    1. openai/gpt-oss-120b:free             → OpenRouter (instruction following 8.71/10)
    2. nousresearch/hermes-3-llama-3.1-405b:free → OpenRouter (dense 405B, multi-turn)
    3. deepseek-v4-pro                      → DeepSeek direct API (paid, last resort)
       Hanya aktif jika DEEPSEEK_API_KEY di-set.
    Secret wajib: OPENROUTER_API_KEY (GitHub Actions secret)
    Secret opsional: DEEPSEEK_API_KEY (GitHub Actions secret)

FALLBACK TRIGGERS (coba model berikutnya):
  - HTTP 404 → model tidak tersedia di OpenRouter (endpoint hardcoded, 404 = routing failure)
              Contoh: "No endpoints found", "unavailable for free"
  - HTTP 429 + "upstream" → provider-side rate limit (bukan limit akun kita)
  Selain itu → raise langsung, fallback tidak membantu.

CATATAN PENTING:
  - Staging dicek SEBELUM pick keyword.
  - extract_html_from_response() membuang DECISIONS block.
  - Handle quadruple (````) dan triple (```) backticks.
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
DEEPSEEK_KEY   = os.environ.get("DEEPSEEK_API_KEY", "")
TASK_TYPE      = os.environ.get("TASK_TYPE", "article")
SITE_BASE_URL  = os.environ.get("SITE_BASE_URL", "https://saastools.corenk.com")

OR_URL = "https://openrouter.ai/api/v1/chat/completions"
DS_URL = "https://api.deepseek.com/v1/chat/completions"

MAX_TOKENS = 8192

# Model priority berbeda per TASK_TYPE.
# Setiap entry: {"model": str, "url": str, "key": str}
#
# calculator_tool: DeepSeek V4 Pro SAJA.
#   Tools adalah interactive HTML+JS calculator. Formula salah tidak terdeteksi
#   sampai user pakai. Free model tidak diizinkan untuk task ini.
#   Script exit jika DEEPSEEK_API_KEY tidak di-set.
#
# article: Free models dulu, V4 Pro sebagai last resort.
#   gpt-oss-120b:free     — instruction following 8.71/10, writing 7.91/10
#   hermes-3-405b:free    — dense 405B, dilatih untuk ikuti prompt secara presisi,
#                           multi-turn coherent (penting untuk 2-pass generation)
#   deepseek-v4-pro       — paid, hanya aktif jika DEEPSEEK_API_KEY di-set
if TASK_TYPE == "calculator_tool":
    if not DEEPSEEK_KEY:
        print("FATAL: DEEPSEEK_API_KEY wajib untuk task_type=calculator_tool.")
        print("       Set secret DEEPSEEK_API_KEY di GitHub Actions → Settings → Secrets.")
        print("       Free model tidak diizinkan untuk generate interactive tools.")
        sys.exit(1)
    MODELS = [
        {"model": "deepseek-v4-pro", "url": DS_URL, "key": DEEPSEEK_KEY},
    ]
else:
    # article (default)
    MODELS = [
        {"model": "openai/gpt-oss-120b:free",                  "url": OR_URL, "key": OPENROUTER_KEY},
        {"model": "nousresearch/hermes-3-llama-3.1-405b:free", "url": OR_URL, "key": OPENROUTER_KEY},
    ]
    if DEEPSEEK_KEY:
        MODELS.append(
            {"model": "deepseek-v4-pro", "url": DS_URL, "key": DEEPSEEK_KEY}
        )


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


def pick_best_keyword(stock: dict, is_article: bool,
                      exclude_slugs: set | None = None) -> dict | None:
    """
    Pilih keyword PENDING terbaik sesuai task type.
    Urutan prioritas: EASY > MEDIUM, lalu score tertinggi.
    exclude_slugs: set slug yang sudah ada di staging — dilewati langsung.
    """
    if exclude_slugs is None:
        exclude_slugs = set()

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
        if keyword_to_slug(kw["keyword"]) in exclude_slugs:
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


# ─── Staging slug check ────────────────────────────────────────────────────────

def get_staged_slugs(is_article: bool) -> set:
    """
    Ambil semua slug yang sudah ada di staging via /get_memory.
    Digunakan SEBELUM pick keyword.
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


# ─── AI call dengan multi-endpoint fallback ───────────────────────────────────

def _should_fallback(code: int, body: str) -> bool:
    """
    Tentukan apakah error ini layak untuk mencoba model berikutnya.

    Fallback jika:
    - 404 → model tidak tersedia di OpenRouter. Endpoint OR di-hardcode, sehingga
            404 selalu berarti model routing failure (bukan URL salah).
            Contoh pesan: "No endpoints found", "unavailable for free"
    - 429 + "upstream" → rate limit di sisi provider, bukan akun kita

    Tidak fallback jika:
    - 401 → API key salah (semua model akan sama-sama gagal)
    - 429 tanpa "upstream" → limit akun kita sendiri
    - 500, 503 → server error, retry bukan fallback yang tepat
    """
    if code == 404:
        return True
    if code == 429 and "upstream" in body.lower():
        return True
    return False


def call_openrouter(messages: list, label: str = "") -> str:
    """
    Kirim messages ke AI. Coba MODELS secara berurutan.
    Setiap model bisa punya endpoint dan API key berbeda
    (OpenRouter untuk free models, DeepSeek direct untuk V4 Pro).

    Raise Exception hanya jika semua model gagal.
    """
    tag        = f" ({label})" if label else ""
    last_error = None

    for entry in MODELS:
        model = entry["model"]
        url   = entry["url"]
        key   = entry["key"]

        if not key:
            print(f"    Skip {model}: API key tidak tersedia.")
            continue

        payload = json.dumps({
            "model":      model,
            "messages":   messages,
            "max_tokens": MAX_TOKENS,
        }).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type":  "application/json",
                "HTTP-Referer":  SITE_BASE_URL,
                "X-Title":       "SaaS Tools Content Engine",
                "User-Agent":    "ai-engine",
            },
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                data = json.loads(r.read())
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            if _should_fallback(e.code, body):
                reason = "No endpoints" if e.code == 404 else "upstream rate-limit"
                print(f"    Warning: {model} tidak tersedia ({reason}), coba fallback...")
                last_error = f"HTTP {e.code}{tag} [{model}]: {body[:200]}"
                continue
            # Error lain: tidak ada gunanya coba model lain
            raise Exception(f"OpenRouter/DeepSeek HTTP {e.code}{tag} [{model}]: {body[:400]}")

        try:
            content = data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError) as e:
            raise Exception(
                f"Response format tidak terduga{tag} [{model}]: {e}. "
                f"Response: {str(data)[:300]}"
            )

        if not content:
            raise Exception(f"AI mengembalikan konten kosong{tag} [{model}].")

        print(f"    Model dipakai: {model}")
        return content

    raise Exception(
        f"Semua model tidak tersedia{tag}. "
        f"{len(MODELS)} model dicoba, semua gagal. "
        f"Error terakhir: {last_error}"
    )


# ─── HTML extraction ──────────────────────────────────────────────────────────

def extract_html_from_response(response: str) -> str:
    """
    Ekstrak HTML dari dalam code block di response AI.

    AI diinstruksikan output dalam dua blok:
      1. DECISIONS block (plain text — dibuang)
      2. HTML dalam satu code block: ````html ... ````

    Strategi: cari PEMBUKA code block, lalu ambil konten hingga
    PENUTUP TERAKHIR — bukan penutup pertama. Ini menangani kasus
    rogue triple backtick di dalam konten HTML yang menyebabkan
    regex standar berhenti terlalu awal.

    Fallback: ekstrak dari <meta name="cluster"> jika tidak ada
    code block sama sekali.
    """
    # Cari pembuka: quadruple atau triple backticks diikuti 'html'
    open_match = re.search(r'(`{3,4})html\s*\n', response, re.IGNORECASE)
    if open_match:
        marker     = open_match.group(1)          # '```' atau '````'
        content_start = open_match.end()
        # Cari PENUTUP TERAKHIR yang cocok (bukan yang pertama)
        # Ini menangani rogue backtick di dalam konten
        close_pattern = '\n' + marker
        last_close = response.rfind(close_pattern)
        if last_close > content_start:
            extracted = response[content_start:last_close].strip()
            if extracted:
                return extracted
        # Pembuka ada tapi penutup tidak ditemukan:
        # Ambil semua konten setelah pembuka
        extracted = response[content_start:].strip()
        if extracted:
            print("Warning: Code block tidak memiliki penutup. Ambil semua setelah pembuka.")
            return extracted

    # Quadruple tanpa 'html' (jarang, tapi mungkin)
    open_match = re.search(r'````\s*\n', response)
    if open_match:
        content_start = open_match.end()
        last_close = response.rfind('\n````')
        if last_close > content_start:
            extracted = response[content_start:last_close].strip()
            if "<" in extracted:
                return extracted

    # Triple tanpa 'html' (jarang)
    open_match = re.search(r'```\s*\n', response)
    if open_match:
        content_start = open_match.end()
        last_close = response.rfind('\n```')
        if last_close > content_start:
            extracted = response[content_start:last_close].strip()
            if "<" in extracted:
                return extracted

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
    print("Warning: Tidak bisa ekstrak HTML dengan metode apapun. Returning raw response.")
    return response.strip()

# ─── Validasi & post-process ──────────────────────────────────────────────────

def validate_html(html: str, keyword: str) -> None:
    """
    Validasi minimum sebelum upload ke staging.
    Jika gagal → raise Exception → sys.exit(1) di caller.
    Konten jelek tidak pernah masuk staging.
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
    # Validasi env vars wajib
    missing = []
    if not WORKER_URL or WORKER_URL == "/":
        missing.append("WORKER_URL")
    if not BRIEF_TOKEN:
        missing.append("BRIEF_TOKEN")
    # OPENROUTER_API_KEY hanya wajib untuk article. Untuk calculator_tool,
    # MODELS construction sudah exit jika DEEPSEEK_KEY tidak tersedia.
    if TASK_TYPE != "calculator_tool" and not OPENROUTER_KEY:
        missing.append("OPENROUTER_API_KEY")
    if missing:
        print(f"FATAL: Environment variable tidak di-set: {', '.join(missing)}")
        print("       Pastikan secret sudah di-set di GitHub Actions → Settings → Secrets.")
        sys.exit(1)

    if not DEEPSEEK_KEY and TASK_TYPE != "calculator_tool":
        print("Warning: DEEPSEEK_API_KEY tidak di-set. Fallback V4 Pro tidak aktif.")

    is_article   = (TASK_TYPE == "article")
    content_type = "article" if is_article else "tool"
    type_label   = "artikel" if is_article else "tool"

    model_names = " → ".join(e["model"] for e in MODELS)
    print(f"=== auto_generate.py | task: {type_label} ===")
    print(f"    Model priority: {model_names}")

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

    # 2. Cek staging LEBIH DULU — ambil semua slug yang sudah ada
    print("2/8 Mengambil daftar staging (filter sebelum pick)...")
    staged_slugs = get_staged_slugs(is_article)
    print(f"    Slug di staging: {len(staged_slugs)} item.")

    # 3. Pilih keyword terbaik yang BELUM ada di staging
    print(f"3/8 Memilih keyword terbaik untuk {type_label}...")
    kw = pick_best_keyword(stock, is_article, exclude_slugs=staged_slugs)
    if not kw:
        print(f"SKIP: Tidak ada keyword PENDING (EASY/MEDIUM) yang belum di staging.")
        print("Semua keyword tersedia sudah ada di staging atau belum distock.")
        print("Pipeline tetap berjalan untuk publish dari staging yang ada.")
        sys.exit(0)
    slug = keyword_to_slug(kw["keyword"])
    print(
        f"    Terpilih: '{kw['keyword']}' "
        f"[{kw.get('verdict')} | score {kw.get('score')} | intent {kw.get('intent')}]"
    )
    print(f"    Slug: '{slug}' — belum di staging, lanjut generate.")

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
    print("5/8 Pass 1 — Generate draft...")
    messages_pass1 = [{"role": "user", "content": prompt}]
    try:
        response_pass1 = call_openrouter(messages_pass1, label="pass1")
    except Exception as e:
        print(f"FATAL: Gagal generate pass 1: {e}")
        sys.exit(1)

    html_draft = extract_html_from_response(response_pass1)
    print(f"    Draft: {len(html_draft.split()):,} kata.")

    # 6. Pass 2: Critique & refinement
    # Kirim full conversation: user → assistant (pass1) → user (critique)
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

    # Validasi final — konten jelek tidak masuk staging
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
        print(
            f"    Warning: Gagal daftarkan slug (non-fatal, "
            f"sync_check sebagai fallback): {e}"
        )

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
