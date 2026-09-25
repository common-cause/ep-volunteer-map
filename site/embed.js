/**
 * EP Volunteer Map — US map of Election Protection volunteer opportunities.
 *
 * A public page: served from GitHub Pages and iframed on protectthevote.net.
 * Content comes from an organizer-edited Google Sheet via
 * scripts/sync_opportunities.py, so every string in the data file is
 * user-entered. Two rules follow from that, and neither may be relaxed:
 *   - All Sheet text goes through esc() before it touches innerHTML.
 *   - Only http(s) URLs become links (safeUrl), re-checked here even though
 *     the sync already refuses anything else.
 *
 * Lifted from ep-training-map's embed.js (map, small-state callouts, picker,
 * deep link, iframe height reporting); the staff mode and session logic are
 * gone, and a state opens a list of opportunities instead.
 *
 * Attributes on the mount div:
 *   data-api   the opportunities file   (opportunities.json)
 *   data-geo   the state geometry       (us-states.json)
 *
 * No dependencies, no build step.
 */
(function () {
  "use strict";

  var MOUNT_ID = "cc-ep-volunteer-map";
  var NS = "cevm";                       // class prefix, scoped under the mount
  var SIGNUP_URL = "https://protectthevote.net/";

  var mount = document.getElementById(MOUNT_ID);
  if (!mount) {
    console.warn("[ep-volunteer-map] no #" + MOUNT_ID + " element on the page");
    return;
  }

  var dataSrc = mount.getAttribute("data-api") || "opportunities.json";
  var geoSrc = mount.getAttribute("data-geo") || "us-states.json";

  // The map lives in an iframe on protectthevote.net, and its height changes a
  // lot: an open state panel docks below the map on a phone and can be several
  // screens tall. So it reports its own height to the host page, and the
  // snippet in docs/wordpress_embed.md sizes the iframe to match. Without the
  // listener the iframe keeps its fixed height and scrolls inside, which still
  // works, just less well. Nothing but a number is sent.
  if (window.parent !== window) {
    var lastHeight = 0;
    var reportHeight = function () {
      var h = Math.ceil(document.documentElement.getBoundingClientRect().height);
      if (h && h !== lastHeight) {
        lastHeight = h;
        window.parent.postMessage({ type: "ep-volunteer-map:height", height: h }, "*");
      }
    };
    if (window.ResizeObserver) {
      new ResizeObserver(reportHeight).observe(document.documentElement);
    } else {
      window.addEventListener("resize", reportHeight);
      setInterval(reportHeight, 1000);
    }
    window.addEventListener("load", reportHeight);
  }

  // Small jurisdictions get a labelled chip in the Atlantic with a leader line.
  // Without it DC is under 3 real pixels wide and RI about 10: unclickable.
  // Ordered north to south to keep leaders tidy.
  var CALLOUTS = ["VT", "NH", "MA", "RI", "CT", "NJ", "DE", "MD", "DC"];
  var CHIP = { x: 992, w: 84, h: 26, top: 116, pitch: 30 };
  var VIEWBOX = "-62 8 1150 604";

  var MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

  // --- Helpers --------------------------------------------------------------

  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  /** Only http(s) becomes a link. A javascript: URL must never reach an href. */
  function safeUrl(u) {
    if (!u) return "";
    var s = String(u).trim();
    return /^https?:\/\/[^\s]+$/i.test(s) ? s : "";
  }

  /** '2026-10-31' -> 'Oct 31'. Parsed as a calendar date, NOT via new
   *  Date(iso), which reads as UTC and shifts a day back in every US timezone. */
  function dayLabel(iso) {
    var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(iso || "").trim());
    return m ? MONTHS[+m[2] - 1] + " " + (+m[3]) : "";
  }

  /** Escaped description: blank lines are paragraphs, single newlines breaks. */
  function paragraphs(text) {
    return String(text || "").split(/\n{2,}/).map(function (p) {
      return "<p>" + esc(p).replace(/\n/g, "<br>") + "</p>";
    }).join("");
  }

  function el(tag, cls, html) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (html != null) e.innerHTML = html;
    return e;
  }

  function svgEl(tag, attrs) {
    var e = document.createElementNS("http://www.w3.org/2000/svg", tag);
    for (var k in attrs) {
      if (Object.prototype.hasOwnProperty.call(attrs, k)) {
        e.setAttribute(k, attrs[k]);
      }
    }
    return e;
  }

  // --- Load -----------------------------------------------------------------

  function getJson(url) {
    return fetch(url, { credentials: "omit" }).then(function (r) {
      if (!r.ok) throw new Error(url + " -> HTTP " + r.status);
      return r.json();
    });
  }

  mount.appendChild(el("div", NS + "-loading", "Loading volunteer map…"));

  Promise.all([getJson(geoSrc), getJson(dataSrc)])
    .then(function (res) { render(res[0], res[1]); })
    .catch(function (err) {
      console.error("[ep-volunteer-map]", err);
      mount.innerHTML = "";
      mount.classList.add(NS + "-root");
      var m = el("div", NS + "-error");
      m.appendChild(el("p", null, "We couldn’t load the volunteer map just now."));
      m.appendChild(el("p", null,
        'You can still sign up at <a href="' + SIGNUP_URL
        + '" target="_top">protectthevote.net</a>.'));
      mount.appendChild(m);
    });

  // --- Render ---------------------------------------------------------------

  function render(geo, data) {
    var states = (data && data.states) || {};

    function items(code) { return states[code] || []; }

    mount.innerHTML = "";
    mount.classList.add(NS + "-root");

    // ---- header
    var head = el("div", NS + "-head");
    head.appendChild(el("h2", NS + "-title", "Volunteer with Election Protection"));
    head.appendChild(el("p", NS + "-sub", "Find opportunities in your state."));
    mount.appendChild(head);

    // ---- state picker (precision, and the accessible path on any screen)
    var controls = el("div", NS + "-controls");
    var label = el("label", NS + "-sronly", "Choose a state");
    label.setAttribute("for", NS + "-select");
    var select = el("select", NS + "-select");
    select.id = NS + "-select";
    var opt0 = el("option", null, "Choose a state…");
    opt0.value = "";
    select.appendChild(opt0);
    Object.keys(geo).sort(function (a, b) {
      return geo[a].name.localeCompare(geo[b].name);
    }).forEach(function (code) {
      var o = el("option", null, esc(geo[code].name));
      o.value = code;
      select.appendChild(o);
    });
    controls.appendChild(label);
    controls.appendChild(select);
    mount.appendChild(controls);

    // ---- map + panel share a positioning context
    var stage = el("div", NS + "-stage");
    var svg = svgEl("svg", {
      viewBox: VIEWBOX,
      class: NS + "-map",
      role: "group",
      "aria-label": "Map of Election Protection volunteer opportunities by state"
    });

    // Every state has something to offer: its own rows, or the default
    // volunteer item (Rob, 2026-09-25). So one fill, no legend, and every
    // state is a keyboard stop.
    function tooltip(code) { return geo[code].name; }

    var paths = {};
    var gStates = svgEl("g", { class: NS + "-states" });
    // Draw in a stable order so focus order is alphabetical, not file order.
    Object.keys(geo).sort().forEach(function (code) {
      var p = svgEl("path", {
        d: geo[code].d,
        class: NS + "-st",
        "data-state": code,
        tabindex: "0",
        role: "button"
      });
      var t = svgEl("title", {});
      t.textContent = tooltip(code);
      p.appendChild(t);
      gStates.appendChild(p);
      paths[code] = p;
    });
    svg.appendChild(gStates);

    // ---- callout chips for jurisdictions too small to click
    var gCall = svgEl("g", { class: NS + "-callouts" });
    CALLOUTS.forEach(function (code, idx) {
      if (!geo[code]) return;
      var y = CHIP.top + idx * CHIP.pitch;
      var bb = geo[code].bbox;
      var cx = (bb[0] + bb[2]) / 2;
      var cy = (bb[1] + bb[3]) / 2;

      gCall.appendChild(svgEl("line", {
        class: NS + "-leader",
        x1: cx, y1: cy, x2: CHIP.x - 4, y2: y + CHIP.h / 2
      }));

      var g = svgEl("g", {
        class: NS + "-chip",
        "data-state": code,
        tabindex: "0",
        role: "button"
      });
      g.appendChild(svgEl("rect", {
        x: CHIP.x, y: y, width: CHIP.w, height: CHIP.h, rx: 4
      }));
      var txt = svgEl("text", {
        x: CHIP.x + CHIP.w / 2, y: y + CHIP.h / 2,
        "text-anchor": "middle", "dominant-baseline": "central"
      });
      txt.textContent = code;
      g.appendChild(txt);
      var ct = svgEl("title", {});
      ct.textContent = tooltip(code);
      g.appendChild(ct);
      gCall.appendChild(g);
    });
    svg.appendChild(gCall);
    stage.appendChild(svg);

    var panel = el("div", NS + "-panel");
    panel.setAttribute("role", "dialog");
    panel.setAttribute("aria-label", "Volunteer opportunities in the selected state");
    panel.hidden = true;
    stage.appendChild(panel);
    mount.appendChild(stage);

    // --- Selection ----------------------------------------------------------

    var selected = null;

    function clearSelection() {
      Object.keys(paths).forEach(function (c) {
        paths[c].classList.remove(NS + "-sel");
      });
      Array.prototype.forEach.call(
        svg.querySelectorAll("." + NS + "-chip"), function (g) {
          g.classList.remove(NS + "-sel");
        });
    }

    function closePanel() {
      panel.hidden = true;
      panel.innerHTML = "";
      selected = null;
      clearSelection();
      if (select.value !== "") select.value = "";
      syncUrl(null);
    }

    function selectState(code, viaKeyboard) {
      if (!geo[code]) return;
      selected = code;
      clearSelection();
      if (paths[code]) paths[code].classList.add(NS + "-sel");
      var chip = svg.querySelector("." + NS + "-chip[data-state='" + code + "']");
      if (chip) chip.classList.add(NS + "-sel");
      if (select.value !== code) select.value = code;
      buildPanel(code);
      panel.hidden = false;
      positionPanel(code);
      syncUrl(code);
      if (viaKeyboard) {
        var close = panel.querySelector("." + NS + "-close");
        if (close) close.focus();
      }
    }

    /** The default item for a state with no rows (SPEC Phase 2, Q6 copy).
     *  PTV is the volunteer front door for every state without its own. A
     *  state whose coalition-plan recruitment link differs gets a door: row
     *  from the sweep instead, so it never reaches this fallback. */
    function defaultItem(name) {
      return {
        title: "Election Protection Volunteer",
        description: "Help make sure every eligible voter in " + name
          + " can cast their ballot. Sign up to volunteer with Election "
          + "Protection and we’ll connect you with training and opportunities "
          + "near you.",
        link: SIGNUP_URL
      };
    }

    function buildPanel(code) {
      var name = geo[code].name;
      var list = items(code).length ? items(code) : [defaultItem(name)];
      var html = '<button type="button" class="' + NS
        + '-close" aria-label="Close">&times;</button>'
        + '<div class="' + NS + '-pTitle">' + esc(name) + "</div>";

      // Sheet order, deliberately: organizers rank their own list (Rob,
      // 2026-09-25). Don't sort here.
      html += '<ul class="' + NS + '-list">';
      list.forEach(function (o) {
        var url = safeUrl(o.link);
        html += '<li class="' + NS + '-item">';
        html += '<div class="' + NS + '-oName">' + esc(o.title) + "</div>";
        var through = dayLabel(o.ends);
        if (through) {
          html += '<div class="' + NS + '-ends">Through ' + esc(through) + "</div>";
        }
        html += '<div class="' + NS + '-desc">' + paragraphs(o.description) + "</div>";
        if (url) {
          html += '<a class="' + NS + '-btn" href="' + esc(url)
            + '" target="_blank" rel="noopener">Get involved'
            + ' <span aria-hidden="true">&rarr;</span></a>';
        }
        html += "</li>";
      });
      html += "</ul>";
      panel.innerHTML = html;
      wirePanel();
    }

    function wirePanel() {
      var close = panel.querySelector("." + NS + "-close");
      if (close) {
        close.addEventListener("click", function (e) {
          e.stopPropagation();
          closePanel();
        });
      }
    }

    /** Anchor the panel beside the selected state, clamped inside the stage.
     *  Uses real screen rects, so it survives any responsive scaling. */
    function positionPanel(code) {
      panel.style.left = "";
      panel.style.top = "";
      panel.classList.remove(NS + "-sheet");

      // Narrow viewports: a floating bubble is unusable, so dock it.
      if (stage.clientWidth < 680) {
        panel.classList.add(NS + "-sheet");
        return;
      }

      var target = svg.querySelector("." + NS + "-chip[data-state='" + code
        + "']") || paths[code];
      if (!target) return;

      var sr = stage.getBoundingClientRect();
      var tr = target.getBoundingClientRect();
      var pw = panel.offsetWidth;
      var ph = panel.offsetHeight;
      var gap = 14;

      // Place it on whichever side of the state has more room.
      var tCx = tr.left + tr.width / 2 - sr.left;
      var left = (tCx > sr.width / 2)
        ? (tr.left - sr.left) - pw - gap
        : (tr.right - sr.left) + gap;
      left = Math.max(8, Math.min(left, Math.max(8, sr.width - pw - 8)));

      var top = (tr.top + tr.height / 2 - sr.top) - ph / 2;
      top = Math.max(8, Math.min(top, Math.max(8, sr.height - ph - 8)));

      panel.style.left = Math.round(left) + "px";
      panel.style.top = Math.round(top) + "px";
    }

    // --- Events -------------------------------------------------------------

    /** Walk up to the nearest element carrying data-state. */
    function hit(e) {
      var n = e.target;
      while (n && n !== svg) {
        if (n.getAttribute && n.getAttribute("data-state")) {
          return n.getAttribute("data-state");
        }
        n = n.parentNode;
      }
      return null;
    }

    svg.addEventListener("click", function (e) {
      var code = hit(e);
      if (!code) return;
      e.stopPropagation();
      if (code === selected) { closePanel(); return; }
      selectState(code, false);
    });

    svg.addEventListener("keydown", function (e) {
      if (e.key !== "Enter" && e.key !== " ") return;
      var code = hit(e);
      if (!code) return;
      e.preventDefault();
      selectState(code, true);
    });

    select.addEventListener("change", function () {
      if (!select.value) { closePanel(); return; }
      selectState(select.value, false);
    });

    // The panel has to survive clicking inside it, so it closes only on an
    // explicit gesture: its button, Escape, or a click outside.
    panel.addEventListener("click", function (e) { e.stopPropagation(); });

    document.addEventListener("click", function (e) {
      if (!selected) return;
      if (mount.contains(e.target)) return;
      closePanel();
    });

    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && selected) {
        var t = paths[selected];
        closePanel();
        if (t && t.getAttribute("tabindex") != null) t.focus();
      }
    });

    var rt;
    window.addEventListener("resize", function () {
      if (!selected) return;
      clearTimeout(rt);
      rt = setTimeout(function () { positionPanel(selected); }, 80);
    });

    // ---- deep link ?state=OH ---------------------------------------------
    // replaceState, not pushState: the panel is a view of this page, and
    // stacking history entries would make Back feel broken.
    function syncUrl(code) {
      if (!window.history || !window.history.replaceState) return;
      var q = code ? "?state=" + encodeURIComponent(code) : "";
      window.history.replaceState(null, "", window.location.pathname + q);
    }

    var initial = /[?&]state=([A-Za-z]{2})\b/.exec(window.location.search);
    if (initial) {
      var code0 = initial[1].toUpperCase();
      if (geo[code0]) selectState(code0, false);
    }
  }
})();
