/* ============================================================
   Subtitled Cinema — v2 app logic (vanilla, no framework)

   Two ways in, one filtered list:
     • Pick a film in the rail  -> that film, grouped by cinema (near you first)
     • Browse by date/location  -> every accessible screening for the filters

   Test hooks: window.__DATA__ (skip fetch), window.__NOW__ (ms), window.__COORDS__.
   ============================================================ */
(function () {
  "use strict";

  // ---------- theme ----------
  var root = document.documentElement, TKEY = "sc-theme";
  var saved = localStorage.getItem(TKEY);
  if (saved) root.setAttribute("data-theme", saved);
  function syncThemeLabel() {
    var t = root.getAttribute("data-theme");
    var dark = t ? t === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
    document.querySelectorAll("[data-tglabel]").forEach(function (e) { e.textContent = dark ? "☀️" : "🌙"; });
  }
  document.getElementById("themeBtn").addEventListener("click", function () {
    var cur = root.getAttribute("data-theme");
    var next = cur === "light" ? "dark" : cur === "dark" ? "light"
      : (matchMedia("(prefers-color-scheme: dark)").matches ? "light" : "dark");
    root.setAttribute("data-theme", next); localStorage.setItem(TKEY, next); syncThemeLabel();
  });
  syncThemeLabel();

  // ---------- helpers ----------
  var $ = function (id) { return document.getElementById(id); };
  function now() { return window.__NOW__ ? new Date(window.__NOW__) : new Date(); }
  function esc(s) { var d = document.createElement("div"); d.textContent = s == null ? "" : s; return d.innerHTML; }
  function hue(s) { var h = 0; for (var i = 0; i < s.length; i++) h = (h + s.charCodeAt(i)) % 360; return h; }
  function initials(t) { return t.split(/\s+/).slice(0, 2).map(function (w) { return w[0]; }).join("").toUpperCase(); }
  var DOW = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
  var MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  function hhmm(d) { return String(d.getHours()).padStart(2, "0") + ":" + String(d.getMinutes()).padStart(2, "0"); }
  function dayKey(d) { return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0"); }
  function relDay(d, ref) {
    var a = new Date(d.getFullYear(), d.getMonth(), d.getDate());
    var b = new Date(ref.getFullYear(), ref.getMonth(), ref.getDate());
    var diff = Math.round((a - b) / 86400000);
    if (diff === 0) return "Today"; if (diff === 1) return "Tomorrow";
    return DOW[d.getDay()] + " " + d.getDate() + " " + MON[d.getMonth()];
  }
  function haversine(a, b, c, e) {
    var R = 3958.8, dLat = (c - a) * Math.PI / 180, dLng = (e - b) * Math.PI / 180;
    var s = Math.sin(dLat / 2) ** 2 + Math.cos(a * Math.PI / 180) * Math.cos(c * Math.PI / 180) * Math.sin(dLng / 2) ** 2;
    return R * 2 * Math.atan2(Math.sqrt(s), Math.sqrt(1 - s));
  }
  function miles(m) { return m < 10 ? m.toFixed(1) + " mi" : Math.round(m) + " mi"; }

  function posterInner(url, title, cnt) {
    var h = 'style="--h:' + hue(title) + '"';
    var fall = '<span class="pfall">' + esc(initials(title)) + "</span>";
    var img = url ? '<img loading="lazy" alt="" src="' + esc(url) + '" onload="this.classList.add(\'on\')" onerror="this.remove()">' : "";
    var badge = cnt ? '<span class="cnt">' + cnt + "</span>" : "";
    return { h: h, html: fall + img + badge };
  }

  // ---------- state ----------
  var DATA = null, SESSIONS = [], FILMS = [], CINEMAS = {}, COORDS = window.__COORDS__ || null;
  var state = { film: "", date: "all", group: "cinema", access: "", cinemas: [], sort: "time", q: "" };

  // ---------- load ----------
  function boot(data) {
    DATA = data;
    CINEMAS = {};
    data.cinemas.forEach(function (c) { CINEMAS[c.id] = c; });
    // flat, upcoming-only session list
    var n = now(); SESSIONS = [];
    data.cinemas.forEach(function (c) {
      (c.screenings || []).forEach(function (s) {
        var when = new Date(s.starts_at);
        if (when.getTime() < n.getTime() - 40 * 60000) return; // drop screenings >40m past
        SESSIONS.push({
          title: s.title, film_id: s.film_id, poster: s.poster_url, cert: s.certificate,
          acc: s.accessibility || [], lang: s.language, screen: s.screen_type, imdb: s.imdb_url,
          when: when, cinema: c, book: c.booking_url || "#"
        });
      });
    });
    FILMS = (data.films || []).slice().map(function (f) {
      var mine = SESSIONS.filter(function (s) { return s.film_id === f.id; });
      var cinemas = {}; mine.forEach(function (s) { cinemas[s.cinema.id] = 1; });
      return { id: f.id, title: f.title, cert: f.certificate, poster: f.poster_url,
        ntimes: mine.length, nvenues: Object.keys(cinemas).length, lang: (mine[0] || {}).lang };
    }).filter(function (f) { return f.ntimes > 0; })
      .sort(function (a, b) { return b.ntimes - a.ntimes; });

    var st = DATA.stats || {};
    $("statPill").innerHTML = "<b>" + st.screenings + "</b> screenings · <b>" + st.cinemas + "</b> cinemas";
    var gen = DATA.generated_at ? new Date(DATA.generated_at) : n;
    $("lastUpdated").textContent = "Last checked " + relDay(gen, n).toLowerCase() + " · " +
      DOW[gen.getDay()] + " " + gen.getDate() + " " + MON[gen.getMonth()] + " " + gen.getFullYear();

    if (COORDS) { $("nearBtn").setAttribute("aria-pressed", "true"); state.sort = "near"; $("sortBy").value = "near"; }
    // build the film rail first — it's the thing users rely on — and never let a
    // filter-builder error stop it from rendering.
    buildRail();
    try { buildCinemaMenu(); } catch (e) { console.error("cinema menu failed", e); }
    try { buildDateStrip(); } catch (e) { console.error("date strip failed", e); }
    readURL();
    $("skeleton").hidden = true; if ($("skeleton")) $("skeleton").remove();
    render();
  }

  if (window.__DATA__) { boot(window.__DATA__); }
  else {
    fetch("data.json").then(function (r) { return r.json(); }).then(boot).catch(function () {
      $("skeleton").hidden = true;
      $("list").innerHTML = '<p class="empty">Couldn’t load the listings just now. Please refresh.</p>';
    });
  }

  // ---------- build controls ----------
  // Cinemas grouped by chain (Vue, Odeon, …); ungrouped venues under "Independent".
  function chainsModel() {
    var groups = {}, order = [];
    DATA.cinemas.slice().sort(function (a, b) { return a.name.localeCompare(b.name); })
      .forEach(function (c) {
        var g = c.chain || "Independent";
        if (!groups[g]) { groups[g] = []; order.push(g); }
        groups[g].push(c);
      });
    // real chains first (alphabetical), Independent last
    order.sort(function (a, b) {
      if (a === "Independent") return 1; if (b === "Independent") return -1;
      return a.localeCompare(b);
    });
    return order.map(function (name) { return { name: name, cinemas: groups[name] }; });
  }
  function buildCinemaMenu() {
    var menu = $("cinemaMenu"); menu.innerHTML = "";
    var tools = document.createElement("div"); tools.className = "ms-tools";
    tools.innerHTML = '<button type="button" data-all>Select all</button><button type="button" data-none>Clear</button>';
    tools.querySelector("[data-all]").addEventListener("click", function () {
      state.cinemas = DATA.cinemas.map(function (c) { return c.id; }); syncCinemaMenu(); render(); pushURL();
    });
    tools.querySelector("[data-none]").addEventListener("click", function () {
      state.cinemas = []; syncCinemaMenu(); render(); pushURL();
    });
    menu.appendChild(tools);

    chainsModel().forEach(function (grp) {
      var wrap = document.createElement("div"); wrap.className = "ms-group";
      var ids = grp.cinemas.map(function (c) { return c.id; });
      var head = document.createElement("label"); head.className = "ms-chain";
      head.innerHTML = '<input type="checkbox" data-chain>' +
        "<span>" + esc(grp.name) + "</span>" +
        '<span class="ms-chain-count">' + ids.length + "</span>";
      var cb = head.querySelector("input");
      cb.dataset.ids = ids.join(",");
      cb.addEventListener("change", function () {
        var on = cb.checked, set = {};
        state.cinemas.forEach(function (id) { set[id] = 1; });
        ids.forEach(function (id) { if (on) set[id] = 1; else delete set[id]; });
        state.cinemas = Object.keys(set);
        syncCinemaMenu(); render(); pushURL();
      });
      wrap.appendChild(head);

      grp.cinemas.forEach(function (c) {
        var opt = document.createElement("label"); opt.className = "ms-opt";
        opt.innerHTML = '<input type="checkbox" value="' + c.id + '">' +
          "<span>" + esc(c.name) + (c.area && c.area !== c.name ? " <small>" + esc(c.area) + "</small>" : "") + "</span>";
        opt.querySelector("input").addEventListener("change", function () {
          var set = {}; state.cinemas.forEach(function (id) { set[id] = 1; });
          if (this.checked) set[c.id] = 1; else delete set[c.id];
          state.cinemas = Object.keys(set);
          syncCinemaMenu(); render(); pushURL();
        });
        wrap.appendChild(opt);
      });
      menu.appendChild(wrap);
    });
    syncCinemaMenu();
  }
  function syncCinemaMenu() {
    var sel = {}; state.cinemas.forEach(function (id) { sel[id] = 1; });
    $("cinemaMenu").querySelectorAll(".ms-opt input").forEach(function (cb) {
      cb.checked = !!sel[cb.value];
    });
    $("cinemaMenu").querySelectorAll("[data-chain]").forEach(function (cb) {
      var ids = (cb.dataset.ids || "").split(",").filter(Boolean);
      var on = ids.filter(function (id) { return sel[id]; }).length;
      cb.checked = on === ids.length && ids.length > 0;
      cb.indeterminate = on > 0 && on < ids.length;
    });
    // button summary
    var btn = $("cinemaBtn"), n = state.cinemas.length;
    if (!n) btn.textContent = "All cinemas";
    else if (n === 1) btn.textContent = (CINEMAS[state.cinemas[0]] || {}).name || "1 cinema";
    else btn.textContent = n + " cinemas";
  }
  function buildDateStrip() {
    var strip = $("dateStrip"), n = now(); strip.innerHTML = "";
    var days = {}; SESSIONS.forEach(function (s) { days[dayKey(s.when)] = s.when; });
    var keys = Object.keys(days).sort();
    function mk(val, top, sub, active) {
      var b = document.createElement("button"); b.className = "date-btn" + (active ? " active" : "");
      b.dataset.date = val; b.innerHTML = esc(top) + (sub ? "<small>" + esc(sub) + "</small>" : "");
      b.addEventListener("click", function () { state.date = val; syncDateStrip(); render(); pushURL(); });
      return b;
    }
    strip.appendChild(mk("all", "All dates", keys.length + " days", state.date === "all"));
    keys.forEach(function (k) {
      var d = days[k], rel = relDay(d, n);
      var top = rel === "Today" || rel === "Tomorrow" ? rel : DOW[d.getDay()];
      var sub = d.getDate() + " " + MON[d.getMonth()];
      strip.appendChild(mk(k, top, sub, state.date === k));
    });
  }
  function syncDateStrip() {
    $("dateStrip").querySelectorAll(".date-btn").forEach(function (b) {
      b.classList.toggle("active", b.dataset.date === state.date);
    });
  }
  function buildRail() {
    var rail = $("filmRail"); rail.innerHTML = "";
    // "All films" tile
    var all = document.createElement("button");
    all.className = "rail-item all"; all.setAttribute("role", "option");
    all.setAttribute("aria-selected", state.film ? "false" : "true");
    all.innerHTML = '<div class="rail-all-tile"><span><span class="big">🎞️</span>All films</span></div>' +
      '<div class="rail-name">Browse everything by date &amp; location</div>';
    all.addEventListener("click", function () { selectFilm(""); });
    rail.appendChild(all);

    FILMS.forEach(function (f) {
      var p = posterInner(f.poster, f.title, "");
      var b = document.createElement("button");
      b.className = "rail-item"; b.setAttribute("role", "option");
      b.setAttribute("aria-selected", state.film === f.id ? "true" : "false");
      b.dataset.film = f.id;
      b.innerHTML = '<div class="rail-poster" ' + p.h + '>' + p.html +
        '<span class="cnt">' + f.nvenues + " cinema" + (f.nvenues !== 1 ? "s" : "") + "</span></div>" +
        '<div class="rail-name">' + esc(f.title) + "</div>";
      b.addEventListener("click", function () { selectFilm(f.id); });
      rail.appendChild(b);
    });
  }
  function syncRail() {
    $("filmRail").querySelectorAll(".rail-item").forEach(function (b) {
      var id = b.dataset.film || "";
      b.setAttribute("aria-selected", id === state.film ? "true" : "false");
    });
    $("railHint").textContent = state.film ? "Showing one film — tap “All films” to clear" :
      (FILMS.length + " films with subtitled screenings");
  }
  function selectFilm(id) {
    state.film = id;
    if (id) { state.group = "cinema"; syncGroup(); }
    syncRail(); render(); pushURL();
    if (id) {
      // land the film banner just below the sticky nav + controls, not under them
      var nav = document.querySelector(".nav"), shell = document.querySelector(".controls-shell");
      var offset = (nav ? nav.offsetHeight : 0) + (shell ? shell.offsetHeight : 0) + 12;
      var y = $("filmBanner").getBoundingClientRect().top + window.scrollY - offset;
      window.scrollTo({ top: Math.max(0, y), behavior: "smooth" });
    }
  }
  function syncGroup() {
    document.querySelectorAll(".seg-btn").forEach(function (b) {
      var on = b.dataset.group === state.group;
      b.classList.toggle("active", on); b.setAttribute("aria-selected", on ? "true" : "false");
    });
  }

  // ---------- control listeners ----------
  document.querySelectorAll(".seg-btn").forEach(function (b) {
    b.addEventListener("click", function () { state.group = b.dataset.group; syncGroup(); render(); pushURL(); });
  });
  $("search").addEventListener("input", function () { state.q = this.value.trim().toLowerCase(); render(); });
  $("accessFilter").addEventListener("change", function () { state.access = this.value; render(); pushURL(); });

  // filters drawer
  $("filtersBtn").addEventListener("click", function () {
    var panel = $("filtersPanel"), willOpen = panel.hidden;
    panel.hidden = !willOpen; this.setAttribute("aria-expanded", willOpen ? "true" : "false");
  });

  // cinema multi-select popover
  $("cinemaBtn").addEventListener("click", function (e) {
    e.stopPropagation();
    var open = $("cinemaMs").classList.toggle("open");
    $("cinemaMenu").hidden = !open; this.setAttribute("aria-expanded", open ? "true" : "false");
  });
  $("cinemaMenu").addEventListener("click", function (e) { e.stopPropagation(); });
  document.addEventListener("click", function () {
    if ($("cinemaMs").classList.contains("open")) {
      $("cinemaMs").classList.remove("open"); $("cinemaMenu").hidden = true;
      $("cinemaBtn").setAttribute("aria-expanded", "false");
    }
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && $("cinemaMs").classList.contains("open")) {
      $("cinemaMs").classList.remove("open"); $("cinemaMenu").hidden = true;
      $("cinemaBtn").setAttribute("aria-expanded", "false"); $("cinemaBtn").focus();
    }
  });
  $("sortBy").addEventListener("change", function () { state.sort = this.value; if (this.value === "near" && !COORDS) askLocation(); render(); });
  $("nearBtn").addEventListener("click", function () {
    if (COORDS) { COORDS = null; localStorage.removeItem("sc-coords"); this.setAttribute("aria-pressed", "false"); state.sort = "time"; $("sortBy").value = "time"; render(); }
    else askLocation();
  });
  function askLocation() {
    var stored = localStorage.getItem("sc-coords");
    if (stored) { try { COORDS = JSON.parse(stored); } catch (e) {} }
    if (COORDS) { applyNear(); return; }
    if (!navigator.geolocation) return;
    $("nearBtn").textContent = "📍 Locating…";
    navigator.geolocation.getCurrentPosition(function (pos) {
      COORDS = { lat: pos.coords.latitude, lng: pos.coords.longitude };
      localStorage.setItem("sc-coords", JSON.stringify(COORDS)); applyNear();
    }, function () { $("nearBtn").textContent = "📍 Near me"; }, { timeout: 8000 });
  }
  function applyNear() {
    $("nearBtn").textContent = "📍 Near me"; $("nearBtn").setAttribute("aria-pressed", "true");
    state.sort = "near"; $("sortBy").value = "near"; render();
  }

  // ---------- filtering ----------
  function distFor(c) {
    if (!COORDS || c.lat == null || c.lng == null) return null;
    return haversine(COORDS.lat, COORDS.lng, c.lat, c.lng);
  }
  function passes(s) {
    if (state.film && s.film_id !== state.film) return false;
    if (state.cinemas.length && state.cinemas.indexOf(s.cinema.id) < 0) return false;
    if (state.access === "subtitled" && s.acc.indexOf("subtitled") < 0 && s.acc.indexOf("captioned") < 0) return false;
    if (state.access === "audio-described" && s.acc.indexOf("audio-described") < 0) return false;
    if (state.date !== "all" && dayKey(s.when) !== state.date) return false;
    if (state.q) {
      var hay = (s.title + " " + s.cinema.name + " " + s.cinema.area).toLowerCase();
      if (hay.indexOf(state.q) < 0) return false;
    }
    return true;
  }

  // ---------- render ----------
  function updateFilterCount() {
    var n = 0;
    if (state.date !== "all") n++;
    if (state.cinemas.length) n++;
    if (state.access) n++;
    if (COORDS) n++;
    var el = $("filterCount");
    el.textContent = n; el.hidden = n === 0;
    $("filtersBtn").classList.toggle("on", n > 0);
  }

  function render() {
    var rows = SESSIONS.filter(passes);
    renderChips(rows.length);
    updateFilterCount();
    renderFilmBanner();
    var list = $("list"); list.innerHTML = "";
    if (!rows.length) { $("emptyState").hidden = false; $("resultSummary").textContent = ""; return; }
    $("emptyState").hidden = true;

    var groups = groupRows(rows);
    $("resultSummary").textContent = rows.length + " screening" + (rows.length !== 1 ? "s" : "") +
      " · " + groups.length + " " + (state.group === "film" ? "film" : state.group === "time" ? "day" : "cinema") +
      (groups.length !== 1 ? "s" : "");

    groups.forEach(function (g) { list.appendChild(renderGroup(g)); });
  }

  function groupRows(rows) {
    var map = {}, order = [];
    rows.forEach(function (s) {
      var key, label, sub, dist = null;
      if (state.group === "film") { key = s.film_id; label = s.title; sub = ""; }
      else if (state.group === "time") { key = dayKey(s.when); label = relDay(s.when, now()); sub = DOW[s.when.getDay()] + " " + s.when.getDate() + " " + MON[s.when.getMonth()]; }
      else { key = s.cinema.id; label = s.cinema.name; sub = s.cinema.area || ""; dist = distFor(s.cinema); }
      if (!map[key]) { map[key] = { key: key, label: label, sub: sub, dist: dist, cinema: s.cinema, film_id: s.film_id, rows: [] }; order.push(key); }
      map[key].rows.push(s);
    });
    var groups = order.map(function (k) { return map[k]; });
    // sort groups
    if (state.group === "time") {
      groups.sort(function (a, b) { return a.key < b.key ? -1 : 1; });
    } else if (state.group === "cinema" && state.sort === "near" && COORDS) {
      groups.sort(function (a, b) {
        if (a.dist == null) return 1; if (b.dist == null) return -1; return a.dist - b.dist;
      });
    } else if (state.group === "cinema") {
      groups.sort(function (a, b) { return a.label.localeCompare(b.label); });
    } else { // film
      groups.sort(function (a, b) { return b.rows.length - a.rows.length; });
    }
    // sort rows within a group
    groups.forEach(function (g) {
      if (state.group === "cinema" || state.group === "time") g.rows.sort(function (a, b) { return a.when - b.when; });
      else { // film group: by cinema distance then time
        g.rows.sort(function (a, b) {
          if (state.sort === "near" && COORDS) {
            var da = distFor(a.cinema), db = distFor(b.cinema);
            if (da != null && db != null && da !== db) return da - db;
          }
          return a.when - b.when;
        });
      }
    });
    return groups;
  }

  function renderGroup(g) {
    var wrap = document.createElement("section"); wrap.className = "group";
    var head = document.createElement("div"); head.className = "group-head";
    var distTxt = (g.dist != null) ? '<span class="g-dist">📍 ' + miles(g.dist) + "</span>" : "";
    head.innerHTML = '<span class="g-name">' + esc(g.label) + "</span>" +
      (g.sub ? '<span class="g-sub">' + esc(g.sub) + "</span>" : "") + distTxt +
      '<span class="g-count">' + g.rows.length + "</span>";
    wrap.appendChild(head);

    var cards = document.createElement("div"); cards.className = "cards";
    if (state.group === "cinema") {
      // one card per film at this cinema, showtimes collapsed into pills
      collapseByFilm(g.rows).forEach(function (fg) { cards.appendChild(filmCard(fg, "cinema")); });
    } else if (state.group === "film") {
      // one card per cinema showing this film
      collapseByCinema(g.rows).forEach(function (cg) { cards.appendChild(cinemaCard(cg)); });
    } else { // time: one card per (film, cinema) session on that day
      collapseByFilmCinema(g.rows).forEach(function (fg) { cards.appendChild(filmCard(fg, "time")); });
    }
    wrap.appendChild(cards);
    return wrap;
  }

  function collapseByFilm(rows) {
    var m = {}, o = [];
    rows.forEach(function (s) { if (!m[s.film_id]) { m[s.film_id] = { film_id: s.film_id, title: s.title, poster: s.poster, cert: s.cert, acc: s.acc, lang: s.lang, screen: s.screen, imdb: s.imdb, cinema: s.cinema, times: [] }; o.push(s.film_id); } m[s.film_id].times.push(s); });
    return o.map(function (k) { return m[k]; });
  }
  function collapseByFilmCinema(rows) {
    var m = {}, o = [];
    rows.forEach(function (s) { var k = s.film_id + "@" + s.cinema.id; if (!m[k]) { m[k] = { film_id: s.film_id, title: s.title, poster: s.poster, cert: s.cert, acc: s.acc, lang: s.lang, screen: s.screen, imdb: s.imdb, cinema: s.cinema, times: [] }; o.push(k); } m[k].times.push(s); });
    return o.map(function (k) { return m[k]; });
  }
  function collapseByCinema(rows) {
    var m = {}, o = [];
    rows.forEach(function (s) { if (!m[s.cinema.id]) { m[s.cinema.id] = { cinema: s.cinema, dist: distFor(s.cinema), times: [] }; o.push(s.cinema.id); } m[s.cinema.id].times.push(s); });
    var arr = o.map(function (k) { return m[k]; });
    if (state.sort === "near" && COORDS) arr.sort(function (a, b) { if (a.dist == null) return 1; if (b.dist == null) return -1; return a.dist - b.dist; });
    return arr;
  }

  function badges(fg) {
    var out = "";
    if (fg.cert) out += '<span class="badge cert">' + esc(fg.cert) + "</span>";
    if (fg.acc.indexOf("subtitled") >= 0 || fg.acc.indexOf("captioned") >= 0)
      out += '<span class="badge sub">' + (fg.lang && fg.lang !== "en" ? "Subtitles" : "Captioned") + "</span>";
    if (fg.acc.indexOf("audio-described") >= 0) out += '<span class="badge ad">Audio described</span>';
    if (fg.lang && fg.lang !== "en") out += '<span class="badge foreign">Foreign language</span>';
    if (fg.screen && /imax/i.test(fg.screen)) out += '<span class="badge imax">IMAX</span>';
    return out;
  }
  function showtimePills(times, showDay) {
    var n = now();
    return times.slice().sort(function (a, b) { return a.when - b.when; }).map(function (s) {
      var past = s.when.getTime() < n.getTime();
      var sub = showDay ? "<small>" + esc(relDay(s.when, n)) + "</small>" : "";
      return '<a class="st' + (past ? " past" : "") + '" href="' + esc(s.book) + '" target="_blank" rel="noopener" title="Book at ' +
        esc(s.cinema.name) + '">' + hhmm(s.when) + sub + "</a>";
    }).join("");
  }

  // card variants
  function filmCard(fg, mode) {
    var p = posterInner(fg.poster, fg.title, "");
    var card = document.createElement("div"); card.className = "card";
    var cinLine = mode === "cinema" ? "" :
      '<div class="cinema-line"><span class="c-name" data-cinema="' + fg.cinema.id + '">' + esc(fg.cinema.name) + "</span>" +
      (fg.cinema.area ? '<span>· ' + esc(fg.cinema.area) + "</span>" : "") +
      (distFor(fg.cinema) != null ? '<span class="dist">📍 ' + miles(distFor(fg.cinema)) + "</span>" : "") + "</div>";
    card.innerHTML =
      '<div class="poster" ' + p.h + ' data-film="' + fg.film_id + '">' + p.html + "</div>" +
      '<div class="card-body">' +
        '<button class="card-title" data-film="' + fg.film_id + '">' + esc(fg.title) + "</button>" +
        '<div class="badges">' + badges(fg) + "</div>" + cinLine +
        '<div class="showtimes">' + showtimePills(fg.times, mode === "time" ? false : (state.date === "all")) + "</div>" +
        (fg.imdb ? '<a class="imdb" href="' + esc(fg.imdb) + '" target="_blank" rel="noopener">IMDb ↗</a>' : "") +
      "</div>";
    wireCard(card);
    return card;
  }
  function cinemaCard(cg) {
    var c = cg.cinema;
    var maps = "https://www.google.com/maps/search/?api=1&query=" + encodeURIComponent((c.name || "") + " " + (c.postcode || ""));
    var card = document.createElement("div"); card.className = "card";
    card.innerHTML =
      '<div class="poster" style="--h:' + hue(c.name) + '"><span class="pfall">' + esc(initials(c.name)) + "</span></div>" +
      '<div class="card-body">' +
        '<button class="card-title" data-cinema="' + c.id + '">' + esc(c.name) + "</button>" +
        '<div class="cinema-line"><span>' + esc(c.area || "") + (c.postcode ? " · " + esc(c.postcode) : "") + "</span>" +
        (cg.dist != null ? '<span class="dist">📍 ' + miles(cg.dist) + "</span>" : "") +
        ' · <a class="imdb" href="' + maps + '" target="_blank" rel="noopener" style="margin:0">Maps ↗</a></div>' +
        '<div class="showtimes">' + showtimePills(cg.times, state.date === "all") + "</div>" +
      "</div>";
    wireCard(card);
    return card;
  }
  function wireCard(card) {
    card.querySelectorAll("[data-film]").forEach(function (el) {
      el.addEventListener("click", function () { selectFilm(el.getAttribute("data-film")); });
    });
    card.querySelectorAll("[data-cinema]").forEach(function (el) {
      el.addEventListener("click", function () { state.cinemas = [el.getAttribute("data-cinema")]; syncCinemaMenu(); render(); pushURL(); window.scrollTo({ top: 0, behavior: "smooth" }); });
    });
  }

  // ---------- film banner + chips ----------
  function renderFilmBanner() {
    var b = $("filmBanner");
    if (!state.film) { b.hidden = true; b.innerHTML = ""; return; }
    var f = FILMS.filter(function (x) { return x.id === state.film; })[0];
    if (!f) { b.hidden = true; return; }
    var matching = SESSIONS.filter(function (s) { return s.film_id === f.id && passes(s); });
    var venues = {}; matching.forEach(function (s) { venues[s.cinema.id] = 1; });
    var nv = Object.keys(venues).length;
    var p = posterInner(f.poster, f.title, "");
    b.hidden = false;
    b.innerHTML =
      '<div class="fb-poster" ' + p.h + '>' + p.html + "</div>" +
      '<div class="fb-body"><h2>' + esc(f.title) + "</h2>" +
      '<p class="fb-meta">' + (f.cert ? esc(f.cert) + " · " : "") +
        "Subtitled at " + nv + " cinema" + (nv !== 1 ? "s" : "") +
        " · " + matching.length + " screening" + (matching.length !== 1 ? "s" : "") +
        (state.date !== "all" ? " on this date" : "") + "</p>" +
      '<div class="fb-actions"><button class="btn-ghost" id="clearFilm">← All films</button></div></div>';
    $("clearFilm").addEventListener("click", function () { selectFilm(""); });
  }
  function renderChips() {
    var box = $("activeChips"); box.innerHTML = "";
    function chip(label, onClear, cls) {
      var c = document.createElement("button"); c.className = "fchip" + (cls ? " " + cls : "");
      c.innerHTML = esc(label) + (cls === "clear" ? "" : ' <span class="x">✕</span>');
      c.addEventListener("click", onClear); box.appendChild(c);
    }
    if (state.date !== "all") { var d = SESSIONS.filter(function (s) { return dayKey(s.when) === state.date; })[0]; if (d) chip(relDay(d.when, now()), function () { state.date = "all"; syncDateStrip(); render(); pushURL(); }); }
    if (state.cinemas.length === 1 && CINEMAS[state.cinemas[0]]) chip(CINEMAS[state.cinemas[0]].name, function () { state.cinemas = []; syncCinemaMenu(); render(); pushURL(); });
    else if (state.cinemas.length > 1) chip(state.cinemas.length + " cinemas", function () { state.cinemas = []; syncCinemaMenu(); render(); pushURL(); });
    if (state.access) chip(state.access === "subtitled" ? "Subtitled" : "Audio described", function () { state.access = ""; $("accessFilter").value = ""; render(); pushURL(); });
    if (state.q) chip('“' + state.q + '”', function () { state.q = ""; $("search").value = ""; render(); });
    if (COORDS) chip("📍 Near me", function () { COORDS = null; localStorage.removeItem("sc-coords"); $("nearBtn").setAttribute("aria-pressed", "false"); state.sort = "time"; $("sortBy").value = "time"; render(); });
    if (box.children.length) chip("Clear all", function () {
      state = { film: "", date: "all", group: state.group, access: "", cinemas: [], sort: COORDS ? "near" : "time", q: "" };
      $("search").value = ""; $("accessFilter").value = "";
      syncDateStrip(); syncRail(); syncCinemaMenu(); render(); pushURL();
    }, "clear");
  }

  // ---------- URL state ----------
  function pushURL() {
    var p = new URLSearchParams();
    if (state.film) p.set("film", state.film);
    if (state.date !== "all") p.set("date", state.date);
    if (state.group !== "cinema") p.set("group", state.group);
    if (state.cinemas.length) p.set("cinemas", state.cinemas.join(","));
    if (state.access) p.set("access", state.access);
    var qs = p.toString();
    history.replaceState(null, "", qs ? "?" + qs : location.pathname);
  }
  function readURL() {
    var p = new URLSearchParams(location.search);
    if (p.get("group")) state.group = p.get("group");
    if (p.get("film")) state.film = p.get("film");
    if (p.get("date")) state.date = p.get("date");
    if (p.get("cinemas")) state.cinemas = p.get("cinemas").split(",").filter(function (id) { return CINEMAS[id]; });
    if (p.get("access")) { state.access = p.get("access"); $("accessFilter").value = state.access; }
    syncGroup(); syncDateStrip(); syncRail(); syncCinemaMenu();
    // open the drawer if a shared link arrives with advanced filters applied
    if (state.date !== "all" || state.cinemas.length || state.access) {
      $("filtersPanel").hidden = false; $("filtersBtn").setAttribute("aria-expanded", "true");
    }
  }

  // ---------- to-top ----------
  var toTop = $("toTop");
  addEventListener("scroll", function () { toTop.hidden = scrollY < 600; }, { passive: true });
  toTop.addEventListener("click", function () { window.scrollTo({ top: 0, behavior: "smooth" }); });
})();
