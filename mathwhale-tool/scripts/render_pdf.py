"""
render_pdf.py
==============
Takes a finished content.html (+ style.css) and the client's branded
template_pdf.pdf, and produces the final merged PDF: your lesson content
sitting inside the branded frame, on every page, with the template's own
watermark/logos showing through any transparent diagram or tinted callout.

Usage:
    python scripts/render_pdf.py content/lesson.html output/lesson.pdf

Two gotchas this script exists to avoid (found the hard way):

1. TEMPLATE SCALING BUG (pikepdf add_underlay)
   pikepdf's Page.add_underlay(), called with no explicit `rect`, fits the
   underlay page into the CURRENT page's full mediabox by default. If the
   template's own mediabox height doesn't exactly match your content page's
   mediabox height (very easy to happen - PDF authoring tools often crop a
   page to something like 842.25pt when the "nominal" page is 850.08pt),
   add_underlay silently STRETCHES the template by that tiny ratio to fill
   the gap. The visual effect: header/footer logos creep a few points out
   of position, sometimes just enough to clip page content near the top.
   Fix: always pass rect= the template's OWN mediabox explicitly, with
   shrink=False, expand=False, so it's placed 1:1, never rescaled.

2. TOP MARGIN vs LOGO CLEARANCE
   If a page break happens to land right as a new question/paragraph
   starts, that text sits at the very top of the printable area with no
   preceding element to buffer it. Measure your template's actual header
   graphic bottom edge and leave a few extra points of margin beyond that,
   or a tall first line can visually touch the logo. (In this project:
   logo bottom ~50pt from page top; @page margin-top is set to 76pt.)
"""

import sys
import os
from weasyprint import HTML
import pikepdf


def render_content_pdf(html_path, out_path):
    """Render the HTML+CSS lesson content to a plain (frameless) PDF."""
    base_dir = os.path.dirname(os.path.abspath(html_path)) or '.'
    HTML(html_path, base_url=base_dir).write_pdf(out_path)
    from pypdf import PdfReader
    n = len(PdfReader(out_path).pages)
    print(f'content rendered: {n} pages -> {out_path}')
    return n


def merge_with_template(content_pdf_path, template_pdf_path, final_pdf_path):
    """
    Overlays every page of content_pdf onto a copy of the template page.
    Uses add_underlay with an explicit rect so the template is never
    rescaled (see gotcha #1 above). Also uses a single shared template
    page object underneath the hood (pikepdf handles resource sharing
    automatically here), which keeps file size small even across many
    pages - unlike naively re-reading the template PDF from disk in a
    loop, which balloons file size by duplicating the image data per page.
    """
    content = pikepdf.open(content_pdf_path)
    template = pikepdf.open(template_pdf_path)
    tmpl_page = template.pages[0]

    box = tmpl_page.mediabox
    rect = pikepdf.Rectangle(float(box[0]), float(box[1]), float(box[2]), float(box[3]))

    for page in content.pages:
        page.add_underlay(tmpl_page, rect=rect, shrink=False, expand=False)

    content.save(final_pdf_path)
    size_mb = os.path.getsize(final_pdf_path) / 1_000_000
    print(f'merged with template -> {final_pdf_path} ({size_mb:.1f} MB)')


def build(html_path, final_pdf_path, template_pdf_path='assets/template_pdf.pdf'):
    tmp_content_pdf = final_pdf_path.replace('.pdf', '_content_only.pdf')
    render_content_pdf(html_path, tmp_content_pdf)
    merge_with_template(tmp_content_pdf, template_pdf_path, final_pdf_path)
    os.remove(tmp_content_pdf)
    print(f'done -> {final_pdf_path}')


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print('usage: python render_pdf.py <content.html> <output.pdf> [template_pdf.pdf]')
        sys.exit(1)
    html_path = sys.argv[1]
    out_path = sys.argv[2]
    template = sys.argv[3] if len(sys.argv) > 3 else 'assets/template_pdf.pdf'
    build(html_path, out_path, template)
