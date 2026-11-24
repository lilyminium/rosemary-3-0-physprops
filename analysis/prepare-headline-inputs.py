"""
Build the inputs for the three-force-field headline statistics from the replicate-mean
summaries in data/results/<tier>/summary/<ff>.csv.

Writes <output-dir>/<prop>-<tier>/data.csv for prop in {density, dhmix} and tier in
{training, validation, all}, with columns
    id, index, tier, type, smiles_1, smiles_2, value, uncertainty,
    reference_value, reference_uncertainty, FF
(FF last, so compute-statistics.py computes only the "All" group).

Fails unless every force field has exactly the same properties and reference values.
"""

import pathlib

import click
import numpy as np
import pandas as pd

from forcefield_styles import FORCEFIELDS as FFS  # data-file name -> plot label
TYPES = {"density": "Density", "dhmix": "EnthalpyOfMixing"}
COLS = [
    "id",
    "index",
    "tier",
    "type",
    "smiles_1",
    "smiles_2",
    "value",
    "uncertainty",
    "reference_value",
    "reference_uncertainty",
    "FF",
]


@click.command(help=__doc__)
@click.option("--results-dir", "-b", default="../data/results", show_default=True)
@click.option("--output-dir", "-o", default="output/headline", show_default=True)
def main(results_dir, output_dir):
    results_dir, output_dir = pathlib.Path(results_dir), pathlib.Path(output_dir)
    frames = []
    for tier in ["training", "validation"]:
        for ff, label in FFS.items():
            df = pd.read_csv(results_dir / tier / "summary" / f"{ff}.csv", index_col=0)
            df["tier"] = tier
            df["FF"] = label
            frames.append(df)
    data = pd.concat(frames, ignore_index=True)

    # identical property sets and reference values across force fields
    ref = None
    for label, sub in data.groupby("FF"):
        s = sub.set_index(["tier", "id"]).sort_index()[["type", "reference_value"]]
        if ref is None:
            ref = s
        else:
            assert s.index.equals(ref.index), f"{label}: property set differs"
            assert s["type"].equals(ref["type"]), f"{label}: types differ"
            assert np.array_equal(
                s.reference_value.values, ref.reference_value.values
            ), f"{label}: reference values differ"

    for prop, ptype in TYPES.items():
        for tier in ["training", "validation", "all"]:
            sub = data[data["type"] == ptype]
            if tier != "all":
                sub = sub[sub.tier == tier]
            out = output_dir / f"{prop}-{tier}"
            out.mkdir(parents=True, exist_ok=True)
            sub[COLS].to_csv(out / "data.csv", index=False)
            n = sub.groupby("FF").size()
            print(f"{prop}-{tier}: {n.to_dict()} -> {out / 'data.csv'}")


if __name__ == "__main__":
    main()
