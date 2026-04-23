"""
og_gen.py
Generate Open Graph preview image (1200x630 PNG) untuk setiap artikel.
Dipanggil dari run_pipeline.py setelah artikel di-publish.
Output: og/{slug}.png di branch output.

Font: menggunakan DejaVu Sans (bundled di GitHub Actions ubuntu-latest).
Tidak memerlukan dependensi eksternal selain Pillow.
Design tokens mengikuti --bg, --accent, --text, --muted, --subtle, --border
yang didefinisikan di _BASE_CSS postprocess.py.
"""
import os
from PIL import Image, ImageDraw, ImageFont

OG_W, OG_H = 1200, 630

# Design tokens — identik dengan CSS vars di _BASE_CSS
BG     = (250, 250, 250)   # #fafafa — match --bg CSS
SURFACE = (255, 255, 255)   # --surface #ffffff
ACCENT = ( 37,  99, 235)   # #2563eb — match --accent CSS
TEXT    = ( 24,  24,  27)   # --text    #18181b
MUTED   = (113, 113, 122)   # --muted   #71717a
SUBTLE  = (161, 161, 170)   # --subtle  #a1a1aa
BORDER  = (228, 228, 231)   # --border  #e4e4e7

# Font path — DejaVu tersedia di GitHub Actions ubuntu-latest tanpa install
_FONT_BOLD   = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
_FONT_NORMAL = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def _font(bold: bool, size: int) -> ImageFont.FreeTypeFont:
    path = _FONT_BOLD if bold else _FONT_NORMAL
    return ImageFont.truetype(path, size)


def _wrap_title(draw: ImageDraw.ImageDraw, title: str,
                font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    """Wrap title berdasarkan pixel width, bukan jumlah karakter."""
    words   = title.split()
    lines   = []
    current = ""
    for word in words:
        test = (current + " " + word).strip()
        if draw.textlength(test, font=font) <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines[:3]  # maksimal 3 baris agar tidak overflow


def generate_og_image(title: str, slug: str, output_dir: str) -> str:
    """
    Generate OG image PNG untuk satu artikel.

    Args:
        title      : judul artikel (teks bersih, tanpa HTML tag)
        slug       : slug artikel, digunakan sebagai nama file
        output_dir : folder lokal tempat PNG disimpan sebelum di-upload

    Returns:
        path absolut ke file PNG yang dihasilkan
    """
    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, f"{slug}.png")

    img  = Image.new("RGB", (OG_W, OG_H), color=BG)
    draw = ImageDraw.Draw(img)

    # ── White card ────────────────────────────────────────────────
    MARGIN = 56
    card   = Image.new("RGB", (OG_W - MARGIN * 2, OG_H - MARGIN * 2), SURFACE)
    img.paste(card, (MARGIN, MARGIN))

    # ── Accent bar kiri ───────────────────────────────────────────
    draw.rectangle(
        [MARGIN, MARGIN, MARGIN + 7, OG_H - MARGIN],
        fill=ACCENT
    )

    PAD_L = MARGIN + 52
    PAD_T = MARGIN + 48

    # ── Site name: "SaaS" (accent) + "Tools" (text) ───────────────
    f_brand = _font(bold=True, size=30)
    draw.text((PAD_L, PAD_T), "SaaS", font=f_brand, fill=ACCENT)
    saas_w = int(draw.textlength("SaaS", font=f_brand))
    draw.text((PAD_L + saas_w, PAD_T), "Tools", font=f_brand, fill=TEXT)

    # ── Tagline ───────────────────────────────────────────────────
    f_tag = _font(bold=False, size=22)
    draw.text((PAD_L, PAD_T + 42), "for Bootstrapped Founders",
              font=f_tag, fill=MUTED)

    # ── Divider ───────────────────────────────────────────────────
    div_y   = PAD_T + 102
    right_x = OG_W - MARGIN - 52
    draw.rectangle([PAD_L, div_y, right_x, div_y + 1], fill=BORDER)

    # ── Title (wrapped, max 3 baris) ──────────────────────────────
    f_title  = _font(bold=True, size=54)
    max_w    = right_x - PAD_L - 16
    lines    = _wrap_title(draw, title, f_title, max_w)
    title_y  = div_y + 40
    for line in lines:
        draw.text((PAD_L, title_y), line, font=f_title, fill=TEXT)
        title_y += 72

    # ── Domain ────────────────────────────────────────────────────
    f_domain = _font(bold=False, size=24)
    draw.text(
        (PAD_L, OG_H - MARGIN - 58),
        "saas.blogtrick.eu.org",
        font=f_domain,
        fill=SUBTLE
    )

    img.save(out_path, "PNG", optimize=True)
    return out_path
