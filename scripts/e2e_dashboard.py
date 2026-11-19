"""End-to-end: run the real app and click through the dashboard like a judge would.
python3 scripts/e2e_dashboard.py"""
import os, subprocess, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
env = dict(os.environ, DATABASE_URL="sqlite:///./e2e_heatguard.db", CYCLE_SECONDS="100000",
           HEATGUARD_FIXTURE=str(ROOT / "tests/fixtures/openmeteo_2026-11-06.json"))
Path(ROOT / "e2e_heatguard.db").unlink(missing_ok=True)
srv = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--port", "8123"], cwd=ROOT, env=env,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(4)
res = []
def check(n, ok, d=""):
    res.append(ok); print(("PASS " if ok else "FAIL ") + n + ("" if ok else f" -> {d}"))
try:
    with sync_playwright() as p:
        b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1400, "height": 1000}); errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)[:200])); pg.on("dialog", lambda d: d.accept())
        pg.goto("http://127.0.0.1:8123/"); pg.click("#enter"); pg.wait_for_selector(".crew")
        check("live indicator shows", "Live" in pg.inner_text("#livebar"))
        check("disclaimer visible", "not a medical diagnosis" in pg.inner_text(".disclaimer"))
        check("kpi strip rendered", pg.locator(".kpi").count() == 4)
        # heatwave button -> real change on screen
        pg.select_option("#sim-site", index=0)
        pg.click('[data-preset="heatwave"]'); pg.wait_for_function("document.querySelector('.lv').textContent.trim()==='Extreme'", timeout=15000)
        check("heatwave turns crews Extreme", True)
        check("KPI counts crews at High+", int(pg.locator(".kpi .n").first.inner_text()) >= 1)
        pg.wait_for_function("!document.querySelector('[data-preset=heatwave]').disabled", timeout=10000)
        check("button re-enabled after action", pg.locator('[data-preset="heatwave"]').is_enabled())
        # crew factor select updates and persists
        sel = pg.locator('select[data-k="workload"]').first
        sel.select_option("light"); pg.wait_for_timeout(1500)
        check("workload change saved", pg.locator('select[data-k="workload"]').first.input_value() == "light")
        # plan details open and survive the 5 s refresh
        pg.locator("details.plan summary").first.click()
        pg.wait_for_timeout(6500)
        check("plan stays open after auto-refresh", pg.locator("details.plan").first.get_attribute("open") is not None)
        check("plan has water advice", "Water:" in pg.locator("details.plan").first.inner_text())
        # feed toggle label tracks server state, even after reload
        pg.click("#feed"); pg.wait_for_function("document.querySelector('#feed').textContent.includes('Restore')", timeout=15000)
        pg.reload(); pg.wait_for_selector(".crew")
        check("feed label survives reload", "Restore" in pg.inner_text("#feed"))
        pg.click("#feed"); pg.wait_for_function("document.querySelector('#feed').textContent.includes('Cut')", timeout=15000)
        # escalation: worker says unwell on Phones -> shows on Sites -> mark handled
        pg.click('nav [data-view="phones"]'); pg.wait_for_selector(".people button")
        pg.locator(".people button", has_text="Imran").click()
        pg.wait_for_selector("#reply"); pg.fill("#reply", "UNWELL"); pg.click("#composer button")
        pg.wait_for_timeout(2000)
        pg.click('nav [data-view="live"]')
        pg.wait_for_selector("[data-ack]", timeout=15000)
        check("unwell escalation appears", "unwell" in pg.inner_text("#escs"))
        pg.click("[data-ack]"); pg.wait_for_function("!document.querySelector('[data-ack]')", timeout=15000)
        check("mark as handled works", "Handled by" in pg.inner_text("#escs"))
        # typing is not wiped by refresh
        pg.click('nav [data-view="phones"]'); pg.locator(".people button", has_text="Rajesh").click()
        pg.fill("#reply", "half typed"); pg.wait_for_timeout(6500)
        check("draft text kept across refresh", pg.input_value("#reply") == "half typed")
        # purge control
        pg.locator(".people button", has_text="Imran").click(); pg.wait_for_selector("#purge")
        pg.click("#purge"); pg.wait_for_timeout(1500)
        check("purge removes replies and opts out", "opted out" in pg.inner_text(".people"))
        # results + privacy views
        pg.click('nav [data-view="metrics"]'); pg.wait_for_selector(".stat")
        check("results view has stats", pg.locator(".stat").count() >= 8)
        pg.click('nav [data-view="privacy"]')
        check("privacy view explains purge + planner", "Delete my replies" in pg.inner_text("#privacy") and "shift plan" in pg.inner_text("#privacy"))
        pg.click('nav [data-view="live"]'); pg.screenshot(path="docs/assets/dashboard_v2.png")
        check("no JS errors", not errs, errs)
        # mobile
        m = b.new_page(viewport={"width": 390, "height": 844}); m.goto("http://127.0.0.1:8123/"); m.evaluate("sessionStorage.setItem('hg-guest','1')"); m.reload(); m.wait_for_selector(".crew")
        check("mobile: no sideways scroll", not m.evaluate("document.documentElement.scrollWidth>innerWidth+2"))
        b.close()
finally:
    srv.terminate(); Path(ROOT / "e2e_heatguard.db").unlink(missing_ok=True)
print(f"{sum(res)}/{len(res)} passed"); sys.exit(0 if all(res) else 1)
