import numpy as np

from config import ROOT

PREVIEW_DIR = ROOT / "preview"
ICON_DIR = ROOT / "powerbi" / "assets" / "icons"

INK, SAGE, MUTED = "#201E1F", "#6B8676", "#8A8A85"
REGION_COLOURS = ["#2F3A36", "#6B8676", "#9DB0A5", "#C7D3CC", "#D8C9A6", "#8F8F89"]

ICON_PATHS = {
    "overview": '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/>'
                '<rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
    "trends": '<polyline points="3,17 9,11 13,15 21,6"/><polyline points="15,6 21,6 21,12"/>',
    "compare": '<line x1="6" y1="20" x2="6" y2="11"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="18" y1="20" x2="18" y2="14"/>',
    "country": '<circle cx="12" cy="8" r="4"/><path d="M4 21c0-4 4-6 8-6s8 2 8 6"/>',
    "quality": '<path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z"/><polyline points="9,12 11,14 15,10"/>',
}
LOGO = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" fill="none" stroke="{c}" stroke-width="2.6" '
        'stroke-linecap="round">{lines}</svg>')


def icon_svg(name, colour):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{colour}" '
            f'stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">{ICON_PATHS[name]}</svg>')


def logo_svg(colour):
    lines = ""
    for i in range(12):
        angle = np.radians(i * 30)
        inner, outer = 9, 20 if i % 2 == 0 else 16
        lines += (f'<line x1="{24 + inner * np.cos(angle):.1f}" y1="{24 + inner * np.sin(angle):.1f}" '
                  f'x2="{24 + outer * np.cos(angle):.1f}" y2="{24 + outer * np.sin(angle):.1f}"/>')
    return LOGO.format(c=colour, lines=lines)


def write_icons():
    ICON_DIR.mkdir(parents=True, exist_ok=True)
    for name in ICON_PATHS:
        (ICON_DIR / f"{name}_dark.svg").write_text(icon_svg(name, "#6B6F6A"), encoding="utf-8")
        (ICON_DIR / f"{name}_white.svg").write_text(icon_svg(name, "#FFFFFF"), encoding="utf-8")
    (ICON_DIR / "logo.svg").write_text(logo_svg(SAGE), encoding="utf-8")


def fmt(value):
    return f"{int(round(value)):,}"


def fmt_date(ts):
    return f"{ts.day} {ts:%b %Y}"


def polyline(values, width, height, top=None, step=None):
    values = np.asarray(values, dtype=float)
    keep = np.linspace(0, len(values) - 1, min(len(values), 140)).astype(int)
    v = values[keep]
    top = np.nanmax(v) if top is None else top
    xs = np.linspace(0, width, len(v))
    ys = height - np.nan_to_num(v) / top * height
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in zip(xs, ys))


def sparkline(values, width, height, colour):
    return (f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}"><polyline fill="none" '
            f'stroke="{colour}" stroke-width="1.8" stroke-linejoin="round" points="{polyline(values, width, height)}"/></svg>')


def mini_bars(values, width, height, colour):
    values = np.asarray(values, dtype=float)
    slot = width / len(values)
    bars = "".join(
        f'<rect x="{i * slot:.1f}" y="{height - v / values.max() * height:.1f}" width="{slot * 0.62:.1f}" '
        f'height="{v / values.max() * height:.1f}" rx="1" fill="{colour}"/>' for i, v in enumerate(values))
    return f'<svg width="{width}" height="{height}">{bars}</svg>'


def daily_chart(daily, avg, width=526, height=150):
    top = 4_000_000
    slot = width / len(daily)
    bars = "".join(
        f'<rect x="{i * slot:.2f}" y="{height - min(max(v, 0), top) / top * height:.1f}" width="{max(slot * 0.8, 0.4):.2f}" '
        f'height="{min(max(v, 0), top) / top * height:.1f}" fill="#D6D8D2"/>' for i, v in enumerate(daily["Daily_Cases"]))
    grid = "".join(
        f'<line x1="0" x2="{width}" y1="{height - g / top * height:.1f}" y2="{height - g / top * height:.1f}" stroke="#EDEDE8"/>'
        f'<text x="0" y="{height - g / top * height - 4:.1f}" class="axis">{g // 1_000_000}M</text>' for g in (2_000_000, 4_000_000))
    pts = polyline(avg["Daily_Cases"].fillna(0), width, height, top=top)
    years = ""
    for year in sorted(set(daily.index.year)):
        first = daily.index[daily.index.year == year][0]
        x = (daily.index.get_loc(first)) * slot
        years += f'<text x="{x:.1f}" y="{height + 18}" class="axis">{year}</text>'
    return (f'<svg width="{width}" height="{height + 24}" viewBox="0 0 {width} {height + 24}">{grid}{bars}'
            f'<polyline fill="none" stroke="#2F3A36" stroke-width="1.8" stroke-linejoin="round" points="{pts}"/>{years}</svg>')


def donut(shares, size=124):
    radius, stroke = size / 2 - 14, 22
    circ = 2 * np.pi * radius
    offset, parts = 0.0, ""
    for (name, share), colour in zip(shares, REGION_COLOURS):
        length = circ * share
        parts += (f'<circle cx="{size / 2}" cy="{size / 2}" r="{radius}" fill="none" stroke="{colour}" stroke-width="{stroke}" '
                  f'stroke-dasharray="{max(length - 1.5, 0.5):.2f} {circ:.2f}" stroke-dashoffset="{-offset:.2f}" '
                  f'transform="rotate(-90 {size / 2} {size / 2})"/>')
        offset += length
    return f'<svg width="{size}" height="{size}">{parts}</svg>'


def pct_label(share):
    return "<1%" if share < 0.01 else f"{share * 100:.0f}%"


def compute(fact, dim_country, summary, dq_table, findings):
    last = fact["Date"].max()
    daily = fact.groupby("Date")[["Daily_Cases", "Daily_Deaths"]].sum()
    avg = daily.rolling(7).mean()
    monthly = daily.groupby(daily.index.strftime("%Y-%m")).sum()
    latest = fact[fact["Date"] == last].merge(dim_country, on="ISO_Code")
    with_pop = latest[latest["Population"].notna()]
    regions = latest.groupby("Region")["Confirmed"].sum().sort_values(ascending=False)
    peak_day = avg["Daily_Cases"].idxmax()
    floor = findings["ranking_population_floor"]
    ranked = summary[summary["Population"].astype("float64") >= floor].nlargest(10, "Cases_Per_100K")
    checks = dq_table[~dq_table["Section"].isin(["Summary"])]
    counts = checks["Status"].value_counts()
    return {
        "first": daily.index.min(), "last": last, "daily": daily, "avg": avg, "monthly": monthly,
        "cases": int(latest["Confirmed"].sum()), "deaths": int(latest["Deaths"].sum()),
        "countries": int(latest["ISO_Code"].nunique()),
        "peak_avg": float(avg["Daily_Cases"].max()), "peak_day": peak_day,
        "regions": [(n, v / regions.sum()) for n, v in regions.items()],
        "population": float(with_pop["Population"].sum()),
        "cases_100k": with_pop["Confirmed"].sum() / with_pop["Population"].sum() * 1e5,
        "deaths_100k": with_pop["Deaths"].sum() / with_pop["Population"].sum() * 1e5,
        "ranked": ranked, "floor": floor,
        "top5": summary.nlargest(5, "Confirmed"),
        "overall": dq_table.loc[dq_table["Item"] == "Overall validation status", "Value"].iloc[0],
        "pass": int(counts.get("PASS", 0)), "warn": int(counts.get("WARNING", 0)), "fail": int(counts.get("FAIL", 0)),
    }


CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{background:#d9d8d2;font-family:'DM Sans','Segoe UI',Carlito,'Helvetica Neue',Arial,sans-serif;color:#201E1F;padding:24px;-webkit-font-smoothing:antialiased}
#canvas{position:relative;width:1280px;height:720px;background:#E6E5DF;overflow:hidden;margin:0 auto}
.abs{position:absolute}
.card{position:absolute;background:#FBFBFA;border-radius:24px;box-shadow:0 1px 2px rgba(40,40,30,.05),0 8px 24px rgba(40,40,30,.05)}
.accent{background:#6B8676;color:#fff}
.pill{position:absolute;background:#fff;border-radius:24px;height:44px;display:flex;align-items:center;padding:0 18px;font-size:13px;color:#6f6f6a;box-shadow:0 1px 2px rgba(40,40,30,.05),0 8px 24px rgba(40,40,30,.05);justify-content:space-between}
.circle{position:absolute;width:44px;height:44px;border-radius:22px;background:#fff;display:flex;align-items:center;justify-content:center;box-shadow:0 1px 2px rgba(40,40,30,.05),0 8px 24px rgba(40,40,30,.05)}
.badge{position:absolute;top:-4px;right:-4px;min-width:20px;height:20px;border-radius:10px;background:#201E1F;color:#fff;font-size:11px;font-weight:600;display:flex;align-items:center;justify-content:center}
.rail{position:absolute;left:24px;top:84px;width:60px;height:612px;background:#fff;border-radius:30px;box-shadow:0 1px 2px rgba(40,40,30,.05),0 8px 24px rgba(40,40,30,.05)}
.rail .ic{position:absolute;left:8px;width:44px;height:44px;border-radius:22px;display:flex;align-items:center;justify-content:center}
.rail .ic.on{background:#201E1F}
.rail svg,.circle svg{width:20px;height:20px}
h1{font-size:26px;font-weight:600;letter-spacing:-.3px}
.sub{font-size:12.5px;color:#8A8A85}
.lbl{font-size:13px;color:#8A8A85}
.val{font-size:28px;font-weight:600;letter-spacing:-.5px}
.ttl{font-size:15px;font-weight:600}
.note{font-size:11px;color:#8A8A85}
.axis{font-size:10px;fill:#9a9a94}
.row{display:flex;justify-content:space-between;align-items:center}
.chip{display:inline-block;padding:3px 9px;border-radius:10px;font-size:11px;font-weight:600;background:#E1EDE5;color:#3E6B53}
.btn{position:absolute;background:#6B8676;color:#fff;border-radius:14px;height:40px;display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:600}
.cap{width:1280px;margin:14px auto 0;font-size:12px;color:#6f6f6a}
"""


def build_html(d):
    first, last = d["first"], d["last"]
    daily, avg = d["daily"], d["avg"]
    rail = ""
    for i, name in enumerate(ICON_PATHS):
        colour = "#FFFFFF" if i == 0 else "#6B6F6A"
        rail += f'<div class="ic {"on" if i == 0 else ""}" style="top:{16 + i * 56}px">{icon_svg(name, colour)}</div>'

    kpi_bars = mini_bars(d["monthly"]["Daily_Cases"].clip(lower=0).values, 118, 60, "#454B49")
    kpi_deaths = sparkline(avg["Daily_Deaths"].fillna(0).values, 118, 56, "#A33B32")
    kpi_peak = sparkline(avg["Daily_Cases"].fillna(0).values, 118, 56, "#ffffff")

    legend = "".join(
        f'<div class="row" style="font-size:12px;margin-bottom:7px"><span><i style="display:inline-block;width:9px;height:9px;border-radius:3px;'
        f'background:{c};margin-right:8px"></i>{n}</span><span style="color:#8A8A85">{pct_label(s)}</span></div>'
        for (n, s), c in zip(d["regions"], REGION_COLOURS))

    top = d["ranked"]
    bar_max = top["Cases_Per_100K"].max()
    hbars = "".join(
        f'<div class="row" style="height:16px;margin-bottom:0;font-size:11.5px"><span style="width:112px;white-space:nowrap">{r.Country}</span>'
        f'<span style="flex:1;margin-right:10px"><i style="display:block;height:9px;border-radius:5px;background:#6B8676;'
        f'width:{r.Cases_Per_100K / bar_max * 100:.1f}%"></i></span><span style="width:60px;text-align:right;color:#6f6f6a">{fmt(r.Cases_Per_100K)}</span></div>'
        for r in top.itertuples())

    total = d["cases"]
    top5 = "".join(
        f'<div class="row" style="height:34px;border-left:3px solid #201E1F;padding-left:10px;margin-bottom:2px;line-height:1.2">'
        f'<span style="font-size:12.5px;font-weight:600">{r.Country}<br><span class="note" style="font-weight:400;font-size:10.5px">{fmt(r.Confirmed)}</span></span>'
        f'<span class="chip">{r.Confirmed / total * 100:.1f}%</span></div>' for r in d["top5"].itertuples())

    status_colour = {"PASS": "#2F6F4F", "WARNING": "#B7791F", "FAIL": "#A33B32"}[d["overall"]]
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>COVID-19 global overview: design preview</title>
<style>{CSS}</style></head><body>
<div id="canvas">
 <div class="abs" style="left:24px;top:14px;width:48px;height:48px">{logo_svg(SAGE)}</div>
 <div class="abs" style="left:104px;top:8px"><h1>COVID-19 global overview</h1>
  <div class="sub" style="margin-top:3px">JHU CSSE archive &middot; reported counts through {fmt_date(last)} &middot; data ends {fmt_date(last)}</div></div>
 <div class="pill" style="left:748px;top:14px;width:170px"><span>All regions</span><span>&#9662;</span></div>
 <div class="pill" style="left:930px;top:14px;width:270px"><span>Search country</span><span>&#9662;</span></div>
 <div class="circle" style="left:1212px;top:14px">{icon_svg("quality", INK)}<div class="badge">{d["warn"]}</div></div>

 <div class="rail">{rail}</div>

 <div class="card" style="left:104px;top:84px;width:273px;height:100px"><div class="abs lbl" style="left:20px;top:18px">Reported cases</div>
  <div class="abs val" style="left:20px;top:42px">{fmt(d["cases"])}</div><div class="abs" style="left:146px;top:22px">{kpi_bars}</div></div>
 <div class="card" style="left:397px;top:84px;width:273px;height:100px"><div class="abs lbl" style="left:20px;top:18px">Reported deaths</div>
  <div class="abs val" style="left:20px;top:42px">{fmt(d["deaths"])}</div><div class="abs" style="left:146px;top:30px">{kpi_deaths}</div></div>
 <div class="card" style="left:690px;top:84px;width:273px;height:100px"><div class="abs lbl" style="left:20px;top:18px">Case fatality ratio</div>
  <div class="abs val" style="left:20px;top:42px">{d["deaths"] / d["cases"] * 100:.2f}%</div>
  <div class="abs note" style="left:20px;top:78px">reported deaths &divide; reported cases</div></div>
 <div class="card accent" style="left:983px;top:84px;width:273px;height:100px"><div class="abs lbl" style="left:20px;top:18px;color:#DCE6DF">Peak 7-day average, cases</div>
  <div class="abs val" style="left:20px;top:42px">{fmt(d["peak_avg"])}</div>
  <div class="abs note" style="left:20px;top:78px;color:#DCE6DF">{fmt_date(d["peak_day"])}</div><div class="abs" style="left:146px;top:30px">{kpi_peak}</div></div>

 <div class="card" style="left:104px;top:204px;width:566px;height:232px">
  <div class="abs ttl" style="left:20px;top:18px">Daily cases and 7-day average</div>
  <div class="abs pill" style="left:316px;top:8px;width:234px;height:32px;font-size:11px;padding:0 12px"><span>{first:%d/%m/%Y}</span><span>&ndash;</span><span>{last:%d/%m/%Y}</span></div>
  <div class="abs" style="left:20px;top:58px;width:170px"><div class="note">7-day average, end of period</div>
   <div style="font-size:22px;font-weight:600;margin-top:2px">{fmt(avg["Daily_Cases"].iloc[-1])}</div></div>
  <div class="abs" style="left:20px;top:46px">{daily_chart(daily, avg)}</div></div>

 <div class="card" style="left:690px;top:204px;width:273px;height:232px">
  <div class="abs ttl" style="left:20px;top:18px">Reported cases by region</div>
  <div class="abs" style="left:18px;top:62px">{donut(d["regions"])}</div>
  <div class="abs" style="left:156px;top:64px;width:100px">{legend}</div>
  <div class="abs note" style="left:20px;top:196px;width:235px">Share of reported cases at {fmt_date(last)}</div></div>

 <div class="card" style="left:983px;top:204px;width:273px;height:232px">
  <div class="abs" style="left:104px;top:18px;width:64px;height:64px;border-radius:32px;background:#DDE6E0;display:flex;align-items:center;justify-content:center;font-weight:600;font-size:16px;color:#3E5B49">ALL</div>
  <div class="abs" style="left:0;top:92px;width:273px;text-align:center;font-size:17px;font-weight:600">All countries</div>
  <div class="abs note" style="left:0;top:118px;width:273px;text-align:center">{d["countries"]} countries in selection</div>
  <div class="abs row" style="left:16px;top:156px;width:241px;align-items:flex-start;text-align:center">
   <div style="width:80px"><div class="note">Population</div><div style="font-size:19px;font-weight:600;margin-top:4px">{d["population"] / 1e9:.1f}bn</div></div>
   <div style="width:80px"><div class="note">Cases per 100K</div><div style="font-size:19px;font-weight:600;margin-top:4px">{fmt(d["cases_100k"])}</div></div>
   <div style="width:80px"><div class="note">Deaths per 100K</div><div style="font-size:19px;font-weight:600;margin-top:4px">{fmt(d["deaths_100k"])}</div></div></div></div>

 <div class="card" style="left:104px;top:456px;width:566px;height:240px">
  <div class="abs ttl" style="left:20px;top:18px">Top 10 by reported cases per 100K</div>
  <div class="abs note" style="left:20px;top:40px">Countries with {fmt(d["floor"])} or more people</div>
  <div class="abs" style="left:20px;top:62px;width:526px">{hbars}</div></div>

 <div class="card" style="left:690px;top:456px;width:273px;height:240px">
  <div class="abs ttl" style="left:20px;top:18px">Top 5 by reported cases</div>
  <div class="abs" style="left:20px;top:50px;width:233px">{top5}</div></div>

 <div class="card" style="left:983px;top:456px;width:273px;height:240px">
  <div class="abs ttl" style="left:20px;top:18px">Data validation</div>
  <div class="abs" style="left:20px;top:50px;font-size:26px;font-weight:600;color:{status_colour}">{d["overall"]}</div>
  <div class="abs" style="left:20px;top:88px;font-size:12.5px">{d["pass"]} pass &middot; {d["warn"]} warning &middot; {d["fail"]} fail</div>
  <div class="abs note" style="left:20px;top:114px;width:233px;line-height:1.45">Recovery figures are incomplete. Revisions and impossible values are flagged, not removed.</div>
  <div class="btn" style="left:16px;top:184px;width:241px">View data quality</div></div>
</div>
<div class="cap">Design preview of the Overview page. Static HTML generated by <code>src/preview.py</code> from <code>data/processed</code> (default view: all countries, full date range). It is not a Power BI report.</div>
</body></html>"""


def write_preview(fact, dim_country, summary, dq_table, findings):
    PREVIEW_DIR.mkdir(exist_ok=True)
    write_icons()
    html = build_html(compute(fact, dim_country, summary, dq_table, findings))
    (PREVIEW_DIR / "overview.html").write_text(html, encoding="utf-8")
