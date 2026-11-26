# External project references

`breno_research_studio_v2/` is a separate shallow clone of Breno's public repository, downloaded 20 November 2026 from https://github.com/brenosouzasader-arch/research_studio_team_1_V2 at commit `825538f0a622af6aa9bf08af4059b7f3071c8c40`. It is a reference copy, not an integrated dependency or a source of validated A160 results. Its separate `.git` directory means its contents are not automatically included in this project's Git commits; use the URL and commit to reproduce it.

Useful starting points:

- `docs/SOURCES.md`: source register, dataset descriptions and assumptions.
- `pipeline/step05_forecast_demand/`: Barcelona aggregate processing, synthetic profiles and Spanish meter-model experiment.
- `pipeline/examples/demand_model/`: derived daily averages, hourly shapes and reported model evaluation; these are not A160 or CEP9 meter records.
- `pipeline/examples/cep9_actual.json`, `cep9_members.csv`, `cep9_hourly.csv` and `cep9_both/`: CEP9 reference information, participant assumptions and modeled generation examples. The documented total installation spans two roofs; individual roof attribution needs verification.
- `pipeline/step04_read_host_demand/`, `step06_prices_and_battery/`, `step07_share_energy/` and `step08_compare_investment/`: candidate host, storage, sharing and economic methods for later review.
- `website/`: public demonstration and its generated data; `pipeline/README.md` describes execution.

The clone contains committed files only. The upstream `.gitignore` excludes raw LiDAR, large downloads and `pipeline/data/`; the original meters and external source datasets are not downloaded by cloning. Check each source's license and provenance before reuse; no repository-wide license file was found at the clone root. Review assumptions, temporal alignment, legal eligibility and conservation before integrating any code or results. Preserve this project's actual-versus-hypothetical PV safeguards and trained artifacts.
