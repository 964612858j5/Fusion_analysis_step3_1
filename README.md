# Step3.1 - Multi-method Segmentation Comparator

Standalone experimental comparator for segmentation QC. This module is kept
outside `block01` so it can evolve without changing the stable main pipeline.

Run:

```bash
cd /sda1/Fusion/analysis_pipline/step3.1
python main.py
```

MVP features:

- Load a ROI-based project through `project/roi_index.json`
- Select one ROI
- Select up to four segmentation runs from:
  - `rois/<roi_id>/step2/segmentation_results/*`
  - `rois/<roi_id>/step2/segmentation_runs/*`
- Show a 2x2 comparison grid
- Render DAPI background and mask outline
- Sync zoom/pan across viewers
- Reset current viewer or all viewers

Not implemented in this MVP:

- Fusion and marker overlays
- Mask fill alpha
- Editing or annotation
- IoU/cell matching/statistics
