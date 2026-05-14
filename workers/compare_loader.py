"""Background loading workers for comparator viewers."""

import os
import traceback

import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal

from loaders.image_io import (
    compose_overlay_rgb,
    downsample_view,
    overview_stride,
    read_fusion_region,
    read_ome_2d,
    read_ome_region,
    read_raw_ome_channel_region,
    read_zarr_channel,
)


class RunLoadWorker(QThread):
    loaded = pyqtSignal(str, object, object, int, object)
    failed = pyqtSignal(str, str)

    def __init__(self, viewer_id, dapi_path, mask_path, roi=None, channels=None, parent=None):
        super().__init__(parent)
        self.viewer_id = viewer_id
        self.dapi_path = dapi_path
        self.mask_path = mask_path
        self.roi = roi
        self.channels = channels or []

    def run(self):
        try:
            dapi = read_ome_2d(self.dapi_path)
            mask = read_ome_2d(self.mask_path)
            if dapi.shape != mask.shape:
                h = min(dapi.shape[0], mask.shape[0])
                w = min(dapi.shape[1], mask.shape[1])
                dapi = dapi[:h, :w]
                mask = mask[:h, :w]
            stride = overview_stride(dapi.shape)
            overlays = {"fusion": None, "markers": {}}
            roi_names = [
                getattr(self.roi, "roi_id", None),
                getattr(self.roi, "display_name", None),
                "ROI_1",
            ]
            fusion_path = getattr(self.roi, "fusion_zarr", None)
            if fusion_path:
                for roi_name in roi_names:
                    try:
                        overlays["fusion"] = downsample_view(read_zarr_channel(fusion_path, "0", roi_name=roi_name), stride)
                        break
                    except Exception:
                        overlays["fusion"] = None
            corrected_path = getattr(self.roi, "corrected_zarr", None)
            if corrected_path:
                for ch in self.channels:
                    for roi_name in roi_names:
                        try:
                            overlays["markers"][ch.name] = downsample_view(
                                read_zarr_channel(corrected_path, ch.name, roi_name=roi_name),
                                stride,
                            )
                            break
                        except Exception:
                            continue
            self.loaded.emit(
                self.viewer_id,
                downsample_view(dapi, stride),
                downsample_view(mask, stride),
                stride,
                overlays,
            )
        except Exception:
            self.failed.emit(self.viewer_id, traceback.format_exc())


class PatchLoadWorker(QThread):
    loaded = pyqtSignal(str, object, object, object, object, object)
    failed = pyqtSignal(str, str)

    def __init__(self, viewer_id, run, roi, bbox, channels=None, stride=1, parent=None):
        super().__init__(parent)
        self.viewer_id = viewer_id
        self.run = run
        self.roi = roi
        self.bbox = [int(v) for v in bbox]
        self.channels = list(channels or [])
        self.stride = max(1, int(stride))

    def run(self):
        try:
            y0, y1, x0, x1 = self.bbox
            global_bbox = self._global_bbox(y0, y1, x0, x1)
            print(f"[Viewer{self.viewer_id}] crop bbox={[y0, y1, x0, x1]}")
            print(f"[Viewer{self.viewer_id}] global bbox={global_bbox}")
            tile_infos = self._tile_infos()
            if tile_infos and not (os.path.exists(self.run.dapi_ome) and os.path.exists(self.run.mask_ome)):
                dapi, mask = self._read_stitched_tiles((y0, y1, x0, x1), tile_infos)
            else:
                dapi = read_ome_region(self.run.dapi_ome, y0, y1, x0, x1, self.stride)
                mask = read_ome_region(self.run.mask_ome, y0, y1, x0, x1, self.stride)
            if dapi.shape != mask.shape:
                h = min(dapi.shape[0], mask.shape[0])
                w = min(dapi.shape[1], mask.shape[1])
                dapi = dapi[:h, :w]
                mask = mask[:h, :w]
            mask = np.asarray(mask, dtype=np.uint32)
            print(f"[Viewer{self.viewer_id}] image crop shape={getattr(dapi, 'shape', None)}")
            print(f"[Viewer{self.viewer_id}] mask crop shape={getattr(mask, 'shape', None)}")

            fusion = read_fusion_region(getattr(self.roi, "fusion_zarr", None), y0, y1, x0, x1, self.stride)
            markers = {}
            for ch in self.channels:
                try:
                    if ch.source == "corrected_zarr":
                        roi_names = [
                            getattr(self.roi, "roi_id", None),
                            getattr(self.roi, "display_name", None),
                            "ROI_1",
                        ]
                        arr = None
                        for roi_name in roi_names:
                            try:
                                arr = read_zarr_channel(
                                    self.roi.corrected_zarr,
                                    ch.name,
                                    roi_name=roi_name,
                                    y0=y0,
                                    y1=y1,
                                    x0=x0,
                                    x1=x1,
                                    stride=self.stride,
                                )
                                break
                            except Exception:
                                arr = None
                        if arr is not None:
                            markers[ch.name] = arr
                    elif ch.source == "raw_ome" and getattr(self.roi, "raw_ome", None):
                        rb = getattr(self.roi, "bbox_fullres", None) or [0, 0, 0, 0]
                        gy0, gy1 = int(rb[0]) + y0, int(rb[0]) + y1
                        gx0, gx1 = int(rb[2]) + x0, int(rb[2]) + x1
                        markers[ch.name] = read_raw_ome_channel_region(
                            self.roi.raw_ome,
                            ch.name,
                            [gy0, gy1, gx0, gx1],
                            stride=self.stride,
                        )
                except Exception:
                    print(f"[PatchLoadWorker] channel skipped {ch.name}:\n{traceback.format_exc()}")
            self.loaded.emit(self.viewer_id, dapi, mask, fusion, markers, self.bbox)
        except Exception:
            self.failed.emit(self.viewer_id, traceback.format_exc())

    def _global_bbox(self, y0, y1, x0, x1):
        rb = getattr(self.roi, "bbox_fullres", None) or [0, 0, 0, 0]
        if len(rb) != 4:
            rb = [0, 0, 0, 0]
        return [int(rb[0]) + y0, int(rb[0]) + y1, int(rb[2]) + x0, int(rb[2]) + x1]

    def _tile_infos(self):
        infos = []
        for item in (self.run.meta.get("tile_stats") or []):
            bbox = item.get("bbox_local")
            if not bbox:
                continue
            dapi_path = item.get("dapi_path")
            mask_path = item.get("mask_path")
            if dapi_path and not os.path.isabs(dapi_path):
                dapi_path = os.path.join(self.run.run_dir, dapi_path)
            if mask_path and not os.path.isabs(mask_path):
                mask_path = os.path.join(self.run.run_dir, mask_path)
            infos.append(
                {
                    "row": item.get("row"),
                    "col": item.get("col"),
                    "bbox_local": [int(v) for v in bbox],
                    "dapi_path": dapi_path,
                    "mask_path": mask_path,
                }
            )
        return infos

    def _read_stitched_tiles(self, patch_roi, tile_infos):
        py0, py1, px0, px1 = patch_roi
        ph, pw = py1 - py0, px1 - px0
        if ph <= 0 or pw <= 0:
            raise ValueError("Patch outside ROI.")
        dapi_canvas = None
        mask_canvas = None
        hits = []
        for tile in tile_infos:
            ty0, ty1, tx0, tx1 = [int(v) for v in tile["bbox_local"]]
            iy0 = max(py0, ty0)
            iy1 = min(py1, ty1)
            ix0 = max(px0, tx0)
            ix1 = min(px1, tx1)
            if iy1 <= iy0 or ix1 <= ix0:
                continue
            if not tile.get("dapi_path") or not tile.get("mask_path"):
                continue
            dapi_crop = read_ome_region(tile["dapi_path"], iy0 - ty0, iy1 - ty0, ix0 - tx0, ix1 - tx0, 1)
            mask_crop = read_ome_region(tile["mask_path"], iy0 - ty0, iy1 - ty0, ix0 - tx0, ix1 - tx0, 1)
            if dapi_canvas is None:
                dapi_canvas = np.zeros((ph, pw), dtype=dapi_crop.dtype)
                mask_canvas = np.zeros((ph, pw), dtype=np.uint32)
            dy0, dy1 = iy0 - py0, iy1 - py0
            dx0, dx1 = ix0 - px0, ix1 - px0
            dapi_canvas[dy0:dy1, dx0:dx1] = dapi_crop
            mask_canvas[dy0:dy1, dx0:dx1] = mask_crop.astype(np.uint32)
            hits.append(tile)
        if dapi_canvas is None or mask_canvas is None:
            raise ValueError("Patch outside ROI tiles.")
        if self.stride > 1:
            dapi_canvas = dapi_canvas[::self.stride, ::self.stride]
            mask_canvas = mask_canvas[::self.stride, ::self.stride]
        print(f"[Viewer{self.viewer_id}] patch intersects n_tiles={len(hits)}")
        for tile in hits:
            print(f"[Viewer{self.viewer_id}] using tile r={tile.get('row')} c={tile.get('col')} bbox={tile.get('bbox_local')}")
        return dapi_canvas, mask_canvas


class MarkerLoadWorker(QThread):
    loaded = pyqtSignal(int, object)
    failed = pyqtSignal(int, str)

    def __init__(self, generation, roi, bbox, channels, cache_keys, stride=1, parent=None):
        super().__init__(parent)
        self.generation = int(generation)
        self.roi = roi
        self.bbox = [int(v) for v in bbox]
        self.channels = list(channels or [])
        self.cache_keys = dict(cache_keys or {})
        self.stride = max(1, int(stride))

    def run(self):
        try:
            y0, y1, x0, x1 = self.bbox
            out = {}
            for ch in self.channels:
                arr = None
                try:
                    if ch.source == "corrected_zarr":
                        roi_names = [
                            getattr(self.roi, "roi_id", None),
                            getattr(self.roi, "display_name", None),
                            "ROI_1",
                        ]
                        for roi_name in roi_names:
                            try:
                                arr = read_zarr_channel(
                                    self.roi.corrected_zarr,
                                    ch.name,
                                    roi_name=roi_name,
                                    y0=y0,
                                    y1=y1,
                                    x0=x0,
                                    x1=x1,
                                    stride=self.stride,
                                )
                                break
                            except Exception:
                                arr = None
                    elif ch.source == "raw_ome" and getattr(self.roi, "raw_ome", None):
                        rb = getattr(self.roi, "bbox_fullres", None) or [0, 0, 0, 0]
                        gy0, gy1 = int(rb[0]) + y0, int(rb[0]) + y1
                        gx0, gx1 = int(rb[2]) + x0, int(rb[2]) + x1
                        arr = read_raw_ome_channel_region(
                            self.roi.raw_ome,
                            ch.name,
                            [gy0, gy1, gx0, gx1],
                            stride=self.stride,
                        )
                    if arr is not None:
                        out[ch.name] = (self.cache_keys.get(ch.name), np.asarray(arr))
                        print(f"[MarkerLoad] generation={self.generation} loaded {ch.name} shape={getattr(arr, 'shape', None)}")
                except Exception:
                    print(f"[MarkerLoad] generation={self.generation} skipped {ch.name}:\n{traceback.format_exc()}")
            self.loaded.emit(self.generation, out)
        except Exception:
            self.failed.emit(self.generation, traceback.format_exc())


class CompositeWorker(QThread):
    composed = pyqtSignal(int, object, object)
    failed = pyqtSignal(int, str)

    def __init__(self, generation, cache_key, dapi, fusion, marker_arrays, marker_settings,
                 show_dapi=True, show_fusion=False, dapi_intensity=1.0, fusion_intensity=1.0,
                 dapi_color=(51, 102, 255), fusion_color=(255, 51, 51), parent=None):
        super().__init__(parent)
        self.generation = int(generation)
        self.cache_key = cache_key
        self.dapi = np.asarray(dapi)
        self.fusion = None if fusion is None else np.asarray(fusion)
        self.marker_arrays = dict(marker_arrays or {})
        self.marker_settings = dict(marker_settings or {})
        self.show_dapi = bool(show_dapi)
        self.show_fusion = bool(show_fusion)
        self.dapi_intensity = float(dapi_intensity)
        self.fusion_intensity = float(fusion_intensity)
        self.dapi_color = dapi_color
        self.fusion_color = fusion_color

    def run(self):
        try:
            layers = []
            target = self.dapi.shape[:2]
            for name, arr in self.marker_arrays.items():
                st = self.marker_settings.get(name, {})
                a = self._match_shape(np.asarray(arr), target)
                layers.append(
                    {
                        "array": a,
                        "color": st.get("rgb", (255, 255, 255)),
                        "alpha": st.get("alpha", 0.65),
                        "p_low": st.get("p_low", 1.0),
                        "p_high": st.get("p_high", 99.5),
                    }
                )
            fusion = None if self.fusion is None else self._match_shape(self.fusion, target)
            rgb = compose_overlay_rgb(
                self.dapi,
                fusion=fusion,
                marker_layers=layers,
                dapi_visible=self.show_dapi,
                fusion_visible=self.show_fusion,
                dapi_intensity=self.dapi_intensity,
                fusion_intensity=self.fusion_intensity,
                dapi_color=self.dapi_color,
                fusion_color=self.fusion_color,
            )
            print(f"[Composite] generation={self.generation} composed markers={list(self.marker_arrays)} shape={rgb.shape}")
            self.composed.emit(self.generation, self.cache_key, rgb)
        except Exception:
            self.failed.emit(self.generation, traceback.format_exc())

    @staticmethod
    def _match_shape(arr, target):
        if arr.shape[:2] == tuple(target):
            return arr
        th, tw = target
        out = np.zeros((th, tw) + arr.shape[2:], dtype=arr.dtype)
        mh = min(th, int(arr.shape[0]))
        mw = min(tw, int(arr.shape[1]))
        if mh > 0 and mw > 0:
            out[:mh, :mw, ...] = arr[:mh, :mw, ...]
        return out
