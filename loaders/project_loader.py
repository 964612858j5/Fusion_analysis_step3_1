"""Project, ROI, and segmentation-run discovery for Step3.1."""

import glob
import json
import os
from typing import Dict, List, Optional

from configs.defaults import METHOD_DISPLAY_NAMES
from configs.defaults import DEFAULT_CHANNEL_COLORS
from state.compare_state import ChannelRecord, RoiRecord, RunRecord


def load_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _abs(base: str, path: Optional[str]) -> Optional[str]:
    if not path:
        return None
    path = str(path)
    return path if os.path.isabs(path) else os.path.abspath(os.path.join(base, path))


def _method_display(method: str) -> str:
    return METHOD_DISPLAY_NAMES.get(method, method or "Unknown method")


class ProjectLoader:
    """Reads the ROI architecture without mutating the main project."""

    def __init__(self, project_dir: str):
        self.project_dir = os.path.abspath(project_dir)

    def rois(self) -> List[RoiRecord]:
        records: List[RoiRecord] = []
        index_path = os.path.join(self.project_dir, "roi_index.json")
        index = load_json(index_path, {}) or {}
        for item in index.get("rois") or []:
            manifest_path = _abs(self.project_dir, item.get("manifest"))
            if not manifest_path:
                roi_id = item.get("roi_id")
                manifest_path = os.path.join(self.project_dir, "rois", roi_id, "roi_manifest.json")
            manifest = load_json(manifest_path, {}) or {}
            roi_id = manifest.get("roi_id") or item.get("roi_id") or os.path.basename(os.path.dirname(manifest_path))
            roi_dir = os.path.dirname(manifest_path)
            records.append(
                RoiRecord(
                    roi_id=roi_id,
                    display_name=manifest.get("display_name") or item.get("display_name") or roi_id,
                    roi_dir=roi_dir,
                    manifest_path=manifest_path,
                    bbox_fullres=manifest.get("bbox_fullres"),
                    shape=manifest.get("shape"),
                    fusion_zarr=self._find_fusion_source(roi_dir, manifest),
                    corrected_zarr=self._find_corrected_source(roi_dir, manifest),
                    raw_ome=_abs(self.project_dir, manifest.get("raw_ome") or manifest.get("ome_tiff")),
                )
            )

        if records:
            return records

        for roi_dir in sorted(glob.glob(os.path.join(self.project_dir, "rois", "roi_*"))):
            manifest_path = os.path.join(roi_dir, "roi_manifest.json")
            manifest = load_json(manifest_path, {}) or {}
            roi_id = manifest.get("roi_id") or os.path.basename(roi_dir)
            records.append(
                RoiRecord(
                    roi_id=roi_id,
                    display_name=manifest.get("display_name") or roi_id,
                    roi_dir=roi_dir,
                    manifest_path=manifest_path,
                    bbox_fullres=manifest.get("bbox_fullres"),
                    shape=manifest.get("shape"),
                    fusion_zarr=self._find_fusion_source(roi_dir, manifest),
                    corrected_zarr=self._find_corrected_source(roi_dir, manifest),
                    raw_ome=_abs(self.project_dir, manifest.get("raw_ome") or manifest.get("ome_tiff")),
                )
            )
        return records

    def channels_for_roi(self, roi: RoiRecord):
        records = []
        if roi.corrected_zarr and os.path.exists(roi.corrected_zarr):
            try:
                from loaders.image_io import zarr_group_names

                names = zarr_group_names(roi.corrected_zarr)
                if roi.roi_id in names:
                    names = zarr_group_names(os.path.join(roi.corrected_zarr, roi.roi_id))
                for i, name in enumerate(names):
                    lower = name.lower()
                    if lower in {"0", "1"} or lower.startswith("__"):
                        continue
                    records.append(
                        ChannelRecord(
                            name=name,
                            source="corrected_zarr",
                            color=DEFAULT_CHANNEL_COLORS[i % len(DEFAULT_CHANNEL_COLORS)],
                            visible=False,
                        )
                    )
            except Exception:
                pass
        return records

    def runs_for_roi(self, roi: RoiRecord) -> List[RunRecord]:
        run_dirs = []
        for folder in ("segmentation_results", "segmentation_runs"):
            run_dirs.extend(sorted(glob.glob(os.path.join(roi.roi_dir, "step2", folder, "*"))))

        seen = set()
        records: List[RunRecord] = []
        for run_dir in run_dirs:
            if not os.path.isdir(run_dir) or run_dir in seen:
                continue
            seen.add(run_dir)
            meta_path = os.path.join(run_dir, "segmentation_meta.json")
            run_meta_path = os.path.join(run_dir, "run_metadata.json")
            meta = load_json(meta_path, None)
            if meta is None:
                meta = load_json(run_meta_path, None)
                meta_path = run_meta_path
            if not isinstance(meta, dict):
                continue

            run = self._record_from_meta(roi, run_dir, meta_path, meta)
            if run:
                records.append(run)

        records.sort(key=lambda r: (r.created_at or r.run_id), reverse=True)
        return records

    def _record_from_meta(self, roi: RoiRecord, run_dir: str, meta_path: str, meta: Dict) -> Optional[RunRecord]:
        roi_id = str(meta.get("roi_id") or roi.roi_id)
        if roi_id != str(roi.roi_id):
            return None
        paths = meta.get("paths") if isinstance(meta.get("paths"), dict) else {}

        dapi = (
            paths.get("dapi_ome")
            or meta.get("global_dapi")
            or meta.get("dapi_path")
            or self._first_existing(run_dir, ["global_dapi_*.ome.tiff", "global_dapi.ome.tiff"])
        )
        mask = (
            paths.get("mask_ome")
            or meta.get("global_mask")
            or meta.get("mask_path")
            or meta.get("ome_tiff")
            or self._first_existing(run_dir, ["global_mask_*.ome.tiff", "global_mask.ome.tiff"])
        )
        dapi = _abs(run_dir, dapi)
        mask = _abs(run_dir, mask)
        if not dapi or not mask:
            return None

        method = str(meta.get("method") or (meta.get("seg_config") or {}).get("method") or "unknown")
        created = str(meta.get("created_at") or meta.get("timestamp") or os.path.basename(run_dir))
        run_id = str(meta.get("run_id") or os.path.basename(run_dir))
        mask_zarr = _abs(run_dir, paths.get("mask_zarr") or meta.get("mask_zarr"))
        cell_count = meta.get("cell_count") or meta.get("n_cells")
        return RunRecord(
            run_id=run_id,
            roi_id=roi_id,
            method=method,
            display_name=_method_display(method),
            created_at=created,
            run_dir=run_dir,
            meta_path=meta_path,
            dapi_ome=dapi,
            mask_ome=mask,
            mask_zarr=mask_zarr,
            cell_count=int(cell_count) if isinstance(cell_count, (int, float)) else None,
            meta=meta,
        )

    @staticmethod
    def _first_existing(base: str, patterns: List[str]) -> Optional[str]:
        for pattern in patterns:
            matches = sorted(glob.glob(os.path.join(base, pattern)))
            if matches:
                return matches[0]
        return None

    def _find_fusion_source(self, roi_dir: str, manifest: Dict) -> Optional[str]:
        candidates = [
            manifest.get("fusion_zarr"),
            manifest.get("fused_zarr"),
            manifest.get("fusion_rgb_zarr"),
            os.path.join(roi_dir, "step1", "fusion.zarr"),
            os.path.join(roi_dir, "step1", "fused.zarr"),
            os.path.join(roi_dir, "step1", "fused_channels.zarr"),
            os.path.join(self.project_dir, "fusion.zarr"),
            os.path.join(self.project_dir, "fused.zarr"),
        ]
        for candidate in candidates:
            path = _abs(self.project_dir, candidate)
            if path and os.path.exists(path):
                return path
        return None

    def _find_corrected_source(self, roi_dir: str, manifest: Dict) -> Optional[str]:
        candidates = [
            manifest.get("corrected_zarr"),
            manifest.get("corrected_channels_zarr"),
            os.path.join(roi_dir, "step1", "corrected_channels.zarr"),
            os.path.join(roi_dir, "step2", "corrected_channels.zarr"),
            os.path.join(self.project_dir, "corrected_channels.zarr"),
        ]
        for candidate in candidates:
            path = _abs(self.project_dir, candidate)
            if path and os.path.exists(path):
                return path
        return None
