#!/usr/bin/env bash
# Chemistry-specific breakdown of the phys-prop benchmarks by checkmol functional group and
# Sage 2.3.0 parameter id. Per-group statistics are computed for all four force fields
# (Sage 2.2.1 + TIP3P, Sage 2.3.0 + TIP3P, Rosemary alpha + OPC3, Rosemary rc1 + OPC3); the
# per-group statistics plots and change plots compare Rosemary rc1 + OPC3 with Sage 2.3.0 + TIP3P
# (= fb-fit-v3-single-mean-k100: vdW + valence identical to released openff-2.3.0.offxml), and the
# `combined` step plots density | dHmix RMSE and MSE per group for all four.
#
# Self-contained version of run-rosemary-rc1-breakdown.sh (kept alongside for provenance).
# Run from analysis/ inside the pixi env:
#   pixi run breakdown [all|inputs|map|stats|plots|combined]
#
# Directories can be redirected through the environment:
#   INPUT_DIR  (default input/rosemary-rc1)          multi-force-field input tables
#   OUTPUT_DIR (default output/phys-prop-rosemary)   labelled data, statistics, change tables
#   IMAGE_DIR  (default images/compare-rosemary)     plots
#   LOG_DIR    (default logs/rosemary)               logs
# STATS_SEED: seeds compute-statistics.py (default 2026; set STATS_SEED= empty for unseeded).
set -eo pipefail

STEP="${1:-all}"
INPUT_DIR="${INPUT_DIR:-input/rosemary-rc1}"
OUTPUT_DIR="${OUTPUT_DIR:-output/phys-prop-rosemary}"
IMAGE_DIR="${IMAGE_DIR:-images/compare-rosemary}"
LOG_DIR="${LOG_DIR:-logs/rosemary}"
mkdir -p "$LOG_DIR"

DATASETS=(density-all dhmix-all density-validation dhmix-validation)
# data-file name and label of each force field; the first two keep their original order so their
# rows (and seeded statistics) are unchanged by adding the others
FORCEFIELD_FILES=(fb-fit-v3-single-mean-k100 openff-3.0.0-rc1 openff-2.2.1 rosemary-alpha_opc3)
FORCEFIELDS=('Sage 2.3.0 + TIP3P' 'Rosemary rc1 + OPC3' 'Sage 2.2.1 + TIP3P' 'Rosemary alpha + OPC3')
REFERENCE_FF="${FORCEFIELDS[0]}"
TARGET_FF="${FORCEFIELDS[1]}"
STATS_SEED="${STATS_SEED-2026}"
SEED_ARGS=()
[ -n "${STATS_SEED}" ] && SEED_ARGS=(--seed "${STATS_SEED}")

run_step() { [ "$STEP" = all ] || [ "$STEP" = "$1" ]; }
# file-name form of a force-field label: spaces -> dashes
filename_label() { echo "$1" | tr ' ' '-'; }

# 1. inputs for all force fields (summary + replicate level), with consistency checks
if run_step inputs; then
    INPUT_ARGS=()
    for forcefield_file in "${FORCEFIELD_FILES[@]}"; do INPUT_ARGS+=(-f "$forcefield_file"); done
    python prepare-rosemary-rc1-inputs.py -b ../data/results -o "$INPUT_DIR" "${INPUT_ARGS[@]}" \
        > "$LOG_DIR/prepare-inputs.log"
fi

# 2. map checkmol + v3-k100 parameter labels (precomputed in labels/)
if run_step map; then
    MAP_ARGS=()
    for i in "${!FORCEFIELDS[@]}"; do MAP_ARGS+=(-nf "${FORCEFIELDS[$i]}" "${FORCEFIELD_FILES[$i]}"); done
    MAP_ARGS+=(-s smiles_1 -s smiles_2 -cm forcefield -cff FF
        -ff ../forcefields/fb-fit-v3-single-mean-k100.offxml)
    for dataset in "${DATASETS[@]}"; do mkdir -p "$OUTPUT_DIR/$dataset"; done
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

# 3. per-group bootstrapped stats (1000 bootstraps; seeded with STATS_SEED)
if run_step stats; then
    # compute-statistics.py prints every bootstrap draw ("j x y"); drop those lines from the logs.
    # The dataset x force-field combinations run in parallel.
    pids=()
    for dataset in "${DATASETS[@]}"; do
        mkdir -p "$OUTPUT_DIR/$dataset/stats"
        for forcefield in "${FORCEFIELDS[@]}"; do
            forcefield_file=$(filename_label "$forcefield")
            ( python compute-statistics.py -cy value -cx reference_value -cye uncertainty -cxe reference_uncertainty \
                -ff "$forcefield" -i "$OUTPUT_DIR/$dataset/labelled-data.csv" \
                -o "$OUTPUT_DIR/$dataset/stats/$forcefield_file.csv" "${SEED_ARGS[@]}" 2>&1 \
                | grep -avE '^-?[0-9]+ -?[0-9.eE+-]+ -?[0-9.eE+-]+$' > "$LOG_DIR/stats-$dataset-$forcefield_file.log" ) &
            pids+=($!)
        done
    done
    failed=0
    for pid in "${pids[@]}"; do wait "$pid" || failed=1; done
    for dataset in "${DATASETS[@]}"; do
        for forcefield in "${FORCEFIELDS[@]}"; do
            stats_file="$OUTPUT_DIR/$dataset/stats/$(filename_label "$forcefield").csv"
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
            -i "$OUTPUT_DIR/$dataset/stats/$(filename_label "$REFERENCE_FF").csv" \
            -i "$OUTPUT_DIR/$dataset/stats/$(filename_label "$TARGET_FF").csv" \
            -ff "$REFERENCE_FF" -ff "$TARGET_FF" -im "$IMAGE_DIR/$dataset" -u "$unit_label" \
            > "$LOG_DIR/plot-aggregated-$dataset.log"
    done
    for dataset in density-all dhmix-all; do
        case $dataset in
            density*) property_name='Density'; property_unit='g/mL' ;;
            *)        property_name='∆Hmix';   property_unit='kJ/mol' ;;
        esac
        mkdir -p "$IMAGE_DIR/$dataset-changes"
        python plot-change-in-target.py -i "$OUTPUT_DIR/$dataset/labelled-data.csv" \
            -o "$OUTPUT_DIR/$dataset/$TARGET_FF-vs-$REFERENCE_FF.csv" \
            -im "$IMAGE_DIR/$dataset-changes/$TARGET_FF-vs-$REFERENCE_FF.png" \
            -ref "$REFERENCE_FF" -tgt "$TARGET_FF" -cff FF -cv value -cs smiles_1 -cs smiles_2 \
            -pn "$property_name" -pu "$property_unit" > "$LOG_DIR/plot-change-$dataset.log"
    done
fi

# 6. per-group combined plots: density (left) | dHmix (right), RMSE and MSE, all force fields
if run_step combined; then
    for tier in all validation; do
        python plot-group-combined.py -s "$OUTPUT_DIR" -t "$tier" -im "$IMAGE_DIR/combined-$tier" \
            > "$LOG_DIR/plot-combined-$tier.log"
    done
fi
