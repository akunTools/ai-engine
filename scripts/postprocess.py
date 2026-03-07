"""
postprocess.py
Validasi dan format output dari AI sebelum dipublish.
Artikel di-convert dari Markdown ke HTML lengkap sebelum dipublish.
"""
import re
from datetime import datetime


# ─────────────────────────────────────────────
# MANUAL CONTENT WRAPPING
# Digunakan untuk konten yang ditulis manual
# dan disimpan sebagai body HTML di staging.
# ─────────────────────────────────────────────

def wrap_article_html(body_html: str, slug: str) -> str:
    """
    Bungkus body artikel ke full HTML page.
    Input : body HTML saja (mulai dari <h1>, boleh diawali
            <meta name="cluster"> dan/atau <meta name="description">
            sebelum <h1>)
    Output: full HTML page siap publish

    Judul diambil otomatis dari tag <h1> pertama.
    Cluster diambil dari <meta name="cluster"> jika ada.
    Meta description diambil dari <meta name="description"> jika ada,
    fallback ke judul jika tidak ada.
    Kedua meta tag dihapus dari body sebelum render.
    """
    # Ekstrak cluster_id
    cluster_match = re.search(
        r'<meta\s+name=["\']cluster["\']\s+content=["\']([^"\']*)["\'][^>]*/?>',
        body_html, re.IGNORECASE
    )
    cluster_id = cluster_match.group(1).strip() if cluster_match else ""
    if cluster_match:
        body_html = body_html[:cluster_match.start()] + body_html[cluster_match.end():]
        body_html = body_html.lstrip("\n")

    # Ekstrak meta description
    desc_match = re.search(
        r'<meta\s+name=["\']description["\']\s+content=["\']([^"\']*)["\'][^>]*/?>',
        body_html, re.IGNORECASE
    )
    meta_desc = desc_match.group(1).strip() if desc_match else ""
    if desc_match:
        body_html = body_html[:desc_match.start()] + body_html[desc_match.end():]
        body_html = body_html.lstrip("\n")

    date_str = datetime.utcnow().strftime("%Y-%m-%d")

    h1_match = re.search(r'<h1[^>]*>(.*?)</h1>',
                         body_html, re.IGNORECASE | re.DOTALL)
    title = (h1_match.group(1).strip()
             if h1_match
             else slug.replace("-", " ").title())

    title_clean = re.sub(r'<[^>]+>', '', title).strip()
    word_count  = len(re.sub(r'<[^>]+>', '', body_html).split())

    # Fallback: gunakan judul jika Claude tidak menulis meta description
    if not meta_desc:
        meta_desc = title_clean

    fm = {
        "title":           title_clean,
        "slug":            slug,
        "date":            date_str,
        "primary_keyword": "",
        "cluster_id":      cluster_id,
        "meta_desc":       meta_desc,
        "word_count":      word_count
    }

    return _build_article_html(fm, body_html, slug, date_str, cluster_id)


def wrap_tool_html(body_html: str, slug: str) -> str:
    """
    Bungkus body tool/kalkulator ke full HTML page.
    Input : body HTML saja — boleh diawali <meta name="cluster">
            sebelum <h1>. Tanpa <html>/<head>/<style>.
            Gunakan CSS class yang tersedia di bawah.
    Output: full HTML page siap publish

    CSS classes yang tersedia:
    .card, .card h2
    .input-group, label, .input-wrapper, .input-prefix
    input[type="number"]
    .result-card, .result-label, .result-number, .result-unit
    .interpretation, .secondary-result
    .formula-box, .formula-box h3, .formula-box p
    .affiliate-box, .affiliate-box a
    .related-link, .related-link a
    .subtitle
    """
    # Ekstrak cluster_id dari meta tag
    cluster_match = re.search(
        r'<meta\s+name=["\']cluster["\']\s+content=["\']([^"\']*)["\'][^>]*/?>',
        body_html, re.IGNORECASE
    )
    cluster_id = cluster_match.group(1).strip() if cluster_match else ""
    if cluster_match:
        body_html = body_html[:cluster_match.start()] + body_html[cluster_match.end():]
        body_html = body_html.lstrip("\n")

    # Ekstrak meta description
    desc_match = re.search(
        r'<meta\s+name=["\']description["\']\s+content=["\']([^"\']*)["\'][^>]*/?>',
        body_html, re.IGNORECASE
    )
    meta_desc = desc_match.group(1).strip() if desc_match else ""
    if desc_match:
        body_html = body_html[:desc_match.start()] + body_html[desc_match.end():]
        body_html = body_html.lstrip("\n")

    site_url     = "https://saas.blogtrick.eu.org"
    tool_url     = f"{site_url}/tools/{slug}"
    cluster_meta = f'<meta name="cluster" content="{cluster_id}">' if cluster_id else ""

    h1_match = re.search(r'<h1[^>]*>(.*?)</h1>',
                         body_html, re.IGNORECASE | re.DOTALL)
    title = (h1_match.group(1).strip()
             if h1_match
             else slug.replace("-", " ").title())
    title_clean = re.sub(r'<[^>]+>', '', title).strip()

    # Fallback: generate deskripsi standar jika Claude tidak menulis meta description
    if not meta_desc:
        meta_desc = f"{title_clean}. Free calculator for bootstrapped SaaS founders."

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title_clean} — SaaS Tools for Bootstrapped Founders</title>
  <meta name="description" content="{meta_desc}">
  {cluster_meta}
  <link rel="canonical" href="{tool_url}">
  {_FONT}
  <style>
{{_BASE_CSS}}
{{_NAV_CSS}}

    /* ── LAYOUT ── */
    .container {{ max-width: 680px; margin: 0 auto; padding: 40px 20px 80px; }}

    /* ── TYPOGRAPHY ── */
    h1 {{
      font-size: clamp(1.5rem, 4vw, 1.9rem);
      font-weight: 700;
      letter-spacing: -.03em;
      color: var(--text);
      margin-bottom: 6px;
    }}
    .subtitle {{
      color: var(--muted);
      font-size: .95rem;
      margin-bottom: 28px;
      line-height: 1.5;
    }}

    /* ── CARD ── */
    .card {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--r);
      padding: 24px;
      margin-bottom: 14px;
    }}
    .card h2 {{
      font-size: .9rem;
      font-weight: 600;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: .05em;
      margin-bottom: 20px;
    }}

    /* ── INPUTS ── */
    .input-group {{ margin-bottom: 18px; }}
    .input-group:last-child {{ margin-bottom: 0; }}
    label {{
      display: block;
      font-size: .85rem;
      font-weight: 500;
      color: var(--text);
      margin-bottom: 7px;
    }}
    .input-wrapper {{ position: relative; }}
    .input-prefix {{
      position: absolute;
      left: 13px;
      top: 50%;
      transform: translateY(-50%);
      color: var(--muted);
      font-size: .9rem;
      pointer-events: none;
      font-weight: 500;
    }}
    input[type="number"] {{
      width: 100%;
      padding: 10px 14px 10px 30px;
      border: 1.5px solid var(--border);
      border-radius: 8px;
      font-size: 1rem;
      color: var(--text);
      background: var(--surface);
      font-family: inherit;
      transition: border-color .15s, box-shadow .15s;
      -moz-appearance: textfield;
    }}
    input[type="number"]::-webkit-outer-spin-button,
    input[type="number"]::-webkit-inner-spin-button {{ -webkit-appearance: none; }}
    input[type="number"]:focus {{
      outline: none;
      border-color: var(--accent);
      box-shadow: 0 0 0 3px rgba(79,70,229,.1);
    }}
    input[type="number"].error-input {{ border-color: var(--danger); }}
    .error-msg {{
      color: var(--danger);
      font-size: .75rem;
      margin-top: 4px;
      display: none;
    }}

    /* ── RESULT ── */
    .result-card {{
      background: var(--accent-light);
      border: 1.5px solid rgba(79,70,229,.2);
      border-radius: var(--r);
      padding: 28px 24px 24px;
      margin-bottom: 14px;
    }}
    .result-label {{
      font-size: .75rem;
      font-weight: 600;
      color: var(--accent);
      text-transform: uppercase;
      letter-spacing: .06em;
      margin-bottom: 6px;
    }}
    .result-number {{
      font-size: 3.5rem;
      font-weight: 700;
      color: var(--accent);
      line-height: 1;
      letter-spacing: -.04em;
      margin-bottom: 2px;
    }}
    .result-unit {{
      font-size: .875rem;
      color: var(--accent);
      opacity: .7;
      margin-bottom: 16px;
    }}
    .interpretation {{
      background: var(--surface);
      border-radius: 8px;
      padding: 12px 16px;
      font-size: .875rem;
      color: var(--text);
      line-height: 1.5;
      border-left: 3px solid var(--accent);
    }}
    .interpretation.danger {{
      border-color: var(--danger);
      background: var(--danger-bg);
    }}
    .interpretation.warning {{
      border-color: var(--warning);
      background: var(--warning-bg);
    }}
    .interpretation.healthy {{
      border-color: var(--success);
      background: var(--success-bg);
    }}
    .secondary-result {{
      margin-top: 12px;
      font-size: .8rem;
      color: var(--muted);
    }}

    /* ── FORMULA BOX ── */
    .formula-box {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--r);
      padding: 20px 24px;
      margin-bottom: 14px;
    }}
    .formula-box h3 {{
      font-size: .75rem;
      font-weight: 600;
      color: var(--subtle);
      text-transform: uppercase;
      letter-spacing: .06em;
      margin-bottom: 10px;
    }}
    .formula-box p {{
      font-size: .875rem;
      color: var(--muted);
      line-height: 1.7;
      font-family: 'SFMono-Regular', Consolas, monospace;
    }}

    /* ── AFFILIATE BOX ── */
    .affiliate-box {{
      background: var(--success-bg);
      border: 1px solid rgba(16,185,129,.25);
      border-radius: var(--r);
      padding: 16px 20px;
      margin-bottom: 14px;
      font-size: .875rem;
      color: var(--text);
      line-height: 1.6;
    }}
    .affiliate-box a {{
      color: var(--success);
      font-weight: 500;
      text-decoration: underline;
      text-decoration-color: rgba(16,185,129,.4);
    }}
    .affiliate-box a:hover {{ color: #059669; }}

    /* ── RELATED LINK ── */
    .related-link {{
      font-size: .85rem;
      color: var(--muted);
      padding: 12px 0;
    }}
    .related-link a {{
      color: var(--accent);
      text-decoration: underline;
      text-decoration-color: rgba(79,70,229,.3);
      font-weight: 500;
    }}
    .related-link a:hover {{ color: var(--accent-h); }}

{_RELATED_CSS}
{{_FOOTER_CSS}}

    @media (max-width: 600px) {{
      .container {{ padding: 28px 16px 60px; }}
      .result-number {{ font-size: 2.75rem; }}
    }}
  </style>
</head>
<body>

<nav>
  <div class="nav-inner">
    <a href="/tools/" class="nav-back">← All Tools</a>
    <div class="nav-links">
      <a href="/articles/">Articles</a>
      <a href="/tools/" class="active">Tools</a>
    </div>
  </div>
</nav>

<div class="container">
{body_html}
<div id="related-content"></div>
</div>

{_FOOTER_HTML}

{_RELATED_JS}

</body>
</html>"""
