# Roofscapes (Re)Powered V2 — PAUSE & RESUME MASTER PACKAGE

**Snapshot:** Sunday 15 November 2026 | **Mode:** Research handover / **No development authorized**

This consolidates the user's design/research/development decisions, public sources, source-labeled synthetic hourly-demand references, Rhino model setup instructions, next staged development pipeline, and an explicit **read-only** Codex handover. It does **not** contain a finished A160 `.3dm`, `.gh`, validated EnergyPlus simulation, site-trained AI model, or newly implemented UI functions.

## Files and why they matter

| File | Use |
|---|---|
| `Roofscapes_RePowered_V2_Research_Master_UPDATED.pptx` | **67-slide minimal research master**. Covers full decision history, method, case-site/cluster rationale, V1→V2, datasets, model results and failures, PVGIS, synthetic assumptions, Rhino route, future pipeline, limitations and evidence. Embedded notes on all 67 slides. |
| `Roofscapes_RePowered_V2_Research_Master_UPDATED.pdf` | View/annotate the master without PowerPoint. |
| `Roofscapes_Research_Master_Speaker_Notes.md` | Detailed explanations and per-slide source links. |
| `Research_Source_Register_UPDATED.md` | 75 numbered research source references; links appear also on the respective slides. |
| `Development_Pipeline_NEXT_SESSION.md` | Inputs, tools, outputs and pass/fail gates for next coding phases. |
| `rhino_starter/Rhino_8_A160_Setup_Roadmap.md` | What to download, how to import/validate DWG and create Honeybee zones. |
| `rhino_starter/*_TEMPLATE.csv` | Blank geometry provenance, thermal-zone, and EnergyPlus-model data contracts. |
| `rhino_starter/create_rhino_layers_STARTER.py` | **Optional** future Rhino layer-tree helper; do NOT run during this pause. |
| `synthetic_reference/Roofscapes_A160_Synthetic_Data_Literature_Calibrated_Hourly_Update.zip` | Full companion version of the four-building/12-case literature-calibrated synthetic input package and generation code. |
| `synthetic_reference/Roofscapes_A160_Synthetic_Assumption_Review_Literature_Hourly.xlsx` | Editable assumptions and literature benchmarks. |
| `codex_read_only/CODEX_READ_ONLY_HANDOVER.md` | Exact constraints for Codex, including future UI updates **after** explicit approval. |
| `codex_read_only/PASTE_INTO_CODEX_NEXT_SESSION.txt` | Short read-only prompt. |
| `Research_Master_Contact_Sheet.jpg` | Visual overview of the deck. |
| `Deck_Manifest.json` | Slide taxonomy, evidence IDs and notes manifest. |

## Repository facts at packaging

- Connected public repository: https://github.com/SindhujaDavuluri/rooftops_repowered_v2 ; `main` merge SHA `de3ea0ca5f2c022af5f4d50d054a0c897e5eb914` as checked in this chat.
- Completed: provisional A160 roof screening; PVGIS 2017 hypothetical sensitivity outputs (separate and sharing-ineligible); local seven-view read-only UI; initial U.S. small-office EnergyPlus-to-XGBoost surrogate.
- **Unknown:** A160 actual installed PV kWp, module Wp/count, tilt/azimuth, measured generation, real hourly building meters, as-built conditioned floor areas/HVAC, statutory community eligibility.
- **Not completed:** City DWG manually checked in Rhino; A160 thermal model, A160 EnergyPlus simulation, A160-specific AI, cross-typology demand models, independent allocation evaluation, priced and carbon impacts.
- Source-based synthetic benchmarks and hourly schedules exist in this companion ZIP **only**, not yet merged into GitHub.

## Research integrity rules

Distinguish four categories of numbers clearly:
1. **Published/observed:** architecture and addresses, visible PV coverage from image interpretation, source dates and project reports.
2. **Hypothetical scenario:** rooftop panel packing and PVGIS simulated generation for hypothetical capacities.
3. **Literature-calibrated synthetic proxy:** total electricity magnitude from published analogue plus assumed schedule-distribution. These hourly kWh profiles are not independent reference loads or actual building meters.
4. **Physics simulation / AI prediction:** EnergyPlus can produce simulation labels after runs and QA; XGBoost may then approximate *the simulated domain*, not claim unmeasured actual A160 accuracy.

Do not join PVGIS SARAH3 2017 and office IWEC typical-year merely by matching nominal years. Do not infer existing installed kWp from the 2015 Barcelona map or hypothetical packing. Do not claim benefits merely from the presence of four buildings; if the host absorbs all PV, added collective benefit could be zero.

## Quick next-session workflow

1. In Codex, paste `codex_read_only/PASTE_INTO_CODEX_NEXT_SESSION.txt` and attach this ZIP; **read-only review only**.
2. Review the slide deck and synthetic assumptions; annotate questionable numbers and corrections in the next conversation.
3. When ready for development, **explicitly authorize** one bounded stage: verify 2026 Poblenou DWG and Rhino/Honeybee feasibility, then A160 EnergyPlus model.
4. Only after the simulation QA and validation gate should Codex be authorized to train a separately versioned A160 XGBoost model.
5. After credible outputs exist, ask Codex to add new UI data adapters and plots without mislabeling modeled or hypothetical outputs.

**No GitHub repository or trained models were modified by creation of this package.**
