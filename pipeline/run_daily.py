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
import re
import shutil
import sys
import tempfile
import threading
import time
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import requests
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
import ai_message  # noqa: E402
import annotator  # noqa: E402
import cloudflare  # noqa: E402
import fits2png  # noqa: E402
import mast_discover  # noqa: E402
import mode  # noqa: E402
import news_rss  # noqa: E402
import quality  # noqa: E402
import telegram_publish  # noqa: E402

ROOT = Path(__file__).parent
STATE_PATH = ROOT / "state.json"
ANALYSES = ROOT.parent / "analyses"  # repo-root /analyses (text-only, committed)
UA = {"User-Agent": "jwst-free-pipeline/0.2 (public MAST data; low-volume daily batch)"}

# ---------------------------------------------------------------- anti-duplicate
# Owner directive 2026-10-24 (top priority): a post must NEVER repeat - not after a
# crash, not for a renamed/reprocessed MAST file, not for the same target posted
# back-to-back, not even years from now. Layers implemented here:
#   L1 product ledger (permanent, never evicted - only trimmed) -> same pid never twice
#   L2 sha256 ledger (permanent)       -> same bytes under a new filename never twice
#   L3 combo cooldown (COMBO_MIN_DAYS) -> same TARGNAME|INSTRUME|FILTER not spammed
#   L4 two-phase publish intent        -> a crash can never cause a re-send
#   L5 news title fingerprints (news_rss.py) -> same story via another feed never twice
COMBO_MIN_DAYS = int(os.environ.get("COMBO_MIN_DAYS", "14"))


def _trim_rec(rec):
    """Keep only the dedupe/audit fields of a finished record. The product ledger is
    permanent (owner rule: no repeats even 2+ years later), so every entry must stay
    tiny (~0.3 KB): cand URLs and quality reports are single-run data and are freed
    here. 2 years at ~10 analyzed/day => ~2 MB state.json - far below any limit."""
    for k in ("cand", "quality_log", "last_error", "publish_intent"):
        rec.pop(k, None)


def _combo_of(rec):
    return "|".join([str(rec.get("meta_TARGNAME") or ""),
                     str(rec.get("meta_INSTRUME") or ""),
                     str(rec.get("meta_FILTER") or "")])


def _combo_blocked(state, rec, now=None):
    """True while another product of the same target/instrument/filter combo was
    published within COMBO_MIN_DAYS (channel must not look repetitive)."""
    combo = rec.get("combo") or _combo_of(rec)
    if not combo.strip("|"):
        return False
    ts = (state.get("combo_seen") or {}).get(combo)
    if not ts:
        return False
    try:
        now = now or datetime.now(timezone.utc)
        return (now - datetime.fromisoformat(ts)) < timedelta(days=COMBO_MIN_DAYS)
    except Exception:
        return False


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


def log(msg):
    """Live progress line - always flushed (GH Actions buffers otherwise)."""
    print(f"[jwst {time.strftime('%H:%M:%S', time.gmtime())} UTC] {msg}", flush=True)


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
    """Delegates to mode.py (owner directive 2026-10-24: no test channel anymore;
    per-channel routing — each configured TG_CH_* secret is a live target)."""
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


def _discover_with_watchdog():
    """astroquery has no controllable end-to-end timeout; a stalled MAST portal
    must never eat the whole job (observed 2026-10-23: batch hung 115 min and the
    run died at timeout BEFORE publishing anything). Hard cap: 240 s, then give up
    and let the publish phase proceed (empty batch -> next hourly run retries).
    daemon=True + join(timeout): a hung astroquery thread never blocks the run.
    2026-10-23 addendum: the portal can also return a transient EMPTY result
    (observed 16:05 UTC, same query returned 16 products minutes later) ->
    one 45s-spaced retry before accepting an empty discovery."""
    def _once():
        holder: dict = {}

        def _work():
            try:
                holder["cands"] = mast_discover.direct_urls(
                    mast_discover.discover_jwst_products(min_mb=0.05, max_mb=400, n_obs=8))
            except Exception as e:  # noqa: BLE001 - discovery is best-effort
                holder["err"] = f"{type(e).__name__}: {str(e)[:120]}"

        th = threading.Thread(target=_work, daemon=True)
        th.start()
        th.join(timeout=240)
        if th.is_alive():
            return None, False  # timeout signal
        if "err" in holder:
            log(f"DISCOVERY FAILED: {holder['err']}")
            return [], False
        return holder.get("cands", []), True

    cands, ok = _once()
    if cands is None:  # timeout signal -> normalize to empty list (never None)
        cands = []
    if ok and not cands:  # transient empty portal result -> retry once
        log("DISCOVERY returned 0 candidates - retrying once after 45s "
            "(portal hiccup observed 2026-10-23 16:05 UTC)")
        time.sleep(45)
        cands, ok = _once()
        if ok and not cands:
            log("DISCOVERY retry still 0 candidates - accepting empty batch")
    return cands, ok


def process_batch(state, max_bytes, max_products, tmp, wall_seconds=2100):
    t0 = time.perf_counter()
    cands, discovery_ok = _discover_with_watchdog()
    log(f"BATCH: discovered {len(cands)} candidates (discovery_ok={discovery_ok})")
    budget = max_bytes
    processed = 0
    completed_naturally = discovery_ok
    for i, cand in enumerate(cands, 1):
        pid = cand["filename"]
        elapsed = time.perf_counter() - t0
        if elapsed > wall_seconds:
            log(f"BATCH: wall budget {wall_seconds}s reached ({elapsed:.0f}s) "
                f"- stopping batch, proceeding to publish")
            completed_naturally = True  # time-boxed stop is a NORMAL completion
            break
        log(f"BATCH {i}/{len(cands)}: {pid} ({cand['size_mb']:.1f} MB, "
            f"budget {budget/1048576:.0f} MB left, elapsed {elapsed:.0f}s)")
        rec = state["products"].setdefault(pid, {"channels": {}})
        if rec.get("status") in ("analyzed", "published_test", "published"):
            continue
        if cand["size_mb"] * 1048576 > budget:
            continue
        dest = tmp / pid
        try:
            try:
                n, dl_s = robust_download(cand["url_s3"], dest, hard_cap=budget,
                                          max_seconds=180)
            except Exception:
                n, dl_s = robust_download(cand["url_mast"], dest, hard_cap=budget,
                                          max_seconds=180)
            log(f"BATCH: downloaded {pid} ({n/1048576:.1f} MB in {dl_s:.0f}s)")
        except Exception as e:  # noqa: BLE001
            rec["last_error"] = f"download: {type(e).__name__}: {e}"
            log(f"BATCH: download FAILED {pid}: {type(e).__name__}")
            continue
        budget -= n
        try:
            meta, raw_png, region, score, img8 = _render_and_score(dest, tmp, pid)
            log(f"BATCH: rendered+scored {pid} (score={score})")
        except Exception as e:  # noqa: BLE001 - unsuitable product: record + skip
            rec["last_error"] = f"render: {type(e).__name__}: {e}"
            dest.unlink(missing_ok=True)
            if budget <= 0:
                break
            continue

        # L2 anti-duplicate: MAST reprocesses files under NEW filenames - identical
        # bytes must never be analyzed/posted twice (owner rule 2026-10-24).
        sha = sha256_file(dest)
        dup = next((p for p, r in state["products"].items()
                    if p != pid and r.get("sha256") == sha), None)
        if dup:
            rec.update({"status": "duplicate_sha", "sha256": sha, "duplicate_of": dup})
            log(f"BATCH: DUPLICATE bytes {pid} == {dup} - skipped (never-repeat rule)")
            dest.unlink(missing_ok=True)
            raw_png.unlink(missing_ok=True)
            if budget <= 0:
                break
            continue

        target = str(meta.get("TARGNAME") or "")
        combo = "|".join([target, str(meta.get("INSTRUME") or ""),
                          str(meta.get("FILTER") or "")])
        # L3 anti-duplicate: same TARGNAME|INSTRUME|FILTER combo within the cooldown
        # window is skipped BEFORE analysis (saves AI cost + keeps the feed varied).
        if _combo_blocked(state, {"meta_TARGNAME": target,
                                  "meta_INSTRUME": str(meta.get("INSTRUME") or ""),
                                  "meta_FILTER": str(meta.get("FILTER") or "")}):
            rec.update({"status": "combo_cooldown", "combo": combo, "sha256": sha})
            log(f"BATCH: combo cooldown hit for {target} - skipped "
                f"(published within last {COMBO_MIN_DAYS}d)")
            dest.unlink(missing_ok=True)
            raw_png.unlink(missing_ok=True)
            if budget <= 0:
                break
            continue
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
            "meta_INSTRUME": str(meta.get("INSTRUME") or ""),
            "combo": combo, "sha256": sha,
            "bytes": n, "published_utc": None,
        })
        dest.unlink(missing_ok=True)   # raw FITS freed immediately (mission rule)
        raw_png.unlink(missing_ok=True)
        save_state(state)
        processed += 1
        log(f"BATCH: ANALYZED {processed}/{max_products}: {pid} -> ledger")
        if budget <= 0 or processed >= max_products:
            break
    log(f"BATCH DONE: processed={processed}, elapsed={time.perf_counter()-t0:.0f}s")
    return processed, completed_naturally


def publish_one(pid, state, token, targets, tmp):
    # Defense at the send boundary: analyses must never reach news/test targets.
    targets = [t for t in targets if t[0] in ("fa_ai", "en_ai") and t[1] != "-1004335173102"]
    if not targets:
        return False
    rec = state["products"][pid]
    cand = rec.get("cand") or {}
    dest = tmp / pid

    # ---- L4 anti-duplicate: two-phase publish (crash guard) --------------------
    # Owner rule 2026-10-24: duplicates are ABSOLUTELY forbidden. Observed risk:
    # a run that dies BETWEEN a Telegram send and the state commit would re-send
    # on the next run (this actually happened 2026-10-23 15:19 UTC - album went
    # out, run cancelled, ledger never recorded it). Fix: the publish intent is
    # written to state BEFORE the first send and every per-target result is
    # committed immediately after its send. On retry, any intended target whose
    # outcome is AMBIGUOUS (no record, or a send-phase error) is skipped FOREVER:
    # under-posting is recoverable, a duplicate is not.
    intent = rec.get("publish_intent") or {}
    intended = set(intent.get("targets") or [])
    prior = rec.get("channels") or {}

    def _ambiguous(k):
        v = prior.get(k)
        if v == "sent":
            return False          # verified delivered -> never send again
        if v is None:
            return True           # intent existed, no record -> may be live
        s = str(v)
        return s.startswith("error") or "unverified" in s  # send-phase ambiguity

    guarded_keys = {k for k in intended if _ambiguous(k)}
    verified_sent = {k for k, v in prior.items() if v == "sent"}
    if guarded_keys:
        log(f"PUBLISH {pid}: crash-guard active for {sorted(guarded_keys)} "
            f"(prior attempt unverified - these will NEVER be resent)")
    try:
        try:
            robust_download(cand["url_s3"], dest)
        except Exception:
            robust_download(cand["url_mast"], dest)
    except Exception as e:  # noqa: BLE001
        rec["last_error"] = f"re-download: {type(e).__name__}: {e}"
        rec["redl_fails"] = int(rec.get("redl_fails") or 0) + 1
        if rec["redl_fails"] >= 3:
            # MAST URLs expire; after 3 failed attempts stop retrying so the
            # publish queue cannot be blocked forever by one dead product.
            rec["status"] = "stale_unrecoverable"
            log(f"PUBLISH {pid}: re-download failed {rec['redl_fails']}x -> "
                f"parked as stale_unrecoverable (queue unblocked)")
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
        mock = json.loads(fits2png.analysis_payload(meta))
        sci_payload = {k: v for k, v in mock.items()
                       if k not in ("mock", "warning", "note") and v is not None}
        if prop and not sci_payload.get("proposal_id"):
            sci_payload["proposal_id"] = prop

        # Beautiful per-(kind, lang) content (style package 2026-10-23), built ONCE
        # per product: only AI channels receive analyses. Official news is handled
        # separately by news_rss.publish; there is no test-channel fallback.
        contents: dict[tuple[str, str], tuple[str, str, str]] = {}

        def _content(kind: str, lang: str):
            ck = (kind, lang)
            if ck not in contents:
                contents[ck] = ai_message.build_post(meta, prop, sci_payload, kind, lang)
            return contents[ck]

        results = {}
        sent_contents: dict[tuple[str, str], tuple[str, str, str]] = {}

        def _mark(key: str, val: str):
            """Record one target outcome AND commit it immediately (phase-2 of the
            crash guard: a crash after a real send leaves a durable 'sent' mark,
            so the next run can never duplicate it)."""
            results[key] = val
            rec["channels"] = {**rec.get("channels", {}), key: val}
            save_state(state)

        # Quality report is memoized per (kind, lang): identical inputs otherwise
        # cost up to (90s x2 attempts + 240s vision) x 5 targets per product,
        # which alone could eat the whole job budget (fix 2026-10-23).
        qcache: dict[tuple[str, str], dict] = {}
        # Phase-1: publish intent recorded BEFORE any send (see L4 comment above).
        rec["publish_intent"] = {"utc": _iso_now(),
                                 "targets": [k for k, _c, _l in targets]}
        save_state(state)
        for key, chat_id, lang in targets:
            kind = "ai"
            if prior.get(key) == "sent":  # defense-in-depth: already verified
                _mark(key, "skipped (already verified sent)")
                continue
            if key in guarded_keys:  # ambiguous prior attempt -> never resend
                _mark(key, "crash-guard (unverified prior attempt - never resent)")
                continue
            cap, txt, _gen = _content(kind, lang)
            try:
                ck = (kind, lang)
                if ck not in qcache:
                    qcache[ck] = quality.full_report(
                        np.asarray(Image.open(imgs[0]).convert("L")),
                        rec.get("score") or 0, cap, sci_payload, raw_png)
                q = qcache[ck]
                q["post_generator"] = _gen  # 'ai' | 'template' - style audit trail
                if not quality.passes_gate(q):
                    _mark(key, "held (quality gate)")
                    rec.setdefault("quality_log", {})[key] = q
                    continue
                log(f"PUBLISH {pid}: sending album+text to {key}")
                telegram_publish.send_album(token, chat_id, imgs, cap)
                telegram_publish.send_message(token, chat_id, txt)
                _mark(key, "sent")
                log(f"PUBLISH {pid}: SENT -> {key}")
                sent_contents[(kind, lang)] = (cap, txt, _gen)
                rec.setdefault("quality_log", {})[key] = q
                save_state(state)
            except Exception as e:  # noqa: BLE001 - per-target isolation
                _mark(key, f"error: {type(e).__name__}: {e}")
                tb = traceback.format_exc().splitlines()[-4:]
                rec.setdefault("quality_log", {})[key] = {"error_trace": " | ".join(tb)}
                print(f"PUBLISH-ERROR {pid} {key}: {traceback.format_exc()}", flush=True)
        rec["channels"] = {**rec.get("channels", {}), **results}
        any_sent_now = any(v == "sent" for v in results.values())
        if any_sent_now or verified_sent:  # verified_sent: prior-run sends count too
            rec.pop("publish_intent", None)
            rec["status"] = "published"
            rec["published_utc"] = rec.get("published_utc") or _iso_now()
            # SITE-ARCHIVE (owner-approved 2026-10-23, future posts only): persist the
            # rendered Telegram content + preview image next to the analysis JSON so the
            # website (site/) can show the full post. Additive-only; must NEVER break
            # publishing -> fully wrapped in try/except.
            try:
                arch_dir = analysis_path.parent
                doc = {"product": pid, "published_utc": rec["published_utc"], "items": {}}
                for (k_, l_), (c_, t_, g_) in sent_contents.items():
                    doc["items"][f"{k_}_{l_}"] = {"caption": c_, "text": t_, "generator": g_}
                (arch_dir / (Path(pid).stem + ".post.json")).write_text(
                    json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
                if ok_prev and prev.exists():
                    (arch_dir / (Path(pid).stem + ".jpg")).write_bytes(prev.read_bytes())
            except Exception:
                pass
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
            # L3 anti-duplicate: register the combo AFTER a real publish, then trim
            # the record to its permanent dedupe/audit core (ledger stays tiny).
            state.setdefault("combo_seen", {})[_combo_of(rec)] = _iso_now()
            _trim_rec(rec)
            save_state(state)
            return True
        # Nothing was sent now and nothing was verified before: if every target is
        # ambiguous (crash-guard), park the product permanently - owner rule:
        # resending MIGHT duplicate, and duplicates are absolutely forbidden.
        actionable = [k for k, v in results.items()
                      if not str(v).startswith(("crash-guard", "skipped"))]
        if (not actionable and not verified_sent
                and any(str(v).startswith("crash-guard") for v in results.values())):
            rec.pop("publish_intent", None)
            rec["status"] = "publish_unverified"
            rec["unverified_utc"] = _iso_now()
            save_state(state)
            log(f"PUBLISH {pid}: ALL targets unverified -> parked as publish_unverified "
                f"(never auto-resent; manual review required)")
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
            wall = int(os.environ.get("BATCH_WALL_MINUTES", "35")) * 60
            processed, natural = process_batch(state, max_bytes, max_products, tmp,
                                               wall_seconds=wall)
            summary["batch_processed"] = processed
            # last_batch updates ONLY on a real completion; a discovery failure
            # must be retried by the NEXT hourly run (publish still runs now).
            if natural:
                state["last_batch_utc"] = _iso_now()
            else:
                summary["batch_retry_next_run"] = True

        all_pending = [(pid, rec.get("score") or 0)
                       for pid, rec in state["products"].items()
                       if rec.get("status") == "analyzed"]
        # L3 anti-duplicate: products whose target/instrument/filter combo was
        # published within COMBO_MIN_DAYS wait here (never deleted - data kept).
        blocked = [(pid, s) for pid, s in all_pending
                   if _combo_blocked(state, state["products"][(pid)])]
        pending = sorted((p for p in all_pending if p not in blocked),
                         key=lambda x: -x[1])
        if blocked:
            summary["combo_cooldown_blocked"] = [p for p, _s in blocked]
            log(f"PUBLISH: {len(blocked)} product(s) held by combo cooldown: "
                f"{[p for p, _s in blocked]}")
        ai_only = mode.ai_targets()
        summary["pending_before"] = len(pending)
        log(f"PUBLISH: {len(pending)} analyzed products pending, "
            f"publishing top {min(publish_count, len(pending))} -> "
            f"{[t[0] for t in ai_only]}")
        published = []
        if token and ai_only:
            for pid, _s in pending[:publish_count]:
                log(f"PUBLISH: building album for {pid}")
                if publish_one(pid, state, token, ai_only, tmp):
                    published.append(pid)
                    log(f"PUBLISH: OK {pid}")
                else:
                    log(f"PUBLISH: FAILED {pid} (see ledger last_error)")
        else:
            summary["note"] = "publish deferred (no token/AI targets configured)"
        summary["published"] = published
        try:  # official news feeds -> news channels (never breaks the main pipeline)
            summary["news"] = news_rss.publish(state, token, targets)
        except Exception as e:  # noqa: BLE001
            summary["news"] = {"error": f"{type(e).__name__}: {str(e)[:120]}"}
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
