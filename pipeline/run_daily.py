"""
run_daily.py - v0.2 orchestrator (hourly-cron driven, one workflow does everything).

  1) BATCH (only if last batch > batch_gap_hours ago, default ~20h):
     discover -> download -> render -> deterministic ROI detection -> score ->
     store TEXT analysis JSON in analyses/ (committed to repo) -> free the FITS.
  2) PUBLISH (every run): take top-N unpublished analyses by score -> re-download that
     product (fast on the runner; nothing image-like is stored permanently) ->
     build the 4-image album (FITS raw, FITS annotated, official MAST preview JPEG raw,
     preview annotated with the same ROI) -> send FA album + EN album -> mark published.

State = state.json committed back to the repo (persistence + keepalive).
Raw FITS never persists beyond the run (mission rule). Analysis text persists forever
(small) - that is the memory the future Vision step will condition on.
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import shutil
import sys
import tempfile
import time
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import requests
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
import annotator  # noqa: E402
import cloudflare  # noqa: E402
import fits2png  # noqa: E402
import mast_discover  # noqa: E402
import mode  # noqa: E402
import quality  # noqa: E402
import telegram_publish  # noqa: E402

ROOT = Path(__file__).parent
STATE_PATH = ROOT / "state.json"
ANALYSES = ROOT.parent / "analyses"  # repo-root /analyses (text-only, committed)
UA = {"User-Agent": "jwst-free-pipeline/0.2 (public MAST data; low-volume daily batch)"}


def _iso_now():
    return datetime.now(timezone.utc).isoformat()


def load_state():
    defaults = {"products": {}, "runs": [], "last_batch_utc": None}
    if STATE_PATH.exists():
        try:
            data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                defaults.update(data)
        except Exception:
            pass
    for rec in defaults["products"].values():  # v0.1 ledger migration
        rec.setdefault("status", "legacy_v01")
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


def robust_download(url, dest, hard_cap=None, max_seconds=300, attempts=3):
    """Streaming download with retry/backoff (429 obeys Retry-After), byte + wall caps.
    Returns (n_bytes, seconds)."""
    t0 = time.perf_counter()
    last_err = None
    for a in range(attempts):
        n = 0
        try:
            with requests.get(url, headers=UA, stream=True, timeout=(10, 60)) as r:
                r.raise_for_status()
                with open(dest, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1 << 20):
                        f.write(chunk)
                        n += len(chunk)
                        if hard_cap and n > hard_cap:
                            raise OverflowError("byte budget exceeded")
                        if time.perf_counter() - t0 > max_seconds:
                            raise TimeoutError("download wall-clock cap exceeded")
            return n, time.perf_counter() - t0
        except Exception as e:  # noqa: BLE001 - retry any transport-level failure
            last_err = e
            time.sleep(min(2 ** a, 8) + random.uniform(0, 1))
    raise last_err  # type: ignore[misc]


def publish_targets():
    """Delegates to mode.py (owner directive: TEST-ONLY until explicit go-ahead).
    Public channels activate ONLY with their 4 secrets set AND PROD_UNLOCKED=yes."""
    return mode.publish_targets()


def _render_and_score(dest, tmp, pid):
    """Render raw PNG + detect ROI + score. Returns (meta, raw_png, region, score, img8)."""
    meta = fits2png.metadata_summary(dest)
    raw_png = tmp / f"{pid}.raw.png"
    fits2png.to_png(dest, raw_png)
    img8 = np.asarray(Image.open(raw_png).convert("L"))
    regions = annotator.find_regions(img8, n_regions=1)
    if not regions:
        raise ValueError("no ROI found")
    return meta, raw_png, regions[0], annotator.score_image(img8, regions), img8


def process_batch(state, max_bytes, max_products, tmp):
    cands = mast_discover.direct_urls(
        mast_discover.discover_jwst_products(min_mb=0.05, max_mb=400, n_obs=8))
    budget = max_bytes
    processed = 0
    for cand in cands:
        pid = cand["filename"]
        rec = state["products"].setdefault(pid, {"channels": {}})
        if rec.get("status") in ("analyzed", "published_test", "published"):
            continue
        if cand["size_mb"] * 1048576 > budget:
            continue
        dest = tmp / pid
        try:
            try:
                n, _ = robust_download(cand["url_s3"], dest, hard_cap=budget)
            except Exception:
                n, _ = robust_download(cand["url_mast"], dest, hard_cap=budget)
        except Exception as e:  # noqa: BLE001
            rec["last_error"] = f"download: {type(e).__name__}: {e}"
            continue
        budget -= n
        try:
            meta, raw_png, region, score, img8 = _render_and_score(dest, tmp, pid)
        except Exception as e:  # noqa: BLE001 - unsuitable product: record + skip
            rec["last_error"] = f"render: {type(e).__name__}: {e}"
            dest.unlink(missing_ok=True)
            if budget <= 0:
                break
            continue

        target = str(meta.get("TARGNAME") or "")
        prior = [p for p, r in state["products"].items()
                 if r.get("meta_TARGNAME", "") == target and p != pid][:5]  # memory seeds
        day = _iso_now()[:10].replace("-", "/")
        adir = ANALYSES / day
        adir.mkdir(parents=True, exist_ok=True)
        analysis = {
            "ts": _iso_now(), "product": pid, "uri": cand["uri"],
            "proposal": str(cand.get("proposal") or ""), "meta": meta,
            "region": region, "score": score,
            "quality": quality.heuristic_scores(img8, score),
            "mock_analysis": json.loads(fits2png.analysis_payload(meta)),
            "prior_refs": prior, "bytes": n, "sha256": sha256_file(dest),
            "source": "MAST public data",
        }
        (adir / f"{pid}.json").write_text(
            json.dumps(analysis, ensure_ascii=False, indent=1), encoding="utf-8")
        rec.update({
            "status": "analyzed", "score": score,
            "analysis": f"analyses/{day}/{pid}.json",
            "cand": {"filename": pid, "size_mb": cand["size_mb"], "uri": cand["uri"],
                     "proposal": str(cand.get("proposal") or ""),
                     "obs_id": str(cand.get("obs_id") or ""),
                     "url_mast": cand["url_mast"], "url_s3": cand["url_s3"],
                     "url_preview": cand["url_preview"]},
            "meta_TARGNAME": target, "meta_FILTER": str(meta.get("FILTER") or ""),
            "bytes": n, "published_utc": None,
        })
        dest.unlink(missing_ok=True)   # raw FITS freed immediately (mission rule)
        raw_png.unlink(missing_ok=True)
        save_state(state)
        processed += 1
        if budget <= 0 or processed >= max_products:
            break
    return processed


def _captions(meta, prop):
    targ = str(meta.get("TARGNAME") or "-")
    filt = str(meta.get("FILTER") or "?")
    inst = str(meta.get("INSTRUME") or "?")
    dateobs = str(meta.get("DATE-OBS") or "")[:10]
    cap_fa = (f"🔭 جیمز وب | {targ}\n"
              f"ابزار: {inst} | فیلتر: {filt} | تاریخ مشاهده: {dateobs}\n"
              f"پروپوزال: {prop} | منبع: MAST/STScI (دادهٔ عمومی)\n"
              f"کادر قرمز: ناحیهٔ منتخب (تشخیص قطعی - تحلیل AI به‌زودی)")
    cap_en = (f"🔭 JWST | {targ}\n"
              f"Instrument: {inst} | filter: {filt} | obs date: {dateobs}\n"
              f"Proposal: {prop} | Source: MAST/STScI public data\n"
              f"Red box: selected ROI (deterministic - AI analysis coming soon)")
    return cap_fa, cap_en


def publish_one(pid, state, token, targets, tmp):
    rec = state["products"][pid]
    cand = rec.get("cand") or {}
    dest = tmp / pid
    try:
        try:
            robust_download(cand["url_s3"], dest)
        except Exception:
            robust_download(cand["url_mast"], dest)
    except Exception as e:  # noqa: BLE001
        rec["last_error"] = f"re-download: {type(e).__name__}: {e}"
        return False

    try:
        meta, raw_png, region_re, _score, _img8 = _render_and_score(dest, tmp, pid)
        region = region_re
        analysis_path = ROOT.parent / (rec.get("analysis") or "")
        if analysis_path.exists():  # stored ROI guarantees consistency with the ledger
            try:
                region = json.loads(analysis_path.read_text(encoding="utf-8"))["region"]
            except Exception:
                pass
        ann_png = tmp / f"{pid}.ann.png"
        annotator.annotate(raw_png, region, ann_png, label="ROI-1")
        imgs = [raw_png, ann_png]

        prev = tmp / (Path(pid).stem + ".jpg")
        ok_prev = False
        try:
            r = requests.get(cand["url_preview"], headers=UA, timeout=90)
            if r.status_code == 200 and len(r.content) > 20000:
                prev.write_bytes(r.content)
                ok_prev = True
        except Exception:
            pass
        if ok_prev:
            prev_ann = tmp / (Path(pid).stem + ".ann.jpg")
            annotator.annotate(prev, region, prev_ann, label="ROI-1")
            imgs += [prev, prev_ann]

        prop = str(cand.get("proposal") or meta.get("PROPOSID") or "")
        cap_fa, cap_en = _captions(meta, prop)
        mock = json.loads(fits2png.analysis_payload(meta))
        txt_fa = ("<pre>وضعیت: تحلیل هوش مصنوعی هنوز متصل نشده است (داده آزمایشی)\n"
                  + json.dumps(mock, ensure_ascii=False, indent=1) + "</pre>")
        txt_en = ("<pre>AI analysis not connected yet (mock payload)\n"
                  + json.dumps(mock, ensure_ascii=False, indent=1) + "</pre>")

        results = {}
        for key, chat_id, lang in targets:
            cap, txt = (cap_fa, txt_fa) if lang == "fa" else (cap_en, txt_en)
            try:
                q = quality.full_report(np.asarray(Image.open(imgs[0]).convert("L")),
                                        rec.get("score") or 0, cap, mock, raw_png)
                if not quality.passes_gate(q):
                    results[key] = "held (quality gate)"
                    rec.setdefault("quality_log", {})[key] = q
                    continue
                telegram_publish.send_album(token, chat_id, imgs, cap)
                telegram_publish.send_message(token, chat_id, txt)
                results[key] = "sent"
                rec.setdefault("quality_log", {})[key] = q
            except Exception as e:  # noqa: BLE001 - per-target isolation
                results[key] = f"error: {type(e).__name__}: {e}"
                tb = traceback.format_exc().splitlines()[-4:]
                rec.setdefault("quality_log", {})[key] = {"error_trace": " | ".join(tb)}
                print(f"PUBLISH-ERROR {pid} {key}: {traceback.format_exc()}", flush=True)
        rec["channels"] = {**rec.get("channels", {}), **results}
        if any(v == "sent" for v in results.values()):
            rec["status"] = "published_test" if any(k.startswith("test") for k, v in results.items() if v == "sent") else "published"
            rec["published_utc"] = _iso_now()
            if cloudflare.configured():  # D1 mirror (non-blocking, owner phase-2)
                try:
                    qlog = rec.get("quality_log") or {}
                    ai_s = next(((v.get("ai_message") or {}).get("score")
                                 for v in qlog.values() if isinstance(v, dict)), None)
                    ok_cf, det_cf = cloudflare.sync_analysis(
                        pid, rec["published_utc"], meta, rec.get("score") or 0,
                        ai_s, results, str(rec.get("analysis") or ""))
                    rec["d1_sync"] = "ok" if ok_cf else f"failed: {str(det_cf)[:80]}"
                except Exception as e:  # noqa: BLE001 - D1 mirror must never break publish
                    rec["d1_sync"] = f"error: {type(e).__name__}"
            return True
        return False
    except Exception as e:  # noqa: BLE001
        rec["last_error"] = f"publish: {type(e).__name__}: {e}"
        return False
    finally:
        dest.unlink(missing_ok=True)


def run(max_bytes=1_100_000_000, max_products=6, publish_count=2, batch_gap_hours=20):
    state = load_state()
    token = os.environ.get("TG_BOT_TOKEN", "")
    targets = publish_targets()
    tmp = Path(tempfile.mkdtemp(prefix="jwst_"))
    summary = {"started_utc": _iso_now(), "mode": mode.status_line()}
    try:
        need_batch = True
        if state.get("last_batch_utc"):
            try:
                need_batch = (datetime.now(timezone.utc)
                              - datetime.fromisoformat(state["last_batch_utc"])
                              > timedelta(hours=batch_gap_hours))
            except Exception:
                need_batch = True
        summary["batch_ran"] = bool(need_batch)
        if need_batch:
            summary["batch_processed"] = process_batch(state, max_bytes, max_products, tmp)
            state["last_batch_utc"] = _iso_now()

        pending = sorted(((pid, rec.get("score") or 0)
                          for pid, rec in state["products"].items()
                          if rec.get("status") == "analyzed"),
                         key=lambda x: -x[1])
        summary["pending_before"] = len(pending)
        published = []
        if token and targets:
            for pid, _s in pending[:publish_count]:
                if publish_one(pid, state, token, targets, tmp):
                    published.append(pid)
        else:
            summary["note"] = "publish deferred (no token/targets configured)"
        summary["published"] = published
        summary["cloudflare"] = "configured" if cloudflare.configured() else "off (waiting owner token)"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        summary["finished_utc"] = _iso_now()
        state.setdefault("runs", []).append(summary)
        state["runs"] = state["runs"][-50:]
        save_state(state)
        print(json.dumps(summary, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-bytes", type=int,
                    default=int(os.environ.get("MAX_BYTES", 1_100_000_000)))
    ap.add_argument("--max-products", type=int,
                    default=int(os.environ.get("MAX_PRODUCTS", 6)))
    ap.add_argument("--publish-count", type=int,
                    default=int(os.environ.get("PUBLISH_COUNT", 2)))
    ap.add_argument("--batch-gap-hours", type=int,
                    default=int(os.environ.get("BATCH_GAP_HOURS", 20)))
    a = ap.parse_args()
    run(max_bytes=a.max_bytes, max_products=a.max_products,
        publish_count=a.publish_count, batch_gap_hours=a.batch_gap_hours)
