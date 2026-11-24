"""
Check the per-property benchmark JSONs in a tier directory: list results that failed (to
remove) and, per force field and replicate, the property indices still to (re)submit.
Only reads `rep*/openff-3.0.0-rc1/*.json`.

Copied unchanged from the Sage 2.3.0 repo's working tree on Iris (openforcefield/ash-sage-rc2, 04_benchmark/phys-prop/check-properties-to-run-rc1.py), where it was added
for the OpenFF 3.0.0-rc1 (Rosemary rc1) rerun and never committed; only this note was added.
"""

from collections import defaultdict
import pathlib

import click
import tqdm

from openff.evaluator.datasets.datasets import PhysicalPropertyDataSet
from openff.evaluator.server.server import RequestResult


@click.command()
@click.option(
    "--input-dataset",
    "-i",
    type=click.Path(exists=True, dir_okay=False, file_okay=True),
    default="dataset.json",
    help="Path to the input dataset file.",
)
@click.option(
    "--input-directory",
    "-d",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    default="training",
    help="Directory containing the input JSON files.",
)
@click.option(
    "--output-directory",
    "-o",
    type=click.Path(file_okay=False, dir_okay=True),
    default="output",
    help="Directory to write the output CSV file to.",
)
def main(
    input_dataset: str = "dataset.json",
    input_directory: str = "training",
    output_directory: str = "output",
):
    
    all_json_files = pathlib.Path(input_directory).glob("rep*/openff-3.0.0-rc1/*.json")

    reference_dataset = PhysicalPropertyDataSet.from_json(input_dataset)
    json_files_to_remove = []
    
    forcefields_and_replicates = defaultdict(lambda: defaultdict(set))

    for json_file in tqdm.tqdm(sorted(all_json_files)):
        index = int(json_file.stem.split("-")[-1])
        request_result = RequestResult.from_json(json_file)
        ff_name = json_file.parent.name
        replicate = int(json_file.parent.parent.stem.split("-")[-1])
        try:
            assert len(request_result.estimated_properties.properties) == 1
            forcefields_and_replicates[ff_name][replicate].add((index))
        except:
            print(print(f"Skipping {json_file} -- {request_result.exceptions[0].message}"))
            json_files_to_remove.append(json_file.resolve())
            

    # print json files to remove
    print(f"Need to remove {len(json_files_to_remove)} files")
    print(f"rm {' '.join([str(f) for f in json_files_to_remove])}")

    # print force fields and replicates to re-submit
    original_indices = set(range(len(reference_dataset.properties)))
    for ff_name, replicates in forcefields_and_replicates.items():
        for replicate, indices in replicates.items():
            remaining_indices = original_indices - indices
            indices_str = ','.join(list(map(str, remaining_indices)))
            print(f"Re-submit {len(remaining_indices)} jobs for {ff_name} replicate {replicate}: {indices_str}")


if __name__ == "__main__":
    main()
