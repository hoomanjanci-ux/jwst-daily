# Owner schedule — 2026-10-25

Replaces adaptive 4–8h/rolling-cap publication. Exactly four independent Tehran
calendar windows: [06:00,07:00), [09:00,10:00), [12:00,13:00), [18:00,19:00).
No 15:00 slot, no rolling 24h cap, no out-of-window catch-up burst. Historical
missed windows are audited, not populated with retroactive posts.

## One research, two languages
`bilingual_analysis.py` generates ONE canonical narrative. Persian is a faithful
translation of that narrative, not a second research generation. Both language
texts pass quality checks BEFORE the pair enters `pipeline/analysis_ready/`.
No template/placeholder posts when an API fails. Ready pairs cache compressed
images and both texts, so slow MAST/AI calls are normally outside delivery windows.
Consumed ready caches are removed after successful archive (bounded repository).

`analysis_slots.py` owns calendar slots. Each slot reserves one product. Receipts
are kept separately per language and album/text component. Both destinations are
required to start. A product is published/archived only after both complete.

## Delivery and persistence
GitHub Actions pushes intent BEFORE each Telegram request and receipts AFTER.
Known 4xx rejection may retry in the SAME window, skipping components already
sent. Timeouts/5xx/crash-ambiguous intents are held for review, never blindly resent.
Telegram has no atomic cross-channel transaction: perfect all-or-nothing delivery
cannot be promised on transport failure. Slot state exposes partial/unverified.

A ready pair is archived in both languages with a common research hash; the public
Persian website still exposes Persian only. Existing auto-deploy + live-page smoke
checks remain. Failed local archiving can retry without Telegram re-publication.

## Workflows / official news boundary
- `jwst-daily.yml` is UNMODIFIED, including its existing RSS polling cron, news
  secrets, translation and publishing steps. `news_rss.py` and
  `telegram_publish.py` are UNMODIFIED.
- Additional `jwst-analysis.yml` ticks every five minutes within the four windows,
  plus pre-generation ticks. ANALYSIS_ONLY=1 means news_rss.publish is NOT invoked;
  it receives no official-channel secrets. Shared concurrency protects state.
- Existing daily wakes can also deliver a ready fixed slot, but have no adaptive
  or out-of-window analysis path anymore. Their news invocation stays identical.
- ai_message.build_post has an optional supplied narrative; its default news
  behaviour is unchanged. News research/generation is untouched.

## Limits / operational truth
GitHub scheduling is best-effort and may drop/delay triggers; it cannot guarantee
four on-time posts every day. The code enforces the windows, refuses duplicates,
and records misses. Quality, provider availability and Telegram errors may leave
an unfilled slot. A separately provisioned reliable scheduler would be needed
for stronger timing guarantees. Never claim a full-day live acceptance test from
unit tests or an out-of-window preparation run.
