#!/usr/bin/env bash
# ORIGINAL runner of the 2026-11-19 analysis in ash-sage-rc2/05_analysis, kept for provenance.
# Use run-breakdown.sh in this repository instead.
# Edited in this archive: variables renamed for readability, and the `nagl` and `paired` steps
# removed (check-nagl-charges.py and paired-group-differences.py are not included). The original
# file is in ash-sage-rc2. Paths and labels are as originally
# run: it reads ../04_benchmark (via prepare-rosemary-rc1-inputs.py defaults at the time) and
# labels the force fields 'Sage 2.3.0' / 'Rosemary rc1'; the stats step was unseeded.
#
# Chemistry-specific breakdown of the OpenFF 3.0.0-rc1 ("Rosemary rc1") phys-prop benchmark
# vs Sage 2.3.0 (= fb-fit-v3-single-mean-k100: vdW + valence identical to released openff-2.3.0.offxml).
# Run from 05_analysis/ with an env that has openff-toolkit, rdkit, pyarrow, sklearn, seaborn, loguru
# (used: miniforge env smee-stack-dev).
#   bash run-rosemary-rc1-breakdown.sh [all|inputs|map|stats|plots]
set -eo pipefail

STEP="${1:-all}"
INPUT_DIR=input/rosemary-rc1
OUTPUT_DIR=output/phys-prop-rosemary
IMAGE_DIR=images/compare-rosemary
LOG_DIR=logs/rosemary
mkdir -p "$LOG_DIR"
DATASETS=(density-all dhmix-all density-validation dhmix-validation)
FORCEFIELDS=('Sage 2.3.0' 'Rosemary rc1')

run_step() { [ "$STEP" = all ] || [ "$STEP" = "$1" ]; }

# 1. two-FF inputs (summary + replicate level), with consistency checks
if run_step inputs; then
    python prepare-rosemary-rc1-inputs.py > "$LOG_DIR/prepare-inputs.log"
fi

# 2. map checkmol + v3-k100 parameter labels
if run_step map; then
    MAP_ARGS=(-nf 'Sage 2.3.0' 'fb-fit-v3-single-mean-k100' -nf 'Rosemary rc1' 'openff-3.0.0-rc1'
        -s smiles_1 -s smiles_2 -cm forcefield -cff FF)
    python map-labels-to-data.py "${MAP_ARGS[@]}" \
        -i "$INPUT_DIR/training/summary-Density.csv" -i "$INPUT_DIR/validation/summary-Density.csv" \
        -o "$OUTPUT_DIR/density-all/labelled-data.csv" > "$LOG_DIR/map-density-all.log"
    python map-labels-to-data.py "${MAP_ARGS[@]}" \
        -i "$INPUT_DIR/training/summary-EnthalpyOfMixing.csv" -i "$INPUT_DIR/validation/summary-EnthalpyOfMixing.csv" \
        -o "$OUTPUT_DIR/dhmix-all/labelled-data.csv" > "$LOG_DIR/map-dhmix-all.log"
    python map-labels-to-data.py "${MAP_ARGS[@]}" \
        -i "$INPUT_DIR/validation/summary-Density.csv" \
        -o "$OUTPUT_DIR/density-validation/labelled-data.csv" > "$LOG_DIR/map-density-validation.log"
    python map-labels-to-data.py "${MAP_ARGS[@]}" \
        -i "$INPUT_DIR/validation/summary-EnthalpyOfMixing.csv" \
        -o "$OUTPUT_DIR/dhmix-validation/labelled-data.csv" > "$LOG_DIR/map-dhmix-validation.log"
fi

# 3. per-group bootstrapped stats (existing script; unseeded, 1000 bootstraps)
if run_step stats; then
    # compute-statistics.py prints every bootstrap draw ("j x y"); drop those lines from the logs.
    # The 8 dataset x FF combinations run in parallel.
    pids=()
    for dataset in "${DATASETS[@]}"; do
        for forcefield in "${FORCEFIELDS[@]}"; do
            forcefield_file=$(echo "$forcefield" | tr ' ' '-')
            ( python compute-statistics.py -cy value -cx reference_value -cye uncertainty -cxe reference_uncertainty \
                -ff "$forcefield" -i "$OUTPUT_DIR/$dataset/labelled-data.csv" \
                -o "$OUTPUT_DIR/$dataset/stats/$forcefield_file.csv" 2>&1 \
                | grep -avE '^-?[0-9]+ -?[0-9.eE+-]+ -?[0-9.eE+-]+$' > "$LOG_DIR/stats-$dataset-$forcefield_file.log" ) &
            pids+=($!)
        done
    done
    failed=0
    for pid in "${pids[@]}"; do wait "$pid" || failed=1; done
    for dataset in "${DATASETS[@]}"; do
        for forcefield in "${FORCEFIELDS[@]}"; do
            stats_file="$OUTPUT_DIR/$dataset/stats/$(echo "$forcefield" | tr ' ' '-').csv"
            [ -s "$stats_file" ] || { echo "missing $stats_file" >&2; failed=1; }
        done
    done
    [ "$failed" = 0 ]
fi

# 4./5. aggregated per-group plots and per-property change plots
if run_step plots; then
    for dataset in "${DATASETS[@]}"; do
        case $dataset in density*) unit_label='[g/mL]' ;; *) unit_label='[kJ/mol]' ;; esac
        python plot-aggregated-statistics.py \
            -i "$OUTPUT_DIR/$dataset/stats/Sage-2.3.0.csv" -i "$OUTPUT_DIR/$dataset/stats/Rosemary-rc1.csv" \
            -ff 'Sage 2.3.0' -ff 'Rosemary rc1' -im "$IMAGE_DIR/$dataset" -u "$unit_label" \
            > "$LOG_DIR/plot-aggregated-$dataset.log"
    done
    for dataset in density-all dhmix-all; do
        case $dataset in
            density*) property_name='Density'; property_unit='g/mL' ;;
            *)        property_name='∆Hmix';   property_unit='kJ/mol' ;;
        esac
        python plot-change-in-target.py -i "$OUTPUT_DIR/$dataset/labelled-data.csv" \
            -o "$OUTPUT_DIR/$dataset/Rosemary rc1-vs-Sage 2.3.0.csv" \
            -im "$IMAGE_DIR/$dataset-changes/Rosemary rc1-vs-Sage 2.3.0.png" \
            -ref 'Sage 2.3.0' -tgt 'Rosemary rc1' -cff FF -cv value -cs smiles_1 -cs smiles_2 \
            -pn "$property_name" -pu "$property_unit" > "$LOG_DIR/plot-change-$dataset.log"
    done
fi
