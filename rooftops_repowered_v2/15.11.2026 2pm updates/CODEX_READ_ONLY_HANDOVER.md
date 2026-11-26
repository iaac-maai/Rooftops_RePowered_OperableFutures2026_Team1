# CODEX — READ-ONLY RESUME HANDOVER (DO NOT EXECUTE)

**User instruction for the current session:** Read and understand the project updates, reconcile them with the latest repository, update your own understanding, and wait. **DO NOT start development or modify files**. This explicitly overrides implementation steps in earlier prompts and documents.

Repository: `https://github.com/SindhujaDavuluri/rooftops_repowered_v2`.
Latest confirmed baseline at handover creation: `main` merge `de3ea0ca5f2c022af5f4d50d054a0c897e5eb914` (2026-11-15). Verify again when user asks to resume; don't assume current SHA later.

## Read these in order

1. `PACKAGE_README_START_HERE.md` (outside repo, in this ZIP): structure, source priority and state.
2. `Development_Pipeline_NEXT_SESSION.md`: chronological methodology and quality gates.
3. `rhino_starter/Rhino_8_A160_Setup_Roadmap.md` and three CSV templates: future DWG→Rhino→Honeybee→EnergyPlus path, never claim geometry ready now.
4. `synthetic_reference/` companion ZIP / `datasets/synthetic/a160_cluster/README.md`, `electricity_proxy_method.md`, `source_register.csv`, `weather_alignment_contract.json`: distinguish published, synthetic, proxy and simulated.
5. `Research_Source_Register_UPDATED.md` and `Roofscapes_Research_Master_Speaker_Notes.md`: presentation evidence and decision chronology.
6. Live repo `README.md`, `reports/NEXT_STEPS.md`, `PIPELINE.md`, `docs/METHOD.md`, `docs/DATA_CONTRACTS.md`.
7. Live repo `ui/README.md`, `ui/API.md`, `ui/docs/pv-integration/README.md`, `reports/roof_capacity/A160/README.md`, `reports/simulation_surrogate/MODEL_CARD.md`.

## What is completed, reported / uncompleted

- Confirmed remotely: seven-view read-only UI, hypothetical PVGIS acquisition/cached provenance, two provisional A160 rooftop assessments, actual PV specifications unknown, existing reference-office EnergyPlus-XGBoost surrogate.
- Reported by repo (not independently rerun in this handover): 70 Python tests, 11 general and five PV UI browser groups passed; 34 protected files unchanged at recorded verification.
- Synthetic literature pack is **outside GitHub** and is supplied for subsequent import after review; no claim it is merged.
- Missing: as-built A160 PV specs; inspected 2026 city DWG and a Rhino/Honeybee .3dm/.gh; A160 EnergyPlus hourly simulation; A160-trained AI; independent 3-typology physics models; synchronized PV/demand; real cluster balance and impact results.

## Changes future development needs

**Future task A, only with explicit go-ahead:** import provenance-labeled synthetic input package into its designated folder. Do not use literature-calibrated hourly profiles as supervised AI targets or as actual metered demand. Verify geometry and building use assumptions.

**Future task B, only with explicit go-ahead:** verify Rhino 8 / Ladybug Tools installation, obtain city DWG (el Parc i la Llacuna del Poblenou), assess A160 model quality, create valid Honeybee thermal zones, export and run EnergyPlus. If Rhino is absent, propose a documented fallback rather than fabricate files.

**Future task C, only if EnergyPlus and QA gates pass:** train a **separate** A160-specific XGBoost surrogate using simulated EnergyPlus labels; hold out entire simulation configurations (prefer scenario/geometry groups as applicable); compare with simple and schedule-aware baselines; preserve existing 511 m² office surrogate and measured BDG2 failure record.

**Future task D, only once scientifically meaningful:** simulate school, residential and hotel types separately; align PVGIS/EnergyPlus weather calendars; test allocations with conservation; source economic/emissions assumptions; add evidence-labeled, read-only UI adapters for results, with new screenshots/tests. Keep actual vs hypothetical separation.

## Required behavior now

- **No code editing; no file writes, downloads, installs or simulation/training commands; no Git push/branch/PR; no CLI tests; no UI modifications; no Stitch changes.**
- Do not change `config/project.json`, PVGIS eligibility flags, `pipeline/models/`, source manifests or frozen rooftop inputs.
- If there is a mismatch between the standalone handover and the live repository, document it in your response; don't silently resolve by editing code.
- After reviewing, **reply in chat only** with: (a) what you understand of the latest state; (b) outstanding unknowns; (c) next proposed work package with acceptance criteria; (d) any file or source limitations; (e) explicit confirmation no implementation was started.
- Ask for the user's explicit instruction in the **next session** before doing more.
