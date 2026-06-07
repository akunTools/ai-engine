"""
social_gen.py
Generate social media posts dari artikel/tool yang baru dipublish,
lalu post ke Twitter/X via Official API v2 (OAuth 1.0a).

Pola AI call identik dengan auto_generate.py:
  Model priority: kimi-k2.6:free → deepseek-v4-flash:free → deepseek-v4-pro (jika key tersedia)

Usage: python scripts/social_gen.py <folder> <slug>
  folder : articles | tools
  slug   : slug artikel (tanpa .html, tanpa date prefix)
"""
import os
import re
import sys
import json
import hmac
import uuid
import time
import base64
import hashlib
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime

# ── Environment ───────────────────────────────────────────────────────────────
ENGINE_REPO    = os.environ.get("ENGINE_REPO", "")
GITHUB_TOKEN   = os.environ.get("GITHUB_TOKEN", "")
SITE_URL       = os.environ.get("SITE_BASE_URL", "https://saastools.corenk.com")
OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY", "")
DEEPSEEK_KEY   = os.environ.get("DEEPSEEK_API_KEY", "")

TWITTER_API_KEY             = os.environ.get("TWITTER_API_KEY", "")
TWITTER_API_SECRET          = os.environ.get("TWITTER_API_SECRET", "")
TWITTER_ACCESS_TOKEN        = os.environ.get("TWITTER_ACCESS_TOKEN", "")
TWITTER_ACCESS_TOKEN_SECRET = os.environ.get("TWITTER_ACCESS_TOKEN_SECRET", "")

OUTPUT_BRANCH = "output"
API_BASE      = "https://api.github.com"

# ── AI endpoints & model priority — identik dengan auto_generate.py ───────────
OR_URL = "https://openrouter.ai/api/v1/chat/completions"
DS_URL = "https://api.deepseek.com/v1/chat/completions"

MODELS = [
    {"model": "moonshotai/kimi-k2.6:free",      "url": OR_URL, "key": OPENROUTER_KEY},
    {"model": "deepseek/deepseek-v4-flash:free", "url": OR_URL, "key": OPENROUTER_KEY},
]
if DEEPSEEK_KEY:
    MODELS.append(
        {"model": "deepseek-v4-pro", "url": DS_URL, "key": DEEPSEEK_KEY}
    )

# ── GitHub helpers ─────────────────────────────────────────────────────────────

def _gh_headers() -> dict:
    return {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept":        "application/vnd.github.v3+json",
        "User-Agent":    "ai-engine"
    }


def fetch_article_html(folder: str, slug: str) -> str:
    """
    Fetch HTML dari output branch.
    Publisher menulis file tanpa date prefix: articles/slug.html
    """
    path = f"{folder}/{slug}.html"
    url  = f"{API_BASE}/repos/{ENGINE_REPO}/contents/{path}?ref={OUTPUT_BRANCH}"
    req  = urllib.request.Request(url, headers=_gh_headers())
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
            return base64.b64decode(data["content"]).decode("utf-8")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Gagal fetch {path}: HTTP {e.code}")


def save_social_post(slug: str, posts: dict) -> None:
    """Simpan generated posts ke social_posts/{slug}.json di output branch."""
    path    = f"social_posts/{slug}.json"
    api_url = f"{API_BASE}/repos/{ENGINE_REPO}/contents/{path}"

    sha = None
    try:
        req = urllib.request.Request(
            f"{api_url}?ref={OUTPUT_BRANCH}", headers=_gh_headers()
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            sha = json.loads(r.read()).get("sha")
    except Exception:
        pass

    payload = {
        "message": f"[social] Generated posts for {slug}",
        "content": base64.b64encode(
            json.dumps(posts, indent=2, ensure_ascii=False).encode()
        ).decode(),
        "branch": OUTPUT_BRANCH
    }
    if sha:
        payload["sha"] = sha

    req = urllib.request.Request(
        api_url,
        data=json.dumps(payload).encode(),
        headers={**_gh_headers(), "Content-Type": "application/json"},
        method="PUT"
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        print(f"Social post saved: HTTP {r.status}")


# ── Content extraction ─────────────────────────────────────────────────────────

def strip_html(html: str) -> str:
    html = re.sub(r'<script[^>]*>.*?</script>', ' ', html,
                  flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<style[^>]*>.*?</style>', ' ', html,
                  flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<[^>]+>', ' ', html)
    return re.sub(r'\s+', ' ', html).strip()


def extract_meta(html: str) -> dict:
    title_m = re.search(r'<title>([^<]+)</title>', html, re.IGNORECASE)
    desc_m  = re.search(
        r'<meta\s+name=["\']description["\']\s+content=["\'](.*?)["\']',
        html, re.IGNORECASE
    )
    title = title_m.group(1).strip() if title_m else ""
    title = re.sub(r'\s*[—\-]\s*SaaS Tools.*$', '', title).strip()
    desc  = desc_m.group(1).strip() if desc_m else ""
    return {"title": title, "description": desc}


# ── AI call — identik pola dengan auto_generate.py ────────────────────────────

def _should_fallback(code: int, body: str) -> bool:
    """
    Identik dengan auto_generate.py:
    Fallback hanya untuk error yang memang bisa diselesaikan dengan ganti model.
    """
    if code == 404 and "No endpoints found" in body:
        return True
    if code == 429 and "upstream" in body.lower():
        return True
    return False


def call_ai(messages: list, label: str = "") -> str:
    """
    Kirim messages ke AI dengan fallback antar model.
    Identik polanya dengan call_openrouter() di auto_generate.py.
    """
    tag        = f" ({label})" if label else ""
    last_error = None

    for entry in MODELS:
        model = entry["model"]
        url   = entry["url"]
        key   = entry["key"]

        if not key:
            print(f"    Skip {model}: key tidak tersedia.")
            continue

        payload = json.dumps({
            "model":      model,
            "messages":   messages,
            "max_tokens": 700,
        }).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type":  "application/json",
                "HTTP-Referer":  SITE_URL,
                "X-Title":       "SaaS Tools Content Engine",
                "User-Agent":    "ai-engine",
            },
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                data = json.loads(r.read())
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")
            if _should_fallback(e.code, body):
                reason = "No endpoints" if e.code == 404 else "upstream rate-limit"
                print(f"    Warning: {model} tidak tersedia ({reason}), coba fallback...")
                last_error = f"HTTP {e.code}{tag} [{model}]: {body[:200]}"
                continue
            raise Exception(f"AI API HTTP {e.code}{tag} [{model}]: {body[:400]}")

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
        f"Error terakhir: {last_error}"
    )


# ── Social post generation ─────────────────────────────────────────────────────

def generate_social_posts(folder: str, slug: str, html: str) -> dict:
    """Generate Twitter + LinkedIn post via AI."""
    article_url  = f"{SITE_URL}/{folder}/{slug}"
    content_type = "calculator tool" if folder == "tools" else "article"
    meta         = extract_meta(html)
    plain_text   = strip_html(html)[:3500]

    prompt = f"""You are a copywriter for SaaS metrics content.
Target audience: bootstrapped founders who are busy, data-driven, and skeptical of VC growth narratives.
Tone: peer-to-peer practitioner, not guru. Direct, no fluff.

Newly published {content_type}:
Title: {meta['title']}
Description: {meta['description']}
URL: {article_url}
Content excerpt: {plain_text}

Return ONLY valid JSON (no markdown, no backticks, no preamble):
{{
  "twitter": "Max 260 chars. ONE sharp insight or counterintuitive stat from this content. End with the URL. Not a summary — a single punchline that makes a founder stop scrolling. No hashtags.",
  "linkedin": "150-180 words. Start with one concrete data point. Explain why it matters for sub-$50K MRR founders. End with rhetorical question or short CTA + URL. No emoji.",
  "hook_type": "stat | insight | question | counterintuitive"
}}"""

    messages = [{"role": "user", "content": prompt}]
    raw      = call_ai(messages, label="social_gen")

    # Strip markdown fences kalau ada
    raw = re.sub(r'^```(?:json)?\s*', '', raw)
    raw = re.sub(r'\s*```\s*$', '',       raw).strip()

    result = json.loads(raw)
    result.update({
        "url":          article_url,
        "slug":         slug,
        "folder":       folder,
        "title":        meta["title"],
        "generated_at": datetime.utcnow().isoformat() + "Z"
    })
    return result


# ── Twitter / X OAuth 1.0a ────────────────────────────────────────────────────

def _oauth1_header(method: str, url: str) -> str:
    """
    Build OAuth 1.0a Authorization header untuk Twitter API v2.
    Pure stdlib. JSON body tidak di-include dalam signature
    (body hanya di-include untuk application/x-www-form-urlencoded).
    """
    oauth_params = {
        "oauth_consumer_key":     TWITTER_API_KEY,
        "oauth_nonce":            uuid.uuid4().hex,
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp":        str(int(time.time())),
        "oauth_token":            TWITTER_ACCESS_TOKEN,
        "oauth_version":          "1.0"
    }

    param_str = "&".join(
        f"{urllib.parse.quote(k, safe='')}={urllib.parse.quote(str(v), safe='')}"
        for k, v in sorted(oauth_params.items())
    )
    base_string = "&".join([
        method.upper(),
        urllib.parse.quote(url, safe=""),
        urllib.parse.quote(param_str, safe="")
    ])
    signing_key = (
        urllib.parse.quote(TWITTER_API_SECRET,          safe="") + "&" +
        urllib.parse.quote(TWITTER_ACCESS_TOKEN_SECRET, safe="")
    )
    signature = base64.b64encode(
        hmac.new(
            signing_key.encode("ascii"),
            base_string.encode("ascii"),
            hashlib.sha1
        ).digest()
    ).decode()

    oauth_params["oauth_signature"] = signature
    header_value = "OAuth " + ", ".join(
        f'{k}="{urllib.parse.quote(str(v), safe="")}"'
        for k, v in sorted(oauth_params.items())
    )
    return header_value


def post_to_twitter(text: str) -> dict:
    """Post tweet via Twitter API v2. Non-fatal — failure dicatat, tidak raise."""
    creds = [TWITTER_API_KEY, TWITTER_API_SECRET,
             TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_TOKEN_SECRET]
    if not all(creds):
        print("SKIP: Twitter credentials tidak lengkap.")
        return {"skipped": True, "reason": "missing_credentials"}

    url  = "https://api.twitter.com/2/tweets"
    body = json.dumps({"text": text[:280]}).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": _oauth1_header("POST", url),
            "Content-Type":  "application/json",
            "User-Agent":    "ai-engine"
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            result   = json.loads(r.read())
            tweet_id = result.get("data", {}).get("id", "unknown")
            print(f"Tweet posted: id={tweet_id}")
            return result
    except urllib.error.HTTPError as e:
        err_body = e.read().decode(errors="replace")
        raise RuntimeError(f"Twitter API error {e.code}: {err_body}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 3:
        print("Usage: python scripts/social_gen.py <folder> <slug>")
        sys.exit(1)

    folder = sys.argv[1]
    slug   = sys.argv[2]

    if folder not in ("articles", "tools"):
        print(f"ERROR: folder harus 'articles' atau 'tools', bukan '{folder}'")
        sys.exit(1)

    # Validasi env wajib
    missing = []
    if not ENGINE_REPO:  missing.append("ENGINE_REPO")
    if not GITHUB_TOKEN: missing.append("GITHUB_TOKEN")
    if not OPENROUTER_KEY: missing.append("OPENROUTER_API_KEY")
    if missing:
        print(f"FATAL: Env tidak di-set: {', '.join(missing)}")
        sys.exit(1)

    model_names = " → ".join(e["model"] for e in MODELS)
    print(f"[social_gen] {folder}/{slug}")
    print(f"    Model priority: {model_names}")

    # 1. Fetch HTML
    print("1/4 Fetch article HTML...")
    html = fetch_article_html(folder, slug)
    print(f"    Fetched: {len(html):,} chars")

    # 2. Generate posts
    print("2/4 Generate social posts via AI...")
    posts = generate_social_posts(folder, slug, html)
    hook  = posts.get("hook_type", "unknown")
    tw    = posts.get("twitter", "")
    li    = posts.get("linkedin", "")
    print(f"    hook_type: {hook}")
    print(f"    Twitter  ({len(tw)} chars): {tw[:100]}...")
    print(f"    LinkedIn ({len(li)} chars): {li[:100]}...")

    # 3. Simpan ke output branch (selalu, sebelum posting ke Twitter)
    print("3/4 Save to output branch...")
    save_social_post(slug, posts)

    # 4. Post ke Twitter (non-fatal)
    if tw:
        print("4/4 Post to Twitter/X...")
        try:
            result = post_to_twitter(tw)
            posts["twitter_posted"] = True
            posts["twitter_result"] = result
        except Exception as e:
            print(f"WARNING: Twitter posting failed: {e}")
            posts["twitter_posted"] = False
            posts["twitter_error"]  = str(e)
    else:
        print("4/4 SKIP: Twitter post kosong.")

    print(f"\n✓ Done: {folder}/{slug}")


if __name__ == "__main__":
    main()
