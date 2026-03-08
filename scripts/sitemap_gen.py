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


def file_to_slug(filename: str) -> str:
    slug = filename.replace(".md", "").replace(".html", "")
    slug = re.sub(r'^\d{4}-\d{2}-\d{2}-', '', slug)
    return slug


def file_to_url(folder: str, filename: str) -> str:
    return f"{SITE_URL}/{folder}/{file_to_slug(filename)}"


def slug_to_title(slug: str) -> str:
    return slug.replace("-", " ").title()


# ─────────────────────────────────────────────
# MODULE-LEVEL HELPERS (dipakai oleh beberapa builder)
# ─────────────────────────────────────────────

_TOOL_DESCRIPTIONS = {
    "runway":     "How many months before cash runs out?",
    "burn":       "What is your real monthly cash burn?",
    "break-even": "How many customers to cover all fixed costs?",
    "ltv":        "Is your LTV:CAC ratio healthy?",
    "cac":        "Is your LTV:CAC ratio healthy?",
    "churn":      "What percentage of customers are you losing?",
    "mrr":        "How fast is your MRR actually growing?",
    "pricing":    "Is your pricing model financially sound?",
}


def _get_tool_desc(slug: str) -> str:
    slug_lower = slug.lower()
    for kw, desc in _TOOL_DESCRIPTIONS.items():
        if kw in slug_lower:
            return desc
    return "Calculate and understand your SaaS metrics."


def _parse_display_date(filename: str) -> str:
    """
    Extract dan format tanggal dari filename seperti 2026-03-07-slug.html.
    Return string kosong jika tidak ada tanggal.
    Linux: strftime('%-d') → '7'. Windows: ganti ke '%#d'.
    """
    date_match = re.match(r'^(\d{4}-\d{2}-\d{2})', filename)
    if not date_match:
        return ""
    date_str = date_match.group(1)
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").strftime("%b %-d, %Y")
    except Exception:
        return date_str


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

# ── Updated: 10.9 design session ──────────────────────────────────────────────
_NAV_CSS = """
  nav {
    position: sticky;
    top: 0;
    z-index: 100;
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    box-shadow: var(--shadow);
  }

  .nav-inner {
    max-width: 1120px;
    margin: 0 auto;
    padding: 0 24px;
    height: 56px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 24px;
  }

  .nav-brand {
    font-size: 1.125rem;
    font-weight: 700;
    color: var(--text);
    text-decoration: none;
    letter-spacing: -0.02em;
    flex-shrink: 0;
    line-height: 56px;
  }

  .nav-brand:hover {
    color: var(--text);
  }

  .brand-accent {
    color: var(--accent);
  }

  .nav-links {
    display: flex;
    align-items: center;
    gap: 4px;
  }

  .nav-links a {
    font-size: 0.9rem;
    font-weight: 500;
    color: var(--muted);
    text-decoration: none;
    padding: 6px 12px;
    border-radius: 6px;
    transition: color 0.15s, background 0.15s;
    min-height: 44px;
    display: flex;
    align-items: center;
  }

  .nav-links a:hover {
    color: var(--text);
    background: var(--bg);
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
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 6px 0;
    min-height: 44px;
    transition: color 0.15s;
  }

  .nav-back:hover {
    color: var(--accent);
  }

  @media (max-width: 640px) {
    .nav-inner {
      padding: 0 16px;
    }

    .nav-links a {
      padding: 6px 8px;
    }
  }
"""

# ── Updated: 10.9 design session ──────────────────────────────────────────────
_FOOTER_CSS = """
  footer {
    background: var(--surface);
    border-top: 1px solid var(--border);
    margin-top: 80px;
  }

  .footer-inner {
    max-width: 1120px;
    margin: 0 auto;
    padding: 0 24px;
  }

  .footer-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 24px;
    padding: 28px 0 20px;
  }

  .footer-brand {
    font-size: 1rem;
    font-weight: 700;
    color: var(--text);
    text-decoration: none;
    letter-spacing: -0.02em;
  }

  .footer-brand:hover {
    color: var(--text);
  }

  .footer-accent {
    color: var(--accent);
  }

  .footer-nav {
    display: flex;
    align-items: center;
    gap: 4px;
  }

  .footer-nav a {
    font-size: 0.875rem;
    font-weight: 500;
    color: var(--muted);
    text-decoration: none;
    padding: 6px 10px;
    border-radius: 6px;
    min-height: 44px;
    display: flex;
    align-items: center;
    transition: color 0.15s;
  }

  .footer-nav a:hover {
    color: var(--accent);
  }

  .footer-bottom {
    border-top: 1px solid var(--border);
    padding: 16px 0 24px;
    font-size: 0.8125rem;
    color: var(--subtle);
    line-height: 1.5;
  }

  @media (max-width: 640px) {
    .footer-inner {
      padding: 0 16px;
    }

    .footer-top {
      flex-direction: column;
      align-items: flex-start;
      gap: 12px;
      padding: 24px 0 16px;
    }

    .footer-nav {
      gap: 0;
    }

    .footer-nav a {
      padding: 6px 8px;
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

def build_homepage(files: list) -> str:
    """Build homepage index.html."""
    article_files = sorted(
        [f for f in files if f["folder"] == "articles"],
        key=lambda x: x["name"], reverse=True
    )[:5]

    tool_files = sorted(
        [f for f in files if f["folder"] == "tools"],
        key=lambda x: x["name"]
    )[:6]

    # ── Article list HTML ──
    # CSS contract: <a class="article-item">
    #   <div class="article-item__left">
    #     <span class="article-item__title">...</span>
    #   </div>
    #   <span class="article-item__date">...</span>
    # </a>
    if article_files:
        articles_html = ""
        for f in article_files:
            slug         = file_to_slug(f["name"])
            url          = file_to_url("articles", f["name"])
            title        = slug_to_title(slug)
            display_date = _parse_display_date(f["name"])
            date_span    = (
                f'<span class="article-item__date">{display_date}</span>'
                if display_date else ""
            )
            articles_html += f"""
        <a href="{url}" class="article-item">
          <div class="article-item__left">
            <span class="article-item__title">{title}</span>
          </div>
          {date_span}
        </a>"""
    else:
        articles_html = (
            '<p class="empty-note">No articles yet — check back soon.</p>'
        )

    # ── Tools grid HTML ──
    # CSS contract: <a class="tool-card">
    #   <div class="tool-card__icon">...</div>
    #   <div class="tool-card__name">...</div>
    #   <div class="tool-card__desc">...</div>
    # </a>
    if tool_files:
        tools_html = ""
        for f in tool_files:
            slug       = file_to_slug(f["name"])
            url        = file_to_url("tools", f["name"])
            title      = slug_to_title(slug)
            desc       = _get_tool_desc(slug)
            tools_html += f"""
        <a href="{url}" class="tool-card">
          <div class="tool-card__icon">⚡</div>
          <div class="tool-card__name">{title}</div>
          <div class="tool-card__desc">{desc}</div>
        </a>"""
    else:
        tools_html = (
            '<p class="empty-note">No tools yet — check back soon.</p>'
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>SaaS Financial Tools &amp; Honest Guides — blogtrick</title>
  <meta name="description" content="Free financial calculators and no-fluff guides for bootstrapped SaaS founders. MRR, churn, runway — calculated clearly.">
  <link rel="canonical" href="{SITE_URL}/">
  {_FONT}
  <style>
{_BASE_CSS}
{_NAV_CSS}

    /* ── Layout ─────────────────────────────────────── */
    .page-wrap {{
      max-width: 720px;
      margin: 0 auto;
      padding: 0 1.25rem;
    }}

    /* ── Hero ───────────────────────────────────────── */
    .hero {{
      padding: 4rem 0 3rem;
      border-bottom: 1px solid var(--border);
    }}

    .hero__eyebrow {{
      display: inline-flex;
      align-items: center;
      gap: 0.375rem;
      font-size: 0.6875rem;
      font-weight: 700;
      letter-spacing: 0.1em;
      text-transform: uppercase;
      color: var(--accent);
      background: var(--accent-light);
      padding: 0.25rem 0.625rem;
      border-radius: 4px;
      margin-bottom: 1.25rem;
    }}

    .hero__title {{
      font-size: clamp(1.75rem, 5vw, 2.5rem);
      font-weight: 700;
      line-height: 1.18;
      letter-spacing: -0.025em;
      color: var(--text);
      margin-bottom: 1rem;
      max-width: 580px;
    }}

    .hero__desc {{
      font-size: 1.0625rem;
      color: var(--muted);
      line-height: 1.75;
      max-width: 520px;
      margin-bottom: 1.875rem;
    }}

    .hero__actions {{
      display: flex;
      gap: 0.75rem;
      flex-wrap: wrap;
    }}

    /* ── Buttons ────────────────────────────────────── */
    .btn {{
      display: inline-flex;
      align-items: center;
      gap: 0.375rem;
      padding: 0.6875rem 1.125rem;
      border-radius: var(--r);
      font-family: inherit;
      font-size: 0.9375rem;
      font-weight: 500;
      cursor: pointer;
      text-decoration: none;
      transition: background 0.13s ease, border-color 0.13s ease, color 0.13s ease;
      min-height: 44px;
      border: 1px solid transparent;
      line-height: 1;
    }}

    .btn--primary {{
      background: var(--accent);
      color: #fff;
      border-color: var(--accent);
    }}

    .btn--primary:hover {{
      background: var(--accent-h);
      border-color: var(--accent-h);
      color: #fff;
    }}

    .btn--ghost {{
      background: var(--surface);
      color: var(--text);
      border-color: var(--border);
      box-shadow: var(--shadow);
    }}

    .btn--ghost:hover {{
      border-color: var(--accent);
      color: var(--accent);
    }}

    /* ── Sections ───────────────────────────────────── */
    .section {{
      padding: 2.75rem 0;
    }}

    .section + .section {{
      border-top: 1px solid var(--border);
    }}

    .section__header {{
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      margin-bottom: 1.375rem;
      gap: 1rem;
    }}

    .section__title {{
      font-size: 0.8125rem;
      font-weight: 700;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: var(--subtle);
    }}

    .section__link {{
      font-size: 0.875rem;
      color: var(--accent);
      text-decoration: none;
      font-weight: 500;
      white-space: nowrap;
      flex-shrink: 0;
    }}

    .section__link:hover {{
      color: var(--accent-h);
      text-decoration: underline;
      text-underline-offset: 3px;
    }}

    /* ── Article List ───────────────────────────────── */
    .article-list {{
      display: flex;
      flex-direction: column;
    }}

    .article-list .article-item {{
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: 1rem;
      padding: 0.9375rem 0;
      border-bottom: 1px solid var(--border);
      text-decoration: none;
      color: inherit;
      position: relative;
      transition: padding-left 0.18s ease;
    }}

    .article-list .article-item::before {{
      content: '';
      position: absolute;
      left: -0.875rem;
      top: 50%;
      transform: translateY(-50%);
      width: 3px;
      height: 0;
      background: var(--accent);
      border-radius: 2px;
      transition: height 0.18s ease;
    }}

    .article-list .article-item:last-child {{
      border-bottom: none;
    }}

    .article-item__left {{
      min-width: 0;
      flex: 1;
    }}

    .article-item__title {{
      display: block;
      font-size: 0.9375rem;
      font-weight: 500;
      color: var(--text);
      margin-bottom: 0.1875rem;
      line-height: 1.4;
      transition: color 0.13s ease;
    }}

    .article-item__desc {{
      display: block;
      font-size: 0.8125rem;
      color: var(--subtle);
      line-height: 1.4;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }}

    .article-item__date {{
      font-size: 0.8125rem;
      color: var(--subtle);
      white-space: nowrap;
      flex-shrink: 0;
    }}

    @media (hover: hover) {{
      .article-list .article-item:hover {{
        padding-left: 0.5625rem;
      }}

      .article-list .article-item:hover::before {{
        height: 55%;
      }}

      .article-list .article-item:hover .article-item__title {{
        color: var(--accent);
      }}
    }}

    /* ── Tools Grid ─────────────────────────────────── */
    .tools-grid {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 0.75rem;
    }}

    .tool-card {{
      display: block;
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--r);
      padding: 1.125rem;
      text-decoration: none;
      color: inherit;
      box-shadow: var(--shadow);
      transition: box-shadow 0.15s ease, border-color 0.15s ease, transform 0.15s ease;
    }}

    .tool-card:hover {{
      box-shadow: var(--shadow-md);
      border-color: var(--accent);
      transform: translateY(-2px);
    }}

    .tool-card__icon {{
      width: 34px;
      height: 34px;
      background: var(--accent-light);
      border-radius: 8px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 1rem;
      margin-bottom: 0.8125rem;
      flex-shrink: 0;
    }}

    .tool-card__name {{
      font-size: 0.9375rem;
      font-weight: 600;
      color: var(--text);
      margin-bottom: 0.3125rem;
      line-height: 1.3;
      transition: color 0.13s ease;
    }}

    .tool-card:hover .tool-card__name {{
      color: var(--accent);
    }}

    .tool-card__desc {{
      font-size: 0.8125rem;
      color: var(--muted);
      line-height: 1.55;
    }}

    /* ── Hosting nudge ──────────────────────────────── */
    .hosting-nudge {{
      margin-top: 2.75rem;
      padding: 1.25rem 1.375rem;
      background: var(--success-bg);
      border: 1px solid var(--border);
      border-radius: var(--r);
      display: flex;
      align-items: flex-start;
      gap: 0.875rem;
    }}

    .hosting-nudge__dot {{
      width: 8px;
      height: 8px;
      background: var(--success);
      border-radius: 50%;
      flex-shrink: 0;
      margin-top: 0.4rem;
    }}

    .hosting-nudge__body {{
      flex: 1;
    }}

    .hosting-nudge__label {{
      font-size: 0.75rem;
      font-weight: 700;
      letter-spacing: 0.07em;
      text-transform: uppercase;
      color: var(--success);
      margin-bottom: 0.3125rem;
    }}

    .hosting-nudge__text {{
      font-size: 0.9rem;
      color: var(--text);
      line-height: 1.55;
    }}

    .hosting-nudge__text a {{
      color: var(--accent);
      font-weight: 500;
      text-decoration: underline;
      text-underline-offset: 3px;
    }}

    .hosting-nudge__text a:hover {{
      color: var(--accent-h);
    }}

    .empty-note {{
      font-size: 0.9rem;
      color: var(--muted);
      padding: 1rem 0;
    }}

{_FOOTER_CSS}

    /* ── Responsive ─────────────────────────────────── */
    @media (max-width: 600px) {{
      .hero {{
        padding: 2.5rem 0 2rem;
      }}

      .tools-grid {{
        grid-template-columns: 1fr;
      }}

      .section {{
        padding: 2rem 0;
      }}

      .article-item__desc {{
        white-space: normal;
        overflow: visible;
        text-overflow: unset;
      }}

      .hosting-nudge {{
        flex-direction: column;
        gap: 0.5rem;
      }}
    }}
  </style>
</head>
<body>

{_nav()}

<main class="page-wrap">

  <section class="hero">
    <div class="hero__eyebrow">For bootstrapped SaaS founders</div>
    <h1 class="hero__title">Financial tools and honest guides — no hype</h1>
    <p class="hero__desc">
      Free calculators for the numbers that actually matter: MRR, churn,
      runway, LTV. Plus practical articles written by someone who has
      iterated in production, not a content team chasing SEO.
    </p>
    <div class="hero__actions">
      <a href="/tools/" class="btn btn--primary">Browse tools →</a>
      <a href="/articles/" class="btn btn--ghost">Read articles</a>
    </div>
  </section>

  <section class="section">
    <div class="section__header">
      <h2 class="section__title">Recent articles</h2>
      <a href="/articles/" class="section__link">All articles →</a>
    </div>
    <div class="article-list">
      {articles_html}
    </div>
  </section>

  <section class="section">
    <div class="section__header">
      <h2 class="section__title">Calculators &amp; tools</h2>
      <a href="/tools/" class="section__link">All tools →</a>
    </div>
    <div class="tools-grid">
      {tools_html}
    </div>
  </section>

  <div class="hosting-nudge">
    <div class="hosting-nudge__dot"></div>
    <div class="hosting-nudge__body">
      <div class="hosting-nudge__label">Hosting recommendation</div>
      <p class="hosting-nudge__text">
        This site runs on
        <a href="https://www.cloudways.com" rel="noopener sponsored">Cloudways</a> —
        managed cloud hosting with per-app scaling and no markup confusion.
        Worth considering if you are outgrowing shared plans.
      </p>
    </div>
  </div>

</main>

{_FOOTER}

</body>
</html>"""


# ─────────────────────────────────────────────
# ARTICLES INDEX
# ─────────────────────────────────────────────

def build_articles_index(files: list) -> str:
    """Build articles/index.html."""
    article_files = sorted(
        [f for f in files if f["folder"] == "articles"],
        key=lambda x: x["name"], reverse=True
    )
    total = len(article_files)

    # ── Article list HTML ──
    # Same CSS contract as homepage article list —
    # identical structure so one builder output works on both pages.
    items_html = ""
    for f in article_files:
        slug         = file_to_slug(f["name"])
        url          = file_to_url("articles", f["name"])
        title        = slug_to_title(slug)
        display_date = _parse_display_date(f["name"])
        date_span    = (
            f'<span class="article-item__date">{display_date}</span>'
            if display_date else ""
        )
        items_html += f"""
      <a href="{url}" class="article-item">
        <div class="article-item__left">
          <span class="article-item__title">{title}</span>
        </div>
        {date_span}
      </a>"""

    if not items_html:
        items_html = '\n      <div class="empty">No articles yet. Check back soon.</div>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>All Articles — blogtrick</title>
  <meta name="description" content="No-fluff guides for bootstrapped SaaS founders. {total} articles covering pricing, metrics, ops, and growth.">
  <link rel="canonical" href="{SITE_URL}/articles/">
  {_FONT}
  <style>
{_BASE_CSS}
{_NAV_CSS}

    /* ── Layout ─────────────────────────────────────── */
    .page-wrap {{
      max-width: 720px;
      margin: 0 auto;
      padding: 0 1.25rem;
    }}

    /* ── Page Header ────────────────────────────────── */
    .page-header {{
      padding: 3.5rem 0 2.25rem;
      border-bottom: 1px solid var(--border);
    }}

    .page-header__title {{
      font-size: clamp(1.5rem, 4vw, 2.125rem);
      font-weight: 700;
      letter-spacing: -0.02em;
      color: var(--text);
      margin-bottom: 0.5rem;
      line-height: 1.2;
    }}

    .page-header__meta {{
      font-size: 0.9rem;
      color: var(--muted);
    }}

    .page-header__meta strong {{
      color: var(--text);
      font-weight: 600;
    }}

    /* ── Article List ───────────────────────────────── */
    .article-list {{
      padding: 0.5rem 0 3rem;
      display: flex;
      flex-direction: column;
    }}

    .article-list .article-item {{
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: 1rem;
      padding: 1.0625rem 0;
      border-bottom: 1px solid var(--border);
      text-decoration: none;
      color: inherit;
      position: relative;
      transition: padding-left 0.18s ease;
    }}

    .article-list .article-item::before {{
      content: '';
      position: absolute;
      left: -0.875rem;
      top: 50%;
      transform: translateY(-50%);
      width: 3px;
      height: 0;
      background: var(--accent);
      border-radius: 2px;
      transition: height 0.18s ease;
    }}

    .article-list .article-item:last-child {{
      border-bottom: none;
    }}

    .article-item__left {{
      min-width: 0;
      flex: 1;
    }}

    .article-item__title {{
      display: block;
      font-size: 0.9375rem;
      font-weight: 500;
      color: var(--text);
      line-height: 1.4;
      margin-bottom: 0.25rem;
      transition: color 0.13s ease;
    }}

    .article-item__desc {{
      display: block;
      font-size: 0.8125rem;
      color: var(--muted);
      line-height: 1.5;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }}

    .article-item__date {{
      font-size: 0.8125rem;
      color: var(--subtle);
      white-space: nowrap;
      flex-shrink: 0;
    }}

    @media (hover: hover) {{
      .article-list .article-item:hover {{
        padding-left: 0.5625rem;
      }}

      .article-list .article-item:hover::before {{
        height: 50%;
      }}

      .article-list .article-item:hover .article-item__title {{
        color: var(--accent);
      }}
    }}

    .empty {{
      text-align: center;
      color: var(--muted);
      font-size: 0.9rem;
      padding: 3rem 0;
    }}

{_FOOTER_CSS}

    /* ── Responsive ─────────────────────────────────── */
    @media (max-width: 600px) {{
      .page-header {{
        padding: 2.5rem 0 1.75rem;
      }}

      .article-list .article-item {{
        align-items: flex-start;
        flex-wrap: wrap;
        gap: 0.25rem;
      }}

      .article-item__desc {{
        white-space: normal;
        overflow: visible;
        text-overflow: unset;
      }}

      .article-item__date {{
        width: 100%;
        font-size: 0.75rem;
      }}
    }}
  </style>
</head>
<body>

{_nav("articles")}

<main class="page-wrap">

  <header class="page-header">
    <h1 class="page-header__title">Articles</h1>
    <p class="page-header__meta">
      <strong>{total}</strong> articles — practical writing for founders
      who would rather read once and decide than read ten posts and stay confused.
    </p>
  </header>

  <div class="article-list">
    {items_html}
  </div>

</main>

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
    total = len(tool_files)

    # ── Tools grid HTML ──
    # Same CSS contract as homepage tools grid —
    # identical structure so one builder output works on both pages.
    items_html = ""
    for f in tool_files:
        slug  = file_to_slug(f["name"])
        url   = file_to_url("tools", f["name"])
        title = slug_to_title(slug)
        desc  = _get_tool_desc(slug)
        items_html += f"""
      <a href="{url}" class="tool-card">
        <div class="tool-card__icon">⚡</div>
        <div class="tool-card__name">{title}</div>
        <div class="tool-card__desc">{desc}</div>
      </a>"""

    if not items_html:
        items_html = '\n      <div class="empty">No tools yet. Check back soon.</div>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>SaaS Calculators &amp; Tools — blogtrick</title>
  <meta name="description" content="Free financial calculators for SaaS founders. MRR, churn, LTV, CAC, runway — built for quick, honest answers.">
  <link rel="canonical" href="{SITE_URL}/tools/">
  {_FONT}
  <style>
{_BASE_CSS}
{_NAV_CSS}

    /* ── Layout ─────────────────────────────────────── */
    .page-wrap {{
      max-width: 720px;
      margin: 0 auto;
      padding: 0 1.25rem;
    }}

    /* ── Page Header ────────────────────────────────── */
    .page-header {{
      padding: 3.5rem 0 2.25rem;
      border-bottom: 1px solid var(--border);
    }}

    .page-header__title {{
      font-size: clamp(1.5rem, 4vw, 2.125rem);
      font-weight: 700;
      letter-spacing: -0.02em;
      color: var(--text);
      margin-bottom: 0.5rem;
      line-height: 1.2;
    }}

    .page-header__meta {{
      font-size: 0.9rem;
      color: var(--muted);
    }}

    .page-header__meta strong {{
      color: var(--text);
      font-weight: 600;
    }}

    /* ── Tools section ──────────────────────────────── */
    .tools-section {{
      padding: 2.25rem 0 3rem;
    }}

    /* ── Intent strip ───────────────────────────────── */
    .usecase-strip {{
      margin-bottom: 1.875rem;
      padding: 1rem 1.125rem;
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--r);
      display: flex;
      align-items: flex-start;
      gap: 0.75rem;
      box-shadow: var(--shadow);
    }}

    .usecase-strip__icon {{
      font-size: 1.125rem;
      flex-shrink: 0;
      line-height: 1.5;
    }}

    .usecase-strip__text {{
      font-size: 0.875rem;
      color: var(--muted);
      line-height: 1.6;
    }}

    .usecase-strip__text strong {{
      color: var(--text);
      font-weight: 600;
    }}

    /* ── Tools Grid ─────────────────────────────────── */
    .tools-grid {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 0.75rem;
    }}

    .tool-card {{
      display: block;
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--r);
      padding: 1.25rem;
      text-decoration: none;
      color: inherit;
      box-shadow: var(--shadow);
      transition: box-shadow 0.15s ease, border-color 0.15s ease, transform 0.15s ease;
    }}

    .tool-card:hover {{
      box-shadow: var(--shadow-md);
      border-color: var(--accent);
      transform: translateY(-2px);
    }}

    .tool-card__icon {{
      width: 36px;
      height: 36px;
      background: var(--accent-light);
      border-radius: 8px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 1.0625rem;
      margin-bottom: 0.875rem;
      flex-shrink: 0;
    }}

    .tool-card__name {{
      font-size: 0.9375rem;
      font-weight: 600;
      color: var(--text);
      margin-bottom: 0.375rem;
      line-height: 1.3;
      transition: color 0.13s ease;
    }}

    .tool-card:hover .tool-card__name {{
      color: var(--accent);
    }}

    .tool-card__desc {{
      font-size: 0.8125rem;
      color: var(--muted);
      line-height: 1.55;
    }}

    .empty {{
      text-align: center;
      color: var(--muted);
      font-size: 0.9rem;
      padding: 3rem 0;
    }}

{_FOOTER_CSS}

    /* ── Responsive ─────────────────────────────────── */
    @media (max-width: 600px) {{
      .page-header {{
        padding: 2.5rem 0 1.75rem;
      }}

      .tools-section {{
        padding: 1.75rem 0 2.5rem;
      }}

      .tools-grid {{
        grid-template-columns: 1fr;
      }}
    }}
  </style>
</head>
<body>

{_nav("tools")}

<main class="page-wrap">

  <header class="page-header">
    <h1 class="page-header__title">Calculators &amp; Tools</h1>
    <p class="page-header__meta">
      <strong>{total}</strong> free tools — input your numbers, get a clean
      answer. No signup, no export-locked results, no upsell.
    </p>
  </header>

  <section class="tools-section">
    <div class="usecase-strip">
      <div class="usecase-strip__icon">📐</div>
      <p class="usecase-strip__text">
        <strong>Built for real decisions.</strong> Each tool is scoped
        to one question: what is my payback period, how long does runway
        last at this burn rate, what churn kills LTV first. Numbers you
        can bring to a conversation with a co-founder or investor.
      </p>
    </div>

    <div class="tools-grid">
      {items_html}
    </div>
  </section>

</main>

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

    publish_file("sitemap.xml",         build_sitemap(files),         "Sitemap")
    publish_file("index.html",          build_homepage(files),         "Homepage")
    publish_file("articles/index.html", build_articles_index(files),  "Articles index")
    publish_file("tools/index.html",    build_tools_index(files),     "Tools index")
    prune_content_index(files)

    print("Done")
