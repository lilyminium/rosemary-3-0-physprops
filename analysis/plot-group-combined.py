"""
Per-group combined plots for the chemistry breakdown: for every checkmol functional group and
Sage 2.3.0 parameter id, one figure with density (left) and dHmix (right), showing RMSE and MSE
with 95% bootstrap CIs for each force field (layout as images/headline/combined-<tier>.png).

Reads <stats-dir>/{density,dhmix}-<tier>/stats/<force field>.csv (run-breakdown.sh `stats` step)
and writes to <image-dir>:
  <group>.png           one figure per group
  index.csv             group -> file name, n (density), n (dHmix)
  plotted-values.csv    every plotted number (group, property, FF, stat, n, mle, low, high)

The group set is the union of groups over both properties and all force fields. A property with
no statistics for a group (compute-statistics.py skips groups with <= 2 properties) gets an
empty panel saying so.

Written for this repository (not part of the Sage 2.3.0 repo).
"""

import pathlib
import re

import click
import matplotlib as mpl
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib import pyplot as plt
from openff.toolkit import ForceField

from forcefield_styles import COLORS, FF_ORDER, MARKERS, file_label

PROPS = {
    "density": {"label": "Density", "unit": "g/mL"},
    "dhmix": {"label": "∆H$_{mix}$", "unit": "kJ/mol"},
}
STATS = ["RMSE", "MSE"]
TIER_LABELS = {"all": "training + validation", "validation": "validation set"}

sns.set_context("paper")
sns.set_style("ticks")
mpl.rcParams.update(
    {"axes.spines.top": False, "axes.spines.right": False, "savefig.dpi": 200}
)


def safe_filename(group: str) -> str:
    return re.sub(r"[^A-Za-z0-9._+-]+", "_", group).strip("_")


def parameter_smirks(offxml: str) -> dict:
    ff = ForceField(offxml)
    out = {}
    for handler in ["Bonds", "Angles", "ProperTorsions", "ImproperTorsions", "vdW"]:
        for p in ff.get_parameter_handler(handler).parameters:
            out[p.id] = p.smirks
    return out


def read_stats(stats_dir: pathlib.Path, prop: str, tier: str) -> pd.DataFrame:
    frames = []
    for ff in FF_ORDER:
        f = stats_dir / f"{prop}-{tier}" / "stats" / f"{file_label(ff)}.csv"
        df = pd.read_csv(f)
        assert (df.FF == ff).all(), f"{f}: FF column is not {ff!r}"
        frames.append(df[df.stat.isin(STATS)])
    return pd.concat(frames, ignore_index=True)


def draw_panel(ax, df, prop):
    x = {s: i for i, s in enumerate(STATS)}
    spacing = 0.18
    for i, ff in enumerate(FF_ORDER):
        sub = df[df.FF == ff].set_index("stat").loc[STATS]
        xpos = np.array([x[s] for s in STATS]) + (i - (len(FF_ORDER) - 1) / 2) * spacing
        yerr = np.vstack(
            [(sub.mle - sub.low).clip(lower=0), (sub.high - sub.mle).clip(lower=0)]
        )
        ax.errorbar(
            xpos,
            sub.mle,
            yerr=yerr,
            fmt=MARKERS[ff],
            color=COLORS[ff],
            ms=5,
            capsize=3,
            lw=1.3,
            label=ff,
        )
    ax.set_xticks(list(x.values()), STATS)
    ax.set_xlim(-0.5, len(STATS) - 0.5)
    ax.axhline(0, ls="--", color="0.6", lw=1, zorder=0)
    ax.set_ylabel(f"Error [{PROPS[prop]['unit']}]")


@click.command(help=__doc__)
@click.option(
    "--stats-dir", "-s", default="output/phys-prop-rosemary", show_default=True
)
@click.option("--tier", "-t", type=click.Choice(list(TIER_LABELS)), required=True)
@click.option("--image-dir", "-im", required=True)
@click.option(
    "--forcefield",
    "-ff",
    "offxml",
    default="../forcefields/fb-fit-v3-single-mean-k100.offxml",
    show_default=True,
    help="force field whose parameter ids label the groups (for SMIRKS in titles)",
)
def main(stats_dir, tier, image_dir, offxml):
    stats_dir, image_dir = pathlib.Path(stats_dir), pathlib.Path(image_dir)
    image_dir.mkdir(parents=True, exist_ok=True)
    smirks = parameter_smirks(offxml)
    stats = {prop: read_stats(stats_dir, prop, tier) for prop in PROPS}
    groups = sorted(
        set().union(*(set(df.group) for df in stats.values())),
        key=lambda g: (g != "All", g),
    )
    files = {g: safe_filename(g) + ".png" for g in groups}
    assert len(set(files.values())) == len(
        files
    ), "file-name collision after sanitising"

    index_rows, plotted = [], []
    for group in groups:
        fig, axes = plt.subplots(1, 2, figsize=(5.6, 3.6))
        n_by_prop = {}
        for ax, prop in zip(axes, PROPS):
            df = stats[prop][stats[prop].group == group]
            if df.empty:
                n_by_prop[prop] = 0
                ax.text(
                    0.5,
                    0.5,
                    "no statistics\n(n < 3 properties)",
                    ha="center",
                    va="center",
                    transform=ax.transAxes,
                    color="0.4",
                )
                ax.axis("off")
                ax.set_title(PROPS[prop]["label"])
                continue
            assert set(df.FF) == set(FF_ORDER), f"{group} {prop}: missing force fields"
            ns = df.n.unique()
            assert len(ns) == 1, f"{group} {prop}: n differs between force fields {ns}"
            n_by_prop[prop] = int(ns[0])
            draw_panel(ax, df, prop)
            ax.set_title(f"{PROPS[prop]['label']} (n={int(ns[0])})")
            plotted.append(
                df.assign(property=prop)[
                    ["group", "property", "FF", "stat", "n", "mle", "low", "high"]
                ]
            )
        title = group if group not in smirks else f"{group}: {smirks[group]}"
        fig.suptitle(f"{title}\n{TIER_LABELS[tier]}", fontsize=9)
        handles, labels = next(
            (
                ax.get_legend_handles_labels()
                for ax in axes
                if ax.get_legend_handles_labels()[0]
            ),
            ([], []),
        )
        fig.legend(
            handles,
            labels,
            loc="lower center",
            ncol=2,
            frameon=False,
            fontsize=7.5,
            bbox_to_anchor=(0.5, 0.0),
        )
        fig.tight_layout(rect=(0, 0.14, 1, 1))
        fig.savefig(image_dir / files[group])
        plt.close(fig)
        index_rows.append(
            {
                "group": group,
                "file": files[group],
                "n_density": n_by_prop["density"],
                "n_dhmix": n_by_prop["dhmix"],
            }
        )

    pd.DataFrame(index_rows).to_csv(image_dir / "index.csv", index=False)
    pd.concat(plotted, ignore_index=True).to_csv(
        image_dir / "plotted-values.csv", index=False
    )
    print(f"{len(groups)} groups -> {image_dir}")


if __name__ == "__main__":
    main()
