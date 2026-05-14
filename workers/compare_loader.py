"""Background loading workers for comparator viewers."""

import traceback

from PyQt5.QtCore import QThread, pyqtSignal

from loaders.image_io import downsample_view, overview_stride, read_ome_2d, read_zarr_channel


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
