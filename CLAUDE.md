# ep-volunteer-map

Sheet-backed US map of Election Protection volunteer opportunities for protectthevote.net: organizers list opportunities (state, title, description, get-involved link) in a Google Sheet, a twice-daily Civis job publishes them to GitHub Pages, and the map shows each state's opportunities as a list. dynamic-action-map's pipeline with many items per state. Requested by Amy.

## Project Type: cc-embed

A self-contained HTML/CSS/JS embed for commoncause.org. No backend, no build step.
Hosted on GitHub Pages, embedded on WordPress pages via a two-line snippet.

## Key Files

- `index.html` — local dev preview (simulates a CC page; not deployed as a standalone page)
- `src/embed.js` — widget entry point; finds the `#cc-tool` div and renders the tool
- `src/embed.css` — all styles, namespaced under `.cc-tool` to avoid host page collisions
- `data/tree.json` — decision tree content; edit this to update the tool without touching code

## Local Development

Open `index.html` directly in a browser, or run a local server to avoid CORS issues
when fetching `tree.json`:

```bash
python -m http.server 8080
```
Then open http://localhost:8080

## Content Updates

All tool content lives in `data/tree.json`. Schema reference:

- `meta.title` — displayed at the top of the embed
- `meta.start` — ID of the first node to render
- `nodes` — a map of node ID → node object

### Node types

**`question`** — asks a question and branches based on the answer:
```json
{
  "type": "question",
  "text": "The question text",
  "hint": "Optional clarifying subtext",
  "choices": [
    { "label": "Yes", "next": "some_node_id" },
    { "label": "No",  "next": "other_node_id" }
  ]
}
```

**`result`** — terminal node with outcome content and an optional signup:
```json
{
  "type": "result",
  "status": "clear",
  "heading": "You're all set!",
  "body": "Explanatory paragraph.",
  "links": [
    { "label": "Link text", "url": "https://..." }
  ],
  "signup": {
    "heading": "Stay informed",
    "body": "Optional sub-heading for the signup block.",
    "embed_code": "<!-- Paste Action Network embed snippet here -->",
    "an_tag": "short-identifier-for-this-outcome"
  }
}
```

`status` values: `clear` (green), `action_required` (orange), `ineligible` (red).
`signup` is optional — omit the key entirely to show no signup on that result.
`an_tag` populates a hidden field in the AN form so signups are segmented by path.

## CSS Namespacing

ALL styles must be scoped under `.cc-tool`. Never use bare element selectors (`p`, `h2`, etc.)
that could bleed into the host page. Use `.cc-tool p`, `.cc-tool h2`, etc.

## Accessibility Requirements

- Questions use `aria-labelledby` pointing to the question text element
- Answer buttons are `<button>` elements — keyboard navigable by default
- Result headings use `role="alert"` so screen readers announce the outcome
- Status is conveyed by both color AND structure (heading text, border) — never color alone

## Deploying

Push to `main` — GitHub Actions auto-deploys to GitHub Pages.

Embed URL after deployment:
```
https://common-cause.github.io/ep-volunteer-map/src/embed.js
```

## WordPress Embed Snippet

Paste this into a Gutenberg "Custom HTML" block on the target CC page:

```html
<div id="cc-tool"></div>
<script src="https://common-cause.github.io/ep-volunteer-map/src/embed.js"></script>
```

No other changes needed. Updates to `main` go live automatically on every page using the embed.
