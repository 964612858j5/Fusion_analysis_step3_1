"""Default constants for the Step3.1 comparator."""

MAX_VIEWERS = 4
MAX_OVERVIEW_SIDE = 2400

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
