# ep-volunteer-map

> Sheet-backed US map of Election Protection volunteer opportunities for protectthevote.net: organizers list opportunities (state, title, description, get-involved link) in a Google Sheet, a twice-daily Civis job publishes them to GitHub Pages, and the map shows each state's opportunities as a list. dynamic-action-map's pipeline with many items per state. Requested by Amy.

## Embed on commoncause.org

Paste into a WordPress **Custom HTML** block on the target page:

```html
<div id="cc-tool"></div>
<script src="https://common-cause.github.io/ep-volunteer-map/src/embed.js"></script>
```

## Local Development

```bash
python -m http.server 8080
# Open http://localhost:8080
```

## Updating Content

Edit `data/tree.json` — no code changes needed for content updates.
Push to `main` to deploy.

## Project Structure

```
ep-volunteer-map/
├── index.html              # Local dev wrapper (simulates a CC page)
├── src/
│   ├── embed.js            # Widget — finds #cc-tool div and renders the tool
│   └── embed.css           # Namespaced styles (.cc-tool *)
├── data/
│   └── tree.json           # Decision tree content — edit this for content changes
└── .github/
    └── workflows/
        └── deploy.yml      # Auto-deploys to GitHub Pages on push to main
```
