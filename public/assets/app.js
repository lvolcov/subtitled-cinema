/* Subtitled Cinema — client. Loads data.json, renders + filters screenings.
   No build step, no dependencies. Runs on GitHub Pages as static files. */
(function () {
  "use strict";

  var state = {
    data: null,
    flat: [],           // flattened screenings (joined with cinema)
    day: "all",
    search: "",
    cinema: "",
    access: "",
    groupBy: "cinema",
    near: false,
    coords: null,       // {lat, lng} when geolocation granted
  };

  // ---- helpers ----------------------------------------------------------
  var WD = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
  var MO = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];

  // Parse "2026-07-28T20:00:00" as LOCAL wall-clock (avoid timezone shifting).
  function parseLocal(iso) {
    var m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/.exec(iso);
    if (!m) return null;
    return new Date(+m[1], +m[2] - 1, +m[3], +m[4], +m[5]);
  }
  function startOfDay(d) { return new Date(d.getFullYear(), d.getMonth(), d.getDate()); }
  function sameDay(a, b) { return startOfDay(a).getTime() === startOfDay(b).getTime(); }
  function dayKey(d) { return d.getFullYear() + "-" + (d.getMonth()+1) + "-" + d.getDate(); }

  function fmtTime(d) {
    var h = d.getHours(), m = d.getMinutes();
    return (h < 10 ? "0" : "") + h + ":" + (m < 10 ? "0" : "") + m;
  }
  function fmtDayLabel(d, now) {
    if (sameDay(d, now)) return "Today";
    var t = new Date(now); t.setDate(t.getDate() + 1);
    if (sameDay(d, t)) return "Tomorrow";
    return WD[d.getDay()] + " " + d.getDate() + " " + MO[d.getMonth()];
  }

  function hashHue(s) {
    var h = 0;
    for (var i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) % 360;
    return h;
  }
  function initials(title) {
    var w = title.replace(/[^A-Za-z0-9 ]/g, "").trim().split(/\s+/);
    return ((w[0] || "?")[0] + (w[1] ? w[1][0] : "")).toUpperCase();
  }
  function haversineMi(a, b) {
    var R = 3958.8, toR = Math.PI / 180;
    var dLat = (b.lat - a.lat) * toR, dLng = (b.lng - a.lng) * toR;
    var la1 = a.lat * toR, la2 = b.lat * toR;
    var x = Math.sin(dLat/2)*Math.sin(dLat/2) +
            Math.cos(la1)*Math.cos(la2)*Math.sin(dLng/2)*Math.sin(dLng/2);
    return R * 2 * Math.atan2(Math.sqrt(x), Math.sqrt(1 - x));
  }
  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;" }[c];
    });
  }

  // ---- data prep --------------------------------------------------------
  function flatten(data) {
    var out = [];
    data.cinemas.forEach(function (c) {
      c.screenings.forEach(function (s) {
        var d = parseLocal(s.starts_at);
        if (!d) return;
        out.push({
          date: d, title: s.title, film_id: s.film_id,
          certificate: s.certificate, accessibility: s.accessibility || [],
          screen_type: s.screen_type, language: s.language, note: s.note,
          imdb_url: s.imdb_url, source_url: s.source_url,
          cinema_id: c.id, cinema_name: c.name, area: c.area,
          chain: c.chain, postcode: c.postcode, booking_url: c.booking_url,
          last_checked: c.last_checked, lat: c.lat, lng: c.lng,
        });
      });
    });
    return out;
  }

  // ---- filtering --------------------------------------------------------
  function visible(now) {
    var cutoff = now.getTime() - 60 * 60 * 1000; // hide >60min past
    var q = state.search.trim().toLowerCase();
    var tomorrow = new Date(now); tomorrow.setDate(tomorrow.getDate() + 1);
    var weekEnd = new Date(now); weekEnd.setDate(weekEnd.getDate() + 7);

    return state.flat.filter(function (s) {
      if (s.date.getTime() < cutoff) return false;
      if (state.day === "today" && !sameDay(s.date, now)) return false;
      if (state.day === "tomorrow" && !sameDay(s.date, tomorrow)) return false;
      if (state.day === "week" && (s.date < startOfDay(now) || s.date > weekEnd)) return false;
      if (state.cinema && s.cinema_id !== state.cinema) return false;
      if (state.access && s.accessibility.indexOf(state.access) === -1) return false;
      if (q) {
        var hay = (s.title + " " + s.cinema_name + " " + (s.area||"") + " " + (s.chain||"")).toLowerCase();
        if (hay.indexOf(q) === -1) return false;
      }
      return true;
    });
  }

  function withDistance(list) {
    if (!state.coords) return list;
    list.forEach(function (s) {
      s.dist = (s.lat != null && s.lng != null)
        ? haversineMi(state.coords, { lat: s.lat, lng: s.lng }) : null;
    });
    return list;
  }

  // ---- grouping ---------------------------------------------------------
  function group(list, now) {
    var mode = state.near ? "cinema" : state.groupBy;
    var groups = {};
    var order = [];
    list.forEach(function (s) {
      var key, label, sub;
      if (mode === "film") { key = s.film_id; label = s.title; sub = s.certificate || ""; }
      else if (mode === "day") { key = dayKey(s.date); label = fmtDayLabel(s.date, now); sub = ""; }
      else { key = s.cinema_id; label = s.cinema_name; sub = s.chain || ""; }
      if (!groups[key]) { groups[key] = { label: label, sub: sub, items: [], sample: s }; order.push(key); }
      groups[key].items.push(s);
    });

    order.forEach(function (k) {
      groups[k].items.sort(function (a, b) { return a.date - b.date; });
    });

    order.sort(function (a, b) {
      var ga = groups[a], gb = groups[b];
      if (mode === "day") return ga.items[0].date - gb.items[0].date;
      if (state.near) {
        var da = ga.sample.dist == null ? Infinity : ga.sample.dist;
        var db = gb.sample.dist == null ? Infinity : gb.sample.dist;
        if (da !== db) return da - db;
      }
      if (mode === "cinema") return ga.label.localeCompare(gb.label);
      return gb.items.length - ga.items.length; // film: most screenings first
    });

    return order.map(function (k) { return groups[k]; });
  }

  // ---- rendering --------------------------------------------------------
  function cardHTML(s, now) {
    var hue = hashHue(s.title);
    var poster = '<div class="poster" style="background:linear-gradient(150deg,hsl(' +
      hue + ' 70% 62%),hsl(' + ((hue + 40) % 360) + ' 70% 48%))">' + esc(initials(s.title)) + '</div>';

    var badges = "";
    if (s.certificate) badges += '<span class="badge cert">' + esc(s.certificate) + '</span>';
    if (s.accessibility.indexOf("subtitled") !== -1) badges += '<span class="badge sub">Subtitled</span>';
    if (s.accessibility.indexOf("audio-described") !== -1) badges += '<span class="badge ad">Audio described</span>';
    if (s.screen_type === "imax") badges += '<span class="badge imax">IMAX</span>';
    if (s.language === "foreign") badges += '<span class="badge foreign">Orig + subs</span>';

    var mins = (s.date - now) / 60000;
    var soon = mins >= 0 && mins <= 180 ? ' <span class="soon">· soon</span>' : "";
    var when = '<span class="when">' + fmtDayLabel(s.date, now) + " " + fmtTime(s.date) + "</span>" + soon;

    var dist = (s.dist != null) ? '<span class="dist">' + s.dist.toFixed(1) + ' mi</span>' : "";
    var cinema = '<div class="cinema-line"><span class="name">' + esc(s.cinema_name) + "</span>" +
      (s.postcode ? '<span class="pc">' + esc(s.postcode) + "</span>" : "") + dist + "</div>";

    var noteExtra = "";
    var ncheck = (s.note || "").toLowerCase();
    if (/parent|baby|relax|dubbed|double check/.test(ncheck)) noteExtra = '<div class="note">⚠ ' + esc(s.note) + "</div>";

    var links = '<div class="links">';
    if (s.booking_url) links += '<a class="primary" href="' + esc(s.booking_url) + '" target="_blank" rel="noopener">Book</a>';
    if (s.imdb_url) links += '<a href="' + esc(s.imdb_url) + '" target="_blank" rel="noopener">IMDb</a>';
    links += "</div>";

    return '<article class="card" data-cinema="' + esc(s.cinema_id) + '" data-title="' + esc(s.title) +
      '" data-day="' + dayKey(s.date) + '">' + poster +
      '<div class="card-body"><div class="card-head"><h3 class="film-title">' + esc(s.title) + "</h3></div>" +
      '<div class="badges">' + badges + "</div>" +
      '<div class="meta">' + when + "</div>" + cinema + noteExtra + links + "</div></article>";
  }

  function render() {
    var now = window.__NOW__ ? new Date(window.__NOW__) : new Date();
    var results = document.getElementById("results");
    var empty = document.getElementById("emptyState");
    var summary = document.getElementById("resultSummary");

    var list = withDistance(visible(now));
    summary.textContent = list.length + " screening" + (list.length === 1 ? "" : "s") +
      (state.near && state.coords ? " · nearest first" : "");

    if (!list.length) { results.innerHTML = ""; empty.hidden = false; return; }
    empty.hidden = true;

    var groups = group(list, now);
    var html = groups.map(function (g) {
      var checked = g.sample.last_checked ? '<span class="checked">checked ' +
        esc(g.sample.last_checked.slice(0, 10)) + "</span>" : "";
      var sub = g.sub ? '<span class="sub">' + esc(g.sub) + "</span>" : "";
      var head = '<h2 class="group-title">' + esc(g.label) + " " + sub + checked + "</h2>";
      var cards = '<div class="cards">' + g.items.map(function (s) { return cardHTML(s, now); }).join("") + "</div>";
      return head + cards;
    }).join("");
    results.innerHTML = html;
  }

  // ---- wiring -----------------------------------------------------------
  function fillCinemaFilter() {
    var sel = document.getElementById("cinemaFilter");
    state.data.cinemas.slice().sort(function (a, b) {
      return a.name.localeCompare(b.name);
    }).forEach(function (c) {
      var o = document.createElement("option");
      o.value = c.id; o.textContent = c.name + " (" + c.screenings.length + ")";
      sel.appendChild(o);
    });
  }

  function renderStats() {
    var s = state.data.stats;
    document.getElementById("stats").innerHTML =
      '<span><b>' + s.cinemas + "</b>cinemas</span>" +
      '<span><b>' + s.screenings + "</b>screenings</span>" +
      '<span><b>' + s.films + "</b>films</span>";
    var gen = state.data.generated_at || "";
    document.getElementById("lastUpdated").textContent =
      "Listings last updated " + gen.replace("T", " ").slice(0, 16) + " (" + state.data.timezone + ").";
  }

  function bind() {
    document.getElementById("search").addEventListener("input", function (e) {
      state.search = e.target.value; render();
    });
    document.querySelectorAll(".seg-btn").forEach(function (b) {
      b.addEventListener("click", function () {
        document.querySelectorAll(".seg-btn").forEach(function (x) { x.classList.remove("active"); });
        b.classList.add("active"); state.day = b.dataset.day; render();
      });
    });
    document.getElementById("cinemaFilter").addEventListener("change", function (e) {
      state.cinema = e.target.value; render();
    });
    document.getElementById("accessFilter").addEventListener("change", function (e) {
      state.access = e.target.value; render();
    });
    document.getElementById("groupBy").addEventListener("change", function (e) {
      state.groupBy = e.target.value; render();
    });
    document.getElementById("nearBtn").addEventListener("click", onNear);
  }

  function onNear() {
    var btn = document.getElementById("nearBtn");
    if (state.near) { // toggle off
      state.near = false; btn.setAttribute("aria-pressed", "false"); btn.textContent = "📍 Nearest"; render(); return;
    }
    // test hook: allow injecting coords without the geolocation prompt
    if (window.__COORDS__) { state.coords = window.__COORDS__; }
    if (state.coords) { activateNear(btn); return; }
    if (!navigator.geolocation) { btn.textContent = "Location unavailable"; return; }
    btn.textContent = "Locating…";
    navigator.geolocation.getCurrentPosition(function (pos) {
      state.coords = { lat: pos.coords.latitude, lng: pos.coords.longitude };
      activateNear(btn);
    }, function () { btn.textContent = "📍 Nearest"; });
  }
  function activateNear(btn) {
    state.near = true; btn.setAttribute("aria-pressed", "true"); btn.textContent = "📍 Nearest ✓"; render();
  }

  function boot(data) {
    state.data = data;
    state.flat = flatten(data);
    renderStats();
    fillCinemaFilter();
    bind();
    render();
    document.body.dataset.ready = "1";
  }

  // Allow tests to preload data via window.__DATA__; otherwise fetch.
  if (window.__DATA__) { boot(window.__DATA__); }
  else {
    fetch("data.json").then(function (r) { return r.json(); }).then(boot).catch(function (e) {
      document.getElementById("results").innerHTML =
        '<p class="empty">Could not load listings. ' + esc(e.message) + "</p>";
    });
  }
})();
