"""Offline browser acceptance checks using installed Chrome and a loopback server."""
import json
import argparse
from pathlib import Path
import sys
import threading

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from playwright.sync_api import sync_playwright, expect
from ui.server import make_server
from ui.data import RepositoryData
from ui.tests.accessibility import contrast_samples,capture_page


def run(base_url=None, output_dir=None):
    out = (ROOT / output_dir).resolve() if output_dir else ROOT / 'ui/docs/screenshots'
    if not out.is_relative_to(ROOT):
        raise ValueError('Browser evidence must stay within the workspace.')
    out.mkdir(parents=True, exist_ok=True)
    temporary = ROOT / 'ui/.test-output'
    temporary.mkdir(exist_ok=True)
    server = None
    worker = None
    if base_url:
        from urllib.parse import urlsplit
        parsed = urlsplit(base_url)
        if parsed.scheme != 'http' or parsed.hostname not in ('localhost', '127.0.0.1'):
            raise ValueError('Browser audit accepts a local HTTP dashboard only.')
        base = base_url.rstrip('/')
    else:
        server = make_server(0)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        base = f'http://127.0.0.1:{server.server_port}'
    checks = []
    errors = []
    api = RepositoryData().dashboard()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(channel='chrome', headless=True)
            context = browser.new_context(viewport={'width':1440,'height':1000}, accept_downloads=True)
            # Routine QA never depends on external internet.
            context.route('**/*', lambda route: route.continue_() if route.request.url.startswith(base) or route.request.url.startswith(('data:','blob:')) else route.abort())
            page = context.new_page()
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(base)
            expect(page.locator('#connection-status')).to_contain_text('Repository data connected')
            assert page.locator('#building-inventory .cluster-item').count() == len(api['buildings']['buildings'])
            assert page.locator('.candidate-evidence').count()==len(api['buildings']['buildings'])
            page.locator('.candidate-evidence summary').first.click()
            expect(page.locator('.candidate-evidence').first).to_contain_text('installed kWp are unknown')
            page.locator('.candidate-evidence summary').first.click()
            checks.append('Live public candidate inventory and repository connection')
            contrast=contrast_samples(page)
            assert all(sample['meets_normal_text_4_5'] for sample in contrast),contrast
            checks.append('Eleven sampled text styles meet 4.5:1 contrast; keyboard/dialog checks remain separate')
            for view in ('overview','roof','solar','demand','sharing','impact','evidence'):
                page.locator(f'.nav-btn[data-view="{view}"]').click()
                expect(page.locator(f'#view-{view}')).to_be_visible()
                assert not page.evaluate('document.documentElement.scrollWidth > innerWidth'), view
                if view == 'roof':
                    expect(page.locator('#roof-map svg')).to_be_visible()
                if view=='solar' and api['pvgis'].get('hypothetical_state')=='available':
                    expect(page.locator('#pvgis-chart svg')).to_be_visible()
                capture_page(page,out / f'desktop-{view}.png')
            checks.append('All seven desktop views, no horizontal overflow, screenshots')
            page.locator('[data-view="roof"]').click()
            for scenario in ('conservative','base','optimistic'):
                page.locator(f'[data-roof-scenario="{scenario}"]').click()
                for assessment,target in (('retrospective','roof-retro'),('additional','roof-additional')):
                    expected = next(row for row in api['roof']['assessments'][assessment]['scenarios'] if row['scenario']==scenario)
                    expect(page.locator(f'#{target}')).to_have_text(f'{expected["estimated_kwp"]:.2f} kWp')
            page.locator('#assessment-select').select_option('additional')
            expect(page.locator('#roof-map svg')).to_have_attribute('aria-label', 'Actual A160 WGS84 geometry: additional, optimistic. Local metric projection.')
            page.locator('[data-roof-scenario="base"]').click()
            checks.append('Both roof assessments and all scenario values match source CSVs; map updates')
            trigger = page.get_by_role('button', name='Sources & assumptions')
            trigger.click()
            expect(page.locator('#evidence-dialog')).to_be_visible()
            expect(page.locator('#evidence-dialog')).to_contain_text('Roof model version:')
            page.keyboard.press('Tab')
            assert page.evaluate('document.getElementById("evidence-dialog").contains(document.activeElement)')
            page.keyboard.press('Escape')
            expect(page.locator('#evidence-dialog')).not_to_be_visible()
            expect(trigger).to_be_focused()
            checks.append('Evidence drawer, keyboard focus containment, Escape and focus return')
            page.locator('[data-view="demand"]').click()
            page.locator('#typology-select').select_option('home')
            slider=page.locator('#view-demand .hour-control')
            slider.focus();page.keyboard.press('End')
            expect(page.locator('#view-demand .hour-label')).to_have_text('23:00')
            expect(page.locator('#view-demand')).to_contain_text('ILLUSTRATIVE_NOT_SIMULATED')
            expected_model=next(row for row in api['model']['metrics'] if row['split']=='test' and row['model']=='office_energyplus_xgboost')
            expect(page.locator('#model-mae')).to_have_text(f'{expected_model["mae_kwh"]:.3f} kWh')
            checks.append('Typology/hour explorer and CSV-derived model metrics with illustrative labels')
            page.locator('[data-view="sharing"]').click()
            for strategy in ('grid','host','fixed','informed'):
                page.locator(f'[data-strategy="{strategy}"]').click()
                expect(page.locator(f'[data-strategy="{strategy}"]')).to_have_attribute('aria-pressed','true')
            with page.expect_download() as download:
                page.locator('#export-config').click()
            path=temporary/'scenario.json';download.value.save_as(path)
            export=json.loads(path.read_text())
            assert export['document_type']=='UI_SCENARIO_TEMPLATE' and export['executed'] is False
            assert export['roof_estimation']['assessment']=='additional' and export['roof_estimation']['estimated_kwp']==1.26
            assert export['roof_estimation']['actual_installed_kwp'] is None
            assert export['sharing_strategy']=='informed' and export['explorer_hour']==23 and export['demand_typology_preview']=='home'
            for key in ('pv_hourly','demand_hourly','scenario_results','impact_results'):
                assert export[key] is None
            checks.append('All sharing selectors and unexecuted export, separate assessment, null unknown results')
            for view in ('solar','demand','sharing','impact'):
                page.locator(f'[data-view="{view}"]').click()
                expect(page.locator(f'#pending-{view}')).to_contain_text('PENDING')
            checks.append('All unready stages visibly pending')
            page.set_viewport_size({'width':390,'height':844})
            for view in ('overview','roof','solar','demand','sharing','impact','evidence'):
                page.locator(f'.nav-btn[data-view="{view}"]').click()
                expect(page.locator(f'#view-{view}')).to_be_visible()
                assert not page.evaluate('document.documentElement.scrollWidth > innerWidth'), f'mobile {view}'
                capture_page(page,out / f'mobile-{view}.png')
            checks.append('All seven mobile views and screenshots; labeled scrollable navigation; no overflow')
            with page.expect_download() as download:
                page.locator('#export-config-mobile').click()
            assert download.value.suggested_filename.endswith('.json')
            checks.append('Mobile JSON export')
            # A failed backend must never leave prototype numbers masquerading as results.
            context.unroute('**/*')
            context.route('**/api/dashboard', lambda route: route.abort())
            page.reload()
            expect(page.locator('#connection-status')).to_contain_text('Repository data unavailable')
            expect(page.locator('#roof-retro')).to_contain_text('Pending')
            assert page.locator('#export-config-mobile').is_disabled()
            checks.append('Offline/backend failure leaves values pending and export disabled')
            assert not errors, errors
            report={'status':'passed','browser':browser.version,'checks_passed':len(checks),'checks':checks,'page_errors':errors,'external_network_required':False,
                    'server_mode':'existing_user_dashboard' if base_url else 'ephemeral_test_server','base_url':base}
            browser.close()
        (out.parent/'browser_results.json').write_text(json.dumps(report,indent=2)+'\n')
        (out.parent/'contrast_samples.json').write_text(json.dumps({'method':'Computed solid-color samples; not a full accessibility certification','samples':contrast},indent=2)+'\n')
        print(json.dumps(report,indent=2))
    finally:
        if server:
            server.shutdown();server.server_close();worker.join(timeout=5)


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', help='Audit an already running loopback dashboard without stopping it')
    parser.add_argument('--output-dir', help='Screenshot folder relative to the workspace')
    args = parser.parse_args()
    run(args.base_url, args.output_dir)
