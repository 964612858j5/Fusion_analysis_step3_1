"""Default constants for the Step3.1 comparator."""

MAX_VIEWERS = 4
MAX_OVERVIEW_SIDE = 2400

OUTLINE_WIDTH_OPTIONS = [0.25, 0.5, 1.0, 1.5, 2.0, 3.0]
DEFAULT_OUTLINE_WIDTH_INDEX = 1
DEFAULT_MASK_ALPHA = 0.0

DEFAULT_CHANNEL_COLORS = [
    "#3366ff",
    "#ff4040",
    "#40ff80",
    "#ffd040",
    "#ff40ff",
    "#40d0ff",
]

VIEWER_COLORS = {
    "A": "#ff3333",
    "B": "#33dd66",
    "C": "#ffee33",
    "D": "#33ddff",
}

METHOD_DISPLAY_NAMES = {
    "cellpose_wholecell_fusion": "Cellpose whole-cell",
    "cellpose_nuclei_dapi": "Cellpose nuclei",
    "cellpose_nuclei_expansion": "Cellpose nuclei + expansion",
    "stardist_nuclei_dapi": "StarDist nuclei",
    "stardist_nuclei_expansion": "StarDist nuclei + expansion",
    "legacy_cellpose_wholecell_fusion": "Legacy Cellpose whole-cell",
}
