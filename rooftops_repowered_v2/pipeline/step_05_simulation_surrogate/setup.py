"""Download a pinned portable EnergyPlus engine and Barcelona reference weather.

No system installation or PATH changes. Run as a module from the project root.
"""
import hashlib
from pathlib import Path
import zipfile

from download_datasets import fetch
from pipeline.common import ROOT, directory, load_config, now, write_json

VERSION = '26.2.0'
ASSET = 'EnergyPlus-26.2.0-4bd7a1f26f-Windows-x86_64.zip'
ENGINE_URL = f'https://github.com/NatLabRockies/EnergyPlus/releases/download/v{VERSION}/{ASSET}'
ENGINE_SHA256 = '15ab698803f459444ec3e97ee52ab9f99db93a583819c7821b17dfcd7b4461e7'
WEATHER_URL = 'https://energyplus-weather.s3.amazonaws.com/europe_wmo_region_6/ESP/ESP_Barcelona.081810_IWEC/ESP_Barcelona.081810_IWEC.zip'


def unpack(archive, destination):
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as handle:
        for member in handle.infolist():
            resolved = (destination / member.filename).resolve()
            resolved.relative_to(destination.resolve())
        corrupt = handle.testzip()
        if corrupt:
            raise ValueError(f'Corrupt archive member: {corrupt}')
        handle.extractall(destination)


def main():
    cfg = load_config()
    out = directory(cfg, 'reports') / 'simulation_surrogate'
    out.mkdir(parents=True, exist_ok=True)
    log = out / 'setup.log'
    tools = ROOT / 'tools/energyplus'
    archive = tools / ASSET
    engine = tools / VERSION
    print('Downloading portable EnergyPlus; no system installation.', flush=True)
    if not archive.exists():
        fetch(ENGINE_URL, archive, log)
    with archive.open('rb') as handle:
        digest = hashlib.file_digest(handle, 'sha256').hexdigest()
    if digest != ENGINE_SHA256:
        raise ValueError('EnergyPlus archive checksum does not match the pinned publisher digest.')
    if not list(engine.rglob('energyplus.exe')):
        unpack(archive, engine)
    executable = next(engine.rglob('energyplus.exe'))
    weather_dir = directory(cfg, 'datasets') / 'raw/simulation_weather'
    weather_zip = weather_dir / 'ESP_Barcelona.081810_IWEC.zip'
    print('Downloading Barcelona IWEC station weather (reference climate, not a selected roof).', flush=True)
    if not weather_zip.exists():
        fetch(WEATHER_URL, weather_zip, log, 300)
    unpack(weather_zip, weather_dir)
    epw = next(weather_dir.rglob('*.epw'))
    first_line = epw.read_text(encoding='utf-8-sig').splitlines()[0]
    epw_location = first_line.split(',')
    if epw_location[0] != 'LOCATION' or 'BARCELONA' not in first_line.upper():
        raise ValueError(f'Unexpected weather station header: {first_line}')
    office_files = sorted(str(p.relative_to(ROOT)) for p in engine.rglob('*.idf') if 'office' in p.name.lower())
    write_json(out / 'setup_manifest.json', {
        'created_utc': now(), 'engine_version': VERSION, 'engine_url': ENGINE_URL,
        'engine_sha256': digest, 'executable': str(executable.relative_to(ROOT)),
        'weather_url': WEATHER_URL, 'weather_epw': str(epw.relative_to(ROOT)),
        'weather_header': epw_location, 'available_office_examples': office_files,
        'weather_provenance': 'IWEC typical/reference weather; not actual 2026 observations or host-specific PVGIS data',
        'status': 'reference_tools_downloaded_not_a_validated_building_model'})
    print(f'Engine: {executable}\nWeather: {epw}\nOffice examples: {office_files}', flush=True)


if __name__ == '__main__':
    main()
