"""
Shared force-field registry for the plotting scripts in this directory: data-file names, plot
labels, order, colours and markers.

Written for this repository (not part of the Sage 2.3.0 repo).
"""

# data-file name (data/results/<tier>/*/<name>.csv) -> plot label, in plotting order
FORCEFIELDS = {
    "openff-2.2.1": "Sage 2.2.1 + TIP3P",
    "fb-fit-v3-single-mean-k100": "Sage 2.3.0 + TIP3P",
    "rosemary-alpha_opc3": "Rosemary alpha + OPC3",
    "openff-3.0.0-rc1": "Rosemary rc1 + OPC3",
}
FF_ORDER = list(FORCEFIELDS.values())

# Colour follows the force field (never its position): categorical slots of the dataviz
# reference palette. Sage 2.3.0 / alpha / rc1 keep slots 1-3; Sage 2.2.1 takes slot 4.
# Validated in plotting order (validate_palette.js, light mode): CVD dE >= 9.2, normal >= 27.6.
# Markers are a second, non-colour encoding.
COLORS = {
    "Sage 2.2.1 + TIP3P": "#eda100",
    "Sage 2.3.0 + TIP3P": "#2a78d6",
    "Rosemary alpha + OPC3": "#eb6834",
    "Rosemary rc1 + OPC3": "#1baf7a",
}
MARKERS = {
    "Sage 2.2.1 + TIP3P": "v",
    "Sage 2.3.0 + TIP3P": "o",
    "Rosemary alpha + OPC3": "s",
    "Rosemary rc1 + OPC3": "D",
}

def file_label(label: str) -> str:
    """File-name form of a plot label, as written by run-*.sh (spaces -> dashes)."""
    return label.replace(" ", "-")
