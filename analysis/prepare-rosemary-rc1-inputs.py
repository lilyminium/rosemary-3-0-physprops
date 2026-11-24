"""
Build multi-force-field inputs for the chemistry breakdown (by default Sage 2.3.0 and OpenFF
3.0.0-rc1 "Rosemary rc1"; more with repeated --forcefield), from the per-force-field gathered
phys-prop results in data/results. Force fields are written in the order given, so adding force
fields after the default two leaves the rows of the first two unchanged.
(Originally read Sage 2.3.0 from the collated output/<tier>/*-benchmarks.csv; data/results
holds the identical rows.)

Writes, per tier and property type:
    <output-dir>/<tier>/summary-<Type>.csv   (one row per property per FF; replicate mean + SD)
    <output-dir>/<tier>/all-<Type>.csv       (one row per replicate per property per FF)

Fails if the force fields do not all have exactly one complete, identical set of properties
(same ids, SMILES, types, reference values) and 3 replicates each.

Copied from the Sage 2.3.0 repo's working tree (written there for the rc1 comparison);
generalised here from two to any number of force fields.
"""

import pathlib
import sys

import click
import numpy as np
import pandas as pd
from loguru import logger

logger.remove()
logger.add(sys.stdout)

SAGE = "fb-fit-v3-single-mean-k100"
RC1 = "openff-3.0.0-rc1"
KEY_COLS = ["id", "index", "type", "smiles_1", "smiles_2", "reference_value"]


def _check_pair(df: pd.DataFrame, level: str, ff_a: str, ff_b: str):
    a = df[df.forcefield == ff_a].set_index("id").sort_index()
    b = df[df.forcefield == ff_b].set_index("id").sort_index()
    if level == "summary":
        assert a.index.is_unique and b.index.is_unique, "duplicate ids"
    else:
        a = a.groupby(level=0).first()
        b = b.groupby(level=0).first()
    assert a.index.equals(b.index), "property ids differ between force fields"
    for col in ["index", "type", "smiles_1", "smiles_2"]:
        assert (
            a[col].fillna("").astype(str).equals(b[col].fillna("").astype(str))
        ), f"{col} differs"
    assert np.allclose(
        a["reference_value"], b["reference_value"]
    ), "reference values differ"


@click.command(help=__doc__)
@click.option(
    "--results-dir", "-b", default="../data/results", show_default=True
)
@click.option("--output-dir", "-o", default="input/rosemary-rc1", show_default=True)
@click.option(
    "--forcefield",
    "-f",
    "forcefields",
    multiple=True,
    default=(SAGE, RC1),
    show_default=True,
    help="data/results file name of a force field (repeatable; order is kept)",
)
def main(results_dir: str, output_dir: str, forcefields: tuple[str, ...]):
    results_dir = pathlib.Path(results_dir)
    output_dir = pathlib.Path(output_dir)
    for tier in ["training", "validation"]:

        summary_cols = [
            "id",
            "forcefield",
            "value",
            "uncertainty",
            "reference_value",
            "reference_uncertainty",
            "n_replicates",
            "index",
            "type",
            "substance",
            "smiles_1",
            "smiles_2",
        ]
        all_cols = [
            "id",
            "index",
            "type",
            "substance",
            "smiles_1",
            "smiles_2",
            "forcefield",
            "replicate",
            "value",
            "uncertainty",
            "reference_value",
            "reference_uncertainty",
        ]

        # per-force-field gathered results (data/results/<tier>/{summary,all}/<ff>.csv)
        summary = pd.concat(
            [
                pd.read_csv(results_dir / tier / "summary" / f"{ff}.csv")[summary_cols]
                for ff in forcefields
            ],
            ignore_index=True,
        )
        allrep = pd.concat(
            [
                pd.read_csv(results_dir / tier / "all" / f"{ff}.csv")[all_cols]
                for ff in forcefields
            ],
            ignore_index=True,
        )
        for ff in forcefields[1:]:
            _check_pair(summary, "summary", forcefields[0], ff)
            _check_pair(allrep, "all", forcefields[0], ff)
        reps = allrep.groupby(["forcefield", "id"]).size()
        assert (
            reps == 3
        ).all(), (
            f"expected 3 replicates per property, got {reps.value_counts().to_dict()}"
        )
        # summary must equal replicate mean
        m = allrep.groupby(["forcefield", "id"])["value"].mean()
        s = summary.set_index(["forcefield", "id"])["value"]
        assert np.allclose(s.loc[m.index], m), "summary value != replicate mean"

        for ptype in ["Density", "EnthalpyOfMixing"]:
            out = output_dir / tier
            out.mkdir(parents=True, exist_ok=True)
            s_ = summary[summary.type == ptype]
            a_ = allrep[allrep.type == ptype]
            s_.to_csv(out / f"summary-{ptype}.csv", index=False)
            a_.to_csv(out / f"all-{ptype}.csv", index=False)
            logger.info(
                f"{tier} {ptype}: {s_.id.nunique()} properties, "
                f"{len(s_)} summary rows, {len(a_)} replicate rows -> {out}"
            )


if __name__ == "__main__":
    main()
