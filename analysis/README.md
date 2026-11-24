# Analysis

Analysis and plotting of the phys-prop benchmarks of **Sage 2.2.1 + TIP3P**, **Sage 2.3.0 +
TIP3P**, **Rosemary alpha + OPC3** and **Rosemary rc1 + OPC3**. Sage 2.2.1 is an archived result
whose run configuration is not recorded (see the top-level README). Run everything from this directory through pixi (see the
top-level README).

**Most of the scripts here are copied from the Sage 2.3.0 repository**
([openforcefield/ash-sage-rc2](https://github.com/openforcefield/ash-sage-rc2), `05_analysis/`),
where they were written for the Sage 2.3.0 benchmarks. Only the headline step, the per-group
combined plots, the shared plot styles and the self-contained runner were written for this
repository.

## Where each script comes from

| Script | Origin | Changes in this repository |
|---|---|---|
| `compute-statistics.py` | Copied from Sage 2.3.0 repo | Opt-in `--seed`; without it, behaviour is unchanged |
| `map-labels-to-data.py` | Copied from Sage 2.3.0 repo | Default force-field path points to `../forcefields/` |
| `plot-aggregated-statistics.py` | Copied from Sage 2.3.0 repo | Docstring note only |
| `plot-change-in-target.py` | Copied from Sage 2.3.0 repo | Docstring note only |
| `plot_helpers.py` | Copied from Sage 2.3.0 repo | None |
| `label-with-checkmol.py` | Copied from Sage 2.3.0 repo | Docstring only |
| `label-with-forcefield.py` | Copied from Sage 2.3.0 repo | Docstring only |
| `prepare-rosemary-rc1-inputs.py` | Copied from the Sage 2.3.0 repo's working tree (written for the rc1 comparison; never committed there) | Reads `../data/results` instead of the source repository's collated tables (identical rows); takes any number of force fields (`-f`, default the original two, whose output is byte-identical) |
| `run-rosemary-rc1-breakdown.sh` | Copied from the Sage 2.3.0 repo's working tree (original runner; never committed there) | Variables renamed; `nagl` and `paired` steps removed. Kept as a record and uses the source repository's paths; run `run-breakdown.sh` instead |
| `run-breakdown.sh` | New | Self-contained version of the runner above, for four force fields, plus the `combined` step |
| `plot-group-combined.py` | New | Per-group combined plots (density \| ΔH<sub>mix</sub>, RMSE and MSE, four force fields) |
| `forcefield_styles.py` | New | Shared force-field labels, order, colours, and markers |
| `prepare-headline-inputs.py`, `plot-headline.py`, `run-headline.sh` | New | Headline step for all four force fields; the plot layout follows `07_plot-for-preprint/physprop` in the Sage 2.3.0 repo |

## Headline: all four force fields

Run with `pixi run headline` (`run-headline.sh`):

1. `prepare-headline-inputs.py` writes `output/headline/<property>-<tier>/data.csv` from
   `../data/results/<tier>/summary/`. It checks that all four force fields have identical
   property sets and reference values.
2. `compute-statistics.py --seed 2026` computes RMSE, MUE, MSE, R² and ρ with 95% bootstrap
   CIs (1000 draws) for the "All" group. Output: `output/headline/<property>-<tier>/stats/<force field>.csv`.
3. `plot-headline.py` writes the figures and `output/headline/headline-stats.csv`:
   - `images/headline/combined-<tier>.png`: RMSE and MSE, density and ΔH<sub>mix</sub> side by side;
   - `images/headline/<property>-<tier>-stats.png`: all five statistics;
   - `images/headline/scatter-<tier>.png`: calculated vs experiment for each force field.

`<property>` is `density` or `dhmix`. `<tier>` is `training`, `validation` or `all`.

## Breakdown by chemistry

Run with `pixi run breakdown [step]` (`run-breakdown.sh`). With no step, all steps run in order.
Labelled data and per-group statistics cover all four force fields. The `plots` step compares
Rosemary rc1 + OPC3 with Sage 2.3.0 + TIP3P, and the `combined` step shows all four.

| Step | Script | Output |
|---|---|---|
| `inputs` | `prepare-rosemary-rc1-inputs.py` | `input/rosemary-rc1/<tier>/{summary,all}-<type>.csv`: the four force fields on identical property sets, with consistency checks |
| `map` | `map-labels-to-data.py` | `output/phys-prop-rosemary/<dataset>/labelled-data.csv`: checkmol functional groups and Sage 2.3.0 parameter IDs for each property, from `labels/` |
| `stats` | `compute-statistics.py` | `output/phys-prop-rosemary/<dataset>/stats/<force field>.csv` (e.g. `Sage-2.3.0-+-TIP3P.csv`): per-group RMSE, MUE, MSE, R² and ρ with bootstrap CIs (1000 draws, seeded with `STATS_SEED`, default 2026) |
| `plots` | `plot-aggregated-statistics.py`, `plot-change-in-target.py` | `images/compare-rosemary/<dataset>/stats-<group>.png` (one per group); `images/compare-rosemary/<dataset>-changes/` and `output/phys-prop-rosemary/<dataset>/Rosemary rc1 + OPC3-vs-Sage 2.3.0 + TIP3P.{png,csv}` (change from Sage to rc1 for each property) |
| `combined` | `plot-group-combined.py` | `images/compare-rosemary/combined-{all,validation}/<group>.png`: one figure per group, density (left) and ΔH<sub>mix</sub> (right), RMSE and MSE with CIs for all four force fields. A property with no statistics for a group (fewer than 3 properties) is shown as an empty panel. `index.csv` maps groups to files, and `plotted-values.csv` holds every plotted number |

`<dataset>` is `density-all` or `dhmix-all` (training + validation), or `density-validation` or
`dhmix-validation`. The change plots are made for the `-all` datasets only.


## Other files

- `labels/`: precomputed checkmol (`labels/checkmol/`) and Sage 2.3.0 parameter
  (`labels/forcefields/v3-k100/`) labels for the phys-prop molecules, copied from the Sage 2.3.0
  repo. `label-with-checkmol.py` and `label-with-forcefield.py` produced them. Both need `yammbs`,
  and the first also needs `checkmol`
