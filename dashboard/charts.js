const Charts = (() => {
  const NS = "http://www.w3.org/2000/svg";
  const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const tip = document.getElementById("tooltip");

  function svgEl(name, attrs, parent) {
    const node = document.createElementNS(NS, name);
    for (const key in attrs) node.setAttribute(key, attrs[key]);
    if (parent) parent.appendChild(node);
    return node;
  }

  function niceTicks(min, max, count) {
    const range = max - min || 1;
    const rough = range / count;
    const magnitude = Math.pow(10, Math.floor(Math.log10(rough)));
    const residual = rough / magnitude;
    const nice = residual > 5 ? 10 : residual > 2 ? 5 : residual > 1 ? 2 : 1;
    const step = nice * magnitude;
    const ticks = [];
    for (let v = Math.floor(min / step) * step; v <= Math.ceil(max / step) * step + step / 2; v += step) ticks.push(v);
    return ticks;
  }

  function axisLabel(v) {
    const abs = Math.abs(v);
    if (abs >= 1e9) return Number((v / 1e9).toFixed(1)) + "B";
    if (abs >= 1e6) return Number((v / 1e6).toFixed(1)) + "M";
    if (abs >= 1e3) return Number((v / 1e3).toFixed(1)) + "K";
    return String(Math.round(v));
  }

  function showTip(html, event) {
    tip.innerHTML = html;
    tip.hidden = false;
    const box = tip.getBoundingClientRect();
    let x = event.clientX + 14;
    let y = event.clientY + 14;
    if (x + box.width > window.innerWidth - 8) x = event.clientX - box.width - 14;
    if (y + box.height > window.innerHeight - 8) y = event.clientY - box.height - 14;
    tip.style.left = Math.max(8, x) + "px";
    tip.style.top = Math.max(8, y) + "px";
  }

  function hideTip() {
    tip.hidden = true;
  }

  function frame(box, height, aria) {
    box.innerHTML = "";
    const width = Math.max(box.clientWidth, 260);
    const svg = svgEl("svg", { width, height, viewBox: `0 0 ${width} ${height}`, role: "img", "aria-label": aria }, box);
    return { svg, width };
  }

  function drawAxes(svg, m, pw, ph, yMin, yMax, y, ticks) {
    ticks.forEach((t) => {
      if (t < yMin - 1e-9 || t > yMax + 1e-9) return;
      svgEl("line", { x1: m.l, x2: m.l + pw, y1: y(t), y2: y(t), class: t === 0 ? "zero" : "grid" }, svg);
      const label = svgEl("text", { x: m.l - 8, y: y(t) + 3.5, class: "axis", "text-anchor": "end" }, svg);
      label.textContent = axisLabel(t);
    });
  }

  function range(series, from, to) {
    let lo = 0;
    let hi = 0;
    series.forEach((s) => {
      for (let i = from; i <= to; i++) {
        const v = s.values[i];
        if (v != null && isFinite(v)) {
          if (v < lo) lo = v;
          if (v > hi) hi = v;
        }
      }
    });
    return hi === lo ? [lo, lo + 1] : [lo, hi];
  }

  // Time series: optional bars (negative days drawn in a second colour) plus lines.
  function timeChart(box, o) {
    const height = o.height || 230;
    const { svg, width } = frame(box, height, o.aria);
    const m = { l: 52, r: 12, t: 10, b: 26 };
    const pw = width - m.l - m.r;
    const ph = height - m.t - m.b;
    const n = o.to - o.from + 1;
    const series = [o.bars, ...(o.lines || [])].filter(Boolean);
    const [lo, hi] = range(series, o.from, o.to);
    const ticks = niceTicks(lo, hi, 5);
    const yMin = Math.min(lo, ticks[0]);
    const yMax = Math.max(hi, ticks[ticks.length - 1]);
    const y = (v) => m.t + ph - ((v - yMin) / (yMax - yMin)) * ph;
    const step = pw / n;
    const x = (k) => m.l + (k + 0.5) * step;
    drawAxes(svg, m, pw, ph, yMin, yMax, y, ticks);

    const labelEvery = n > 700 ? 6 : n > 300 ? 3 : n > 100 ? 1 : 0;
    let lastLabelX = -100;
    for (let k = 0; k < n; k++) {
      const iso = o.dates[o.from + k];
      let text = null;
      if (labelEvery && iso.slice(8) === "01" && (Number(iso.slice(5, 7)) - 1) % labelEvery === 0) {
        text = iso.slice(5, 7) === "01" ? iso.slice(0, 4) : MONTHS[Number(iso.slice(5, 7)) - 1] + " " + iso.slice(2, 4);
      } else if (!labelEvery && k % Math.max(1, Math.ceil(n / 6)) === 0) {
        text = Number(iso.slice(8)) + " " + MONTHS[Number(iso.slice(5, 7)) - 1];
      }
      if (text && x(k) - lastLabelX > 38) {
        svgEl("text", { x: x(k), y: height - 8, class: "axis", "text-anchor": "middle" }, svg).textContent = text;
        lastLabelX = x(k);
      }
    }

    if (o.bars) {
      let positive = "";
      let negative = "";
      const w = Math.max(step * 0.8, 0.6).toFixed(2);
      for (let k = 0; k < n; k++) {
        const v = o.bars.values[o.from + k];
        if (!v) continue;
        const top = Math.min(y(v), y(0));
        const rect = `M${(x(k) - step * 0.4).toFixed(2)} ${top.toFixed(1)}h${w}v${Math.abs(y(v) - y(0)).toFixed(1)}h-${w}z`;
        if (v > 0) positive += rect;
        else negative += rect;
      }
      svgEl("path", { d: positive, fill: o.bars.color }, svg);
      svgEl("path", { d: negative, fill: "#A33B32" }, svg);
    }
    (o.lines || []).forEach((line) => {
      let d = "";
      let pen = false;
      for (let k = 0; k < n; k++) {
        const v = line.values[o.from + k];
        if (v == null || !isFinite(v)) {
          pen = false;
          continue;
        }
        d += (pen ? "L" : "M") + x(k).toFixed(1) + " " + y(v).toFixed(1);
        pen = true;
      }
      svgEl("path", { d, fill: "none", stroke: line.color, "stroke-width": line.width || 1.8, "stroke-linejoin": "round" }, svg);
    });

    const cross = svgEl("line", { y1: m.t, y2: m.t + ph, class: "cross", visibility: "hidden" }, svg);
    const overlay = svgEl("rect", { x: m.l, y: m.t, width: pw, height: ph, fill: "transparent" }, svg);
    overlay.addEventListener("pointermove", (event) => {
      const rect = svg.getBoundingClientRect();
      const k = Math.max(0, Math.min(n - 1, Math.floor((event.clientX - rect.left - m.l) / step)));
      const i = o.from + k;
      cross.setAttribute("x1", x(k));
      cross.setAttribute("x2", x(k));
      cross.setAttribute("visibility", "visible");
      let html = `<strong>${o.dateLabel(i)}</strong>`;
      series.forEach((s) => {
        const v = s.values[i];
        html += `<div><i style="background:${s.color}"></i>${s.name}: <b>${v == null || !isFinite(v) ? "n/a" : s.format(v)}</b></div>`;
      });
      if (o.bars && o.bars.values[i] < 0) html += `<div class="warn">Negative day: downward revision in the reported series</div>`;
      if (o.extra) html += o.extra(i);
      showTip(html, event);
    });
    overlay.addEventListener("pointerleave", () => {
      cross.setAttribute("visibility", "hidden");
      hideTip();
    });
  }

  // Category bars (monthly totals). Partial months are drawn lighter and labelled in the tooltip.
  function categoryBars(box, o) {
    const height = o.height || 230;
    const { svg, width } = frame(box, height, o.aria);
    const m = { l: 52, r: 12, t: 10, b: 26 };
    const pw = width - m.l - m.r;
    const ph = height - m.t - m.b;
    const n = o.labels.length;
    const [lo, hi] = range([{ values: o.values }], 0, n - 1);
    const ticks = niceTicks(lo, hi, 5);
    const yMin = Math.min(lo, ticks[0]);
    const yMax = Math.max(hi, ticks[ticks.length - 1]);
    const y = (v) => m.t + ph - ((v - yMin) / (yMax - yMin)) * ph;
    const step = pw / Math.max(n, 1);
    drawAxes(svg, m, pw, ph, yMin, yMax, y, ticks);
    const every = Math.ceil(n / Math.max(2, Math.floor(pw / 46)));
    o.labels.forEach((label, k) => {
      const cx = m.l + (k + 0.5) * step;
      if (k % every === 0) svgEl("text", { x: cx, y: height - 8, class: "axis", "text-anchor": "middle" }, svg).textContent = label;
      const v = o.values[k];
      const top = Math.min(y(v), y(0));
      const bar = svgEl("rect", {
        x: cx - step * 0.36, y: top, width: step * 0.72, height: Math.max(Math.abs(y(v) - y(0)), 0.5), rx: 2,
        fill: o.partial[k] ? o.lightColor : o.color,
      }, svg);
      bar.addEventListener("pointermove", (event) => {
        showTip(`<strong>${o.titles[k]}</strong><div><i style="background:${o.color}"></i>${o.name}: <b>${o.format(v)}</b></div>` +
          (o.partial[k] ? `<div class="warn">Partial month: ${o.partialNote[k]}</div>` : ""), event);
      });
      bar.addEventListener("pointerleave", hideTip);
    });
  }

  // Donut with clickable slices.
  function donut(box, o) {
    box.innerHTML = "";
    const size = 150;
    const svg = svgEl("svg", { width: size, height: size, viewBox: `0 0 ${size} ${size}`, role: "img", "aria-label": o.aria }, box);
    const radius = size / 2 - 14;
    const circ = 2 * Math.PI * radius;
    const total = o.items.reduce((a, b) => a + b.value, 0) || 1;
    let offset = 0;
    o.items.forEach((item) => {
      const length = (item.value / total) * circ;
      const circle = svgEl("circle", {
        cx: size / 2, cy: size / 2, r: radius, fill: "none", stroke: item.color,
        "stroke-width": item.key === o.selected ? 26 : 22,
        "stroke-dasharray": `${Math.max(length - 1.5, 0.5)} ${circ}`, "stroke-dashoffset": -offset,
        transform: `rotate(-90 ${size / 2} ${size / 2})`, class: "slice", tabindex: 0, role: "button",
        "aria-label": `${item.label}: ${o.format(item.value)}`,
      }, svg);
      offset += length;
      circle.addEventListener("click", () => o.onSelect(item.key));
      circle.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") o.onSelect(item.key); });
      circle.addEventListener("pointermove", (e) =>
        showTip(`<strong>${item.label}</strong><div>${o.format(item.value)} (${((item.value / total) * 100).toFixed(1)}%)</div>`, e));
      circle.addEventListener("pointerleave", hideTip);
    });
  }

  return { timeChart, categoryBars, donut, hideTip, MONTHS };
})();
