#!/usr/bin/env bash
# Headline statistics and figures for Sage 2.2.1 + TIP3P, Sage 2.3.0 + TIP3P, Rosemary alpha + OPC3
# and Rosemary rc1 + OPC3 (labels and order: forcefield_styles.py).
# Run from analysis/:  pixi run headline
#   1. prepare-headline-inputs.py  -> output/headline/<property>-<tier>/data.csv
#   2. compute-statistics.py       -> output/headline/<property>-<tier>/stats/<force field>.csv
#      ("All" group; 1000 bootstraps, seeded with STATS_SEED, default 2026)
#   3. plot-headline.py            -> images/headline/*.png, output/headline/headline-stats.csv
#
# Directories can be redirected through the environment:
#   OUTPUT_DIR (default output/headline)  IMAGE_DIR (default images/headline)  LOG_DIR (default logs/headline)
set -eo pipefail

OUTPUT_DIR="${OUTPUT_DIR:-output/headline}"
IMAGE_DIR="${IMAGE_DIR:-images/headline}"
LOG_DIR="${LOG_DIR:-logs/headline}"
STATS_SEED="${STATS_SEED:-2026}"
FORCEFIELDS=('Sage 2.2.1 + TIP3P' 'Sage 2.3.0 + TIP3P' 'Rosemary alpha + OPC3' 'Rosemary rc1 + OPC3')
mkdir -p "$LOG_DIR"

python prepare-headline-inputs.py -b ../data/results -o "$OUTPUT_DIR" > "$LOG_DIR/prepare.log"

# compute-statistics.py prints every bootstrap draw ("j x y"); drop those lines from the logs.
# The property x tier x force-field combinations run in parallel.
pids=()
for property in density dhmix; do
    for tier in training validation all; do
        dataset_dir="$OUTPUT_DIR/$property-$tier"
        mkdir -p "$dataset_dir/stats"
        for forcefield in "${FORCEFIELDS[@]}"; do
            forcefield_file=$(echo "$forcefield" | tr ' ' '-')
            ( python compute-statistics.py -cy value -cx reference_value -cye uncertainty -cxe reference_uncertainty \
                -ff "$forcefield" -i "$dataset_dir/data.csv" -o "$dataset_dir/stats/$forcefield_file.csv" \
                --seed "$STATS_SEED" 2>&1 \
                | grep -avE '^-?[0-9]+ -?[0-9.eE+-]+ -?[0-9.eE+-]+$' \
                > "$LOG_DIR/stats-$property-$tier-$forcefield_file.log" ) &
            pids+=($!)
        done
    done
done
failed=0
for pid in "${pids[@]}"; do wait "$pid" || failed=1; done
[ "$failed" = 0 ] || { echo "compute-statistics failed; see $LOG_DIR" >&2; exit 1; }

python plot-headline.py -o "$OUTPUT_DIR" -im "$IMAGE_DIR" | tee "$LOG_DIR/plot.log"
