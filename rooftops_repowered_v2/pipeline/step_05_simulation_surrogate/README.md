# Office physics-simulation surrogate

Alternative primary AI route, selected after measured BDG2 did not show an XGBoost
gain. Starts with one office reference archetype, separately from the real host.

1. `python -m pipeline.step_05_simulation_surrogate.setup`: download the pinned portable
   EnergyPlus engine plus Barcelona IWEC weather. No system installation.
2. `python -m pipeline.step_05_simulation_surrogate.simulate --limit 1`: annual smoke run.
3. `python -m pipeline.step_05_simulation_surrogate.simulate`: run the 36 configurations in
   `config/simulation.json`, isolated in individual working directories.
4. `python -m pipeline train-office-surrogate`: prepare hourly electric targets,
   hold out entire configurations, fit XGBoost and compare both hourly and
   schedule-aware linear baselines.
5. `python -m pipeline predict-office --input FILE --output FILE`: inference only
   within the documented archetype, floor-area and operation-parameter domain.

Files:

- Engine and examples: `tools/energyplus/` (kept local).
- Weather: `datasets/raw/simulation_weather/`.
- Scenario inputs, raw outputs and logs: `datasets/synthetic/energyplus/office_NNN/`.
- Combined labeled data: `datasets/processed/office_simulation_training.csv.gz`.
- Quality, splits, metrics and model card: `reports/simulation_surrogate/`.
- Saved models/manifests: `pipeline/models/`.

The source is the official `RefBldgSmallOfficeNew2004_Chicago` example, with
Barcelona weather and its companion design days replacing Chicago conditions.
Use the coldest winter and hottest summer design conditions in that companion
file for sizing. Envelope, geometry and HVAC remain the published U.S. example;
this is **not** a calibrated Barcelona office.

36 combinations vary start hour, duration, plug-load density and weekend activity.
People, lighting, equipment and HVAC availability schedules are changed explicitly.
Standby fractions are assumed: occupancy 0, lighting 5%, equipment 15%; peak
lighting density and occupancy density inherit the reference model. These are
synthetic operating scenarios, not observed schedules. All parameters and input
hashes are recorded alongside each run.

Use a non-leap 2017 calendar, local standard time without DST, and an IWEC typical
weather sequence; these are simulation conventions, not observed 2017 Barcelona
conditions. Facility electricity is EnergyPlus `Electricity:Facility` in joules,
converted to kWh by dividing by 3,600,000. Gas and ideal thermal demand are not
counted as electricity. Hour-end labels 01:00–24:00 map to interval starts 00:00–23:00.

Validation holds out full operating configurations, with the same geometry and
weather sequence. The stronger linear baseline receives the same schedules,
known plug/lighting products and weather features, so XGBoost must improve more
than a pooled hourly profile. A successful score establishes simulator approximation
within this domain. It does not establish real-building accuracy, geometry scaling,
unseen climates or residential demand. New host geometry needs new simulations
or a justified domain-expansion method before applying the surrogate.
