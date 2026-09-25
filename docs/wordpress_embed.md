# Embedding the volunteer map on protectthevote.net

For: the protectthevote.net WordPress admin. One-time setup. Same pattern as
the EP training map embed.

## Steps

1. Open the page the map should live on (or create one).
2. Add a **Custom HTML** block. Don't use the "Embed" block.
3. Paste this snippet in:

```html
<iframe id="ep-volunteer-map-frame"
  src="https://common-cause.github.io/ep-volunteer-map/"
  title="Election Protection volunteer opportunities map"
  style="width:100%; height:850px; border:0; display:block;"
  loading="lazy"
  referrerpolicy="no-referrer"></iframe>
<script>
/* Grows the frame to fit the map, e.g. when a state's list opens on a phone.
   Accepts a height (a number) from the map's own address only. */
window.addEventListener("message", function (e) {
  if (e.origin !== "https://common-cause.github.io") return;
  var d = e.data;
  if (!d || d.type !== "ep-volunteer-map:height" || typeof d.height !== "number") return;
  var f = document.getElementById("ep-volunteer-map-frame");
  if (f) f.style.height = Math.min(Math.max(d.height, 400), 20000) + "px";
});
</script>
```

If WordPress strips the `<script>` (some setups do this for non-admins), the
iframe still works at its fixed 850px height and scrolls inside when a state's
list is long. Adding the script later only improves it.

4. Preview the page on desktop and mobile, then publish. Send the page URL to Rob.

A link can open a specific state: add `?state=OH` (any two-letter code) to the
iframe `src`.

## Why an iframe

The iframe keeps the map's styling separate from the WordPress theme, so a theme
update can't break the map and the map can't break the page.

## Updates

Opportunities come from a Google Sheet that organizers edit, and the map
refreshes itself twice a day (about 7am and 3pm Eastern). There's nothing to do
in WordPress when opportunities change. If the map looks empty or out of date,
contact Rob. Don't edit the snippet to work around it.
