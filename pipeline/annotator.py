"""
annotator.py - Deterministic region-of-interest detection + red-box annotation.
No AI required (works before Vision API arrives): sliding-window structure score,
non-max suppression, relative-coordinate boxes. The SAME relative box is applied to
the FITS render and to the official MAST preview JPEG (approximate mapping).
The stored fractions are the annotation "memory" the future Vision step will refine.
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


def _windows(h, w, win):
    step = max(win // 2, 1)
    margin = win // 2  # skip detector edge artifacts: keep windows off the borders
    y0, x0 = (margin if h > win + margin else 0), (margin if w > win + margin else 0)
    ys = range(y0, max(h - win - margin, y0) + 1, step) or range(0, max(h - win, 1) + 1, step)
    xs = range(x0, max(w - win - margin, x0) + 1, step) or range(0, max(w - win, 1) + 1, step)
    for y in ys:
        for x in xs:
            yield y, x


def find_regions(img8, n_regions=1, win=96, pad=0.35):
    """img8: 2-D uint8 (the stretched render). Score = per-window std (structure proxy).
    Returns regions with absolute px + relative fractions (fractions are what we store)."""
    h, w = img8.shape
    win = max(8, min(win, h // 2 or 1, w // 2 or 1))
    cands = []
    for y, x in _windows(h, w, win):
        patch = img8[y:y + win, x:x + win].astype(np.float32)
        cands.append((float(patch.std()), x, y))
    cands.sort(reverse=True)
    regions = []
    for s, x, y in cands:
        if all(abs(x - cx) > win and abs(y - cy) > win for _, cx, cy in regions):
            regions.append((s, x, y))
        if len(regions) >= n_regions:
            break
    out = []
    for s, x, y in regions:
        d = int(win * pad)
        x0, y0 = max(0, x - d), max(0, y - d)
        x1, y1 = min(w, x + win + d), min(h, y + win + d)
        out.append({"x0": int(x0), "y0": int(y0), "x1": int(x1), "y1": int(y1),
                    "fx0": round(x0 / w, 4), "fy0": round(y0 / h, 4),
                    "fx1": round(x1 / w, 4), "fy1": round(y1 / h, 4),
                    "score": round(s, 2)})
    return out


def score_image(img8, regions):
    """Deterministic interestingness score (no AI): structure std of best region +
    global contrast. Replaced by Vision-model scoring once the API is connected."""
    g = float(np.asarray(img8, dtype=np.float32).std())
    r = regions[0]["score"] if regions else 0.0
    return round(0.7 * r + 0.3 * g, 2)


def annotate(src_png, region, out_png, color=(255, 45, 45), width=6, label=None):
    """Draw the red box at the region's RELATIVE coordinates on any image that shares
    the same frame (FITS render or official preview JPEG). Returns artifact info."""
    im = Image.open(src_png).convert("RGB")
    d = ImageDraw.Draw(im)
    W, H = im.size
    box = [region["fx0"] * W, region["fy0"] * H, region["fx1"] * W, region["fy1"] * H]
    for k in range(width):
        d.rectangle([box[0] - k, box[1] - k, box[2] + k, box[3] + k], outline=color)
    if label:
        d.text((box[0] + 8, max(2, box[1] - 14)), label, fill=(255, 235, 120))
    im.save(out_png, optimize=True)
    return {"png": str(out_png), "bytes": os.path.getsize(out_png),
            "dims": [int(W), int(H)]}


if __name__ == "__main__":
    import sys, json
    im = Image.open(sys.argv[1]).convert("L")
    arr = np.asarray(im)
    regs = find_regions(arr)
    print(json.dumps(regs, indent=1))
    info = annotate(sys.argv[1], regs[0], sys.argv[2], label="ROI-1 (deterministic)")
    print(json.dumps(info))
