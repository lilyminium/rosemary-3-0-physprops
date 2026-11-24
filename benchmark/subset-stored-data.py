"""
Copy only the pre-equilibrated boxes needed to benchmark the training and validation sets
out of an OpenFF Evaluator LocalFileStorage directory.

Box selection uses Evaluator's own code path, as the PreequilibratedSimulationLayer does at
run time (openff/evaluator/layers/equilibration.py,
EquilibrationLayer._update_metadata_with_template_queries): for each property and each
storage query in its calculation schema (request-options.json), the query is filled with
EquilibrationLayer._update_query and applied with storage.query(); from each result list the
object with the lowest statistical inefficiency is the one used ("full_system_data"), and for
"component_data" the lowest-inefficiency object per component.

By default only those selected boxes are copied (--all-matches copies every matching box).
Object JSON + ancillary directory are copied, never moved, plus the ForceFieldData object
each box references if present. Run under every Evaluator version used for the benchmarks
and merge (selection can depend on the Evaluator version).

Writes <output-dir>/ (a LocalFileStorage root) and <output-dir>-manifest.csv.
Exits non-zero if any property has no box for a query.

Written for this repository (not part of the Sage 2.3.0 repo).
"""

import csv
import pathlib
import shutil
import sys

import click
import openff.evaluator
from openff.evaluator.client import RequestOptions
from openff.evaluator.datasets import PhysicalPropertyDataSet
from openff.evaluator.layers.equilibration import EquilibrationLayer
from openff.evaluator.storage.localfile import LocalFileStorage


def select(storage, prop, schema, all_matches: bool):
    """Return {query_key: [(storage_key, data_object, data_dir), ...]} as used at run time."""
    selected = {}
    for key, template in schema.storage_queries.items():
        query = EquilibrationLayer._update_query(template, prop, schema)
        results = storage.query(query)
        flat = [r for lst in results.values() for r in lst]
        if all_matches or not flat:
            selected[key] = flat
        elif key == "component_data":
            best = {}
            for r in flat:
                comp = r[1].substance.components[0]
                if (
                    comp not in best
                    or r[1].statistical_inefficiency
                    < best[comp][1].statistical_inefficiency
                ):
                    best[comp] = r
            selected[key] = [best[c] for c in prop.substance.components if c in best]
            if len(selected[key]) != len(prop.substance.components):
                selected[key] = []
        else:
            assert len(results) == 1, results
            selected[key] = [min(flat, key=lambda x: x[1].statistical_inefficiency)]
    return selected


@click.command(help=__doc__)
@click.option("--storage", "-s", default="stored_data", show_default=True)
@click.option(
    "--dataset",
    "-d",
    multiple=True,
    required=True,
    help="Evaluator dataset JSON (repeatable)",
)
@click.option("--options", "-of", default="request-options.json", show_default=True)
@click.option("--output-dir", "-o", default="stored_data_subset", show_default=True)
@click.option("--all-matches", is_flag=True, default=False)
def main(storage, dataset, options, output_dir, all_matches):
    print(f"openff-evaluator {openff.evaluator.__version__}")
    output_dir = pathlib.Path(output_dir)
    if output_dir.exists():
        sys.exit(f"{output_dir} exists; refusing to overwrite")
    storage_root = pathlib.Path(storage).resolve()
    store = LocalFileStorage(
        root_directory=str(storage_root), cache_objects_in_memory=True
    )
    print(f"loaded {len(store._cached_retrieved_objects)} objects from {storage_root}")
    request_options = RequestOptions.from_json(options)
    layer = request_options.calculation_layers[0]
    assert layer == "PreequilibratedSimulationLayer", layer

    rows, missing = [], []
    for ds in dataset:
        props = PhysicalPropertyDataSet.from_json(ds).properties
        print(f"{ds}: {len(props)} properties")
        for index, prop in enumerate(props):
            schema = request_options.calculation_schemas[type(prop).__name__][layer]
            for key, objs in select(store, prop, schema, all_matches).items():
                if not objs:
                    missing.append((ds, index, prop.id, key))
                for storage_key, obj, data_dir in objs:
                    rows.append(
                        {
                            "dataset": pathlib.Path(ds).name,
                            "index": index,
                            "id": prop.id,
                            "query": key,
                            "storage_key": storage_key,
                            "substance": obj.substance.identifier,
                            "force_field_id": obj.force_field_id,
                            "statistical_inefficiency": obj.statistical_inefficiency,
                            "data_dir": pathlib.Path(data_dir).name,
                        }
                    )
    for m in missing:
        print("MISSING", m)
    print(f"properties x queries without a box: {len(missing)}")

    output_dir.mkdir(parents=True)
    keys = sorted({r["storage_key"] for r in rows})
    n_bytes = 0
    ff_ids = set()
    for r in rows:
        ff_ids.add(r["force_field_id"])
    for k in keys:
        src_json = storage_root / f"{k}.json"
        shutil.copy2(src_json, output_dir / src_json.name)
        n_bytes += src_json.stat().st_size
        src_dir = storage_root / k
        if src_dir.is_dir():
            shutil.copytree(src_dir, output_dir / k)
            n_bytes += sum(f.stat().st_size for f in src_dir.rglob("*") if f.is_file())
    n_ff = 0
    for ff_id in sorted(i for i in ff_ids if i):
        src = storage_root / f"{ff_id}.json"
        if src.exists():
            shutil.copy2(src, output_dir / src.name)
            n_bytes += src.stat().st_size
            n_ff += 1
    with open(f"{output_dir}-manifest.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"referenced ForceFieldData ids: {len(ff_ids)}, copied: {n_ff}")
    print(f"copied {len(keys)} boxes, {n_bytes / 1e6:.1f} MB, to {output_dir}")
    if missing:
        sys.exit(1)


if __name__ == "__main__":
    main()
