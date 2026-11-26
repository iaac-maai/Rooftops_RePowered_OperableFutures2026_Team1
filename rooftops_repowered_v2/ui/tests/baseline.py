"""Capture the untouched approved prototype before integration (installed Chrome)."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
source = ROOT / 'UI Interface/Roofscapes_UI_Template_Editable_Package/index.html'
out = ROOT / 'ui/docs/baseline'
out.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch(channel='chrome', headless=True)
    page = browser.new_page(viewport={'width': 1440, 'height': 1000})
    page.goto(source.as_uri())
    results = []
    for view in ('overview','roof','solar','demand','sharing','impact','evidence'):
        page.locator(f'.nav-btn[data-view="{view}"]').click()
        assert page.locator(f'#view-{view}').is_visible()
        page.screenshot(path=str(out / f'desktop-{view}.png'), full_page=True)
        results.append(view)
    page.locator('[data-view="overview"]').click()
    page.set_viewport_size({'width': 390, 'height': 844})
    page.screenshot(path=str(out / 'mobile-overview.png'), full_page=True)
    (out / 'results.json').write_text(json.dumps({'views_reached': results,
        'source': str(source.relative_to(ROOT)), 'browser': browser.version,
        'overflow_mobile': page.evaluate('document.documentElement.scrollWidth > innerWidth')}, indent=2))
    browser.close()
print('Baseline: seven desktop views and one mobile screenshot captured.')
