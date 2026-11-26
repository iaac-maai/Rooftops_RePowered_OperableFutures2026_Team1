"""Live-server acceptance for existing-PV comparison and real hypothetical PVGIS."""
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from playwright.sync_api import sync_playwright,expect
from ui.tests.accessibility import capture_page


def run():
    out=ROOT/'ui/docs/pv-integration';out.mkdir(exist_ok=True)
    checks=[];errors=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='chrome',headless=True)
        page=browser.new_page(viewport={'width':1440,'height':1000},accept_downloads=True)
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.goto('http://127.0.0.1:8765')
        expect(page.locator('#connection-status')).to_contain_text('Repository data connected')
        page.locator('[data-view="roof"]').click()
        expect(page.locator('#existing-pv-comparison')).to_be_visible()
        assert page.locator('.comparison-table tbody tr').count()==3
        page.locator('[data-compare-scenario="conservative"]').click()
        expect(page.locator('#roof-retro')).to_have_text('95.34 kWp')
        expect(page.locator('#comparison-summary')).to_contain_text('+8.2%')
        page.locator('[data-compare-scenario="base"]').click()
        capture_page(page,out/'desktop-comparison.png')
        checks.append('Existing image coverage vs all three predicted-area/IoU scenarios; no capacity error invented')
        page.locator('[data-view="solar"]').click()
        expect(page.locator('#existing-pv-dossier')).to_contain_text('Installed capacity / module count')
        expect(page.locator('#existing-pv-dossier')).to_contain_text('Unknown')
        expect(page.locator('#pvgis-chart svg')).to_be_visible()
        expect(page.locator('#pvgis-day-summary')).to_contain_text('24 source intervals')
        expect(page.locator('#pvgis-explorer')).to_contain_text('does not estimate or measure the actual installed A160 system')
        checks.append('Official hourly PVGIS chart loads while installed specifications remain unknown')
        day=page.locator('#pvgis-day')
        day.fill('2017-10-29');day.dispatch_event('change')
        expect(page.locator('#pvgis-day-summary')).to_contain_text('25 source intervals')
        day.fill('2017-03-26');day.dispatch_event('change')
        expect(page.locator('#pvgis-day-summary')).to_contain_text('23 source intervals')
        day.fill('2018-01-01');day.dispatch_event('change')
        expect(page.locator('#pvgis-day-summary')).to_contain_text('1 source intervals')
        day.fill('2017-06-21');day.dispatch_event('change')
        checks.append('Europe/Madrid DST and partial local UTC-year boundaries display exact retained source intervals')
        page.locator('#pvgis-case').select_option('additional_conservative')
        expect(page.locator('#pvgis-chart')).to_contain_text('Zero hypothetical capacity')
        assert page.locator('#pvgis-chart svg').count()==0
        page.locator('#pvgis-case').select_option('additional_base')
        expect(page.locator('#pvgis-chart svg')).to_be_visible()
        expect(page.locator('#pvgis-run-details')).to_contain_text('1.26 kWp')
        with page.expect_download() as download: page.locator('#download-pvgis-settings').click()
        temp=ROOT/'ui/.test-output/pvgis_export.json';download.value.save_as(temp)
        exported=json.loads(temp.read_text())
        assert exported['hypothetical'] is True and exported['energy_sharing_eligible'] is False
        assert exported['actual_installed_capacity_kwp'] is None
        checks.append('Capacity selector, zero-case skip and provenance export preserve hypothetical/actual separation')
        capture_page(page,out/'desktop-solar.png')
        page.set_viewport_size({'width':390,'height':844})
        for view in ('roof','solar'):
            page.locator(f'[data-view="{view}"]').click()
            assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
            capture_page(page,out/f'mobile-{view}.png')
        checks.append('New comparison and PVGIS explorer remain usable at mobile width')
        assert not errors,errors
        report={'status':'passed','checks_passed':len(checks),'checks':checks,'page_errors':errors,'browser':browser.version}
        (out/'pv_workflow_results.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2));browser.close()


if __name__=='__main__':run()
