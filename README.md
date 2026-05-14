# Step3.1 - Multi-method Segmentation Comparator

Standalone segmentation QC comparator with a Step3-style preview, ROI, overlay,
and 2x2 comparison workflow. This module is kept outside `block01` so it can
evolve without changing the stable main pipeline.

Run:

```bash
cd /sda1/Fusion/analysis_pipline/step3.1
python main.py
```

Features:

- Load a ROI-based project through `project/roi_index.json`
- Select one ROI
- Select up to four segmentation runs from:
  - `rois/<roi_id>/step2/segmentation_results/*`
  - `rois/<roi_id>/step2/segmentation_runs/*`
- Show a 2x2 comparison grid
- Render DAPI background, Fusion fallback/overlay when available, marker overlays, mask fill, and mask outline
- Draw a rectangular ROI in the preview viewer and zoom the comparison grid into that region
- Marker channels support visibility, color, and alpha controls
- Outline width supports thin display values: 0.25, 0.5, 1, 1.5, 2, and 3 px
- Sync zoom/pan across viewers
- Reset current viewer or all viewers
