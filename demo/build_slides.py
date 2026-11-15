"""Build the 7-slide demo (the Space Apps limit, title included) -> demo/slides.pdf, with numbers from
demo/tokens.json (pipeline/report.py) and pictures from the web app, which must be running on :5173.
Run: TEAM="Team name" MEMBERS="Name One, Name Two" python3 demo/build_slides.py
"""

import base64
import json
import os
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).parent.parent
TEAM = os.environ.get("TEAM", "TEAM NAME")
MEMBERS = os.environ.get("MEMBERS", "Member One, Member Two")
APP = "http://localhost:5173/"
K = json.loads((ROOT / "demo/tokens.json").read_text())  # every number, already formatted
TMP = Path(tempfile.mkdtemp())


def img(path):
    return "data:image/png;base64," + base64.b64encode(Path(path).read_bytes()).decode()


def shots(pw):
    b = pw.chromium.launch()
    p = b.new_context(
        viewport={"width": 1440, "height": 1000}, device_scale_factor=2, color_scheme="light"
    ).new_page()
    p.goto(APP, wait_until="networkidle")
    p.evaluate("localStorage.setItem('theme', 'light')")
    p.reload(wait_until="networkidle")
    p.wait_for_timeout(5000)
    p.locator(".two .card").nth(1).screenshot(path=TMP / "record.png")
    p.screenshot(path=TMP / "app.png", clip={"x": 0, "y": 0, "width": 1440, "height": 1000})
    p.locator("#evidence .scales").screenshot(path=TMP / "scales.png")
    p.get_by_role("button", name="Black Summer").first.click()
    p.wait_for_timeout(6000)
    p.mouse.move(5, 500)
    g = p.locator(".grid").bounding_box()
    p.evaluate("window.scrollTo(0, 0)")
    p.wait_for_timeout(300)
    # map and calendar, not the cards below
    p.screenshot(path=TMP / "story.png", clip={"x": g["x"], "y": g["y"], "width": g["width"], "height": 790})
    p.get_by_role("button", name="Greece, before VIIRS").first.click()
    p.wait_for_timeout(5000)
    p.mouse.move(5, 500)
    p.locator(".col .card").nth(1).screenshot(path=TMP / "here.png")
    b.close()


def html():
    foot = "<footer>Burning Activity Calendar · Data: NASA FIRMS · Burning Activity Calendar</footer>"

    def s(body, cls=""):
        return f'<section class="{cls}">{body}{foot}</section>'

    def row(name, p, bold=False):
        """A table row of the method whose tokens start with p."""
        if bold:
            name = f"<b>{name}</b>"
        return f"<tr><td>{name}</td><td>{K[p + '_country']}</td><td>{K[p + '_box']}</td><td>{K[p + '_cell']}</td></tr>"

    return f"""<!doctype html><html lang="en"><meta charset="utf-8"><style>
@page {{ size: 1280px 720px; margin: 0 }} * {{ box-sizing: border-box }}
body {{ margin: 0; font: 22px/1.4 system-ui, sans-serif; color: #16150f }}
section {{ width: 1280px; height: 720px; padding: 54px 64px 60px; position: relative; page-break-after: always; background: #f4f3ef; overflow: hidden }}
h1 {{ font-size: 56px; line-height: 1.08; margin: 0 0 16px; letter-spacing: -.02em }} h2 {{ font-size: 36px; margin: 0 0 22px; line-height: 1.15; letter-spacing: -.015em }}
p {{ margin: 0 0 14px }} ul {{ margin: 0; padding-left: 26px }} li {{ margin-bottom: 12px }} b {{ color: #d9480f }}
.sub {{ font-size: 26px; color: #55534b }} .k {{ font-size: 15px; letter-spacing: .08em; text-transform: uppercase; color: #d9480f; font-weight: 700; margin-bottom: 10px }}
.two {{ display: grid; grid-template-columns: 1fr 1fr; gap: 36px; align-items: start }} .wide {{ display: grid; grid-template-columns: 5fr 7fr; gap: 32px; align-items: start }}
img {{ width: 100%; border: 1px solid #e5e2d9; border-radius: 12px; background: #fff; display: block }}
footer {{ position: absolute; left: 64px; right: 64px; bottom: 20px; font-size: 13px; color: #86847a }}
table {{ border-collapse: collapse; width: 100%; font-size: 20px }} th, td {{ padding: 8px 10px; text-align: right; border-bottom: 1px solid #e5e2d9 }}
th {{ font-size: 14px; color: #55534b; font-weight: 600 }} td:first-child, th:first-child {{ text-align: left }} td b {{ color: #16150f }}
.big {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 18px; margin: 0 0 18px }} .big div {{ background: #fff; border: 1px solid #e5e2d9; border-radius: 12px; padding: 14px 18px }}
.big strong {{ display: block; font-size: 40px; color: #d9480f; line-height: 1.1; letter-spacing: -.02em }} .big span {{ font-size: 16px; color: #55534b }}
.steps {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-bottom: 22px }} .steps div {{ background: #fff; border: 1px solid #e5e2d9; border-radius: 12px; padding: 14px 16px; font-size: 18px }}
.steps strong {{ display: block; font-size: 15px; color: #d9480f; text-transform: uppercase; letter-spacing: .05em; margin-bottom: 4px }}
.title {{ background: #16150f; color: #f4f3ef }} .title .sub {{ color: #c9c6bd }} .title b {{ color: #fdc050 }}
.small {{ font-size: 18px; color: #55534b }}
</style>
{s(f'''<div class="k" style="color:#fdc050">NASA Space Apps Challenge 2026 · Harmonization of MODIS and VIIRS Hot Spots</div>
<h1 style="margin-top:100px">Burning Activity Calendar</h1>
<p class="sub">One consistent fire record for the whole planet, from MODIS to VIIRS and beyond.</p>
<p style="margin-top:120px"><b>{TEAM}</b></p><p class="sub" style="font-size:22px">{MEMBERS}</p>''', "title")}
{s(f'''<div class="k">The problem</div><h2>Two satellite records, one fire history that does not line up</h2>
<div class="wide"><div><ul>
<li>MODIS has recorded fire hotspots since 2000 and still flies. VIIRS joined in 2012 with sharper pixels.</li>
<li>VIIRS records about <b>four times</b> as many fire pixels.</li>
<li>Joined as counted, the planet's record steps by {K["raw_join"]} in 2012 (grey line). That step is the sensor, not the fire.</li>
<li>Fire managers lose the long history that tells them whether this month is unusual.</li></ul></div>
<div><img src="{img(TMP / "record.png")}"><p class="small" style="margin-top:8px">The whole world, hotspots per year. Grey: raw sensors joined. Orange: our harmonized record.</p></div></div>''')}
{s(f'''<div class="k">Our solution</div><h2>Convert every MODIS count into what VIIRS would have recorded</h2>
<div class="steps">
<div><strong>1 · NASA data</strong>{K["hot_m"]} million FIRMS hotspots: MODIS, VIIRS on Suomi NPP and NOAA-20, 2000 to this week, the whole planet.</div>
<div><strong>2 · Put in order</strong>Outage days of all four satellites found and corrected; lava and gas flares left out.</div>
<div><strong>3 · Every cell, every month</strong>A model estimates VIIRS counts in {K["cells"]} cells of 25 km, even where MODIS saw nothing.</div>
<div><strong>4 · A second VIIRS</strong>NOAA-20 fills the days Suomi NPP lost and carries the record on after Suomi NPP's data ended in November 2026.</div></div>
<ul><li>The years before 2012 become VIIRS-equivalent, <b>with tested ranges on the estimates</b>.</li>
<li>Trained on 2012–2019, before the MODIS orbits drifted; months before the Aqua satellite use a Terra-only model.</li>
<li>One model for the world, so <b>any country or drawn area</b> works at once.</li></ul>''')}
{s(f'''<div class="k">The web app</div><h2>Any country, any area: when, where and how unusually it burned</h2>
<div class="wide" style="grid-template-columns: 7fr 4fr"><img src="{img(TMP / "story.png")}"><div><ul style="font-size:20px">
<li><b>Calendar</b> of every month since 2000, colour-blind safe, light and dark.</li>
<li><b>Against the median</b>: is this month unusual for the season?</li>
<li><b>Map</b> of where it burned, for any month you click.</li>
<li><b>Any area</b>: a country, or a box you draw.</li>
<li><b>Download</b> the monthly table, the cells and the calendar image.</li></ul>
<p class="small">Shown: Australia, December 2019.</p></div></div>''')}
{s(f'''<div class="k">Does it work?</div><h2>Tested on years the model never saw</h2>
<div class="big"><div><strong>{K["m_box"]}</strong><span>error per 1° box and month; the best simple method: {K["b_box"]}</span></div>
<div><strong>{K["seam_world"]}</strong><span>step at 2012 for the world, where VIIRS begins (raw sensors joined: {K["raw_join"]})</span></div>
<div><strong>{K["rng_country"]}</strong><span>of real values fall inside the range of an estimate, tested across periods</span></div></div>
<table><tr><th>Error on hidden years (both time directions)</th><th>Countries</th><th>1° boxes</th><th>25 km cells (log)</th></tr>
<tr><td>A second VIIRS of the same design (benchmark)</td><td>{K["f_country"]}</td><td>{K["f_box"]}</td><td>{K["f_cell"]}</td></tr>
{row("Our record", "m", True)}{row("Best simple method (local ratio + usual small fires)", "b")}{row("Ratio per country and calendar month", "s")}{row("One ratio per country", "o")}</table>
<p class="small" style="margin-top:10px">With stable orbits a seasonal ratio is as good for whole countries ({K["an_s_country"]} against {K["an_m_country"]}); the model's gain is below country size and in big fire months.
Against burned-area maps, which use no VIIRS data, the estimated years sit {K["ba_h_words"]} the VIIRS years; in the raw join, {K["ba_raw_words"]}.</p>''')}
{s(f'''<div class="k">How we got here</div><h2>Experiments and a review that changed the project</h2>
<div class="two"><div><ul style="font-size:20px">
<li><b>We broke our first model.</b> A seam test showed a step of up to +33% at 2012: fires only VIIRS can see were missing. Modelling every cell and month closed most of it.</li>
<li><b>Independent validation stress-tests.</b> Six multi-stage audit checks found a faulty input (months before Aqua were 13% low), a bug in our downloader and claims that were too strong. All fixed or stated.</li>
<li><b>Two good sensors disagree</b> by {K["f_country"]} per country and month: the scale to read errors against. A third, NOAA-21, confirms it.</li>
<li><b>Three more NASA sensors as tests.</b> A third VIIRS, Landsat's 30 m pixels and the GOES geostationary satellite. GOES's daily fire cycle explains why MODIS conversions age: Terra now looks at fire at {K["dr_terra_to"]}, not {K["dr_terra_from"]}.</li></ul></div>
<div><img src="{img(TMP / "here.png")}"><p class="small" style="margin-top:8px">Every area shows its own test, and its step at 2012.</p></div></div>''')}
{s(f'''<div class="k">Honest, open, ready to grow</div><h2>What makes it trustworthy, and what comes next</h2>
<div class="two"><div><p><b>Built on NASA open data</b></p><ul style="font-size:20px"><li>NASA FIRMS: MODIS Collection 6.1, VIIRS on Suomi NPP and NOAA-20, 2000–2026.</li>
<li>The whole planet: {K["cells"]} cells, {K["countries"]} countries tested.</li><li>Estimates carry tested ranges. Every weak result is in the write-up.</li>
<li>Open code and a lab notebook of every experiment.</li></ul></div>
<div><p><b>Next</b></p><ul style="font-size:20px"><li>NOAA-21 in the record itself, not only in the tests.</li><li>Daily updates, and alerts when a month runs far above its median.</li>
<li>Day and night separately; single harmonized hotspots.</li></ul>
<p style="margin-top:26px; font-size:26px"><b>One fire record, from MODIS to VIIRS and beyond.</b></p></div></div>''')}
</html>"""


def main():
    out = ROOT / "demo" / "slides.pdf"
    with sync_playwright() as pw:
        shots(pw)
        (TMP / "slides.html").write_text(html())
        b = pw.chromium.launch()
        p = b.new_page()
        p.goto(f"file://{TMP / 'slides.html'}")
        p.wait_for_timeout(500)
        p.pdf(path=str(out), width="1280px", height="720px", print_background=True)
        for i in range(7):  # previews, for checking
            p.set_viewport_size({"width": 1280, "height": 720})
            p.evaluate(f"document.querySelectorAll('section')[{i}].scrollIntoView()")
            p.screenshot(path=TMP / f"slide{i + 1}.png")
        b.close()
    print("saved", out, "| previews in", TMP)


if __name__ == "__main__":
    main()
