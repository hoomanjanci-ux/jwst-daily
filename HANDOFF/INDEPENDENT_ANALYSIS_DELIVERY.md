# Reliable analysis delivery — 2026-10-26

## Independent sender
Cloudflare Worker `jwst-analysis-scheduler` wakes every five minutes and directly
publishes prepared bilingual pairs from dedicated D1 `ai_*` tables. It does not
need a GitHub runner for delivery. Tehran windows remain 06–07, 09–10, 12–13, 18–19.
A unique slot and per-language/per-component receipt prevent duplicate/racing sends.
Known Telegram rejection is retryable; ambiguous acceptance is never blindly resent.
No official-news channel ID, news feed or news secret is present in this Worker.

Preparation/site archiving stay in GitHub. Cloudflare explicitly dispatches them
when the ready reserve is low or a publication needs site sync. A sparse GitHub
cron remains as backup; the former unreliable publication cron is no longer primary.
`analysis_runtime.json` locks the sender to Cloudflare after verified activation:
D1/network failure must never silently turn on a competing GitHub sender.

## Real measured content without provider outages
The old AI editor was repeatedly rejecting source metadata as 'not exciting',
sometimes hallucinating that real JWST filters/detector names were invalid. The
text service also returned 503. The new production research object is computed
from the actual FITS science plane: robust median/MAD, valid sampled pixel count,
and bright-tail fraction. DO_NOT_USE/SATURATED DQ pixels are excluded. Source
statistics and method are permanently archived. It never guesses target type,
claims a discovery, counts stars from threshold pixels, or treats a display stretch
as calibrated flux. English and Persian render the SAME numerical object.

The AI provider can select analysis focus from a closed, validated fact-ID schema
with a bounded request timeout. It cannot introduce new factual claims. Both
languages render one shared plan. Such posts explicitly say 'AI-assisted focus
selection'. On provider failure, posts honestly say 'computational data analysis',
not 'AI-generated prose'.
No placeholder template or invented scientific result is used when an API fails.
The image/evidence validity gate remains mandatory; blank/low-quality data is held.
The shared legacy AI/news writer and news quality policy are not changed.

## Security and activation
Read-only infrastructure probe confirmed Workers, subdomain and D1 access.
Tokens live only in GitHub/Worker encrypted secrets, never code or artifacts.
Deployment seeds previously sent slots to avoid migration duplicates, verifies
Worker reachability and dispatch acceptance, then activates the sender marker.
Cron propagation is external and must be checked through the independent D1
heartbeat, not inferred from a successful deploy command.

## Boundaries
Official-news workflow, news_rss.py and telegram_publish.py are unchanged. The
Persian website remains Persian-only; only new analysis content/site sync changes.
No internet service can promise zero outages or an atomic cross-channel Telegram
transaction. Failures and partial/ambiguous receipts are exposed, not hidden.
