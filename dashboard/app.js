(() => {
  "use strict";
  const D = window.COVID_DATA;
  const N = D.meta.days;
  const MONTHS = Charts.MONTHS;
  const nf = new Intl.NumberFormat("en-US");
  const bad = (v) => v == null || !isFinite(v);
  const fmt = (v) => (bad(v) ? "n/a" : nf.format(Math.round(v)));
  const fmt1 = (v) => (bad(v) ? "n/a" : v.toLocaleString("en-US", { minimumFractionDigits: 1, maximumFractionDigits: 1 }));
  const pct2 = (v) => (bad(v) ? "n/a" : (v * 100).toFixed(2) + "%");
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));

  // ---- dates
  const [fy, fm, fd] = D.meta.first.split("-").map(Number);
  const base = Date.UTC(fy, fm - 1, fd);
  const dates = Array.from({ length: N }, (_, i) => new Date(base + i * 864e5).toISOString().slice(0, 10));
  const fmtDate = (iso) => `${Number(iso.slice(8))} ${MONTHS[Number(iso.slice(5, 7)) - 1]} ${iso.slice(0, 4)}`;
  const dateLabel = (i) => fmtDate(dates[i]);
  const indexOf = (iso) => Math.round((Date.UTC(+iso.slice(0, 4), +iso.slice(5, 7) - 1, +iso.slice(8, 10)) - base) / 864e5);
  const clamp = (i) => Math.max(0, Math.min(N - 1, i));
  const recoveryEnd = indexOf(D.meta.recoveryLastDate);

  // ---- countries with cumulative arrays
  const countries = D.countries.map((c) => {
    const s = D.series[c.iso];
    const daily = Float64Array.from(s.c);
    const deaths = Float64Array.from(s.d);
    const cumC = new Float64Array(N);
    const cumD = new Float64Array(N);
    let a = 0;
    let b = 0;
    for (let i = 0; i < N; i++) {
      a += daily[i];
      b += deaths[i];
      cumC[i] = a;
      cumD[i] = b;
    }
    let lastR = -1;
    for (let i = N - 1; i >= 0; i--) if (s.r[i] != null) { lastR = i; break; }
    return { ...c, c: daily, d: deaths, r: s.r, rev: s.rev, inc: s.inc, cumC, cumD, lastR };
  });
  const byIso = Object.fromEntries(countries.map((c) => [c.iso, c]));
  const REGION_COLOURS = { Europe: "#2F3A36", Asia: "#6B8676", Americas: "#9DB0A5", Oceania: "#C7D3CC", Africa: "#D8C9A6", Antarctica: "#8F8F89" };

  // ---- state
  const defaults = () => ({ region: "", country: "", from: 0, to: N - 1, search: "", sortKey: "cases", sortDir: "desc", warnOnly: false });
  const state = { page: "overview", ...defaults() };
  const PAGES = {
    overview: "COVID-19 global overview",
    trends: "Global trends",
    compare: "Country comparison",
    detail: "Country detail",
    quality: "Data quality and methodology",
  };

  const browse = () => countries.filter((c) => !state.region || c.region === state.region);
  const scopeList = () => (state.country ? [byIso[state.country]] : browse());

  // ---- aggregation
  function rolling(arr) {
    const out = new Float64Array(N).fill(NaN);
    let sum = 0;
    for (let i = 0; i < N; i++) {
      sum += arr[i];
      if (i >= 7) sum -= arr[i - 7];
      if (i >= 6) out[i] = sum / 7;
    }
    return out;
  }
  const cache = new Map();
  function agg() {
    const key = state.country ? "C:" + state.country : "R:" + state.region;
    if (cache.has(key)) return cache.get(key);
    const dc = new Float64Array(N);
    const dd = new Float64Array(N);
    scopeList().forEach((c) => {
      for (let i = 0; i < N; i++) {
        dc[i] += c.c[i];
        dd[i] += c.d[i];
      }
    });
    const cumC = new Float64Array(N);
    const cumD = new Float64Array(N);
    let a = 0;
    let b = 0;
    for (let i = 0; i < N; i++) {
      a += dc[i];
      b += dd[i];
      cumC[i] = a;
      cumD[i] = b;
    }
    const result = { dc, dd, cumC, cumD, avgC: rolling(dc), avgD: rolling(dd) };
    cache.set(key, result);
    return result;
  }
  const inPeriod = (cum, f, b) => cum[b] - (f > 0 ? cum[f - 1] : 0);
  function peak(values, f, b) {
    let best = -Infinity;
    let at = -1;
    for (let i = f; i <= b; i++) if (!isNaN(values[i]) && values[i] > best) { best = values[i]; at = i; }
    return at < 0 ? null : { value: best, index: at };
  }
  function rates(list, b) {
    let cases = 0;
    let deaths = 0;
    let pop = 0;
    list.forEach((c) => {
      if (c.pop != null) { cases += c.cumC[b]; deaths += c.cumD[b]; pop += c.pop; }
    });
    return { pop, c100: pop ? (cases / pop) * 1e5 : null, d100: pop ? (deaths / pop) * 1e5 : null };
  }
  const rankByCases = (iso, b) => 1 + countries.filter((c) => c.cumC[b] > byIso[iso].cumC[b]).length;
  const cfr = (cases, deaths) => (cases > 0 ? deaths / cases : null);

  const legend = (items) => items.map((it) => `<span><i style="background:${it.color}"></i>${it.label}</span>`).join("");
  const scopeName = () => (state.country ? byIso[state.country].name : state.region ? state.region : "All countries");
  const warnings = D.dq.filter((r) => r.Section !== "Summary" && r.Status === "WARNING").length;

  // ---- header and filters
  function renderHeader() {
    const f = state.from;
    const b = state.to;
    const where = state.country ? byIso[state.country].name
      : state.region ? `${state.region} (${browse().length} countries)` : `all ${countries.length} countries`;
    $("#scopeLine").textContent = `Showing ${where}, ${fmtDate(dates[f])} to ${fmtDate(dates[b])} (${nf.format(b - f + 1)} days)`;
    $("#fromDate").value = dates[f];
    $("#toDate").value = dates[b];
    $("#regionSel").value = state.region;
    $("#countryInput").value = state.country ? byIso[state.country].name : "";
    $("#countryClear").hidden = !state.country;
    $$("#presets button").forEach((button) => {
      button.setAttribute("aria-pressed", String(Number(button.dataset.from) === f && Number(button.dataset.to) === b));
    });
    $("#dqCount").textContent = warnings;
  }

  // ---- overview
  function renderOverview() {
    const a = agg();
    const f = state.from;
    const b = state.to;
    const cases = a.cumC[b];
    const deaths = a.cumD[b];
    const kpi = (name, value, note) => {
      $(`[data-kpi="${name}"]`).textContent = value;
      if (note != null) $(`[data-kpi-note="${name}"]`).textContent = note;
    };
    kpi("cases", fmt(cases), `+${fmt(inPeriod(a.cumC, f, b))} in the selected period`);
    kpi("deaths", fmt(deaths), `+${fmt(inPeriod(a.cumD, f, b))} in the selected period`);
    kpi("cfr", pct2(cfr(cases, deaths)));
    const p = peak(a.avgC, f, b);
    kpi("peak", p ? fmt(p.value) : "n/a", p ? dateLabel(p.index) : "needs at least 7 days of data");

    $("#ovLegend").innerHTML = legend([
      { color: "#D6D8D2", label: "Daily cases" }, { color: "#2F3A36", label: "7-day average" }, { color: "#A33B32", label: "Negative day (revision)" }]);
    Charts.timeChart($("#ovDaily"), {
      dates, dateLabel, from: f, to: b,
      bars: { values: a.dc, color: "#D6D8D2", name: "Daily cases", format: fmt },
      lines: [{ values: a.avgC, color: "#2F3A36", name: "7-day average", format: fmt }],
      aria: `Daily reported cases and 7-day average for ${scopeName()}`,
    });

    const regionTotals = D.regions.map((name) => ({
      key: name, label: name, color: REGION_COLOURS[name] || "#8F8F89",
      value: countries.filter((c) => c.region === name).reduce((s, c) => s + c.cumC[b], 0),
    })).sort((x, y) => y.value - x.value);
    const total = regionTotals.reduce((s, r) => s + r.value, 0) || 1;
    Charts.donut($("#ovDonut"), {
      items: regionTotals, selected: state.region, format: fmt, aria: "Reported cases by region",
      onSelect: (key) => setRegion(state.region === key ? "" : key),
    });
    $("#ovRegions").innerHTML = regionTotals.map((r) =>
      `<li role="button" tabindex="0" data-region="${esc(r.key)}" aria-selected="${state.region === r.key}"><span><i style="background:${r.color}"></i>${esc(r.label)}</span>` +
      `<span>${r.value / total < 0.01 ? "<1%" : Math.round((r.value / total) * 100) + "%"}</span></li>`).join("");

    const list = scopeList();
    const r = rates(list, b);
    const one = state.country ? byIso[state.country] : null;
    const badge = one ? one.iso : state.region ? state.region.slice(0, 3).toUpperCase() : "ALL";
    $("#selCard").innerHTML = `<div class="iso">${esc(badge)}</div><div class="nm">${esc(scopeName())}</div>` +
      `<p class="note">${one ? esc(one.region + (one.sub ? " / " + one.sub : "")) : nf.format(list.length) + " countries in selection"}</p>` +
      `<div class="stats"><div><span>Population</span><b>${r.pop ? (r.pop >= 1e9 ? (r.pop / 1e9).toFixed(1) + "bn" : fmt(r.pop)) : "n/a"}</b></div>` +
      `<div><span>Cases per 100K</span><b>${fmt(r.c100)}</b></div><div><span>Deaths per 100K</span><b>${fmt(r.d100)}</b></div></div>` +
      (one ? `<p class="note">Rank by reported cases: ${rankByCases(one.iso, b)} of ${countries.length}</p><p style="margin-top:10px"><a class="btn" href="#detail">Open country detail</a></p>`
        : `<p class="note">Click a country in a ranking, the region chart or the comparison table to select it.</p><p style="margin-top:10px"><a class="btn ghost" href="#compare">Open comparison table</a></p>`) +
      (r.pop && list.some((c) => c.pop == null) ? `<p class="note" style="margin-top:6px">Rates use only countries with a population value.</p>` : "");

    const rows = browse().map((c) => ({ c, v: c.cumC[b] })).sort((x, y) => y.v - x.v).slice(0, 10);
    $("#topCasesNote").textContent = `Cumulative through ${dateLabel(b)}${state.region ? ", " + state.region : ""}. Click a country to select it.`;
    rankList($("#topCases"), rows.map((x) => ({ c: x.c, v: x.v, text: fmt(x.v) })));
    const floor = D.meta.rankingPopulationFloor;
    const rate = browse().filter((c) => c.pop != null && c.pop >= floor).map((c) => ({ c, v: (c.cumC[b] / c.pop) * 1e5 })).sort((x, y) => y.v - x.v).slice(0, 10);
    $("#topRateNote").textContent = `Countries with ${nf.format(floor)} or more people, cumulative through ${dateLabel(b)}.`;
    rankList($("#topRate"), rate.map((x) => ({ c: x.c, v: x.v, text: fmt(x.v) })));

    const overall = D.dq.find((x) => x.Item === "Overall validation status");
    const checks = D.dq.filter((x) => x.Section !== "Summary");
    const count = (s) => checks.filter((x) => x.Status === s).length;
    $("#ovDq").innerHTML = `<h2>Data validation</h2><span class="status" style="color:${overall.Value === "PASS" ? "#2F6F4F" : overall.Value === "FAIL" ? "#A33B32" : "#B7791F"}">${esc(overall.Value)}</span>` +
      `<span>${count("PASS")} pass &middot; ${count("WARNING")} warning &middot; ${count("FAIL")} fail</span>` +
      `<span class="note" style="flex:1;min-width:240px">Recovery figures are incomplete, and downward revisions and impossible values are flagged, not removed.</span><a class="btn" href="#quality">View data quality</a>`;
  }

  function rankList(root, rows) {
    const max = Math.max(...rows.map((x) => x.v), 1);
    root.innerHTML = rows.map((x, i) =>
      `<li role="button" tabindex="0" data-iso="${x.c.iso}" aria-selected="${state.country === x.c.iso}" title="${esc(x.c.name)}: ${x.text}">` +
      `<span class="rk">${i + 1}</span><span class="nm">${esc(x.c.name)}</span><span><i class="bar" style="display:block;width:${(x.v / max) * 100}%"></i></span><span class="vv">${x.text}</span></li>`).join("");
  }

  // ---- trends
  function monthly(values, f, b) {
    const groups = new Map();
    for (let i = f; i <= b; i++) {
      const key = dates[i].slice(0, 7);
      const g = groups.get(key) || { sum: 0, days: 0 };
      g.sum += values[i];
      g.days += 1;
      groups.set(key, g);
    }
    return Array.from(groups, ([key, g]) => {
      const [y, m] = key.split("-").map(Number);
      const days = new Date(Date.UTC(y, m, 0)).getUTCDate();
      return { label: `${MONTHS[m - 1]} ${String(y).slice(2)}`, title: `${MONTHS[m - 1]} ${y}`, sum: g.sum, partial: g.days < days, note: `${g.days} of ${days} days in the selection` };
    });
  }
  function monthChart(box, rows, color, light, name) {
    Charts.categoryBars(box, {
      labels: rows.map((r) => r.label), titles: rows.map((r) => r.title), values: rows.map((r) => r.sum),
      partial: rows.map((r) => r.partial), partialNote: rows.map((r) => r.note), color, lightColor: light, name, format: fmt,
      aria: `${name} by month for ${scopeName()}`,
    });
  }
  function renderTrends() {
    const a = agg();
    const f = state.from;
    const b = state.to;
    const swatch = (color, label) => ({ color, label });
    $("#trLegendC").innerHTML = legend([swatch("#D6D8D2", "Daily cases"), swatch("#2F3A36", "7-day average"), swatch("#A33B32", "Negative day (revision)")]);
    $("#trLegendD").innerHTML = legend([swatch("#E3C7C3", "Daily deaths"), swatch("#A33B32", "7-day average")]);
    $("#trLegendMC").innerHTML = legend([swatch("#6B8676", "Cases per month"), swatch("#C7D3CC", "Partial month")]);
    $("#trLegendMD").innerHTML = legend([swatch("#A33B32", "Deaths per month"), swatch("#E3C7C3", "Partial month")]);
    const common = { dates, dateLabel, from: f, to: b };
    Charts.timeChart($("#trDaily"), { ...common, bars: { values: a.dc, color: "#D6D8D2", name: "Daily cases", format: fmt },
      lines: [{ values: a.avgC, color: "#2F3A36", name: "7-day average", format: fmt }], aria: `Daily cases for ${scopeName()}` });
    Charts.timeChart($("#trDeaths"), { ...common, bars: { values: a.dd, color: "#E3C7C3", name: "Daily deaths", format: fmt },
      lines: [{ values: a.avgD, color: "#A33B32", name: "7-day average", format: fmt }], aria: `Daily deaths for ${scopeName()}` });
    monthChart($("#trMonthC"), monthly(a.dc, f, b), "#6B8676", "#C7D3CC", "Reported cases");
    monthChart($("#trMonthD"), monthly(a.dd, f, b), "#A33B32", "#E3C7C3", "Reported deaths");
    Charts.timeChart($("#trCumC"), { ...common, lines: [{ values: a.cumC, color: "#2F3A36", name: "Cumulative cases", format: fmt, width: 2 }], aria: `Cumulative cases for ${scopeName()}` });
    Charts.timeChart($("#trCumD"), { ...common, lines: [{ values: a.cumD, color: "#A33B32", name: "Cumulative deaths", format: fmt, width: 2 }], aria: `Cumulative deaths for ${scopeName()}` });
  }

  // ---- comparison table
  function tableRows() {
    const b = state.to;
    const q = state.search.trim().toLowerCase();
    const rows = browse().filter((c) => !q || [c.name, c.iso, c.iso2, c.region, c.sub || ""].some((t) => t.toLowerCase().includes(q))).map((c) => ({
      c, name: c.name, region: c.region, cases: c.cumC[b], deaths: c.cumD[b], pop: c.pop,
      c100: c.pop ? (c.cumC[b] / c.pop) * 1e5 : null, d100: c.pop ? (c.cumD[b] / c.pop) * 1e5 : null, cfr: cfr(c.cumC[b], c.cumD[b]),
    }));
    const dir = state.sortDir === "asc" ? 1 : -1;
    const key = state.sortKey;
    rows.sort((x, y) => {
      const u = x[key];
      const v = y[key];
      if (bad(u) && bad(v)) return x.name.localeCompare(y.name);
      if (bad(u)) return 1;
      if (bad(v)) return -1;
      return (typeof u === "string" ? u.localeCompare(v) : u - v) * dir || x.name.localeCompare(y.name);
    });
    return rows;
  }
  function renderCompare() {
    const rows = tableRows();
    const b = state.to;
    const max = Math.max(...rows.map((r) => r.cases), 1);
    $$("#cmpTable thead th").forEach((th) => {
      th.setAttribute("aria-sort", th.dataset.sort === state.sortKey ? (state.sortDir === "asc" ? "ascending" : "descending") : "none");
    });
    $("#cmpBody").innerHTML = rows.length ? rows.map((r) =>
      `<tr data-iso="${r.c.iso}" tabindex="0" aria-selected="${state.country === r.c.iso}"><td>${esc(r.name)}<small>${r.c.iso}</small></td><td>${esc(r.region)}</td>` +
      `<td class="num"><span class="inl" style="width:${Math.max(1, (r.cases / max) * 60)}px"></span>${fmt(r.cases)}</td><td class="num">${fmt(r.deaths)}</td>` +
      `<td class="num">${fmt(r.c100)}</td><td class="num">${fmt1(r.d100)}</td><td class="num">${pct2(r.cfr)}</td><td class="num">${fmt(r.pop)}</td></tr>`).join("")
      : `<tr><td colspan="8">No countries match "${esc(state.search)}".</td></tr>`;
    $("#tblCount").textContent = `${rows.length} of ${browse().length} countries${state.region ? " in " + state.region : ""}`;
    $("#tblNote").textContent = `Values are cumulative through ${dateLabel(b)}. Rates use one population figure per country and show n/a where population is missing. ` +
      `CFR is reported deaths divided by reported cases, and n/a when a country reported no cases. Click a row to select the country.`;
  }

  // ---- country detail
  function renderDetail() {
    const one = state.country ? byIso[state.country] : null;
    $("#detailEmpty").hidden = !!one;
    $("#detailBody").hidden = !one;
    if (!one) {
      const b = state.to;
      const picks = browse().slice().sort((x, y) => y.cumC[b] - x.cumC[b]).slice(0, 8);
      $("#detailEmpty").innerHTML = `<h2>No country selected</h2><p class="note" style="margin:6px 0 12px">Choose a country in the search box at the top, click one in a ranking or the comparison table, or pick one of the largest below.</p>` +
        `<div class="presets">${picks.map((c) => `<button type="button" data-pick="${c.iso}">${esc(c.name)}</button>`).join("")}</div>`;
      return;
    }
    const a = agg();
    const f = state.from;
    const b = state.to;
    const set = (key, value) => { $(`[data-dk="${key}"]`).textContent = value; };
    const note = (key, value) => { $(`[data-dn="${key}"]`).textContent = value; };
    $("#detailHead").innerHTML = `<div class="iso">${one.iso}</div><div><h2>${esc(one.name)}</h2><div class="tags"><span>ISO3 ${one.iso}</span><span>ISO2 ${esc(one.iso2)}</span>` +
      `<span>${esc(one.region)}</span><span>${esc(one.sub || "")}</span><span>Population ${one.pop == null ? "not available" : fmt(one.pop)}</span>` +
      (one.jhu !== one.name ? `<span>Source name: ${esc(one.jhu)}</span>` : "") + `</div></div>`;
    set("cases", fmt(a.cumC[b])); note("cases", `+${fmt(inPeriod(a.cumC, f, b))} in the selected period`);
    set("deaths", fmt(a.cumD[b])); note("deaths", `+${fmt(inPeriod(a.cumD, f, b))} in the selected period`);
    set("cfr", pct2(cfr(a.cumC[b], a.cumD[b])));
    const r = rates([one], b);
    set("c100", fmt(r.c100)); note("c100", one.pop == null ? "no population value" : `population ${fmt(one.pop)}`);
    set("d100", fmt1(r.d100)); note("d100", one.pop == null ? "no population value" : "reported deaths per 100,000 people");
    set("rank", String(rankByCases(one.iso, b))); note("rank", `of ${countries.length} countries, by cumulative cases`);
    const revDays = one.rev.filter((i) => i >= f && i <= b).length;
    set("rev", String(revDays)); note("rev", revDays ? "the country lowered a cumulative total on these days" : "no downward revisions in this period");
    if (one.lastR < 0) { set("rec", "n/a"); note("rec", "this country has no recovery series in the source"); }
    else {
      const at = Math.min(one.lastR, b);
      set("rec", fmt(one.r[at]));
      note("rec", `as of ${dateLabel(at)}${one.lastR < recoveryEnd - 30 ? ", where the country's series stops" : one.lastR === recoveryEnd && b >= recoveryEnd ? ", where the source series ends" : ""}`);
    }

    $("#dtLegendC").innerHTML = legend([{ color: "#D6D8D2", label: "Daily cases" }, { color: "#2F3A36", label: "7-day average" }, { color: "#A33B32", label: "Negative day" }]);
    $("#dtLegendD").innerHTML = legend([{ color: "#E3C7C3", label: "Daily deaths" }, { color: "#A33B32", label: "7-day average" }]);
    const flagged = (i) => (one.rev.includes(i) ? `<div class="warn">Revision_Flag set for this day</div>` : "");
    const common = { dates, dateLabel, from: f, to: b, extra: flagged };
    Charts.timeChart($("#dtDaily"), { ...common, bars: { values: a.dc, color: "#D6D8D2", name: "Daily cases", format: fmt },
      lines: [{ values: a.avgC, color: "#2F3A36", name: "7-day average", format: fmt }], aria: `Daily cases for ${one.name}` });
    Charts.timeChart($("#dtDeaths"), { ...common, bars: { values: a.dd, color: "#E3C7C3", name: "Daily deaths", format: fmt },
      lines: [{ values: a.avgD, color: "#A33B32", name: "7-day average", format: fmt }], aria: `Daily deaths for ${one.name}` });
    Charts.timeChart($("#dtCumC"), { ...common, lines: [{ values: a.cumC, color: "#2F3A36", name: "Cumulative cases", format: fmt, width: 2 }], aria: `Cumulative cases for ${one.name}` });
    Charts.timeChart($("#dtCumD"), { ...common, lines: [{ values: a.cumD, color: "#A33B32", name: "Cumulative deaths", format: fmt, width: 2 }], aria: `Cumulative deaths for ${one.name}` });

    const pc = peak(a.dc, f, b);
    const pa = peak(a.avgC, f, b);
    const pd = peak(a.dd, f, b);
    const row = (label, p) => `<tr><td>${label}</td><td class="num">${p ? fmt(p.value) : "n/a"}</td><td>${p ? dateLabel(p.index) : ""}</td></tr>`;
    $("#dtPeaks").innerHTML = `<thead><tr><th>Measure</th><th class="num">Value</th><th>Date</th></tr></thead><tbody>${row("Peak daily cases", pc)}${row("Peak 7-day average, cases", pa)}${row("Peak daily deaths", pd)}</tbody>`;

    const sel = selectionNotes([one], f, b);
    const notes = [];
    notes.push(sel.negCases || sel.negDeaths
      ? { warn: true, text: `${sel.negCases} days with negative daily cases (${fmt(-sel.negCasesTotal)} cases lowered in total) and ${sel.negDeaths} days with negative daily deaths. These are revisions of the cumulative series and are kept as reported.` }
      : { text: "No negative daily values in this period." });
    if (sel.inconsistent) notes.push({ warn: true, text: `${sel.inconsistent} days where reported deaths plus recoveries exceed reported cases (Inconsistency_Flag). Values are kept as reported.` });
    if (one.pop == null) notes.push({ warn: true, text: "No population value, so per-100K rates are not calculated." });
    notes.push(one.lastR < 0 ? { warn: true, text: "No recovery series: recoveries and active cases are blank, not zero." }
      : { text: `Recoveries are reported only up to ${dateLabel(one.lastR)}; later dates are blank, not zero.` });
    notes.push({ text: "Single days can include backlog added to the series at once; the 7-day average is the better guide to trends." });
    $("#dtNotes").innerHTML = notes.map((n) => `<li${n.warn ? ' class="warn"' : ""}>${esc(n.text)}</li>`).join("");
  }

  // ---- data quality
  function selectionNotes(list, f, b) {
    const out = { countries: list.length, days: b - f + 1, countryDays: 0, revision: 0, revCountries: new Set(), negCases: 0, negCasesTotal: 0,
      negDeaths: 0, inconsistent: 0, recovery: 0, biggest: [] };
    list.forEach((c) => {
      c.rev.forEach((i) => { if (i >= f && i <= b) { out.revision++; out.revCountries.add(c.iso); } });
      c.inc.forEach((i) => { if (i >= f && i <= b) out.inconsistent++; });
      for (let i = f; i <= b; i++) {
        out.countryDays++;
        if (c.c[i] < 0) { out.negCases++; out.negCasesTotal += c.c[i]; out.biggest.push({ c, i, v: c.c[i] }); }
        if (c.d[i] < 0) out.negDeaths++;
        if (c.r[i] != null) out.recovery++;
      }
    });
    out.biggest.sort((x, y) => x.v - y.v);
    out.biggest = out.biggest.slice(0, 5);
    return out;
  }
  function renderQuality() {
    const summary = D.dq.filter((r) => r.Section === "Summary");
    const checks = D.dq.filter((r) => r.Section !== "Summary");
    const facts = summary.filter((r) => r.Item !== "Overall validation status").map((r) => [r.Item, r.Value]);
    facts.push(["Source commit", D.meta.sourceCommit], ["Source accessed", D.meta.sourceAccessed],
      ["Last date with recoveries", fmtDate(D.meta.recoveryLastDate)]);
    $("#dqFacts").innerHTML = facts.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join("") +
      `<dt>Reading the data</dt><dd>Historical archive from ${fmtDate(D.meta.first)} to ${fmtDate(D.meta.last)}. It does not describe current conditions.</dd>`;
    const count = (s) => checks.filter((r) => r.Status === s).length;
    const overall = summary.find((r) => r.Item === "Overall validation status").Value;
    $("#dqSummary").innerHTML = `<p class="status" style="font-size:24px;font-weight:600;margin:8px 0;color:${overall === "PASS" ? "#2F6F4F" : overall === "FAIL" ? "#A33B32" : "#B7791F"}">${esc(overall)}</p>` +
      `<div class="tags"><span class="chip PASS">${count("PASS")} pass</span><span class="chip WARNING">${count("WARNING")} warning</span><span class="chip FAIL">${count("FAIL")} fail</span></div>` +
      `<p class="note" style="margin-top:10px">Warnings describe real limits of the source data (incomplete recoveries, revisions, impossible values). They are reported, not corrected.</p>`;

    const sel = selectionNotes(scopeList(), state.from, state.to);
    const biggest = sel.biggest.length
      ? `<p class="note" style="margin-top:12px">Largest downward revisions of reported cases in this selection:</p><ul class="notes">${sel.biggest.map((x) => `<li class="warn">${esc(x.c.name)}, ${dateLabel(x.i)}: ${fmt(x.v)} cases</li>`).join("")}</ul>`
      : `<p class="note" style="margin-top:12px">No negative daily case values in this selection.</p>`;
    $("#dqSelection").innerHTML = `<div class="counts">` +
      `<div><b>${fmt(sel.countryDays)}</b><span>country-days in the selection</span></div>` +
      `<div><b>${fmt(sel.revision)}</b><span>days with a downward revision (${sel.revCountries.size} ${sel.revCountries.size === 1 ? "country" : "countries"})</span></div>` +
      `<div><b>${fmt(sel.negCases)}</b><span>days with negative daily cases (${fmt(-sel.negCasesTotal)} cases lowered)</span></div>` +
      `<div><b>${fmt(sel.negDeaths)}</b><span>days with negative daily deaths</span></div>` +
      `<div><b>${fmt(sel.inconsistent)}</b><span>flagged inconsistent records</span></div>` +
      `<div><b>${sel.countryDays ? ((sel.recovery / sel.countryDays) * 100).toFixed(1) + "%" : "n/a"}</b><span>of country-days have a recovery figure</span></div></div>` + biggest;

    const rows = checks.filter((r) => !state.warnOnly || r.Status !== "PASS");
    $("#dqBody").innerHTML = rows.map((r) => `<tr><td>${esc(r.Section)}</td><td>${esc(r.Item)}</td><td>${esc(r.Value)}</td><td><span class="chip ${esc(r.Status)}">${esc(r.Status)}</span></td><td>${esc(r.Note)}</td></tr>`).join("");

    const none = countries.filter((c) => c.lastR < 0);
    const early = countries.filter((c) => c.lastR >= 0 && c.lastR < recoveryEnd - 30).sort((x, y) => x.lastR - y.lastR);
    const full = countries.length - none.length - early.length;
    $("#dqRecovery").innerHTML = `<div class="counts"><div><b>${full}</b><span>countries with recoveries until ${fmtDate(D.meta.recoveryLastDate)}</span></div>` +
      `<div><b>${early.length}</b><span>stop earlier</span></div><div><b>${none.length}</b><span>never report recoveries</span></div></div>` +
      `<ul class="notes"><li class="warn">Stop earlier: ${early.map((c) => `${esc(c.name)} (last value ${dateLabel(c.lastR)})`).join("; ") || "none"}.</li>` +
      `<li class="warn">No recovery series: ${none.map((c) => esc(c.name)).join("; ") || "none"}.</li>` +
      `<li>After a country's last recovery date its recovery figure is blank, never zero, and active cases are not calculated.</li></ul>`;

    $("#dqMethod").innerHTML = [
      "Reported cases and deaths are the cumulative totals published by national authorities and collected by JHU CSSE. They are not estimates of true infections or deaths.",
      "Daily values are the change in the cumulative total from the previous day. When a country lowers its total, the daily value is negative; these days are kept, drawn in red, and flagged.",
      "Case fatality ratio is reported deaths divided by reported cases on the same date. It is not the probability of dying for an infected person.",
      "Rates per 100K divide reported cases or deaths by one population figure per country and use only countries that have a population value. Very small populations give volatile rates, so rankings use countries with at least " + nf.format(D.meta.rankingPopulationFloor) + " people.",
      "The 7-day average is the mean of the last 7 days of daily values. It is calculated on the full series, so the first days of a selected range use days before the range.",
      "Testing, case definitions, reporting frequency and death attribution differ between countries and changed over time; many countries moved to weekly reporting in 2022 and 2023. Differences between countries are not differences in infection or mortality.",
      "The source stopped collecting on 10 March 2023, so the data ends on " + fmtDate(D.meta.last) + ". Nothing here reflects later events.",
    ].map((t) => `<li>${esc(t)}</li>`).join("");
  }

  // ---- actions
  function setRegion(region) {
    state.region = region;
    if (region && state.country && byIso[state.country].region !== region) state.country = "";
    update();
  }
  function selectCountry(iso) {
    state.country = iso;
    if (state.region && byIso[iso].region !== state.region) state.region = "";
    update();
  }
  function setRange(from, to) {
    state.from = clamp(from);
    state.to = clamp(to);
    if (state.from > state.to) state.to = state.from;
    update();
  }
  function reset() {
    Object.assign(state, defaults());
    $("#tblSearch").value = "";
    $("#warnOnly").checked = false;
    Charts.hideTip();
    update();
  }

  const renderers = { overview: renderOverview, trends: renderTrends, compare: renderCompare, detail: renderDetail, quality: renderQuality };
  function renderPage() { renderers[state.page](); }
  function update() { renderHeader(); renderPage(); }

  function route() {
    const hash = location.hash.slice(1);
    state.page = PAGES[hash] ? hash : "overview";
    $$(".page").forEach((s) => { s.hidden = s.id !== "page-" + state.page; });
    $$(".rail a").forEach((a) => {
      if (a.dataset.nav === state.page) a.setAttribute("aria-current", "page");
      else a.removeAttribute("aria-current");
    });
    $("#pageTitle").textContent = PAGES[state.page];
    document.title = PAGES[state.page] + " | COVID-19 analytics";
    Charts.hideTip();
    update();
    window.scrollTo(0, 0);
  }

  // ---- country combobox
  const combo = { input: $("#countryInput"), list: $("#countryList"), items: [], active: 0 };
  function buildList(query) {
    const q = query.trim().toLowerCase();
    combo.items = countries.filter((c) => !q || c.name.toLowerCase().includes(q) || c.iso.toLowerCase().includes(q) || c.iso2.toLowerCase() === q);
    combo.active = 0;
    combo.list.innerHTML = combo.items.length
      ? combo.items.map((c, i) => `<li role="option" data-iso="${c.iso}"${i === 0 ? ' class="active"' : ""}>${esc(c.name)}<small>${c.iso} &middot; ${esc(c.region)}</small></li>`).join("")
      : `<li class="empty">No matching country</li>`;
  }
  function openList(query) {
    buildList(query);
    combo.list.hidden = false;
    combo.input.setAttribute("aria-expanded", "true");
  }
  function closeList() {
    combo.list.hidden = true;
    combo.input.setAttribute("aria-expanded", "false");
    combo.input.value = state.country ? byIso[state.country].name : "";
  }
  function moveActive(step) {
    if (!combo.items.length) return;
    combo.active = (combo.active + step + combo.items.length) % combo.items.length;
    $$("li", combo.list).forEach((li, i) => li.classList.toggle("active", i === combo.active));
    const li = $$("li", combo.list)[combo.active];
    if (li) li.scrollIntoView({ block: "nearest" });
  }
  function choose(iso) {
    combo.list.hidden = true;
    combo.input.setAttribute("aria-expanded", "false");
    selectCountry(iso);
  }

  function init() {
    $("#regionSel").innerHTML = `<option value="">All regions</option>` + D.regions.map((r) => `<option value="${esc(r)}">${esc(r)}</option>`).join("");
    $("#fromDate").min = $("#toDate").min = dates[0];
    $("#fromDate").max = $("#toDate").max = dates[N - 1];
    const years = [...new Set(dates.map((d) => d.slice(0, 4)))];
    $("#presets").innerHTML = `<button type="button" data-from="0" data-to="${N - 1}">Full period</button>` + years.map((y) => {
      const from = dates.findIndex((d) => d.startsWith(y));
      const to = dates.length - 1 - [...dates].reverse().findIndex((d) => d.startsWith(y));
      return `<button type="button" data-from="${from}" data-to="${to}">${y}</button>`;
    }).join("");
    $("#foot").textContent = `Data: ${D.meta.dataset}, commit ${D.meta.sourceCommit.slice(0, 7)}, processed by the project pipeline on ${D.meta.pipelineRun}. ` +
      `Generated from data/processed into dashboard/data.js. This page makes no network requests.`;

    $("#regionSel").addEventListener("change", (e) => setRegion(e.target.value));
    $("#fromDate").addEventListener("change", (e) => {
      if (!e.target.value) return renderHeader();
      const from = indexOf(e.target.value);
      setRange(from, Math.max(from, state.to));
    });
    $("#toDate").addEventListener("change", (e) => {
      if (!e.target.value) return renderHeader();
      const to = indexOf(e.target.value);
      setRange(Math.min(to, state.from), to);
    });
    $("#presets").addEventListener("click", (e) => {
      const button = e.target.closest("button");
      if (button) setRange(Number(button.dataset.from), Number(button.dataset.to));
    });
    $("#resetBtn").addEventListener("click", reset);
    $("#countryClear").addEventListener("click", () => { state.country = ""; closeList(); update(); });

    const openAll = () => { if (combo.list.hidden) { combo.input.select(); openList(""); } };
    combo.input.addEventListener("focus", openAll);
    combo.input.addEventListener("click", openAll);
    combo.input.addEventListener("input", () => openList(combo.input.value));
    combo.input.addEventListener("keydown", (e) => {
      if (e.key === "ArrowDown") { e.preventDefault(); if (combo.list.hidden) openList(""); else moveActive(1); }
      else if (e.key === "ArrowUp") { e.preventDefault(); moveActive(-1); }
      else if (e.key === "Enter") { e.preventDefault(); const c = combo.items[combo.active]; if (c && !combo.list.hidden) choose(c.iso); }
      else if (e.key === "Escape") { closeList(); combo.input.blur(); }
    });
    combo.list.addEventListener("pointerdown", (e) => {
      const li = e.target.closest("li[data-iso]");
      if (li) { e.preventDefault(); choose(li.dataset.iso); }
    });
    document.addEventListener("pointerdown", (e) => { if (!e.target.closest("#countryCombo") && !combo.list.hidden) closeList(); });

    const activate = (e, selector, handler) => {
      const el = e.target.closest(selector);
      if (!el) return;
      if (e.type === "keydown" && e.key !== "Enter" && e.key !== " ") return;
      e.preventDefault();
      handler(el);
    };
    ["click", "keydown"].forEach((type) => {
      $("#topCases").addEventListener(type, (e) => activate(e, "li[data-iso]", (li) => selectCountry(li.dataset.iso)));
      $("#topRate").addEventListener(type, (e) => activate(e, "li[data-iso]", (li) => selectCountry(li.dataset.iso)));
      $("#ovRegions").addEventListener(type, (e) => activate(e, "li[data-region]", (li) => setRegion(state.region === li.dataset.region ? "" : li.dataset.region)));
      $("#cmpBody").addEventListener(type, (e) => activate(e, "tr[data-iso]", (tr) => selectCountry(tr.dataset.iso)));
      $("#detailEmpty").addEventListener(type, (e) => activate(e, "button[data-pick]", (btn) => selectCountry(btn.dataset.pick)));
    });
    $("#cmpTable thead").addEventListener("click", (e) => {
      const th = e.target.closest("th[data-sort]");
      if (!th) return;
      if (state.sortKey === th.dataset.sort) state.sortDir = state.sortDir === "asc" ? "desc" : "asc";
      else { state.sortKey = th.dataset.sort; state.sortDir = th.dataset.sort === "name" || th.dataset.sort === "region" ? "asc" : "desc"; }
      renderCompare();
    });
    $("#tblSearch").addEventListener("input", (e) => { state.search = e.target.value; renderCompare(); });
    $("#warnOnly").addEventListener("change", (e) => { state.warnOnly = e.target.checked; renderQuality(); });

    window.addEventListener("hashchange", route);
    let lastWidth = $("#main").clientWidth;
    let timer = 0;
    new ResizeObserver(() => {
      const width = $("#main").clientWidth;
      if (width === lastWidth) return;
      lastWidth = width;
      clearTimeout(timer);
      timer = setTimeout(renderPage, 120);
    }).observe($("#main"));

    $("#pageSub").textContent = `JHU CSSE archive, reported counts, data ends ${fmtDate(D.meta.last)}. Historical, not current conditions.`;
    route();
    window.__dashboardReady = true;
  }

  init();
})();
