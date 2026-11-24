"""
Headline figures for the four force fields (Sage 2.2.1 + TIP3P, Sage 2.3.0 + TIP3P,
Rosemary alpha + OPC3, Rosemary rc1 + OPC3).

Reads output/headline/<prop>-<tier>/{data.csv, stats/<FF>.csv} (see run-headline.sh) and writes
  images/headline/<prop>-<tier>-stats.png     RMSE/MUE/MSE and rho/R2 with 95% bootstrap CIs
  images/headline/combined-<tier>.png         RMSE and MSE, density | dHmix side by side
  images/headline/scatter-<tier>.png          calc vs expt, one panel per force field and property
  output/headline/headline-stats.csv          the plotted numbers

The stats layout (dodged error bars, Error | Correlation panels) follows
07_plot-for-preprint/physprop/helpers.py in the source repository.
"""

import pathlib

import click
import matplotlib as mpl
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib import pyplot as plt

from forcefield_styles import COLORS, FF_ORDER, MARKERS, file_label

PANEL_MAP = {
    "RMSE": "Error",
    "MUE": "Error",
    "MSE": "Error",
    "rho": "Correlation",
    "R2": "Correlation",
}
PROPS = {
    "density": {"label": "Density", "unit": "g/mL"},
    "dhmix": {"label": "∆H$_{mix}$", "unit": "kJ/mol"},
}
TIERS = {
    "training": "training set",
    "validation": "validation set",
    "all": "training + validation",
}

sns.set_context("paper")
sns.set_style("ticks")
mpl.rcParams.update(
    {"axes.spines.top": False, "axes.spines.right": False, "savefig.dpi": 300}
)


def read_stats(base: pathlib.Path) -> pd.DataFrame:
    dfs = [
        pd.read_csv(base / "stats" / f"{file_label(ff)}.csv") for ff in FF_ORDER
    ]
    df = pd.concat(dfs, ignore_index=True)
    return df[df.group == "All"].copy()


def dodge(df, stats, spacing):
    x = {s: i for i, s in enumerate(stats)}
    off = {ff: (i - (len(FF_ORDER) - 1) / 2) * spacing for i, ff in enumerate(FF_ORDER)}
    df = df[df.stat.isin(stats)].copy()
    df["xpos"] = df.stat.map(x).astype(float) + df.FF.map(off)
    return df, x


def errorbars(ax, df):
    for ff in FF_ORDER:
        sub = df[df.FF == ff]
        yerr = np.vstack(
            [(sub.mle - sub.low).clip(lower=0), (sub.high - sub.mle).clip(lower=0)]
        )
        ax.errorbar(
            sub.xpos,
            sub.mle,
            yerr=yerr,
            fmt=MARKERS[ff],
            color=COLORS[ff],
            ms=6,
            capsize=3,
            lw=1.5,
            label=ff,
        )


def legend_below(fig, ax, ncol=2):
    handles, labels = ax.get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=ncol, frameon=False,
               fontsize=8, bbox_to_anchor=(0.5, 0.0))
    fig.tight_layout(rect=(0, 0.14, 1, 1))


def plot_stats(df, prop, tier, out):
    info = PROPS[prop]
    n = int(df.n.iloc[0])
    fig, axes = plt.subplots(
        1, 2, figsize=(6.4, 3.5), gridspec_kw={"width_ratios": [3, 2]}
    )
    for ax, panel in zip(axes, ["Error", "Correlation"]):
        stats = [s for s, p in PANEL_MAP.items() if p == panel]
        d, x = dodge(df, stats, 0.18)
        errorbars(ax, d)
        ax.set_xticks(list(x.values()), list(x))
        ax.set_xlim(-0.5, len(stats) - 0.5)
        if panel == "Error":
            ax.axhline(0, ls="--", color="0.6", lw=1, zorder=0)
            ax.set_ylabel(f"Error [{info['unit']}]")
        else:
            ax.set_ylabel("Correlation")
    fig.suptitle(f"{info['label']}, {TIERS[tier]} (n={n})")
    legend_below(fig, axes[0])
    fig.savefig(out)
    plt.close(fig)


def plot_combined(stats_by_prop, tier, out):
    fig, axes = plt.subplots(1, 2, figsize=(5.6, 3.4))
    for ax, (prop, df) in zip(axes, stats_by_prop.items()):
        d, x = dodge(df, ["RMSE", "MSE"], 0.2)
        errorbars(ax, d)
        ax.set_xticks(list(x.values()), list(x))
        ax.set_xlim(-0.5, 1.5)
        ax.axhline(0, ls="--", color="0.6", lw=1, zorder=0)
        ax.set_ylabel(f"Error [{PROPS[prop]['unit']}]")
        ax.set_title(f"{PROPS[prop]['label']} (n={int(df.n.iloc[0])})")
    fig.suptitle(TIERS[tier])
    legend_below(fig, axes[0])
    fig.savefig(out)
    plt.close(fig)


def plot_scatter(data_by_prop, stats_by_prop, tier, out):
    fig, axes = plt.subplots(2, len(FF_ORDER), figsize=(2.6 * len(FF_ORDER), 6.6))
    for row, (prop, data) in zip(axes, data_by_prop.items()):
        lo = min(data.reference_value.min(), data.value.min())
        hi = max(data.reference_value.max(), data.value.max())
        pad = 0.04 * (hi - lo)
        lims = (lo - pad, hi + pad)
        st = stats_by_prop[prop].set_index(["FF", "stat"]).mle
        for ax, ff in zip(row, FF_ORDER):
            sub = data[data.FF == ff]
            ax.plot(lims, lims, color="0.6", lw=1, ls="--", zorder=0)
            ax.errorbar(
                sub.reference_value,
                sub.value,
                yerr=sub.uncertainty,
                fmt=MARKERS[ff],
                color=COLORS[ff],
                ms=3,
                lw=0.6,
                alpha=0.6,
                mec="white",
                mew=0.3,
            )
            ax.set_xlim(lims)
            ax.set_ylim(lims)
            ax.set_aspect("equal")
            unit = PROPS[prop]["unit"]
            ax.set_title(ff, fontsize=9)
            ax.text(
                0.04,
                0.96,
                f"RMSE {st[(ff, 'RMSE')]:.3g}\nMSE {st[(ff, 'MSE')]:+.2g}\nR² {st[(ff, 'R2')]:.3f}",
                transform=ax.transAxes,
                va="top",
                fontsize=7,
                color="0.2",
            )
            ax.set_xlabel(f"expt {PROPS[prop]['label']} [{unit}]")
            if ff == FF_ORDER[0]:
                ax.set_ylabel(f"calc {PROPS[prop]['label']} [{unit}]")
    fig.suptitle(
        f"Calculated vs experiment, {TIERS[tier]} (error bars: SD over 3 replicates)"
    )
    fig.tight_layout(h_pad=2.0)
    fig.savefig(out)
    plt.close(fig)


@click.command(help=__doc__)
@click.option("--output-dir", "-o", default="output/headline", show_default=True)
@click.option("--image-dir", "-im", default="images/headline", show_default=True)
def main(output_dir, image_dir):
    output_dir, image_dir = pathlib.Path(output_dir), pathlib.Path(image_dir)
    image_dir.mkdir(parents=True, exist_ok=True)
    table = []
    for tier in TIERS:
        stats_by_prop, data_by_prop = {}, {}
        for prop in PROPS:
            base = output_dir / f"{prop}-{tier}"
            df = read_stats(base)
            stats_by_prop[prop] = df
            data_by_prop[prop] = pd.read_csv(base / "data.csv")
            plot_stats(df, prop, tier, image_dir / f"{prop}-{tier}-stats.png")
            table.append(df.assign(property=prop, tier=tier))
        plot_combined(stats_by_prop, tier, image_dir / f"combined-{tier}.png")
        plot_scatter(
            data_by_prop, stats_by_prop, tier, image_dir / f"scatter-{tier}.png"
        )
    t = pd.concat(table)[
        ["tier", "property", "FF", "stat", "n", "mle", "low", "high", "stderr"]
    ]
    t.to_csv(output_dir / "headline-stats.csv", index=False)
    with pd.option_context("display.width", 160):
        print(
            t[t.stat.isin(["RMSE", "MSE", "R2"])].to_string(
                index=False, float_format="{:.4g}".format
            )
        )
    print(f"wrote figures to {image_dir}")


if __name__ == "__main__":
    main()
