# Persian site mobile detail fix — 2026-10-24

- Reproduced a 397px layout viewport on 320/390px mobile analysis detail pages.
  Long FITS identifiers/table min-content widths widened the RTL scrollable area.
- Scope wrapping and stacked table sizing to `.analysis-detail` below 768px.
  Do not mask the issue by clipping the article or change desktop table layout.
- Public website exposes Persian channel descriptors only; remove English-channel
  references from homepage, footer, header tooltip, organization JSON-LD and the
  generated site data. Persian analysis pages do not include English Telegram copy.
- English Telegram publishing and bilingual repository archives remain unchanged.
- `site/scripts/test-mobile-layout.cjs` checks every Persian analysis at 10 viewport
  widths, long-content bounds, mobile tap navigation and English-channel leakage.
  Optional local test dependency: Playwright (see script header). Run against an
  exported-site server, or set TEST_SITE_URL to the deployed site.
- Production build passed; 40 page/viewport checks passed before deployment.
