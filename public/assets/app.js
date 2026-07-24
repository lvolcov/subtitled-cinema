/* Subtitled Cinema — client (v2).
   Static, dependency-free. Adds: real posters, film & cinema detail dialogs
   ("pick a film -> every cinema showing it"), shareable URL state, a date
   strip, active-filter chips, persisted "nearest", and a11y dialogs. */
(function () {
  "use strict";

  var state = {
    data: null, flat: [],
    day: "all", search: "", cinema: "", access: "", groupBy: "cinema",
    near: false, coords: null,
    view: null,            // {type:'film'|'cinema', id} when a dialog is open
  };
  var lastFocus = null;    // element to restore focus to when a dialog closes

  // ---- date/format helpers ---------------------------------------------
  var WD = ["Sun","Mon","Tue","Wed","Thu","Fri","Sat"];
  var MO = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];

  function parseLocal(iso) {
    var m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/.exec(iso);
    return m ? new Date(+m[1], +m[2]-1, +m[3], +m[4], +m[5]) : null;
  }
  function startOfDay(d){ return new Date(d.getFullYear(), d.getMonth(), d.getDate()); }
  function sameDay(a,b){ return startOfDay(a).getTime() === startOfDay(b).getTime(); }
  function isoDay(d){ return d.getFullYear()+"-"+String(d.getMonth()+1).padStart(2,"0")+"-"+String(d.getDate()).padStart(2,"0"); }
  function fmtTime(d){ return String(d.getHours()).padStart(2,"0")+":"+String(d.getMinutes()).padStart(2,"0"); }
  function fmtDayLabel(d, now){
    if (sameDay(d, now)) return "Today";
    var t = new Date(now); t.setDate(t.getDate()+1);
    if (sameDay(d, t)) return "Tomorrow";
    return WD[d.getDay()]+" "+d.getDate()+" "+MO[d.getMonth()];
  }
  function fmtRelative(d, now){
    var mins = (d - now)/60000;
    if (mins < 0) return "";
    if (mins < 60) return "in "+Math.round(mins)+" min";
    if (mins < 180) return "in "+Math.round(mins/60*10)/10+" h";
    return "";
  }
  function hashHue(s){ var h=0; for(var i=0;i<s.length;i++) h=(h*31+s.charCodeAt(i))%360; return h; }
  function initials(t){ var w=t.replace(/[^A-Za-z0-9 ]/g,"").trim().split(/\s+/); return ((w[0]||"?")[0]+(w[1]?w[1][0]:"")).toUpperCase(); }
  function haversineMi(a,b){
    var R=3958.8,toR=Math.PI/180, dLat=(b.lat-a.lat)*toR, dLng=(b.lng-a.lng)*toR, la1=a.lat*toR, la2=b.lat*toR;
    var x=Math.sin(dLat/2)**2 + Math.cos(la1)*Math.cos(la2)*Math.sin(dLng/2)**2;
    return R*2*Math.atan2(Math.sqrt(x), Math.sqrt(1-x));
  }
  function esc(s){ return String(s==null?"":s).replace(/[&<>"']/g, function(c){ return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]; }); }
  function now(){ return window.__NOW__ ? new Date(window.__NOW__) : new Date(); }

  // ---- data prep --------------------------------------------------------
  function flatten(data){
    var byId = {}; data.cinemas.forEach(function(c){ byId[c.id]=c; });
    state.cinemaById = byId;
    var filmById = {}; data.films.forEach(function(f){ filmById[f.id]=f; });
    state.filmById = filmById;
    var out = [];
    data.cinemas.forEach(function(c){
      c.screenings.forEach(function(s){
        var d = parseLocal(s.starts_at); if(!d) return;
        out.push({
          date:d, title:s.title, film_id:s.film_id, poster_url:s.poster_url,
          certificate:s.certificate, accessibility:s.accessibility||[],
          screen_type:s.screen_type, language:s.language, note:s.note,
          imdb_url:s.imdb_url, source_url:s.source_url,
          cinema_id:c.id, cinema_name:c.name, area:c.area, chain:c.chain,
          postcode:c.postcode, booking_url:c.booking_url, last_checked:c.last_checked,
          lat:c.lat, lng:c.lng,
        });
      });
    });
    return out;
  }

  function futureOf(list){
    var cutoff = now().getTime() - 60*60*1000;
    return list.filter(function(s){ return s.date.getTime() >= cutoff; });
  }

  // ---- filtering --------------------------------------------------------
  function passesFilters(s, n){
    var tomorrow = new Date(n); tomorrow.setDate(tomorrow.getDate()+1);
    var weekEnd = new Date(n); weekEnd.setDate(weekEnd.getDate()+7);
    if (state.day === "today" && !sameDay(s.date, n)) return false;
    if (state.day === "tomorrow" && !sameDay(s.date, tomorrow)) return false;
    if (state.day === "week" && (s.date < startOfDay(n) || s.date > weekEnd)) return false;
    if (/^\d{4}-\d{2}-\d{2}$/.test(state.day) && isoDay(s.date) !== state.day) return false;
    if (state.cinema && s.cinema_id !== state.cinema) return false;
    if (state.access && s.accessibility.indexOf(state.access) === -1) return false;
    if (state.search){
      var q = state.search.trim().toLowerCase();
      var hay = (s.title+" "+s.cinema_name+" "+(s.area||"")+" "+(s.chain||"")).toLowerCase();
      if (hay.indexOf(q) === -1) return false;
    }
    return true;
  }
  function visible(n){ return futureOf(state.flat).filter(function(s){ return passesFilters(s, n); }); }

  function withDistance(list){
    if (!state.coords) return list;
    list.forEach(function(s){
      s.dist = (s.lat!=null && s.lng!=null) ? haversineMi(state.coords,{lat:s.lat,lng:s.lng}) : null;
    });
    return list;
  }

  // ---- grouping ---------------------------------------------------------
  function group(list, n){
    var mode = state.near ? "cinema" : state.groupBy;
    var groups = {}, order = [];
    list.forEach(function(s){
      var key,label,sub;
      if (mode==="film"){ key=s.film_id; label=s.title; sub=s.certificate||""; }
      else if (mode==="day"){ key=isoDay(s.date); label=fmtDayLabel(s.date,n); sub=""; }
      else { key=s.cinema_id; label=s.cinema_name; sub=s.chain||""; }
      if(!groups[key]){ groups[key]={key:key,mode:mode,label:label,sub:sub,items:[],sample:s}; order.push(key); }
      groups[key].items.push(s);
    });
    order.forEach(function(k){ groups[k].items.sort(function(a,b){ return a.date-b.date; }); });
    order.sort(function(a,b){
      var ga=groups[a], gb=groups[b];
      if (mode==="day") return ga.items[0].date-gb.items[0].date;
      if (state.near){
        var da=ga.sample.dist==null?Infinity:ga.sample.dist, db=gb.sample.dist==null?Infinity:gb.sample.dist;
        if (da!==db) return da-db;
      }
      if (mode==="cinema") return ga.label.localeCompare(gb.label);
      return gb.items.length-ga.items.length;
    });
    return order.map(function(k){ return groups[k]; });
  }

  // ---- rendering: poster + badges + card --------------------------------
  function posterHTML(item, big){
    var cls = big ? "poster poster-lg" : "poster";
    var hue = hashHue(item.title);
    var fallback = '<span class="poster-fallback" style="background:linear-gradient(150deg,hsl('+hue+' 70% 62%),hsl('+((hue+40)%360)+' 70% 48%))">'+esc(initials(item.title))+'</span>';
    if (item.poster_url){
      return '<div class="'+cls+'">'+fallback+
        '<img src="'+esc(item.poster_url)+'" alt="" loading="lazy" '+
        'onload="this.classList.add(\'loaded\')" onerror="this.remove()"></div>';
    }
    return '<div class="'+cls+'">'+fallback+'</div>';
  }
  function badgesHTML(s){
    var b="";
    if (s.certificate) b+='<span class="badge cert">'+esc(s.certificate)+'</span>';
    if (s.language==="foreign") b+='<span class="badge foreign">Subtitles</span>';
    else if (s.accessibility.indexOf("subtitled")!==-1) b+='<span class="badge sub">Captioned</span>';
    if (s.accessibility.indexOf("audio-described")!==-1) b+='<span class="badge ad">Audio described</span>';
    if (s.screen_type==="imax") b+='<span class="badge imax">IMAX</span>';
    return b;
  }
  function noteHTML(s){
    var n=(s.note||"").toLowerCase();
    return /parent|baby|relax|dubbed|double check/.test(n) ? '<div class="note">⚠ '+esc(s.note)+'</div>' : "";
  }
  function mapsUrl(s){
    if (s.lat!=null && s.lng!=null) return "https://www.google.com/maps/search/?api=1&query="+s.lat+","+s.lng;
    return "https://www.google.com/maps/search/?api=1&query="+encodeURIComponent(s.cinema_name+" "+(s.postcode||"")+" cinema");
  }
  function linksHTML(s){
    var h='<div class="links">';
    if (s.booking_url) h+='<a class="primary" href="'+esc(s.booking_url)+'" target="_blank" rel="noopener">Book</a>';
    h+='<a href="'+esc(mapsUrl(s))+'" target="_blank" rel="noopener">Map</a>';
    if (s.imdb_url) h+='<a href="'+esc(s.imdb_url)+'" target="_blank" rel="noopener">IMDb</a>';
    h+='</div>';
    return h;
  }

  function cardHTML(s, n){
    var soon = fmtRelative(s.date, n);
    var when = '<span class="when">'+fmtDayLabel(s.date,n)+" "+fmtTime(s.date)+'</span>'+
               (soon?' <span class="soon">· '+esc(soon)+'</span>':"");
    var dist = (s.dist!=null)?'<span class="dist">'+s.dist.toFixed(1)+' mi</span>':"";
    return '<article class="card" data-cinema="'+esc(s.cinema_id)+'" data-title="'+esc(s.title)+
      '" data-film="'+esc(s.film_id)+'" data-day="'+isoDay(s.date)+'">'+
      '<button class="poster-btn" data-open-film="'+esc(s.film_id)+'" aria-label="See all cinemas showing '+esc(s.title)+'">'+
        posterHTML(s,false)+'</button>'+
      '<div class="card-body">'+
        '<button class="film-title linky" data-open-film="'+esc(s.film_id)+'">'+esc(s.title)+'</button>'+
        '<div class="badges">'+badgesHTML(s)+'</div>'+
        '<div class="meta">'+when+'</div>'+
        '<div class="cinema-line"><button class="name linky" data-open-cinema="'+esc(s.cinema_id)+'">'+esc(s.cinema_name)+'</button>'+
          (s.postcode?'<span class="pc">'+esc(s.postcode)+'</span>':"")+dist+'</div>'+
        noteHTML(s)+linksHTML(s)+
      '</div></article>';
  }

  function render(){
    var n = now();
    var results = document.getElementById("results");
    var empty = document.getElementById("emptyState");
    var summary = document.getElementById("resultSummary");

    var list = withDistance(visible(n));
    summary.textContent = list.length+" screening"+(list.length===1?"":"s")+
      (state.near && state.coords ? " · nearest first" : "");

    if (!list.length){ results.innerHTML=""; empty.hidden=false; }
    else {
      empty.hidden=true;
      var groups = group(list, n);
      results.innerHTML = groups.map(function(g){
        var checked = g.sample.last_checked ? '<span class="checked">checked '+esc(g.sample.last_checked.slice(0,10))+'</span>' : "";
        var count = '<span class="gcount">'+g.items.length+'</span>';
        var distTag = (state.near && g.sample.dist!=null)?'<span class="dist">'+g.sample.dist.toFixed(1)+' mi</span>':"";
        var sub = g.sub ? '<span class="sub">'+esc(g.sub)+'</span>' : "";
        var clickable = (g.mode==="cinema")?' data-open-cinema="'+esc(g.key)+'"':(g.mode==="film")?' data-open-film="'+esc(g.key)+'"':"";
        var head = '<h2 class="group-title"'+clickable+'>'+esc(g.label)+' '+sub+distTag+count+checked+'</h2>';
        return head+'<div class="cards">'+g.items.map(function(s){ return cardHTML(s,n); }).join("")+'</div>';
      }).join("");
    }
    renderChips();
    updateSegActive();
  }

  // ---- active filter chips ---------------------------------------------
  function renderChips(){
    var wrap = document.getElementById("activeChips");
    var chips = [];
    if (state.search) chips.push(["search","“"+state.search+"”"]);
    if (state.day!=="all"){
      var lbl = state.day==="today"?"Today":state.day==="tomorrow"?"Tomorrow":state.day==="week"?"This week":state.day;
      chips.push(["day", lbl]);
    }
    if (state.cinema && state.cinemaById[state.cinema]) chips.push(["cinema", state.cinemaById[state.cinema].name]);
    if (state.access) chips.push(["access", state.access==="audio-described"?"Audio described":"Subtitled"]);
    if (state.near) chips.push(["near","📍 Nearest"]);
    if (!chips.length){ wrap.innerHTML=""; return; }
    wrap.innerHTML = chips.map(function(c){
      return '<button class="fchip" data-clear="'+c[0]+'">'+esc(c[1])+' <span aria-hidden="true">✕</span></button>';
    }).join("")+'<button class="fchip clear-all" data-clear="all">Clear all</button>';
  }
  function clearFilter(kind){
    if (kind==="all"){ state.search=""; state.day="all"; state.cinema=""; state.access=""; state.near=false; }
    else if (kind==="search") state.search="";
    else if (kind==="day") state.day="all";
    else if (kind==="cinema") state.cinema="";
    else if (kind==="access") state.access="";
    else if (kind==="near"){ state.near=false; setNearBtn(false); }
    syncControls(); writeURL(false); render();
  }

  // ---- date strip -------------------------------------------------------
  function buildDateStrip(){
    var strip = document.getElementById("dateStrip");
    var n = now();
    var days = {};
    futureOf(state.flat).forEach(function(s){ days[isoDay(s.date)] = s.date; });
    var sorted = Object.keys(days).sort().slice(0,14);
    var chips = [["all","All"],["today","Today"],["tomorrow","Tomorrow"]];
    sorted.forEach(function(k){
      var d = days[k];
      if (sameDay(d,n)) return;
      var t=new Date(n); t.setDate(t.getDate()+1); if (sameDay(d,t)) return;
      chips.push([k, WD[d.getDay()]+" "+d.getDate()+" "+MO[d.getMonth()]]);
    });
    strip.innerHTML = chips.map(function(c){
      return '<button class="seg-btn" data-day="'+c[0]+'" type="button">'+esc(c[1])+'</button>';
    }).join("");
    strip.querySelectorAll(".seg-btn").forEach(function(b){
      b.addEventListener("click", function(){ state.day=b.dataset.day; writeURL(false); render(); });
    });
  }
  function updateSegActive(){
    document.querySelectorAll("#dateStrip .seg-btn").forEach(function(b){
      b.classList.toggle("active", b.dataset.day===state.day);
    });
  }

  // ---- detail dialogs ---------------------------------------------------
  function openFilm(id){ state.view={type:"film",id:id}; writeURL(true); renderModal(); }
  function openCinema(id){ state.view={type:"cinema",id:id}; writeURL(true); renderModal(); }
  function closeModal(){
    if (!state.view) return;
    state.view=null; writeURL(true); renderModal();
  }

  function filmModalHTML(film){
    var n = now();
    var shows = withDistance(futureOf(state.flat).filter(function(s){ return s.film_id===film.id; }));
    // group by cinema
    var byC={}, order=[];
    shows.forEach(function(s){ if(!byC[s.cinema_id]){ byC[s.cinema_id]={sample:s,items:[]}; order.push(s.cinema_id);} byC[s.cinema_id].items.push(s); });
    if (state.coords) order.sort(function(a,b){ return (byC[a].sample.dist==null?Infinity:byC[a].sample.dist)-(byC[b].sample.dist==null?Infinity:byC[b].sample.dist); });
    else order.sort(function(a,b){ return byC[a].sample.cinema_name.localeCompare(byC[b].sample.cinema_name); });
    var sample = shows[0] || {title:film.title, poster_url:film.poster_url};
    var head =
      '<div class="modal-head">'+posterHTML({title:film.title,poster_url:film.poster_url},true)+
      '<div><h2 id="modalTitle" class="modal-title">'+esc(film.title)+'</h2>'+
      '<div class="badges">'+(sample.certificate?'<span class="badge cert">'+esc(sample.certificate)+'</span>':"")+
        (film.poster_url?"":"")+'</div>'+
      '<p class="modal-sub">Showing subtitled at <b>'+order.length+'</b> cinema'+(order.length===1?"":"s")+' · '+shows.length+' screening'+(shows.length===1?"":"s")+'</p>'+
      (sample.imdb_url?'<div class="links"><a href="'+esc(sample.imdb_url)+'" target="_blank" rel="noopener">IMDb</a></div>':"")+
      '</div></div>';
    var body = order.map(function(cid){
      var g=byC[cid], c=g.sample;
      var dist=(c.dist!=null)?'<span class="dist">'+c.dist.toFixed(1)+' mi</span>':"";
      var times = g.items.map(function(s){
        return '<a class="showtime-pill" href="'+esc(s.booking_url||mapsUrl(s))+'" target="_blank" rel="noopener" title="Book / info">'+
          fmtDayLabel(s.date,n)+' '+fmtTime(s.date)+'</a>';
      }).join("");
      return '<div class="modal-cinema"><div class="modal-cinema-head">'+
        '<button class="name linky" data-open-cinema="'+esc(cid)+'">'+esc(c.cinema_name)+'</button>'+
        (c.postcode?'<span class="pc">'+esc(c.postcode)+'</span>':"")+dist+
        '<a class="mini" href="'+esc(mapsUrl(c))+'" target="_blank" rel="noopener">Map</a></div>'+
        '<div class="showtimes">'+times+'</div></div>';
    }).join("");
    return head+'<div class="modal-body">'+body+'</div>';
  }

  function cinemaModalHTML(cinema){
    var n = now();
    var shows = withDistance(futureOf(state.flat).filter(function(s){ return s.cinema_id===cinema.id; }));
    shows.sort(function(a,b){ return a.date-b.date; });
    var byDay={}, order=[];
    shows.forEach(function(s){ var k=isoDay(s.date); if(!byDay[k]){byDay[k]={label:fmtDayLabel(s.date,n),items:[]};order.push(k);} byDay[k].items.push(s); });
    var c0 = shows[0];
    var dist = (c0 && c0.dist!=null)?' · <span class="dist">'+c0.dist.toFixed(1)+' mi</span>':"";
    var head = '<div class="modal-head col">'+
      '<h2 id="modalTitle" class="modal-title">'+esc(cinema.name)+'</h2>'+
      '<p class="modal-sub">'+esc(cinema.chain||"Cinema")+(cinema.postcode?' · '+esc(cinema.postcode):"")+dist+' · '+shows.length+' subtitled screening'+(shows.length===1?"":"s")+'</p>'+
      '<div class="links">'+(cinema.booking_url?'<a class="primary" href="'+esc(cinema.booking_url)+'" target="_blank" rel="noopener">Cinema site</a>':"")+
        '<a href="'+esc(mapsUrl(c0||{cinema_name:cinema.name,postcode:cinema.postcode,lat:cinema.lat,lng:cinema.lng}))+'" target="_blank" rel="noopener">Open in Maps</a></div>'+
      '</div>';
    var body = order.map(function(k){
      var g=byDay[k];
      var pills = g.items.map(function(s){
        return '<button class="showtime-pill" data-open-film="'+esc(s.film_id)+'">'+fmtTime(s.date)+' · '+esc(s.title)+'</button>';
      }).join("");
      return '<div class="modal-cinema"><div class="modal-cinema-head"><span class="name">'+esc(g.label)+'</span></div><div class="showtimes col">'+pills+'</div></div>';
    }).join("");
    return head+'<div class="modal-body">'+body+'</div>';
  }

  function renderModal(){
    var root = document.getElementById("modalRoot");
    var content = document.getElementById("modalContent");
    if (!state.view){
      root.hidden = true; document.body.classList.remove("modal-open");
      if (lastFocus && lastFocus.focus){ lastFocus.focus(); lastFocus=null; }
      return;
    }
    var html="";
    if (state.view.type==="film" && state.filmById[state.view.id]) html = filmModalHTML(state.filmById[state.view.id]);
    else if (state.view.type==="cinema" && state.cinemaById[state.view.id]) html = cinemaModalHTML(state.cinemaById[state.view.id]);
    else { state.view=null; root.hidden=true; return; }
    content.innerHTML = html;
    root.hidden = false; document.body.classList.add("modal-open");
    var dialog = root.querySelector(".modal");
    lastFocus = lastFocus || document.activeElement;
    dialog.focus();
  }

  // ---- URL state --------------------------------------------------------
  function writeURL(push){
    var p = new URLSearchParams();
    if (state.search) p.set("q", state.search);
    if (state.day!=="all") p.set("day", state.day);
    if (state.cinema) p.set("cinema", state.cinema);
    if (state.access) p.set("access", state.access);
    if (state.groupBy!=="cinema") p.set("group", state.groupBy);
    if (state.near) p.set("near","1");
    if (state.view) p.set("view", state.view.type+":"+state.view.id);
    var url = location.pathname + (p.toString()?"?"+p.toString():"");
    if (push) history.pushState({app:1}, "", url);
    else history.replaceState({app:1}, "", url);
  }
  function readURL(){
    var p = new URLSearchParams(location.search);
    state.search = p.get("q") || "";
    state.day = p.get("day") || "all";
    state.cinema = p.get("cinema") || "";
    state.access = p.get("access") || "";
    state.groupBy = p.get("group") || "cinema";
    state.near = p.get("near")==="1";
    var v = p.get("view");
    if (v){ var i=v.indexOf(":"); state.view = i>0 ? {type:v.slice(0,i), id:v.slice(i+1)} : null; }
    else state.view = null;
    if (state.near && !state.coords && window.__COORDS__) state.coords = window.__COORDS__;
  }
  function onPop(){ readURL(); syncControls(); render(); renderModal(); }

  // ---- controls sync/wiring --------------------------------------------
  function syncControls(){
    document.getElementById("search").value = state.search;
    document.getElementById("cinemaFilter").value = state.cinema;
    document.getElementById("accessFilter").value = state.access;
    document.getElementById("groupBy").value = state.groupBy;
    setNearBtn(state.near);
  }
  function setNearBtn(on){
    var b=document.getElementById("nearBtn");
    b.setAttribute("aria-pressed", on?"true":"false");
    b.textContent = on ? "📍 Nearest ✓" : "📍 Nearest";
  }
  function fillCinemaFilter(){
    var sel=document.getElementById("cinemaFilter");
    state.data.cinemas.slice().sort(function(a,b){ return a.name.localeCompare(b.name); }).forEach(function(c){
      var o=document.createElement("option"); o.value=c.id; o.textContent=c.name+" ("+c.screenings.length+")"; sel.appendChild(o);
    });
  }
  function renderStats(){
    var s=state.data.stats;
    document.getElementById("stats").innerHTML =
      '<span><b>'+s.cinemas+'</b>cinemas</span><span><b>'+s.screenings+'</b>screenings</span><span><b>'+s.films+'</b>films</span>';
    var gen=state.data.generated_at||"";
    document.getElementById("lastUpdated").textContent =
      "Listings last updated "+gen.replace("T"," ").slice(0,16)+" ("+state.data.timezone+").";
  }

  function bind(){
    document.getElementById("search").addEventListener("input", function(e){ state.search=e.target.value; writeURL(false); render(); });
    document.getElementById("cinemaFilter").addEventListener("change", function(e){ state.cinema=e.target.value; writeURL(false); render(); });
    document.getElementById("accessFilter").addEventListener("change", function(e){ state.access=e.target.value; writeURL(false); render(); });
    document.getElementById("groupBy").addEventListener("change", function(e){ state.groupBy=e.target.value; writeURL(false); render(); });
    document.getElementById("nearBtn").addEventListener("click", onNear);

    // event delegation for opens / chip clears / modal close
    document.addEventListener("click", function(e){
      var t = e.target.closest("[data-open-film],[data-open-cinema],[data-clear],[data-close]");
      if (!t) return;
      if (t.hasAttribute("data-open-film")){ e.preventDefault(); openFilm(t.getAttribute("data-open-film")); }
      else if (t.hasAttribute("data-open-cinema")){ e.preventDefault(); openCinema(t.getAttribute("data-open-cinema")); }
      else if (t.hasAttribute("data-clear")){ clearFilter(t.getAttribute("data-clear")); }
      else if (t.hasAttribute("data-close")){ closeModal(); }
    });
    // Esc closes modal; focus trap
    document.addEventListener("keydown", function(e){
      if (!state.view) return;
      if (e.key==="Escape"){ closeModal(); return; }
      if (e.key==="Tab"){
        var f = document.querySelectorAll("#modalRoot a,#modalRoot button");
        if (!f.length) return;
        var first=f[0], last=f[f.length-1];
        if (e.shiftKey && document.activeElement===first){ e.preventDefault(); last.focus(); }
        else if (!e.shiftKey && document.activeElement===last){ e.preventDefault(); first.focus(); }
      }
    });
    window.addEventListener("popstate", onPop);

    // back-to-top
    var toTop=document.getElementById("toTop");
    window.addEventListener("scroll", function(){ toTop.hidden = window.scrollY < 600; });
    toTop.addEventListener("click", function(){ window.scrollTo({top:0,behavior:"smooth"}); });
  }

  function onNear(){
    if (state.near){ state.near=false; setNearBtn(false); writeURL(false); render(); return; }
    if (!state.coords && window.__COORDS__) state.coords = window.__COORDS__;
    if (!state.coords){
      try { var saved=JSON.parse(localStorage.getItem("sc_coords")||"null"); if(saved) state.coords=saved; } catch(_){}
    }
    if (state.coords){ activateNear(); return; }
    var b=document.getElementById("nearBtn");
    if (!navigator.geolocation){ b.textContent="Location unavailable"; return; }
    b.textContent="Locating…";
    navigator.geolocation.getCurrentPosition(function(pos){
      state.coords={lat:pos.coords.latitude,lng:pos.coords.longitude};
      try{ localStorage.setItem("sc_coords", JSON.stringify(state.coords)); }catch(_){}
      activateNear();
    }, function(){ setNearBtn(false); });
  }
  function activateNear(){ state.near=true; setNearBtn(true); writeURL(false); render(); }

  // ---- boot -------------------------------------------------------------
  function boot(data){
    state.data=data; state.flat=flatten(data);
    document.getElementById("skeleton").remove();
    renderStats(); fillCinemaFilter(); buildDateStrip();
    readURL(); syncControls(); bind();
    render(); renderModal();
    document.body.dataset.ready="1";
  }

  if (window.__DATA__) boot(window.__DATA__);
  else fetch("data.json").then(function(r){ return r.json(); }).then(boot).catch(function(e){
    var sk=document.getElementById("skeleton"); if(sk) sk.remove();
    document.getElementById("results").innerHTML='<p class="empty">Could not load listings. '+esc(e.message)+'</p>';
    document.body.dataset.ready="1";
  });
})();
