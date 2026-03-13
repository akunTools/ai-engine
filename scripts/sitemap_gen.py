"""
sitemap_gen.py
Generate sitemap.xml, homepage, articles index, dan tools index.
Dipanggil setiap konten baru dipublish dan oleh generate-sitemap workflow.
"""
import os
import re
import json
import base64
import urllib.request
import urllib.error
from datetime import datetime

ENGINE_REPO   = os.environ.get("ENGINE_REPO", "akunTools/ai-engine")
ENGINE_TOKEN  = os.environ.get("GITHUB_TOKEN")
SITE_URL      = os.environ.get("SITE_BASE_URL", "https://saas.blogtrick.eu.org")
OUTPUT_BRANCH = "output"
API_BASE      = "https://api.github.com"

# ── URL affiliate — gunakan konstanta ini di semua tempat ─────────────────────
CLOUDWAYS_URL = "https://www.cloudways.com/en/?id=2085949"


def _headers():
    return {
        "Authorization": f"token {ENGINE_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "ai-engine"
    }


def get_output_files() -> list:
    """Ambil daftar semua file di branch output."""
    files = []
    for folder in ["articles", "tools"]:
        url = (
            f"{API_BASE}/repos/{ENGINE_REPO}/contents/"
            f"{folder}?ref={OUTPUT_BRANCH}"
        )
        req = urllib.request.Request(url, headers=_headers())
        try:
            with urllib.request.urlopen(req) as r:
                items = json.loads(r.read())
                for item in items:
                    name = item.get("name", "")
                    if name not in (".gitkeep", "README.md", "index.html", ""):
                        files.append({
                            "path":   item["path"],
                            "folder": folder,
                            "name":   name
                        })
        except Exception as e:
            print(f"Could not list {folder}: {e}")
    return files


def get_content_index() -> dict:
    """
    Baca content-index.json dari branch output.
    Return dict {"articles": [...], "tools": [...]}.
    Setiap entri artikel berisi: slug, title, cluster, date, excerpt.
    """
    path    = "content-index.json"
    api_url = f"{API_BASE}/repos/{ENGINE_REPO}/contents/{path}?ref={OUTPUT_BRANCH}"
    try:
        req = urllib.request.Request(api_url, headers=_headers())
        with urllib.request.urlopen(req) as r:
            data = json.loads(r.read())
            raw  = base64.b64decode(data["content"]).decode("utf-8")
            return json.loads(raw)
    except Exception:
        return {"articles": [], "tools": []}


def file_to_slug(filename: str) -> str:
    slug = filename.replace(".md", "").replace(".html", "")
    slug = re.sub(r'^\d{4}-\d{2}-\d{2}-', '', slug)
    return slug


def file_to_url(folder: str, filename: str) -> str:
    return f"{SITE_URL}/{folder}/{file_to_slug(filename)}"


def slug_to_title(slug: str) -> str:
    return slug.replace("-", " ").title()


# ─────────────────────────────────────────────
# SHARED DESIGN TOKENS — from 10.9
# ─────────────────────────────────────────────

_FONT = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link href="https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,'
    'wght@0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700;1,9..40,400'
    '&display=swap" rel="stylesheet">'
)

# ── Analytics beacon — injected ke semua halaman ──────────────────────────────
_ANALYTICS = (
    "<!-- Cloudflare Web Analytics -->"
    "<script defer src='https://static.cloudflareinsights.com/beacon.min.js'"
    " data-cf-beacon='{\"token\": \"5833f90d78f645e0819abedd665e5d93\"}'>"
    "</script>"
    "<!-- End Cloudflare Web Analytics -->"
)

# ── Affiliate click tracker — injected ke semua halaman ──────────────────────
_AFFILIATE_TRACKER_JS = """<script>
(function () {
  document.addEventListener('click', function (e) {
    var el = e.target.closest('a[href]');
    if (!el) return;
    var href = el.getAttribute('href') || '';
    if (href.indexOf('cloudways.com') === -1 || href.indexOf('id=') === -1) return;
    if (typeof window.cfBeacon === 'undefined' || typeof window.cfBeacon.pushEvent !== 'function') return;
    window.cfBeacon.pushEvent('affiliate_click', {
      affiliate: 'cloudways',
      page: window.location.pathname
    });
  }, true);
})();
</script>"""

_BASE_CSS = """
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  :root {
    --bg:           #f7f6f3;
    --surface:      #ffffff;
    --text:         #18181b;
    --muted:        #71717a;
    --subtle:       #a1a1aa;
    --border:       #e4e4e7;
    --accent:       #4f46e5;
    --accent-h:     #4338ca;
    --accent-light: #eef2ff;
    --danger:       #ef4444;
    --danger-bg:    #fef2f2;
    --warning:      #f59e0b;
    --warning-bg:   #fffbeb;
    --success:      #10b981;
    --success-bg:   #f0fdf4;
    --r:            10px;
    --shadow:       0 1px 3px rgba(0,0,0,.07), 0 1px 2px rgba(0,0,0,.04);
    --shadow-md:    0 4px 16px rgba(0,0,0,.08);
  }
  body {
    font-family: 'DM Sans', -apple-system, BlinkMacSystemFont, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.6;
    -webkit-font-smoothing: antialiased;
  }
  a { color: var(--accent); text-decoration: none; }
  a:hover { color: var(--accent-h); }
"""

_NAV_CSS = """
nav {
  position: sticky;
  top: 0;
  z-index: 100;
  background: var(--surface);
  border-bottom: 1px solid var(--border);
}

.nav-inner {
  max-width: 1120px;
  margin: 0 auto;
  padding: 0 24px;
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.nav-brand {
  font-family: 'DM Sans', sans-serif;
  font-weight: 700;
  font-size: 1.125rem;
  letter-spacing: -0.025em;
  color: var(--text);
  text-decoration: none;
  display: inline-flex;
  align-items: center;
  min-height: 44px;
  white-space: nowrap;
  flex-shrink: 0;
}

.brand-accent {
  color: var(--accent);
}

.nav-links {
  display: flex;
  align-items: center;
  gap: 2px;
}

.nav-links a {
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--muted);
  text-decoration: none;
  padding: 0 12px;
  min-height: 44px;
  display: inline-flex;
  align-items: center;
  border-radius: 6px;
  transition: color 0.15s ease, background 0.15s ease;
}

.nav-links a:hover {
  color: var(--text);
  background: var(--accent-light);
}

.nav-links a.active {
  color: var(--accent);
  background: var(--accent-light);
}

.nav-back {
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--muted);
  text-decoration: none;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 44px;
  padding: 0 6px;
  border-radius: 6px;
  transition: color 0.15s ease;
}

.nav-back:hover {
  color: var(--text);
}

@media (max-width: 640px) {
  .nav-inner {
    padding: 0 16px;
  }

  .nav-links a {
    padding: 0 8px;
    font-size: 0.8125rem;
  }
}
"""

_FOOTER_CSS = """
footer {
  background: var(--surface);
  border-top: 1px solid var(--border);
  margin-top: 80px;
}

.footer-inner {
  max-width: 1120px;
  margin: 0 auto;
  padding: 40px 24px;
}

.footer-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
}

.footer-brand {
  font-family: 'DM Sans', sans-serif;
  font-weight: 700;
  font-size: 1.0625rem;
  letter-spacing: -0.02em;
  color: var(--text);
  text-decoration: none;
  display: inline-flex;
  align-items: center;
  min-height: 44px;
  white-space: nowrap;
}

.footer-accent {
  color: var(--accent);
}

.footer-nav {
  display: flex;
  align-items: center;
  gap: 2px;
}

.footer-nav a {
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--muted);
  text-decoration: none;
  padding: 0 10px;
  min-height: 44px;
  display: inline-flex;
  align-items: center;
  border-radius: 6px;
  transition: color 0.15s ease;
}

.footer-nav a:hover {
  color: var(--text);
}

.footer-bottom {
  margin-top: 24px;
  padding-top: 24px;
  border-top: 1px solid var(--border);
  font-size: 0.8125rem;
  color: var(--subtle);
  line-height: 1.55;
}

@media (max-width: 640px) {
  footer {
    margin-top: 56px;
  }

  .footer-inner {
    padding: 32px 16px;
  }

  .footer-top {
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
  }
}
"""

_HOMEPAGE_CSS = """
.home-wrap {
  max-width: 760px;
  margin: 0 auto;
  padding: 0 24px;
}

.hero {
  padding: 72px 0 56px;
  border-bottom: 1px solid var(--border);
}

.hero__eyebrow {
  display: block;
  font-size: 0.6875rem;
  font-weight: 600;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--accent);
  margin-bottom: 14px;
}

.hero h1 {
  font-size: 2.5rem;
  font-weight: 700;
  letter-spacing: -0.035em;
  line-height: 1.15;
  color: var(--text);
  margin: 0 0 18px;
}

.hero p {
  font-size: 1.0625rem;
  color: var(--muted);
  line-height: 1.75;
  margin: 0;
  max-width: 540px;
}

.home-section {
  padding: 56px 0 0;
}

.section-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 0;
}

.section-header__meta {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.section-label {
  font-size: 0.6875rem;
  font-weight: 600;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--accent);
}

.section-title {
  font-size: 1.0625rem;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--text);
  margin: 0;
  line-height: 1.3;
}

.section-see-all {
  font-size: 0.8125rem;
  font-weight: 500;
  color: var(--accent);
  text-decoration: none;
  white-space: nowrap;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  min-height: 44px;
  padding: 0 2px;
  transition: color 0.15s ease;
}

.section-see-all:hover {
  color: var(--accent-h);
}

.article-list {
  display: flex;
  flex-direction: column;
  margin-top: 24px;
  border-top: 1px solid var(--border);
}

.article-item {
  display: flex;
  flex-direction: row;
  align-items: flex-start;
  gap: 24px;
  padding: 18px 0;
  border-bottom: 1px solid var(--border);
  text-decoration: none;
  color: inherit;
  min-height: 44px;
}

.article-item:hover .article-item__title {
  color: var(--accent);
}

.article-item__left {
  display: flex;
  flex-direction: column;
  gap: 5px;
  flex: 1;
  min-width: 0;
}

.article-item__title {
  font-size: 0.9375rem;
  font-weight: 500;
  color: var(--text);
  line-height: 1.45;
  transition: color 0.12s ease;
}

.article-item__excerpt {
  font-size: 0.875rem;
  color: var(--muted);
  line-height: 1.5;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.article-item__date {
  font-size: 0.8125rem;
  color: var(--subtle);
  white-space: nowrap;
  flex-shrink: 0;
  padding-top: 2px;
  font-variant-numeric: tabular-nums;
}

.tools-grid {
  display: grid;
  gap: 16px;
  grid-template-columns: 1fr;
  margin-top: 24px;
}

.tool-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 20px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--r);
  text-decoration: none;
  color: inherit;
  box-shadow: var(--shadow);
  min-height: 44px;
  transition: box-shadow 0.15s ease, border-color 0.15s ease, transform 0.12s ease;
}

.tool-card:hover {
  box-shadow: var(--shadow-md);
  border-color: var(--accent);
  transform: translateY(-1px);
}

.tool-card__icon {
  font-size: 1.5rem;
  line-height: 1;
}

.tool-card__name {
  font-size: 0.9375rem;
  font-weight: 600;
  color: var(--text);
  letter-spacing: -0.01em;
  line-height: 1.3;
}

.tool-card__desc {
  font-size: 0.8125rem;
  color: var(--muted);
  line-height: 1.6;
}

.hosting-nudge {
  margin-top: 56px;
  padding: 24px;
  background: var(--accent-light);
  border: 1px solid var(--border);
  border-radius: var(--r);
  display: flex;
  align-items: center;
  gap: 20px;
}

.hosting-nudge__text {
  flex: 1;
  font-size: 0.9375rem;
  color: var(--text);
  line-height: 1.65;
  min-width: 0;
}

.hosting-nudge__text strong {
  color: var(--accent);
  font-weight: 600;
}

.hosting-nudge__link {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--surface);
  background: var(--accent);
  text-decoration: none;
  padding: 0 18px;
  min-height: 44px;
  display: inline-flex;
  align-items: center;
  border-radius: 6px;
  white-space: nowrap;
  flex-shrink: 0;
  transition: background 0.15s ease;
}

.hosting-nudge__link:hover {
  background: var(--accent-h);
}

.empty-note {
  font-size: 0.9rem;
  color: var(--muted);
  padding: 24px 0;
}

@media (max-width: 640px) {
  .home-wrap {
    padding: 0 16px;
  }

  .hero {
    padding: 48px 0 40px;
  }

  .hero h1 {
    font-size: 1.875rem;
  }

  .hero p {
    font-size: 1rem;
  }

  .home-section {
    padding: 40px 0 0;
  }

  .article-item {
    flex-direction: column;
    gap: 4px;
  }

  .article-item__date {
    font-size: 0.75rem;
    padding-top: 0;
    width: 100%;
  }

  .hosting-nudge {
    flex-direction: column;
    align-items: flex-start;
    gap: 14px;
  }

  .hosting-nudge__link {
    width: 100%;
    justify-content: center;
  }
}

@media (min-width: 600px) and (max-width: 899px) {
  .tools-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (min-width: 900px) {
  .tools-grid {
    grid-template-columns: repeat(3, 1fr);
  }
}
"""

_INDEX_CSS = """
.index-wrap {
  max-width: 760px;
  margin: 0 auto;
  padding: 0 24px;
}

.index-header {
  padding: 56px 0 40px;
  border-bottom: 1px solid var(--border);
}

.index-label {
  display: block;
  font-size: 0.6875rem;
  font-weight: 600;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--accent);
  margin-bottom: 12px;
}

.index-title {
  font-size: 2rem;
  font-weight: 700;
  letter-spacing: -0.03em;
  color: var(--text);
  line-height: 1.2;
  margin: 0 0 12px;
}

.index-desc {
  font-size: 1rem;
  color: var(--muted);
  line-height: 1.75;
  margin: 0;
  max-width: 520px;
}

.index-content {
  padding: 32px 0 0;
}

.index-content .article-list {
  margin-top: 0;
}

.index-content .tools-grid {
  margin-top: 0;
}

@media (max-width: 640px) {
  .index-wrap {
    padding: 0 16px;
  }

  .index-header {
    padding: 40px 0 32px;
  }

  .index-title {
    font-size: 1.625rem;
  }

  .index-content {
    padding: 24px 0 0;
  }
}

@media (min-width: 641px) and (max-width: 1024px) {
  .index-wrap {
    padding: 0 24px;
  }

  .index-title {
    font-size: 1.75rem;
  }
}
"""


def _nav(active: str = "") -> str:
    art_cls  = ' class="active"' if active == "articles" else ""
    tool_cls = ' class="active"' if active == "tools"    else ""
    return f"""<nav>
  <div class="nav-inner">
    <a href="/" class="nav-brand">
      SaaS<span class="brand-accent">Tools</span>
    </a>
    <div class="nav-links">
      <a href="/articles/"{art_cls}>Articles</a>
      <a href="/tools/"{tool_cls}>Tools</a>
    </div>
  </div>
</nav>"""


_FOOTER = """<footer>
  <div class="footer-inner">
    <div class="footer-top">
      <a href="/" class="footer-brand">SaaS<span class="footer-accent">Tools</span></a>
      <nav class="footer-nav">
        <a href="/articles/">Articles</a>
        <a href="/tools/">Tools</a>
      </nav>
    </div>
    <div class="footer-bottom">
      Free calculators and guides for bootstrapped founders.
    </div>
  </div>
</footer>"""


# ─────────────────────────────────────────────
# SITEMAP
# ─────────────────────────────────────────────

def build_sitemap(files: list) -> str:
    today = datetime.utcnow().strftime("%Y-%m-%d")
    url_entries = [f"""  <url>
    <loc>{SITE_URL}/</loc>
    <lastmod>{today}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>1.0</priority>
  </url>"""]
    for f in files:
        loc      = file_to_url(f["folder"], f["name"])
        priority = "0.8" if f["folder"] == "tools" else "0.6"
        url_entries.append(f"""  <url>
    <loc>{loc}</loc>
    <lastmod>{today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>{priority}</priority>
  </url>""")
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(url_entries)
        + "\n</urlset>"
    )


# ─────────────────────────────────────────────
# HOMEPAGE
# ─────────────────────────────────────────────

def build_homepage(files: list, content_index: dict) -> str:
    """Build homepage index.html."""
    article_files = sorted(
        [f for f in files if f["folder"] == "articles"],
        key=lambda x: x["name"], reverse=True
    )[:5]

    tool_files = sorted(
        [f for f in files if f["folder"] == "tools"],
        key=lambda x: x["name"]
    )[:6]

    excerpt_map = {
        e["slug"]: e.get("excerpt", "")
        for e in content_index.get("articles", [])
    }

    if article_files:
        articles_html = ""
        for f in article_files:
            slug    = file_to_slug(f["name"])
            url     = file_to_url("articles", f["name"])
            title   = slug_to_title(slug)
            excerpt = excerpt_map.get(slug, "")
            date_match = re.match(r'^\d{4}-\d{2}-\d{2}', f["name"])
            date_str = date_match.group(0) if date_match else ""
            try:
                from datetime import datetime as _dt
                display_date = _dt.strptime(date_str, "%Y-%m-%d").strftime("%b %-d, %Y") if date_str else ""
            except Exception:
                display_date = date_str
            excerpt_html = f'<span class="article-item__excerpt">{excerpt}</span>' if excerpt else ""
            date_html    = f'<span class="article-item__date">{display_date}</span>' if display_date else ""
            articles_html += f"""
        <a href="{url}" class="article-item">
          <div class="article-item__left">
            <span class="article-item__title">{title}</span>
            {excerpt_html}
          </div>
          {date_html}
        </a>"""
    else:
        articles_html = '<p class="empty-note">No articles yet — check back soon.</p>'

    if tool_files:
        tools_html = ""
        for f in tool_files:
            slug  = file_to_slug(f["name"])
            url   = file_to_url("tools", f["name"])
            title = slug_to_title(slug)
            tools_html += f"""
        <a href="{url}" class="tool-card">
          <div class="tool-card__icon">⚡</div>
          <div class="tool-card__name">{title}</div>
        </a>"""
    else:
        tools_html = '<p class="empty-note">No tools yet — check back soon.</p>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>SaaSTools — Calculators &amp; Guides for Bootstrapped Founders</title>
  <meta name="description" content="Free financial calculators and practical guides for bootstrapped SaaS founders. No fluff, no VC narratives.">
  <link rel="canonical" href="{SITE_URL}/">
  {_FONT}
  <style>
{_BASE_CSS}
{_NAV_CSS}
{_FOOTER_CSS}
{_HOMEPAGE_CSS}
  </style>
  {_ANALYTICS}
</head>
<body>
  {_nav()}

  <div class="home-wrap">

    <section class="hero">
      <span class="hero__eyebrow">Free Tools &amp; Guides</span>
      <h1>Build a profitable SaaS —&thinsp;without the guesswork</h1>
      <p>Financial calculators and practical guides for bootstrapped founders who prefer numbers over narratives.</p>
    </section>

    <section class="home-section">
      <div class="section-header">
        <div class="section-header__meta">
          <span class="section-label">Calculators</span>
          <h2 class="section-title">Tools</h2>
        </div>
        <a href="/tools/" class="section-see-all">See all →</a>
      </div>
      <div class="tools-grid">
        {tools_html}
      </div>
    </section>

    <section class="home-section">
      <div class="section-header">
        <div class="section-header__meta">
          <span class="section-label">Latest Writing</span>
          <h2 class="section-title">Articles</h2>
        </div>
        <a href="/articles/" class="section-see-all">See all →</a>
      </div>
      <div class="article-list">
        {articles_html}
      </div>
    </section>

    <aside class="hosting-nudge">
      <p class="hosting-nudge__text">
        <strong>Still on shared hosting?</strong> Cloudways gives you managed cloud servers with one-click scaling and zero DevOps overhead — so you can stay focused on MRR, not sysadmin tickets.
      </p>
      <a
        href="{CLOUDWAYS_URL}"
        class="hosting-nudge__link"
        rel="sponsored noopener"
        target="_blank"
      >Try Cloudways →</a>
    </aside>

  </div>

  {_FOOTER}
  {_AFFILIATE_TRACKER_JS}
</body>
</html>"""


# ─────────────────────────────────────────────
# ARTICLES INDEX
# ─────────────────────────────────────────────

def build_articles_index(files: list, content_index: dict) -> str:
    """Build articles/index.html."""
    article_files = sorted(
        [f for f in files if f["folder"] == "articles"],
        key=lambda x: x["name"], reverse=True
    )

    excerpt_map = {
        e["slug"]: e.get("excerpt", "")
        for e in content_index.get("articles", [])
    }

    items_html = ""
    for f in article_files:
        slug    = file_to_slug(f["name"])
        url     = file_to_url("articles", f["name"])
        title   = slug_to_title(slug)
        excerpt = excerpt_map.get(slug, "")
        date_match = re.match(r'^\d{4}-\d{2}-\d{2}', f["name"])
        date_str = date_match.group(0) if date_match else ""
        try:
            from datetime import datetime as _dt
            display_date = _dt.strptime(date_str, "%Y-%m-%d").strftime("%b %-d, %Y") if date_str else ""
        except Exception:
            display_date = date_str
        excerpt_html = f'<span class="article-item__excerpt">{excerpt}</span>' if excerpt else ""
        date_html    = f'<span class="article-item__date">{display_date}</span>' if display_date else ""

        items_html += f"""
      <a href="{url}" class="article-item">
        <div class="article-item__left">
          <span class="article-item__title">{title}</span>
          {excerpt_html}
        </div>
        {date_html}
      </a>"""

    if not items_html:
        items_html = '\n      <p class="empty-note">No articles yet — check back soon.</p>'

    total = len(article_files)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Articles — SaaSTools</title>
  <meta name="description" content="Practical guides and financial breakdowns for bootstrapped SaaS founders. Written for operators, not investors.">
  <link rel="canonical" href="{SITE_URL}/articles/">
  {_FONT}
  <style>
{_BASE_CSS}
{_NAV_CSS}
{_FOOTER_CSS}
{_HOMEPAGE_CSS}
{_INDEX_CSS}
  </style>
  {_ANALYTICS}
</head>
<body>
  {_nav("articles")}

  <div class="index-wrap">

    <header class="index-header">
      <span class="index-label">Writing</span>
      <h1 class="index-title">Articles</h1>
      <p class="index-desc">{total} practical guides for bootstrapped SaaS founders — no fluff, no funding narratives.</p>
    </header>

    <div class="index-content">
      <div class="article-list">
        {items_html}
      </div>
    </div>

  </div>

  {_FOOTER}
  {_AFFILIATE_TRACKER_JS}
</body>
</html>"""


# ─────────────────────────────────────────────
# TOOLS INDEX
# ─────────────────────────────────────────────

def build_tools_index(files: list) -> str:
    """Build tools/index.html."""
    tool_files = sorted(
        [f for f in files if f["folder"] == "tools"],
        key=lambda x: x["name"]
    )

    _DESCRIPTIONS = {
        "runway":     "How many months before cash runs out?",
        "burn":       "What is your real monthly cash burn?",
        "break-even": "How many customers to cover all fixed costs?",
        "ltv":        "Is your LTV:CAC ratio healthy?",
        "cac":        "Is your LTV:CAC ratio healthy?",
        "churn":      "What percentage of customers are you losing?",
        "mrr":        "How fast is your MRR actually growing?",
        "pricing":    "Is your pricing model financially sound?",
    }

    def _get_desc(slug: str) -> str:
        slug_lower = slug.lower()
        for kw, desc in _DESCRIPTIONS.items():
            if kw in slug_lower:
                return desc
        return "Calculate and understand your SaaS metrics."

    items_html = ""
    for f in tool_files:
        slug  = file_to_slug(f["name"])
        url   = file_to_url("tools", f["name"])
        title = slug_to_title(slug)
        desc  = _get_desc(slug)
        items_html += f"""
      <a href="{url}" class="tool-card">
        <div class="tool-card__icon">⚡</div>
        <div class="tool-card__name">{title}</div>
        <div class="tool-card__desc">{desc}</div>
      </a>"""

    if not items_html:
        items_html = '\n      <p class="empty-note">No tools yet — check back soon.</p>'

    total = len(tool_files)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Calculators &amp; Tools — SaaSTools</title>
  <meta name="description" content="Free SaaS financial calculators: MRR, churn, runway, LTV/CAC, pricing and more. Built for bootstrapped founders.">
  <link rel="canonical" href="{SITE_URL}/tools/">
  {_FONT}
  <style>
{_BASE_CSS}
{_NAV_CSS}
{_FOOTER_CSS}
{_HOMEPAGE_CSS}
{_INDEX_CSS}
  </style>
  {_ANALYTICS}
</head>
<body>
  {_nav("tools")}

  <div class="index-wrap">

    <header class="index-header">
      <span class="index-label">Calculators</span>
      <h1 class="index-title">Tools</h1>
      <p class="index-desc">{total} free calculators for the SaaS metrics that actually drive decisions.</p>
    </header>

    <div class="index-content">
      <div class="tools-grid">
        {items_html}
      </div>
    </div>

  </div>

  {_FOOTER}
  {_AFFILIATE_TRACKER_JS}
</body>
</html>"""


# ─────────────────────────────────────────────
# PUBLISH HELPER
# ─────────────────────────────────────────────

def publish_file(path: str, content: str, label: str):
    """Publish satu file ke branch output."""
    url = f"{API_BASE}/repos/{ENGINE_REPO}/contents/{path}"
    sha = None
    try:
        req = urllib.request.Request(
            f"{url}?ref={OUTPUT_BRANCH}", headers=_headers()
        )
        with urllib.request.urlopen(req) as r:
            sha = json.loads(r.read()).get("sha")
    except Exception:
        pass

    payload = {
        "message": f"[sitemap] {label} {datetime.utcnow().strftime('%Y-%m-%d')}",
        "content": base64.b64encode(content.encode("utf-8")).decode("utf-8"),
        "branch":  OUTPUT_BRANCH
    }
    if sha:
        payload["sha"] = sha

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={**_headers(), "Content-Type": "application/json"},
        method="PUT"
    )
    with urllib.request.urlopen(req) as r:
        print(f"{label} published: HTTP {r.status}")


# ─────────────────────────────────────────────
# CONTENT INDEX PRUNING
# ─────────────────────────────────────────────

def prune_content_index(files: list) -> None:
    """
    Hapus entri dari content-index.json yang file-nya
    sudah tidak ada di branch output.
    """
    path    = "content-index.json"
    api_url = f"{API_BASE}/repos/{ENGINE_REPO}/contents/{path}"

    sha   = None
    index = {"articles": [], "tools": []}
    try:
        req = urllib.request.Request(
            f"{api_url}?ref={OUTPUT_BRANCH}", headers=_headers()
        )
        with urllib.request.urlopen(req) as r:
            data  = json.loads(r.read())
            sha   = data.get("sha")
            raw   = base64.b64decode(data["content"]).decode("utf-8")
            index = json.loads(raw)
    except Exception:
        print("content-index.json not found — skip pruning")
        return

    active_slugs = set()
    for f in files:
        slug = f["name"].replace(".html", "").replace(".md", "")
        slug = re.sub(r'^\d{4}-\d{2}-\d{2}-', '', slug)
        active_slugs.add(slug)

    before_articles = len(index.get("articles", []))
    before_tools    = len(index.get("tools", []))

    index["articles"] = [
        e for e in index.get("articles", [])
        if e["slug"] in active_slugs
    ]
    index["tools"] = [
        e for e in index.get("tools", [])
        if e["slug"] in active_slugs
    ]

    removed = (before_articles + before_tools) - \
              (len(index["articles"]) + len(index["tools"]))

    if removed == 0:
        print("content-index.json: no stale entries found")
        return

    payload = {
        "message": f"[sitemap] Prune {removed} stale entries from content-index",
        "content": base64.b64encode(
            json.dumps(index, indent=2).encode("utf-8")
        ).decode("utf-8"),
        "branch":  OUTPUT_BRANCH,
        "sha":     sha
    }
    req = urllib.request.Request(
        api_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={**_headers(), "Content-Type": "application/json"},
        method="PUT"
    )
    try:
        with urllib.request.urlopen(req) as r:
            print(f"content-index.json pruned: {removed} entries removed "
                  f"(HTTP {r.status})")
    except Exception as e:
        print(f"Warning: Could not prune content-index.json: {e}")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("Generating sitemap and index pages...")
    files = get_output_files()
    print(f"Found {len(files)} content files in output branch")

    content_index = get_content_index()
    print(f"Content index: {len(content_index.get('articles', []))} articles, "
          f"{len(content_index.get('tools', []))} tools")

    publish_file("sitemap.xml",         build_sitemap(files),                        "Sitemap")
    publish_file("index.html",          build_homepage(files, content_index),        "Homepage")
    publish_file("articles/index.html", build_articles_index(files, content_index),  "Articles index")
    publish_file("tools/index.html",    build_tools_index(files),                    "Tools index")
    prune_content_index(files)

    print("Done")

