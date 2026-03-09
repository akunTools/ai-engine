"""
sitemap_gen.py
Generate sitemap.xml, homepage, articles index, dan tools index.
Dipanggil setelah setiap konten baru dipublish dan oleh generate-sitemap workflow.
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
    Digunakan oleh build_homepage dan build_articles_index untuk
    mengisi excerpt di artikel list.
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
# SHARED DESIGN TOKENS
# ─────────────────────────────────────────────

_FONT = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link href="https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,'
    'wght@0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700;1,9..40,400'
    '&display=swap" rel="stylesheet">'
)

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
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    padding: 0 20px;
    position: sticky;
    top: 0;
    z-index: 100;
  }
  .nav-inner {
    max-width: 720px;
    margin: 0 auto;
    height: 56px;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  .nav-brand {
    font-size: 1rem;
    font-weight: 700;
    color: var(--text);
    text-decoration: none;
    letter-spacing: -.02em;
    display: flex;
    align-items: center;
    gap: 2px;
  }
  .brand-accent { color: var(--accent); }
  .nav-links { display: flex; gap: 2px; }
  .nav-links a {
    font-size: .875rem;
    font-weight: 500;
    color: var(--muted);
    text-decoration: none;
    padding: 6px 14px;
    border-radius: 8px;
    transition: all .15s;
  }
  .nav-links a:hover { color: var(--text); background: var(--bg); }
  .nav-links a.active { color: var(--accent); background: var(--accent-light); }
"""

_FOOTER_CSS = """
  footer {
    border-top: 1px solid var(--border);
    background: var(--surface);
    padding: 32px 20px;
  }
  .footer-inner { max-width: 720px; margin: 0 auto; }
  .footer-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 20px;
  }
  .footer-brand {
    font-size: .95rem;
    font-weight: 700;
    color: var(--text);
    text-decoration: none;
    letter-spacing: -.02em;
  }
  .footer-accent { color: var(--accent); }
  .footer-nav { display: flex; gap: 24px; }
  .footer-nav a {
    font-size: .8rem;
    color: var(--muted);
    text-decoration: none;
    transition: color .15s;
  }
  .footer-nav a:hover { color: var(--accent); }
  .footer-bottom {
    font-size: .75rem;
    color: var(--subtle);
    border-top: 1px solid var(--border);
    padding-top: 16px;
  }
"""


def _nav(active: str = "") -> str:
    art_cls = ' class="active"' if active == "articles" else ""
    tool_cls = ' class="active"' if active == "tools" else ""
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
    )[:5]  # last 5 articles

    tool_files = sorted(
        [f for f in files if f["folder"] == "tools"],
        key=lambda x: x["name"]
    )[:6]  # up to 6 tools

    # Buat lookup excerpt dari content-index.json
    excerpt_map = {
        e["slug"]: e.get("excerpt", "")
        for e in content_index.get("articles", [])
    }

    # Recent articles HTML
    if article_files:
        articles_html = ""
        for f in article_files:
            slug    = file_to_slug(f["name"])
            url     = file_to_url("articles", f["name"])
            title   = slug_to_title(slug)
            excerpt = excerpt_map.get(slug, "")
            date_match = re.match(r'^(\d{4}-\d{2}-\d{2})', f["name"])
            date_str = date_match.group(1) if date_match else ""
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

    # Tools grid HTML
    if tool_files:
        tools_html = ""
        for f in tool_files:
            slug  = file_to_slug(f["name"])
            url   = file_to_url("tools", f["name"])
            title = slug_to_title(slug)
            tools_html += f"""
      <a href="{url}" class="tool-card">
        <div class="tool-icon">⚡</div>
        <div class="tool-name">{title}</div>
        <div class="tool-cta">Open calculator →</div>
      </a>"""
    else:
        tools_html = '<p class="empty-note">No tools yet — check back soon.</p>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>SaaS Tools for Bootstrapped Founders — Financial Calculators &amp; Guides</title>
  <meta name="description" content="Free financial calculators and no-fluff guides for bootstrapped SaaS founders. Runway, burn rate, break-even, LTV/CAC, and more.">
  <link rel="canonical" href="{SITE_URL}/">
  {_FONT}
  <style>
{_BASE_CSS}
{_NAV_CSS}

    /* ── HERO ── */
    .hero {{
      background: var(--surface);
      border-bottom: 1px solid var(--border);
      padding: 72px 20px 64px;
      text-align: center;
    }}
    .hero-eyebrow {{
      display: inline-block;
      background: var(--accent-light);
      color: var(--accent);
      font-size: .75rem;
      font-weight: 600;
      padding: 4px 12px;
      border-radius: 20px;
      letter-spacing: .04em;
      text-transform: uppercase;
      margin-bottom: 20px;
    }}
    .hero h1 {{
      font-size: clamp(1.75rem, 5vw, 2.75rem);
      font-weight: 700;
      line-height: 1.15;
      letter-spacing: -.03em;
      color: var(--text);
      max-width: 640px;
      margin: 0 auto 16px;
    }}
    .hero h1 em {{
      font-style: normal;
      color: var(--accent);
    }}
    .hero-sub {{
      font-size: 1.05rem;
      color: var(--muted);
      max-width: 480px;
      margin: 0 auto 32px;
      line-height: 1.6;
    }}
    .hero-actions {{
      display: flex;
      gap: 12px;
      justify-content: center;
      flex-wrap: wrap;
    }}
    .btn-primary {{
      display: inline-block;
      background: var(--accent);
      color: white;
      font-weight: 600;
      font-size: .9rem;
      padding: 11px 24px;
      border-radius: 8px;
      text-decoration: none;
      transition: background .15s;
    }}
    .btn-primary:hover {{ background: var(--accent-h); color: white; }}
    .btn-secondary {{
      display: inline-block;
      background: var(--bg);
      color: var(--text);
      font-weight: 500;
      font-size: .9rem;
      padding: 11px 24px;
      border-radius: 8px;
      border: 1px solid var(--border);
      text-decoration: none;
      transition: border-color .15s;
    }}
    .btn-secondary:hover {{ border-color: var(--accent); color: var(--accent); }}

    /* ── SECTIONS ── */
    .sections {{ max-width: 720px; margin: 0 auto; padding: 56px 20px; }}
    .section {{ margin-bottom: 56px; }}
    .section-header {{
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      margin-bottom: 20px;
      padding-bottom: 12px;
      border-bottom: 2px solid var(--border);
    }}
    .section-title {{
      font-size: 1.1rem;
      font-weight: 700;
      color: var(--text);
      letter-spacing: -.01em;
    }}
    .section-link {{
      font-size: .8rem;
      font-weight: 500;
      color: var(--accent);
    }}
    .section-link:hover {{ color: var(--accent-h); }}

    /* ── ARTICLE LIST ── */
    .article-item {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 14px 0;
      border-bottom: 1px solid var(--border);
      text-decoration: none;
      transition: all .15s;
      gap: 12px;
    }}
    .article-item:last-child {{ border-bottom: none; }}
    .article-item:hover .item-title {{ color: var(--accent); }}
    .article-item:hover .item-arrow {{ transform: translateX(4px); color: var(--accent); }}
    .item-title {{
      font-size: .95rem;
      font-weight: 500;
      color: var(--text);
      transition: color .15s;
      flex: 1;
    }}
    .item-arrow {{
      font-size: .9rem;
      color: var(--subtle);
      transition: all .15s;
      flex-shrink: 0;
    }}

    /* ── TOOLS GRID ── */
    .tools-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
      gap: 12px;
    }}
    .tool-card {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--r);
      padding: 20px;
      text-decoration: none;
      transition: all .2s;
    }}
    .tool-card:hover {{
      border-color: var(--accent);
      box-shadow: var(--shadow-md);
      transform: translateY(-2px);
    }}
    .tool-icon {{ font-size: 1.5rem; margin-bottom: 10px; }}
    .tool-name {{
      font-size: .9rem;
      font-weight: 600;
      color: var(--text);
      margin-bottom: 8px;
      line-height: 1.3;
    }}
    .tool-cta {{ font-size: .78rem; color: var(--accent); font-weight: 500; }}

    /* ── VALUE PROPS ── */
    .props {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--r);
      padding: 28px;
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 24px;
    }}
    .prop {{ text-align: center; }}
    .prop-icon {{ font-size: 1.5rem; margin-bottom: 8px; }}
    .prop-title {{
      font-size: .875rem;
      font-weight: 600;
      color: var(--text);
      margin-bottom: 4px;
    }}
    .prop-desc {{ font-size: .8rem; color: var(--muted); line-height: 1.5; }}

    .empty-note {{ font-size: .9rem; color: var(--muted); padding: 16px 0; }}

{_FOOTER_CSS}

    @media (max-width: 600px) {{
      .hero {{ padding: 48px 20px 40px; }}
      .tools-grid {{ grid-template-columns: 1fr 1fr; }}
      .props {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>

{_nav()}

<div class="hero">
  <div class="hero-eyebrow">For Bootstrapped SaaS Founders</div>
  <h1>Make better decisions with <em>real numbers</em></h1>
  <p class="hero-sub">
    Free calculators and no-fluff guides to help you manage finances,
    price your product, and reach profitability — without a CFO.
  </p>
  <div class="hero-actions">
    <a href="/tools/" class="btn-primary">Explore Calculators</a>
    <a href="/articles/" class="btn-secondary">Read Articles</a>
  </div>
</div>

<div class="sections">

  <!-- VALUE PROPS -->
  <div class="section">
    <div class="props">
      <div class="prop">
        <div class="prop-icon">🎯</div>
        <div class="prop-title">No investor fluff</div>
        <div class="prop-desc">Written for founders who fund their own growth, anywhere</div>
      </div>
      <div class="prop">
        <div class="prop-icon">⚡</div>
        <div class="prop-title">Instant results</div>
        <div class="prop-desc">Calculators work in real-time, no signup needed</div>
      </div>
      <div class="prop">
        <div class="prop-icon">🌍</div>
        <div class="prop-title">Founder-first</div>
        <div class="prop-desc">Practical benchmarks for bootstrapped SaaS founders</div>
      </div>
    </div>
  </div>

  <!-- TOOLS -->
  <div class="section">
    <div class="section-header">
      <div class="section-title">Free Calculators</div>
      <a href="/tools/" class="section-link">View all →</a>
    </div>
    <div class="tools-grid">{tools_html}
    </div>
  </div>

  <!-- ARTICLES -->
  <div class="section">
    <div class="section-header">
      <div class="section-title">Latest Articles</div>
      <a href="/articles/" class="section-link">View all →</a>
    </div>
    <div class="articles-list">{articles_html}
    </div>
  </div>

</div>

{_FOOTER}

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

    # Buat lookup excerpt dari content-index.json
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
        date_match = re.match(r'^(\d{4}-\d{2}-\d{2})', f["name"])
        date_str = date_match.group(1) if date_match else ""
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
        items_html = '\n    <div class="empty-note">No articles yet. Check back soon.</div>'

    total = len(article_files)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Articles — SaaS Tools for Bootstrapped Founders</title>
  <meta name="description" content="No-fluff guides on SaaS finances, pricing, and growth for bootstrapped founders.">
  <link rel="canonical" href="{SITE_URL}/articles/">
  {_FONT}
  <style>
{_BASE_CSS}
{_NAV_CSS}

    .page-header {{
      background: var(--surface);
      border-bottom: 1px solid var(--border);
      padding: 48px 20px 40px;
    }}
    .page-header-inner {{
      max-width: 720px;
      margin: 0 auto;
    }}
    .page-eyebrow {{
      font-size: .75rem;
      font-weight: 600;
      color: var(--accent);
      letter-spacing: .06em;
      text-transform: uppercase;
      margin-bottom: 10px;
    }}
    .page-header h1 {{
      font-size: 2rem;
      font-weight: 700;
      letter-spacing: -.03em;
      color: var(--text);
      margin-bottom: 8px;
    }}
    .page-header p {{
      font-size: .95rem;
      color: var(--muted);
      line-height: 1.6;
    }}

    .container {{ max-width: 760px; margin: 0 auto; padding: 40px 24px; }}

    .article-item {{
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 16px;
      padding: 18px 0;
      border-bottom: 1px solid var(--border);
      text-decoration: none;
      transition: all .15s;
    }}
    .article-item:last-child {{ border-bottom: none; }}
    .article-item__left {{ flex: 1; }}
    .article-item__title {{
      display: block;
      font-size: .95rem;
      font-weight: 500;
      color: var(--text);
      margin-bottom: 4px;
      line-height: 1.4;
      transition: color .15s;
    }}
    .article-item:hover .article-item__title {{ color: var(--accent); }}
    .article-item__excerpt {{
      display: block;
      font-size: .875rem;
      color: var(--muted);
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      max-width: 500px;
    }}
    .article-item__date {{
      font-size: .78rem;
      color: var(--subtle);
      white-space: nowrap;
      flex-shrink: 0;
      padding-top: 2px;
    }}
    .empty-note {{
      text-align: center;
      color: var(--muted);
      font-size: .9rem;
      padding: 48px 0;
    }}

{_FOOTER_CSS}
  </style>
</head>
<body>

{_nav("articles")}

<div class="page-header">
  <div class="page-header-inner">
    <div class="page-eyebrow">Reading List</div>
    <h1>Articles</h1>
    <p>{total} practical guides for bootstrapped SaaS founders — no fluff, no funding narratives.</p>
  </div>
</div>

<div class="container">{items_html}
</div>

{_FOOTER}

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

    # Tool descriptions by keyword match — fallback to generic
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
      <div class="tool-inner">
        <div class="tool-icon">⚡</div>
        <div>
          <div class="tool-name">{title}</div>
          <div class="tool-desc">{desc}</div>
        </div>
      </div>
      <div class="tool-arrow">→</div>
    </a>"""

    if not items_html:
        items_html = '\n    <div class="empty">No tools yet. Check back soon.</div>'

    total = len(tool_files)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Free SaaS Calculators — SaaS Tools for Bootstrapped Founders</title>
  <meta name="description" content="Free real-time SaaS calculators for bootstrapped founders. Runway, burn rate, break-even, LTV/CAC, churn rate, and MRR growth.">
  <link rel="canonical" href="{SITE_URL}/tools/">
  {_FONT}
  <style>
{_BASE_CSS}
{_NAV_CSS}

    .page-header {{
      background: var(--surface);
      border-bottom: 1px solid var(--border);
      padding: 48px 20px 40px;
    }}
    .page-header-inner {{
      max-width: 720px;
      margin: 0 auto;
    }}
    .page-eyebrow {{
      font-size: .75rem;
      font-weight: 600;
      color: var(--accent);
      letter-spacing: .06em;
      text-transform: uppercase;
      margin-bottom: 10px;
    }}
    .page-header h1 {{
      font-size: 2rem;
      font-weight: 700;
      letter-spacing: -.03em;
      color: var(--text);
      margin-bottom: 8px;
    }}
    .page-header p {{
      font-size: .95rem;
      color: var(--muted);
    }}

    .container {{ max-width: 720px; margin: 0 auto; padding: 40px 20px; }}

    .tool-card {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--r);
      padding: 20px;
      margin-bottom: 10px;
      text-decoration: none;
      transition: all .2s;
    }}
    .tool-card:hover {{
      border-color: var(--accent);
      box-shadow: var(--shadow-md);
      transform: translateX(2px);
    }}
    .tool-card:hover .tool-arrow {{
      transform: translateX(4px);
      color: var(--accent);
    }}
    .tool-inner {{ display: flex; align-items: center; gap: 14px; flex: 1; }}
    .tool-icon {{
      font-size: 1.4rem;
      width: 44px;
      height: 44px;
      background: var(--accent-light);
      border-radius: 10px;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
    }}
    .tool-name {{
      font-size: .95rem;
      font-weight: 600;
      color: var(--text);
      margin-bottom: 3px;
    }}
    .tool-desc {{ font-size: .8rem; color: var(--muted); }}
    .tool-arrow {{
      font-size: .9rem;
      color: var(--subtle);
      transition: all .2s;
      flex-shrink: 0;
    }}
    .empty {{
      text-align: center;
      color: var(--muted);
      font-size: .9rem;
      padding: 48px 0;
    }}

{_FOOTER_CSS}
  </style>
</head>
<body>

{_nav("tools")}

<div class="page-header">
  <div class="page-header-inner">
    <div class="page-eyebrow">Free Calculators</div>
    <h1>SaaS Tools</h1>
    <p>Real-time calculators for the metrics that matter. No signup. No nonsense.</p>
  </div>
</div>

<div class="container">{items_html}
</div>

{_FOOTER}

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

    Dipanggil setiap kali generate-sitemap berjalan —
    termasuk saat artikel atau tool dihapus dari branch output.
    """
    path    = "content-index.json"
    api_url = f"{API_BASE}/repos/{ENGINE_REPO}/contents/{path}"

    # Baca content-index.json yang ada
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

    # Bangun set slug aktual dari file yang ada di branch output
    active_slugs = set()
    for f in files:
        slug = f["name"].replace(".html", "").replace(".md", "")
        slug = re.sub(r'^\d{4}-\d{2}-\d{2}-', '', slug)
        active_slugs.add(slug)

    # Hapus entri yang slug-nya tidak ada di branch output
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

    # Simpan kembali hanya jika ada yang dihapus
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

    publish_file("sitemap.xml",         build_sitemap(files),                    "Sitemap")
    publish_file("index.html",          build_homepage(files, content_index),    "Homepage")
    publish_file("articles/index.html", build_articles_index(files, content_index), "Articles index")
    publish_file("tools/index.html",    build_tools_index(files),               "Tools index")
    prune_content_index(files)

    print("Done")
