"""Background loading workers for comparator viewers."""

import traceback

from PyQt5.QtCore import QThread, pyqtSignal

from loaders.image_io import (
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
            dapi = read_ome_region(self.run.dapi_ome, y0, y1, x0, x1, self.stride)
            mask = read_ome_region(self.run.mask_ome, y0, y1, x0, x1, self.stride)
            if dapi.shape != mask.shape:
                h = min(dapi.shape[0], mask.shape[0])
                w = min(dapi.shape[1], mask.shape[1])
                dapi = dapi[:h, :w]
                mask = mask[:h, :w]

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
