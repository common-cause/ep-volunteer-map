# ep-volunteer-map

A US map of Election Protection volunteer opportunities for protectthevote.net.
The content comes from a Google Sheet that organizers edit (state, title,
description, get-involved link). A twice-daily job publishes it to GitHub Pages,
and the map shows each state's opportunities as a list.

**Status:** built, not yet deployed. See [`docs/SPEC.md`](docs/SPEC.md) for
decisions and [`docs/wordpress_embed.md`](docs/wordpress_embed.md) for the embed.

```
python scripts/sync_opportunities.py --dry-run          # preview the sync
bash scripts/build_site.sh && python -m http.server -d _site   # preview the site
python -m pytest tests
```
