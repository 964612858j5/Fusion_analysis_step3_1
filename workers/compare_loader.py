"""Background loading workers for comparator viewers."""

import traceback

from PyQt5.QtCore import QThread, pyqtSignal

from loaders.image_io import downsample_view, overview_stride, read_ome_2d


class RunLoadWorker(QThread):
    loaded = pyqtSignal(str, object, object, int)
    failed = pyqtSignal(str, str)

    def __init__(self, viewer_id, dapi_path, mask_path, parent=None):
        super().__init__(parent)
        self.viewer_id = viewer_id
        self.dapi_path = dapi_path
        self.mask_path = mask_path

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
            self.loaded.emit(
                self.viewer_id,
                downsample_view(dapi, stride),
                downsample_view(mask, stride),
                stride,
            )
        except Exception:
            self.failed.emit(self.viewer_id, traceback.format_exc())
