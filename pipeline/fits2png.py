"""
fits2png.py - JWST FITS: HDU classification, metadata extraction, publication PNG rendering.
Zero-cost pipeline (MAST -> GitHub Actions -> Telegram). Pure open-source stack: astropy + numpy + pillow.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from astropy.io import fits
from astropy.visualization import AsinhStretch, ZScaleInterval
from PIL import Image

# HDU EXTNAMEs that are NOT displayable science images
NON_IMAGE_EXT = {"ERR", "DQ", "VAR_POISSON", "VAR_RNOISE", "VAR_FLAT", "WHT", "CON", "IVM"}


def classify_hdus(path):
    """Classify every HDU before any conversion (mission rule: classify first, convert later)."""
    out = []
    with fits.open(path, memmap=False) as hdul:
        for i, hdu in enumerate(hdul):
            shape = None
            dtype = None
            is_image = False
            try:
                if hdu.data is not None:
                    shape = list(np.shape(hdu.data))
                    dtype = str(hdu.data.dtype)
                    is_image = bool(hdu.is_image) and hdu.data.ndim == 2
            except Exception as e:  # unreadable plane: keep it, flag it, never crash the run
                out.append({"index": i, "name": (hdu.name or "PRIMARY"),
                            "class": hdu.__class__.__name__, "is_science_image": False,
                            "shape": None, "dtype": None, "has_wcs": "CTYPE1" in hdu.header,
                            "read_error": f"{type(e).__name__}"})
                continue
            out.append({
                "index": i,
                "name": (hdu.name or "PRIMARY"),
                "class": hdu.__class__.__name__,
                "is_science_image": is_image and (hdu.name not in NON_IMAGE_EXT),
                "shape": shape,
                "dtype": dtype,
                "has_wcs": "CTYPE1" in hdu.header,
            })
    return out


def pick_science_hdu(path):
    """Return index of the first 2-D science image HDU (header-only; skips ERR/DQ/VAR planes)."""
    with fits.open(path, memmap=True) as hdul:
        for i, hdu in enumerate(hdul):
            hdr = hdu.header
            if int(hdr.get("NAXIS", 0)) == 2 and (hdu.name or "PRIMARY") not in NON_IMAGE_EXT \
                    and hdr.get("XTENSION", "PRIMARY") in ("PRIMARY", "IMAGE"):
                return i
    raise ValueError(f"No 2-D science image HDU found in {path}")


def metadata_summary(path):
    """Lightweight metadata-only operation (no full pixel read)."""
    with fits.open(path, memmap=True) as hdul:
        ph = hdul[0].header
        keys = ["TELESCOP", "INSTRUME", "DETECTOR", "FILTER", "PUPIL", "EXPTIME",
                "DATE-OBS", "TARGNAME", "PROPOSID", "PROGRAM", "BUNIT"]
        meta = {k: ph.get(k) for k in keys if ph.get(k) is not None}
        for k in ["FILTER", "EXPTIME", "INSTRUME", "DETECTOR"]:
            if k not in meta:
                for hdu in hdul[1:]:
                    v = hdu.header.get(k)
                    if v is not None:
                        meta[k] = v
                        break
        meta["n_hdus"] = len(hdul)
    return meta


def _to_uint8(norm_data):
    img = np.nan_to_num(norm_data, nan=0.0, posinf=1.0, neginf=0.0)
    return (np.clip(img, 0.0, 1.0) * 255).astype(np.uint8)


def to_png(path, out_path, hdu_index=None, max_side=4096, asinh_a=0.1):
    """ZScale + asinh stretch -> 8-bit grayscale PNG. Returns artifact info."""
    with fits.open(path, memmap=False) as hdul:  # memmap off: BZERO/BSCALE files need scaling
        idx = pick_science_hdu(path) if hdu_index is None else hdu_index
        data = np.asarray(hdul[idx].data, dtype=np.float32)

    finite = data[np.isfinite(data)]
    if finite.size == 0:
        raise ValueError("All-NaN image data")
    vmin, vmax = ZScaleInterval().get_limits(finite)
    stretched = AsinhStretch(a=asinh_a)((finite - vmin) / max(vmax - vmin, 1e-12))
    norm = np.full_like(data, np.nan, dtype=np.float32)
    norm[np.isfinite(data)] = stretched

    h, w = data.shape
    scale = min(1.0, max_side / max(h, w))
    img8 = _to_uint8(norm)
    if scale < 1.0:
        img8 = np.asarray(Image.fromarray(img8).resize((int(w * scale), int(h * scale)), Image.LANCZOS))
    Image.fromarray(img8).save(out_path, optimize=True)
    return {"png": str(out_path), "source_hdu": idx,
            "dims": [int(img8.shape[1]), int(img8.shape[0])],
            "bytes": Path(out_path).stat().st_size,
            "vmin": float(vmin), "vmax": float(vmax)}


def analysis_payload(meta):
    """Interface for the future Vision step: input=metadata dict, output=JSON text.
    Today it is explicitly MOCK (mission rule: never publish mock as real AI analysis)."""
    payload = {
        "mock": True,
        "warning": "MOCK ANALYSIS - not a scientific AI result",
        "telescope": meta.get("TELESCOP"),
        "instrument": meta.get("INSTRUME"),
        "detector": meta.get("DETECTOR"),
        "filter": meta.get("FILTER"),
        "exptime_s": meta.get("EXPTIME"),
        "target": meta.get("TARGNAME"),
        "obs_date": meta.get("DATE-OBS"),
        "proposal_id": meta.get("PROPOSID"),
        "note": "Vision model runs OUTSIDE this pipeline (owner-provided API). "
                "This stub keeps the release path testable.",
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    import sys
    src = Path(sys.argv[1])
    dst = Path(sys.argv[2]) if len(sys.argv) > 2 else src.with_suffix(".png")
    print(json.dumps(metadata_summary(src), ensure_ascii=False)[:1200])
    print(to_png(src, dst))
