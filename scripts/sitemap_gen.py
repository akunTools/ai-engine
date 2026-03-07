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

ENGINE_REPO   = os.environ.get("ENGINE_REPO", "YOUR_USERNAME/ai-engine")
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
# SHARED DESIGN TOKENS
# ─────────────────────────────────────────────

_FONT = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">'
)

_BASE_CSS = """
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  :root {
    --bg:           #ffffff;
    --surface:      #f8fafc;
    --text:         #0f172a;
    --muted:        #64748b;
    --subtle:       #94a3b8;
    --border:       #e2e8f0;
    --accent:       #4f46e5;
    --accent-h:     #4338ca;
    --accent-light: #eef2ff;
    --danger:       #ef4444;
    --danger-bg:    #fef2f2;
    --warning:      #f59e0b;
    --warning-bg:   #fffbeb;
    --success:      #16a34a;
    --success-bg:   #f0fdf4;
    --r:            10px;
    --shadow:       0 1px 3px rgba(0,0,0,.07), 0 1px 2px rgba(0,0,0,.04);
    --shadow-md:    0 4px 16px rgba(0,0,0,.08);
  }
  body {
    font-family: 'Inter', system-ui, -apple-system, sans-serif;
    background: var(--bg);
    color: var(--text);
    font-size: 16px;
    line-height: 1.6;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
  }
  a { color: var(--accent); text-decoration: none; }
  a:hover { color: var(--accent-h); }
"""

_NAV_CSS = """
  nav {
    background: var(--bg);
    border-bottom: 1px solid var(--border);
    padding: 0 1.5rem;
    position: sticky;
    top: 0;
    z-index: 100;
  }
  .nav-inner {
    max-width: 820px;
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
  .nav-links a:hover { color: var(--text); background: var(--surface); }
  .nav-links a.active { color: var(--accent); background: var(--accent-light); }
"""

_FOOTER_CSS = """
  footer {
    border-top: 1px solid var(--border);
    padding: 48px 1.5rem;
    margin-top: 2rem;
  }
  .footer-inner {
    max-width: 820px;
    margin: 0 auto;
    text-align: center;
  }
  .footer-brand {
    font-size: .8rem;
    font-weight: 600;
    color: var(--muted);
    margin-bottom: 16px;
    letter-spacing: .02em;
    text-transform: uppercase;
  }
  .footer-links {
    display: flex;
    justify-content: center;
    gap: 28px;
    margin-bottom: 16px;
  }
  .footer-links a {
    font-size: .8rem;
    color: var(--muted);
    text-decoration: none;
    transition: color .15s;
  }
  .footer-links a:hover { color: var(--accent); }
  .footer-copy { font-size: .75rem; color: var(--subtle); }
"""


def _nav(active: str = "") -> str:
    art_cls  = ' class="active"' if active == "articles" else ""
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
    <div class="footer-brand">SaaS Tools for Bootstrapped Founders</div>
    <div class="footer-links">
      <a href="/">Home</a>
      <a href="/articles/">Articles</a>
      <a href="/tools/">Tools</a>
    </div>
    <div class="footer-copy">
      Free tools and analysis for independent SaaS founders in the US &amp; Canada.
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

    # ── Article items ──────────────────────────────────────────────────────
    # Injects <li class="article-item"> matching homepage CSS
    if article_files:
        articles_html = ""
        for f in article_files:
            slug  = file_to_slug(f["name"])
            url   = file_to_url("articles", f["name"])
            title = slug_to_title(slug)
            date_match = re.match(r'^(\d{4}-\d{2}-\d{2})', f["name"])
            date_str = date_match.group(1) if date_match else ""
            try:
                from datetime import datetime as _dt
                display_date = (
                    _dt.strptime(date_str, "%Y-%m-%d").strftime("%b %-d, %Y")
                    if date_str else ""
                )
            except Exception:
                display_date = date_str

            articles_html += f"""      <li class="article-item">
        <div class="article-item-body">
          <a class="article-item-title" href="{url}">{title}</a>
        </div>
        <span class="article-meta">{display_date}</span>
      </li>\n"""
    else:
        articles_html = (
            '      <li class="article-item" style="border:none; color:var(--muted); '
            'font-size:.9rem; padding:1rem 0;">No articles yet — check back soon.</li>\n'
        )

    # ── Tool cards ─────────────────────────────────────────────────────────
    # Injects <a class="tool-card"> matching homepage CSS
    _CTA = {
        "runway":     "Calculate your runway",
        "burn":       "Model your burn rate",
        "break-even": "Find your break-even point",
        "ltv":        "Check your unit economics",
        "cac":        "Check your unit economics",
        "churn":      "Measure your churn rate",
        "mrr":        "Track your MRR growth",
        "pricing":    "Find your price point",
    }
    _ICONS = {
        "runway": "🛫", "burn": "🔥", "break-even": "⚖️",
        "ltv": "📈", "cac": "📊", "churn": "📉",
        "mrr": "💹", "pricing": "🏷️",
    }
    _DESCS = {
        "runway":     "Enter MRR and monthly burn. Get months of runway and break-even projection.",
        "burn":       "Calculate your real monthly cash burn across all cost categories.",
        "break-even": "How many customers do you need to cover all fixed costs?",
        "ltv":        "Is your LTV:CAC ratio healthy enough to scale paid acquisition?",
        "cac":        "Is your LTV:CAC ratio healthy enough to scale paid acquisition?",
        "churn":      "What percentage of customers and revenue are you losing monthly?",
        "mrr":        "How fast is your MRR actually growing month over month?",
        "pricing":    "Is your pricing model financially sound for your cost structure?",
    }

    def _tool_meta(slug: str, key: str, default: str) -> str:
        slug_lower = slug.lower()
        for kw, val in {"runway": _CTA, "burn": _CTA, "break-even": _CTA,
                        "ltv": _CTA, "cac": _CTA, "churn": _CTA,
                        "mrr": _CTA, "pricing": _CTA}[key if False else key].items() \
                if False else {kw: {"cta": _CTA, "icon": _ICONS, "desc": _DESCS}[key].get(kw, default)
                               for kw in _CTA}.items():
            if kw in slug_lower:
                return val
        return default

    def _get_cta(slug: str)  -> str:
        for kw, val in _CTA.items():
            if kw in slug.lower():
                return val
        return "Open calculator"

    def _get_icon(slug: str) -> str:
        for kw, val in _ICONS.items():
            if kw in slug.lower():
                return val
        return "⚡"

    def _get_desc(slug: str) -> str:
        for kw, val in _DESCS.items():
            if kw in slug.lower():
                return val
        return "Calculate and understand your key SaaS metrics."

    if tool_files:
        tools_html = ""
        for f in tool_files:
            slug  = file_to_slug(f["name"])
            url   = file_to_url("tools", f["name"])
            title = slug_to_title(slug)
            icon  = _get_icon(slug)
            desc  = _get_desc(slug)
            cta   = _get_cta(slug)
            tools_html += f"""      <a class="tool-card" href="{url}">
        <span class="tool-card-icon">{icon}</span>
        <span class="tool-card-title">{title}</span>
        <span class="tool-card-desc">{desc}</span>
        <span class="tool-card-cta">{cta} →</span>
      </a>\n"""
    else:
        tools_html = (
            '      <p style="color:var(--muted); font-size:.9rem;">'
            'No tools yet — check back soon.</p>\n'
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>SaaS Financial Tools — Calculators &amp; Guides for Bootstrapped Founders</title>
  <meta name="description" content="Free financial calculators and plain-English guides to help bootstrapped SaaS founders model runway, price products, and understand their numbers.">
  <link rel="canonical" href="{SITE_URL}/">
  {_FONT}
  <style>
    {_BASE_CSS}
    {_NAV_CSS}

    /* ── Hero ── */
    .hero {{
      padding: 5rem 0 4rem;
      border-bottom: 1px solid var(--border);
    }}

    .hero-eyebrow {{
      display: inline-flex;
      align-items: center;
      gap: .375rem;
      font-size: .75rem;
      font-weight: 600;
      letter-spacing: .08em;
      text-transform: uppercase;
      color: var(--accent);
      margin-bottom: 1.375rem;
    }}

    .hero-eyebrow::before {{
      content: '';
      display: inline-block;
      width: 6px;
      height: 6px;
      border-radius: 50%;
      background: var(--accent);
      flex-shrink: 0;
    }}

    .hero h1 {{
      font-size: 2.5rem;
      font-weight: 700;
      line-height: 1.14;
      letter-spacing: -.025em;
      color: var(--text);
      max-width: 580px;
      margin-bottom: 1.125rem;
    }}

    .hero-subtitle {{
      font-size: 1.0625rem;
      color: var(--muted);
      max-width: 500px;
      line-height: 1.7;
      margin-bottom: 2.25rem;
    }}

    /* ── Buttons — min 44px tap target ── */
    .hero-actions {{
      display: flex;
      gap: .75rem;
      flex-wrap: wrap;
      align-items: center;
    }}

    .btn {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: .375rem;
      font-size: .9375rem;
      font-weight: 600;
      min-height: 44px;
      padding: 0 1.375rem;
      border-radius: var(--r);
      text-decoration: none;
      transition: background .14s ease, border-color .14s ease,
                  color .14s ease, box-shadow .14s;
      white-space: nowrap;
      cursor: pointer;
      border: 1px solid transparent;
    }}

    .btn-primary {{
      background: var(--accent);
      color: #fff;
    }}
    .btn-primary:hover {{
      background: var(--accent-h);
      color: #fff;
      box-shadow: 0 2px 12px rgba(79,70,229,.25);
    }}

    .btn-ghost {{
      background: transparent;
      color: var(--muted);
      border-color: var(--border);
    }}
    .btn-ghost:hover {{
      border-color: var(--accent);
      color: var(--accent);
      background: var(--accent-light);
    }}

    /* ── Layout ── */
    .container {{
      max-width: 820px;
      margin: 0 auto;
      padding: 0 1.5rem;
    }}

    /* ── Sections ── */
    .section {{ padding: 3rem 0; }}
    .section + .section {{ border-top: 1px solid var(--border); }}

    .section-header {{
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: 1rem;
      margin-bottom: 1.75rem;
    }}

    .section-title {{
      font-size: 1.0625rem;
      font-weight: 600;
      letter-spacing: -.01em;
      color: var(--text);
    }}

    .section-link {{
      font-size: .875rem;
      font-weight: 500;
      color: var(--accent);
      white-space: nowrap;
      flex-shrink: 0;
      text-decoration: none;
    }}
    .section-link:hover {{ text-decoration: underline; color: var(--accent-h); }}

    /* ── Article list ── */
    .article-list {{
      list-style: none;
      padding: 0;
      margin: 0;
    }}

    .article-item {{
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 1.75rem;
      padding: 1.125rem 0;
      border-bottom: 1px solid var(--border);
    }}

    .article-item:first-child {{ border-top: 1px solid var(--border); }}

    .article-item-body {{
      flex: 1;
      min-width: 0;
    }}

    .article-item-title {{
      display: block;
      font-size: 1rem;
      font-weight: 600;
      color: var(--text);
      line-height: 1.4;
      text-decoration: none;
      transition: color .12s;
    }}
    .article-item-title:hover {{ color: var(--accent); }}

    .article-meta {{
      font-size: .8125rem;
      color: var(--muted);
      white-space: nowrap;
      flex-shrink: 0;
      padding-top: .125rem;
    }}

    /* ── Tool cards ── */
    .tools-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
      gap: 1rem;
    }}

    .tool-card {{
      display: flex;
      flex-direction: column;
      gap: .375rem;
      padding: 1.25rem;
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--r);
      text-decoration: none;
      color: var(--text);
      position: relative;
      overflow: hidden;
      transition: border-color .15s, box-shadow .15s, transform .12s;
    }}

    .tool-card::before {{
      content: '';
      position: absolute;
      left: 0; top: 0; bottom: 0;
      width: 3px;
      background: var(--accent);
      border-radius: 3px 0 0 3px;
      transform: scaleY(0);
      transform-origin: bottom;
      transition: transform .18s ease;
    }}

    .tool-card:hover {{
      border-color: var(--accent);
      box-shadow: 0 4px 20px rgba(79,70,229,.08);
      transform: translateY(-2px);
    }}

    .tool-card:hover::before {{ transform: scaleY(1); }}
    .tool-card:active {{ transform: translateY(0); box-shadow: none; }}

    .tool-card-icon {{
      font-size: 1.375rem;
      line-height: 1;
      margin-bottom: .375rem;
      display: block;
    }}

    .tool-card-title {{
      font-size: .9375rem;
      font-weight: 600;
      color: var(--text);
      line-height: 1.3;
      display: block;
    }}

    .tool-card-desc {{
      font-size: .8125rem;
      color: var(--muted);
      line-height: 1.55;
      flex: 1;
      display: block;
    }}

    .tool-card-cta {{
      font-size: .8125rem;
      font-weight: 600;
      color: var(--accent);
      margin-top: .5rem;
      display: block;
    }}

    /* ── Affiliate strip ── */
    .affiliate-strip {{
      margin: 3rem 0;
      padding: 1.125rem 1.375rem;
      background: var(--success-bg);
      border: 1px solid #bbf7d0;
      border-radius: var(--r);
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 1rem;
      flex-wrap: wrap;
    }}

    .affiliate-strip p {{
      font-size: .875rem;
      color: var(--text);
      flex: 1;
      min-width: 180px;
      line-height: 1.55;
    }}

    .affiliate-strip strong {{ color: var(--success); font-weight: 600; }}

    .affiliate-link {{
      display: inline-flex;
      align-items: center;
      min-height: 44px;
      padding: 0 1rem;
      font-size: .875rem;
      font-weight: 600;
      color: var(--success);
      border: 1px solid #86efac;
      border-radius: 8px;
      text-decoration: none;
      white-space: nowrap;
      flex-shrink: 0;
      transition: background .13s, border-color .13s;
    }}
    .affiliate-link:hover {{
      background: #dcfce7;
      border-color: var(--success);
      color: var(--success);
    }}

    {_FOOTER_CSS}

    /* ── Responsive ── */
    @media (max-width: 600px) {{
      .hero {{ padding: 2.75rem 0 2.25rem; }}
      .hero h1 {{ font-size: 1.875rem; }}
      .hero-subtitle {{ font-size: 1rem; margin-bottom: 1.75rem; }}
      .tools-grid {{ grid-template-columns: 1fr; }}
      .article-item {{ flex-direction: column; gap: .375rem; }}
      .article-meta {{ padding-top: 0; }}
      .affiliate-strip {{ flex-direction: column; align-items: flex-start; }}
    }}

    @media (max-width: 400px) {{
      .hero h1 {{ font-size: 1.625rem; }}
      .hero-actions {{ flex-direction: column; align-items: stretch; }}
      .btn {{ justify-content: center; }}
    }}
  </style>
</head>
<body>

{_nav()}

<main>
  <div class="container">

    <!-- ── Hero ── -->
    <section class="hero">
      <span class="hero-eyebrow">Free · No login · No data stored</span>
      <h1>Know your numbers.<br>Ship with confidence.</h1>
      <p class="hero-subtitle">
        Financial calculators and plain-English guides built for bootstrapped
        SaaS founders — runway, pricing, LTV:CAC, burn rate, and more.
        No spreadsheet consultant required.
      </p>
      <div class="hero-actions">
        <a href="/tools/" class="btn btn-primary">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none"
               stroke="currentColor" stroke-width="2.5"
               stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <rect x="2" y="3" width="20" height="14" rx="2"/>
            <line x1="8" y1="21" x2="16" y2="21"/>
            <line x1="12" y1="17" x2="12" y2="21"/>
          </svg>
          Open the calculators
        </a>
        <a href="/articles/" class="btn btn-ghost">Read the guides →</a>
      </div>
    </section>

    <!-- ── Recent articles ── -->
    <section class="section">
      <div class="section-header">
        <h2 class="section-title">Recent guides</h2>
        <a href="/articles/" class="section-link">All articles →</a>
      </div>
      <ul class="article-list">
{articles_html}      </ul>
    </section>

    <!-- ── Tools ── -->
    <section class="section">
      <div class="section-header">
        <h2 class="section-title">Financial calculators</h2>
        <a href="/tools/" class="section-link">All tools →</a>
      </div>
      <div class="tools-grid">
{tools_html}      </div>
    </section>

    <!-- ── Affiliate callout ── -->
    <div class="affiliate-strip">
      <p>
        This site runs on <strong>Cloudways</strong> — managed cloud hosting
        that removes server maintenance from your plate. Starts at $14/mo,
        scales without a DevOps hire.
      </p>
      <a
        href="https://www.cloudways.com?id=YOURREF"
        target="_blank"
        rel="noopener sponsored"
        class="affiliate-link"
      >Try Cloudways →</a>
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

    total  = len(article_files)
    plural = "s" if total != 1 else ""

    articles_html = ""
    for f in article_files:
        slug  = file_to_slug(f["name"])
        url   = file_to_url("articles", f["name"])
        title = slug_to_title(slug)
        date_match = re.match(r'^(\d{4}-\d{2}-\d{2})', f["name"])
        date_str = date_match.group(1) if date_match else ""
        try:
            from datetime import datetime as _dt
            display_date = (
                _dt.strptime(date_str, "%Y-%m-%d").strftime("%b %-d, %Y")
                if date_str else ""
            )
        except Exception:
            display_date = date_str

        articles_html += f"""      <li class="article-item">
        <div class="article-item-body">
          <a class="article-item-title" href="{url}">{title}</a>
        </div>
        <div class="article-item-aside">
          <span class="article-meta">{display_date}</span>
        </div>
      </li>\n"""

    if not articles_html:
        articles_html = (
            '      <li class="article-item" style="border:none; justify-content:center; '
            'color:var(--muted); font-size:.9rem; padding:3rem 0;">'
            'No articles yet — check back soon.</li>\n'
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Financial Guides for SaaS Founders — Articles</title>
  <meta name="description" content="Plain-English financial guides for bootstrapped SaaS founders. Runway, pricing, MRR math, burn rate, and more.">
  <link rel="canonical" href="{SITE_URL}/articles/">
  {_FONT}
  <style>
    {_BASE_CSS}
    {_NAV_CSS}

    /* ── Layout ── */
    .container {{
      max-width: 820px;
      margin: 0 auto;
      padding: 0 1.5rem;
    }}

    /* ── Page header ── */
    .page-header {{
      padding: 3.75rem 0 2.75rem;
      border-bottom: 1px solid var(--border);
    }}

    .page-header h1 {{
      font-size: 1.875rem;
      font-weight: 700;
      letter-spacing: -.02em;
      line-height: 1.2;
      margin-bottom: .5rem;
    }}

    .page-header-meta {{
      font-size: .9375rem;
      color: var(--muted);
      line-height: 1.5;
    }}

    .page-header-meta strong {{
      color: var(--text);
      font-weight: 600;
    }}

    /* ── Article list ── */
    .article-section {{ padding: 2.5rem 0 4rem; }}

    .article-list {{
      list-style: none;
      padding: 0;
      margin: 0;
    }}

    .article-item {{
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 2rem;
      padding: 1.375rem 0;
      border-bottom: 1px solid var(--border);
    }}

    .article-item:first-child {{ border-top: 1px solid var(--border); }}

    .article-item-body {{
      flex: 1;
      min-width: 0;
    }}

    .article-item-title {{
      display: block;
      font-size: 1rem;
      font-weight: 600;
      color: var(--text);
      line-height: 1.4;
      text-decoration: none;
      transition: color .12s;
    }}
    .article-item-title:hover {{ color: var(--accent); }}

    .article-item-aside {{
      display: flex;
      flex-direction: column;
      align-items: flex-end;
      gap: .125rem;
      flex-shrink: 0;
      padding-top: .125rem;
    }}

    .article-meta {{
      font-size: .8125rem;
      color: var(--muted);
      white-space: nowrap;
    }}

    .article-readtime {{
      font-size: .75rem;
      color: var(--subtle);
      white-space: nowrap;
    }}

    {_FOOTER_CSS}

    /* ── Responsive ── */
    @media (max-width: 600px) {{
      .page-header {{ padding: 2.25rem 0 1.75rem; }}
      .page-header h1 {{ font-size: 1.5rem; }}
      .article-item {{ flex-direction: column; gap: .5rem; padding: 1.25rem 0; }}
      .article-item-aside {{ flex-direction: row; align-items: center; gap: .625rem; }}
    }}
  </style>
</head>
<body>

{_nav("articles")}

<main>
  <div class="container">

    <header class="page-header">
      <h1>Financial guides</h1>
      <p class="page-header-meta">
        <strong>{total}</strong> article{plural} covering runway,
        pricing strategy, MRR math, burn rate, and SaaS unit economics.
      </p>
    </header>

    <section class="article-section">
      <ul class="article-list">
{articles_html}      </ul>
    </section>

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

    _CTA = {
        "runway":     "Calculate your runway",
        "burn":       "Model your burn rate",
        "break-even": "Find your break-even point",
        "ltv":        "Check your unit economics",
        "cac":        "Check your unit economics",
        "churn":      "Measure your churn rate",
        "mrr":        "Track your MRR growth",
        "pricing":    "Find your price point",
    }
    _ICONS = {
        "runway": "🛫", "burn": "🔥", "break-even": "⚖️",
        "ltv": "📈", "cac": "📊", "churn": "📉",
        "mrr": "💹", "pricing": "🏷️",
    }
    _DESCS = {
        "runway":     "Enter MRR and monthly burn. Get months of runway and a break-even projection.",
        "burn":       "Calculate your real monthly cash burn across all cost categories.",
        "break-even": "How many customers do you need to cover all fixed costs?",
        "ltv":        "Is your LTV:CAC ratio healthy enough to scale paid acquisition?",
        "cac":        "Is your LTV:CAC ratio healthy enough to scale paid acquisition?",
        "churn":      "What percentage of customers and revenue are you losing monthly?",
        "mrr":        "How fast is your MRR actually growing month over month?",
        "pricing":    "Is your pricing model financially sound for your cost structure?",
    }

    def _get_cta(slug: str) -> str:
        for kw, val in _CTA.items():
            if kw in slug.lower():
                return val
        return "Open calculator"

    def _get_icon(slug: str) -> str:
        for kw, val in _ICONS.items():
            if kw in slug.lower():
                return val
        return "⚡"

    def _get_desc(slug: str) -> str:
        for kw, val in _DESCS.items():
            if kw in slug.lower():
                return val
        return "Calculate and understand your key SaaS metrics."

    tools_html = ""
    for f in tool_files:
        slug  = file_to_slug(f["name"])
        url   = file_to_url("tools", f["name"])
        title = slug_to_title(slug)
        icon  = _get_icon(slug)
        desc  = _get_desc(slug)
        cta   = _get_cta(slug)
        tools_html += f"""      <a class="tool-card" href="{url}">
        <span class="tool-card-icon">{icon}</span>
        <span class="tool-card-title">{title}</span>
        <span class="tool-card-desc">{desc}</span>
        <span class="tool-card-cta">{cta} →</span>
      </a>\n"""

    if not tools_html:
        tools_html = (
            '      <p style="color:var(--muted); font-size:.9rem; '
            'padding:3rem 0; text-align:center; grid-column:1/-1;">'
            'No tools yet — check back soon.</p>\n'
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Free SaaS Financial Calculators — Tools for Bootstrapped Founders</title>
  <meta name="description" content="Free financial calculators for bootstrapped SaaS founders. Runway, burn rate, LTV:CAC, pricing, and more. No login required.">
  <link rel="canonical" href="{SITE_URL}/tools/">
  {_FONT}
  <style>
    {_BASE_CSS}
    {_NAV_CSS}

    /* ── Layout ── */
    .container {{
      max-width: 820px;
      margin: 0 auto;
      padding: 0 1.5rem;
    }}

    /* ── Page header ── */
    .page-header {{
      padding: 3.75rem 0 2.75rem;
      border-bottom: 1px solid var(--border);
    }}

    .page-header h1 {{
      font-size: 1.875rem;
      font-weight: 700;
      letter-spacing: -.02em;
      line-height: 1.2;
      margin-bottom: .5rem;
    }}

    .page-header-meta {{
      font-size: .9375rem;
      color: var(--muted);
      line-height: 1.5;
    }}

    .page-header-meta strong {{
      color: var(--text);
      font-weight: 600;
    }}

    /* ── Trust signals ── */
    .trust-row {{
      display: flex;
      flex-wrap: wrap;
      gap: 1.25rem;
      margin-top: 1rem;
    }}

    .trust-item {{
      display: flex;
      align-items: center;
      gap: .375rem;
      font-size: .8125rem;
      color: var(--muted);
    }}

    .trust-item svg {{ color: var(--success); flex-shrink: 0; }}

    /* ── Tools section ── */
    .tools-section {{ padding: 2.5rem 0 2rem; }}

    /* ── Tool cards ── */
    .tools-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(230px, 1fr));
      gap: 1rem;
    }}

    .tool-card {{
      display: flex;
      flex-direction: column;
      gap: .375rem;
      padding: 1.375rem;
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--r);
      text-decoration: none;
      color: var(--text);
      position: relative;
      overflow: hidden;
      min-height: 160px;
      transition: border-color .15s, box-shadow .15s, transform .12s;
    }}

    .tool-card::before {{
      content: '';
      position: absolute;
      left: 0; top: 0; bottom: 0;
      width: 3px;
      background: var(--accent);
      border-radius: 3px 0 0 3px;
      transform: scaleY(0);
      transform-origin: bottom;
      transition: transform .18s ease;
    }}

    .tool-card:hover {{
      border-color: var(--accent);
      box-shadow: 0 4px 20px rgba(79,70,229,.08);
      transform: translateY(-2px);
    }}

    .tool-card:hover::before {{ transform: scaleY(1); }}
    .tool-card:active {{ transform: translateY(0); box-shadow: none; }}

    .tool-card-icon {{
      font-size: 1.5rem;
      line-height: 1;
      margin-bottom: .4375rem;
      display: block;
    }}

    .tool-card-title {{
      font-size: .9375rem;
      font-weight: 600;
      color: var(--text);
      line-height: 1.3;
      display: block;
    }}

    .tool-card-desc {{
      font-size: .8125rem;
      color: var(--muted);
      line-height: 1.6;
      flex: 1;
      display: block;
    }}

    .tool-card-cta {{
      font-size: .8125rem;
      font-weight: 600;
      color: var(--accent);
      margin-top: .625rem;
      display: block;
    }}

    /* ── Hosting note ── */
    .hosting-note {{
      margin-top: 2.5rem;
      margin-bottom: 3rem;
      padding: 1rem 1.25rem;
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--r);
      display: flex;
      align-items: flex-start;
      gap: .75rem;
    }}

    .hosting-note-icon {{
      font-size: .875rem;
      line-height: 1.6;
      flex-shrink: 0;
    }}

    .hosting-note p {{
      font-size: .875rem;
      color: var(--muted);
      line-height: 1.6;
    }}

    .hosting-note a {{
      color: var(--accent);
      font-weight: 500;
      text-decoration: none;
    }}
    .hosting-note a:hover {{ text-decoration: underline; color: var(--accent-h); }}

    {_FOOTER_CSS}

    /* ── Responsive ── */
    @media (max-width: 600px) {{
      .page-header {{ padding: 2.25rem 0 1.75rem; }}
      .page-header h1 {{ font-size: 1.5rem; }}
      .tools-grid {{ grid-template-columns: 1fr; }}
      .trust-row {{ gap: .875rem; }}
      .tool-card {{ min-height: unset; }}
    }}
  </style>
</head>
<body>

{_nav("tools")}

<main>
  <div class="container">

    <header class="page-header">
      <h1>Financial calculators</h1>
      <p class="page-header-meta">
        <strong>{total}</strong> free tools for SaaS unit economics,
        pricing, and runway planning.
      </p>
      <div class="trust-row">
        <span class="trust-item">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none"
               stroke="currentColor" stroke-width="2.5"
               stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <polyline points="20 6 9 17 4 12"/>
          </svg>
          No login required
        </span>
        <span class="trust-item">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none"
               stroke="currentColor" stroke-width="2.5"
               stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <polyline points="20 6 9 17 4 12"/>
          </svg>
          No data stored
        </span>
        <span class="trust-item">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none"
               stroke="currentColor" stroke-width="2.5"
               stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <polyline points="20 6 9 17 4 12"/>
          </svg>
          Runs in your browser
        </span>
      </div>
    </header>

    <section class="tools-section">
      <div class="tools-grid">
{tools_html}      </div>

      <div class="hosting-note">
        <span class="hosting-note-icon">💡</span>
        <p>
          Modeling infrastructure costs?
          <a href="https://www.cloudways.com?id=YOURREF"
             target="_blank" rel="noopener sponsored">Cloudways</a>
          publishes transparent per-server pricing — useful as a concrete
          baseline when you're projecting hosting spend against MRR.
        </p>
      </div>
    </section>

  </div>
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
