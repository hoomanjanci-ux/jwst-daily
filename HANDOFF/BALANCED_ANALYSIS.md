# Balanced analysis publishing — 2026-10-24

Owner authorised an automatic, quality-first cadence, not an hourly quota.

- `pipeline/cadence.py` is the pure scheduling policy. Each product is a bilingual
  publication, not two independent slots. One product max per wake-up.
- Reserve >=5: 4h gap; reserve 3–4: 6h; reserve 1–2: 8h. Absolute cap: 4 products
  per rolling 24h. Missed cron slots never cause catch-up bursts.
- Refill when fewer than 4 unblocked records are ready; maximum reserve 6,
  at most 3 additions per batch. Persist refill attempt before network; 4h backoff.
- Successful batch downloads capped at 900MB per UTC day and 450MB per batch;
  raw FITS is removed as before. This budget excludes publication re-downloads.
- Real publication quality gate: AI text >=60 (when scored), usable image >=40;
  without AI judge, heuristic >=60. Invalid scores fail closed. Gate checks full
  caption and text. Quality-rejected products are held, not spam-retried.
- Existing SHA/product/combo dedupe and ambiguous-send crash guard remain.
- Existing official-news path is unchanged. Deleted test channel remains banned.
- Site archive contains both successfully sent texts and JPEG. If official JPEG
  unavailable, use rendered FITS JPEG. Use actual publication timestamp on site.
- `pipeline/site_sync.json` remains pending until successful deployment. A failed
  deploy is visible as CI failure, and the next scheduled pipeline retries sync
  even when no new analysis is published. No Telegram resend is needed.

Limits: GitHub cron is best effort; MAST/API availability or no acceptable content
can extend silence. Quality is never lowered to meet a quota. Domain/DNS unchanged.
Rollback: revert the balance commit; the persistent published-product ledger must
not be reset, or duplicates could become possible.
