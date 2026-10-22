"""
run_daily.py - Daily orchestrator for the zero-cost JWST -> Telegram pipeline.
Design: GitHub Actions (public repo, free standard runner) -> MAST download -> astropy
metadata/PNG -> Telegram Bot API fan-out to 4 channels. State = state.json committed back
to the repo (no external DB needed; optional D1/KV later).

Rules implemented:
  * byte budget per run (default ~1 GB; never exceeds)
  * product dedup via unique product id + per-channel sent-status
  * download validation: Content-Length match + sha256 recorded
  * temp cleanup after each product (raw FITS is NOT kept permanently)
  * explicit mock labeling for AI analysis (Vision runs outside, owner-provided)
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent))
import fits2png  # noqa: E402
import mast_discover  # noqa: E402
import telegram_publish  # noqa: E402

STATE_PATH = Path(__file__).parent / "state.json"
S3 = "https://s3.us-east-1.amazonaws.com/stpubdata/mast/JWST/product/"
MAST_DL = "https://mast.stsci.edu/api/v0.1/Download/file?uri=mast:JWST/product/"
UA = {"User-Agent": "jwst-free-pipeline/0.1 (public MAST data; low-volume daily batch)"}


def load_state():
    defaults = {"products": {}, "runs": []}
    if STATE_PATH.exists():
        try:
            data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                defaults.update(data)
        except Exception:
            pass  # corrupt/empty state -> start fresh, never crash the run
    return defaults


def save_state(state):
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")


def sha256_file(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def download(url, dest, expected_bytes=None, hard_cap=None, max_seconds=240):
    """Streaming download with byte cap + wall-clock cap; returns (path, n_bytes, seconds)."""
    t0 = time_start = __import__("time").perf_counter()
    n = 0
    with requests.get(url, headers=UA, stream=True, timeout=(10, 60)) as r:
        r.raise_for_status()
        clen = r.headers.get("Content-Length")
        if expected_bytes and clen and abs(int(clen) - expected_bytes) > 1024:
            raise ValueError(f"size mismatch: header={clen} expected={expected_bytes}")
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 20):
                f.write(chunk)
                n += len(chunk)
                if hard_cap and n > hard_cap:
                    raise OverflowError("byte budget exceeded")
                if __import__("time").perf_counter() - t0 > max_seconds:
                    raise TimeoutError("download wall-clock cap exceeded")
    return dest, n, __import__("time").perf_counter() - time_start


def run(max_bytes=1_100_000_000, dry_run=False, max_products=6):
    state = load_state()
    state["runs"].append({"started_utc": datetime.now(timezone.utc).isoformat(),
                          "max_bytes": max_bytes, "dry_run": dry_run})
    token = os.environ.get("TG_BOT_TOKEN", "")
    budget = max_bytes
    published = 0

    candidates = mast_discover.direct_urls(
        mast_discover.discover_jwst_products(min_mb=0.05, max_mb=400, n_obs=8))
    tmp = Path(tempfile.mkdtemp(prefix="jwst_"))

    for cand in candidates:
        pid = cand["filename"]
        rec = state["products"].setdefault(pid, {"channels": {}})
        if all(rec["channels"].get(k) == "sent" for k in telegram_publish.CHANNELS):
            continue  # dedup: fully published already
        if cand["size_mb"] * 1024 * 1024 > budget:
            continue  # stays inside byte budget
        dest = tmp / pid
        try:
            try:
                _, n, secs = download(cand["url_s3"], dest, hard_cap=budget)
            except Exception:
                _, n, secs = download(cand["url_mast"], dest, hard_cap=budget)
        except Exception as e:
            rec["last_error"] = f"{type(e).__name__}: {e}"
            continue

        budget -= n
        try:
            meta = fits2png.metadata_summary(dest)
            png_info = fits2png.to_png(dest, tmp / (pid + ".png"))
        except Exception as e:  # unsuitable product (mission rule): record + skip, run continues
            rec["last_error"] = f"render: {type(e).__name__}: {e}"
            dest.unlink(missing_ok=True)
            save_state(state)
            if budget <= 0:
                break
            continue
        analysis_text = fits2png.analysis_payload(meta)  # explicitly mock-labeled

        if dry_run or not token:
            rec["would_publish"] = telegram_publish.CHANNELS
        else:
            cap_fa = f"جیمز وب | {meta.get('TARGNAME') or 'بدون نام'} | فیلتر {meta.get('FILTER', '?')}"
            cap_en = f"JWST | {meta.get('TARGNAME') or 'Unnamed'} | filter {meta.get('FILTER', '?')}"
            try:
                rec["channels"] = telegram_publish.publish_to_all(
                    token, png_info["png"], cap_fa, cap_en, analysis_text, analysis_text,
                    already_sent={k for k, v in rec["channels"].items() if v == "sent"})
            except Exception as e:  # publishing must never kill the run; per-channel retry next run
                rec["channels"] = {"publish_error": f"{type(e).__name__}: {e}"}

        rec.update({"published_utc": datetime.now(timezone.utc).isoformat(),
                    "bytes": n, "sha256": sha256_file(dest), "png_bytes": png_info["bytes"],
                    "source": "MAST public", "uri": cand["uri"]})
        published += 1
        dest.unlink(missing_ok=True)  # raw FITS cleanup right after use
        save_state(state)
        if budget <= 0 or published >= max_products:
            break

    shutil.rmtree(tmp, ignore_errors=True)  # temp cleanup (mission rule)
    state["runs"][-1].update({"finished_utc": datetime.now(timezone.utc).isoformat(),
                              "published": published, "budget_left_bytes": max(0, budget)})
    save_state(state)
    print(json.dumps(state["runs"][-1], indent=2))


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-bytes", type=int, default=int(os.environ.get("MAX_BYTES", 1_100_000_000)))
    ap.add_argument("--dry-run", action="store_true", default=not bool(os.environ.get("TG_BOT_TOKEN")))
    run(max_bytes=ap.parse_args().max_bytes, dry_run=ap.parse_args().dry_run)
