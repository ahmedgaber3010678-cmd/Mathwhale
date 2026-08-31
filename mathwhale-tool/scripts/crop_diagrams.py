"""
crop_diagrams.py
=================
Detects, crops, and cleans diagrams from photographed textbook pages.

Workflow for a new lesson:
    1. Put the page photos in uploads/
    2. Run: python scripts/crop_diagrams.py contact uploads/page1.jpg
       -> saves a numbered contact sheet (contact_page1.png) so you can see
          which blob index corresponds to which diagram on the page.
    3. Look at the contact sheet, note the index numbers you want.
    4. Run: python scripts/crop_diagrams.py extract uploads/page1.jpg 3=p149_learn1 7=p149_example1
       -> crops blob #3 and #7, cleans them, saves to assets/diagrams/

Everything is also usable as a library:
    from crop_diagrams import find_blobs, extract_by_index, tight_crop, make_transparent
"""

import sys
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage


# ---------------------------------------------------------------------------
# Core ink detection
# ---------------------------------------------------------------------------

def get_ink_mask(a):
    """
    Returns a boolean mask of 'ink' pixels (drawn lines, text, colored fills)
    as opposed to the white page background or a faint watermark.

    Rule: a pixel counts as ink if it is either
      - colored (channel spread > 15) and not near-white, OR
      - dark (mean < 150) regardless of color/gray
    This deliberately excludes light-gray photographed watermarks (which have
    near-zero channel spread and a mid-to-high mean) while keeping black text,
    magenta/maroon diagram lines, and colored angle-arc fills.
    """
    r = a[:, :, 0].astype(int)
    g = a[:, :, 1].astype(int)
    b = a[:, :, 2].astype(int)
    mx = np.maximum(np.maximum(r, g), b)
    mn = np.minimum(np.minimum(r, g), b)
    spread = mx - mn
    mean = (r + g + b) / 3
    mask = ((spread > 15) & (mean < 245)) | (mean < 150)
    return mask


def find_blobs(path, dilate=25, min_area=1500, pad=12):
    """
    Auto-detects distinct ink regions on a page (paragraphs, diagrams, etc.)
    by dilating the ink mask so nearby elements merge into one blob, then
    finding connected components and reporting each one's tight bounding box
    (computed from the UN-dilated mask, so the box hugs the actual ink).

    Returns (list_of_boxes, PIL_Image). Boxes are (x0, y0, x1, y1) tuples,
    sorted top-to-bottom then left-to-right.
    """
    im = Image.open(path).convert('RGB')
    a = np.array(im)
    mask = get_ink_mask(a)
    struct = np.ones((dilate, dilate))
    dilated = ndimage.binary_dilation(mask, structure=struct)
    labeled, n = ndimage.label(dilated)

    boxes = []
    for i in range(1, n + 1):
        ys, xs = np.where(labeled == i)
        if len(ys) < min_area:
            continue
        y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
        sub_mask = mask[y0:y1 + 1, x0:x1 + 1]
        yys, xxs = np.where(sub_mask)
        if len(yys) == 0:
            continue
        ty0, ty1 = yys.min() + y0, yys.max() + y0
        tx0, tx1 = xxs.min() + x0, xxs.max() + x0
        ty0, tx0 = max(0, ty0 - pad), max(0, tx0 - pad)
        ty1 = min(a.shape[0] - 1, ty1 + pad)
        tx1 = min(a.shape[1] - 1, tx1 + pad)
        boxes.append((tx0, ty0, tx1, ty1))

    boxes.sort(key=lambda b: (b[1] // 50, b[0]))
    return boxes, im


def tight_crop(im, rough_box, pad=10):
    """
    Given a PIL image and a rough (x0,y0,x1,y1) region you eyeballed, tightens
    the crop to the actual ink bounding box within that region (+ pad).
    Use this when find_blobs() merges a diagram with nearby text and you need
    to isolate just the diagram by hand.
    """
    a = np.array(im)
    x0, y0, x1, y1 = rough_box
    sub = a[y0:y1, x0:x1]
    mask = get_ink_mask(sub)
    ys, xs = np.where(mask)
    if len(ys) == 0:
        return im.crop(rough_box)
    ty0, ty1, tx0, tx1 = ys.min(), ys.max(), xs.min(), xs.max()
    ty0, tx0 = max(0, ty0 - pad), max(0, tx0 - pad)
    ty1 = min(sub.shape[0] - 1, ty1 + pad)
    tx1 = min(sub.shape[1] - 1, tx1 + pad)
    return im.crop((x0 + tx0, y0 + ty0, x0 + tx1, y0 + ty1))


# ---------------------------------------------------------------------------
# Cleanup: watermark removal + true transparency
# ---------------------------------------------------------------------------

def clean_watermark(im, spread_thresh=20, mean_thresh=160):
    """
    Whites-out a faint gray photographed watermark (e.g. a semi-transparent
    stamp) without touching colored ink or black text.
    Run this BEFORE make_transparent.
    """
    a = np.array(im).astype(int)
    r, g, b = a[:, :, 0], a[:, :, 1], a[:, :, 2]
    mx = np.maximum(np.maximum(r, g), b)
    mn = np.minimum(np.minimum(r, g), b)
    spread = mx - mn
    mean = (r + g + b) / 3
    mask = (spread < spread_thresh) & (mean > mean_thresh)
    a[mask] = [255, 255, 255]
    return Image.fromarray(a.astype('uint8'), 'RGB')


def make_transparent(im):
    """
    Converts the white/near-white background of a cropped diagram to true
    alpha transparency, so it blends into whatever page background or
    colored box it's placed on (no visible white rectangle).

    Alpha is derived per-pixel as 255 - min(R,G,B): pure white -> alpha 0,
    saturated or dark ink -> alpha ~255, with a smooth falloff for
    anti-aliased edges. Works well for maroon/magenta/black line diagrams;
    for diagrams with pale pastel ink you may need a gentler cutoff.

    Accepts and returns a PIL Image (RGBA).
    """
    a = np.array(im.convert('RGBA')).astype(int)
    r, g, b = a[:, :, 0], a[:, :, 1], a[:, :, 2]
    mn = np.minimum(np.minimum(r, g), b)
    alpha = np.clip(255 - mn, 0, 255)
    alpha[mn > 250] = 0
    a[:, :, 3] = alpha
    return Image.fromarray(a.astype('uint8'), 'RGBA')


def process_diagram(im, save_path, clean=True, transparent=True):
    """Convenience: apply clean_watermark then make_transparent then save."""
    if clean:
        im = clean_watermark(im)
    if transparent:
        im = make_transparent(im)
    im.save(save_path)
    return im


# ---------------------------------------------------------------------------
# Batch helpers
# ---------------------------------------------------------------------------

def extract_by_index(path, indices_names, out_dir='assets/diagrams', pad_extra=0):
    """
    indices_names: dict like {3: 'p149_learn1', 7: 'p149_example1'}
    Crops each blob index found by find_blobs(), cleans it, saves as
    {out_dir}/{name}.png
    """
    import os
    os.makedirs(out_dir, exist_ok=True)
    boxes, im = find_blobs(path)
    results = {}
    for idx, name in indices_names.items():
        if idx >= len(boxes):
            print(f'WARNING: blob index {idx} not found (only {len(boxes)} blobs on this page)')
            continue
        x0, y0, x1, y1 = boxes[idx]
        x0 -= pad_extra
        y0 -= pad_extra
        x1 += pad_extra
        y1 += pad_extra
        crop = im.crop((x0, y0, x1, y1))
        out_path = f'{out_dir}/{name}.png'
        process_diagram(crop, out_path)
        results[name] = out_path
        print(f'{name}: saved to {out_path}, size={crop.size}')
    return results


def contact_sheet(path, out_path='contact.png', max_width=900):
    """
    Renders the page with every detected blob outlined and numbered, so you
    can visually pick which index is which diagram before extracting.
    """
    boxes, im = find_blobs(path)
    draw_im = im.copy()
    d = ImageDraw.Draw(draw_im)
    for i, box in enumerate(boxes):
        d.rectangle(box, outline=(0, 150, 255), width=4)
        d.rectangle([box[0], box[1], box[0] + 55, box[1] + 35], fill=(0, 150, 255))
        d.text((box[0] + 8, box[1] + 3), str(i), fill=(255, 255, 255))
    scale = max_width / draw_im.width
    out = draw_im.resize((int(draw_im.width * scale), int(draw_im.height * scale)))
    out.save(out_path)
    print(f'{len(boxes)} blobs found -> {out_path}')
    return boxes


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == 'contact':
        page_path = sys.argv[2]
        import os
        name = os.path.splitext(os.path.basename(page_path))[0]
        contact_sheet(page_path, out_path=f'contact_{name}.png')

    elif cmd == 'extract':
        page_path = sys.argv[2]
        pairs = {}
        for arg in sys.argv[3:]:
            idx_str, name = arg.split('=')
            pairs[int(idx_str)] = name
        extract_by_index(page_path, pairs)

    else:
        print(f'Unknown command: {cmd}')
        print(__doc__)
