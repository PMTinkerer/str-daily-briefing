# SUNSET — 2026-05-04

This project has been replaced by **scmaine-helm**.

The morning briefing email now ships from Helm's in-process scheduler at
04:30 America/New_York, reading directly from the Guesty / Breezeway /
Notion APIs (no Gmail parsing required) and rendering with Helm's
design system. The live dashboard at <https://helm-production-2afa.up.railway.app>
is the canonical operational view.

- **Replacement repo:** <https://github.com/PMTinkerer/scmaine-helm>
- **Live dashboard:** <https://helm-production-2afa.up.railway.app>

## What's been disabled here

- `.github/workflows/daily-briefing.yml` — the cron schedule trigger has
  been removed; the workflow now contains a single sunset-notice job
  that does nothing if invoked. No emails will ever be sent from this
  repo again.
- `docs/index.html` — replaced with a meta-refresh redirect to Helm.

The rest of the source tree (`src/`, `tests/`, etc.) is preserved as a
historical reference. Nothing here is wired to anything; the repo is
safe to archive on GitHub or delete entirely without affecting any
active tooling.
