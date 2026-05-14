"""Single comparison viewport for Step3.1."""

import numpy as np
import pyqtgraph as pg
from PyQt5 import QtCore
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QLabel, QVBoxLayout, QWidget

from loaders.image_io import dapi_rgb, outline_rgba


class CompareViewer(QWidget):
    view_changed = pyqtSignal(str, object, object)
    selected = pyqtSignal(str)

    def __init__(self, viewer_id, outline_color, parent=None):
        super().__init__(parent)
        self.viewer_id = viewer_id
        self.outline_color = outline_color
        self._sync_guard = False
        self._dapi = None
        self._mask = None
        self._stride = 1
        self._dapi_intensity = 1.0
        self._show_outline = True
        self._outline_width = 1

        lay = QVBoxLayout(self)
        lay.setContentsMargins(2, 2, 2, 2)
        lay.setSpacing(2)
        self.title = QLabel(f"Viewer {viewer_id}\nNo run selected")
        self.title.setStyleSheet("color:#ddd;background:#222;padding:4px;font-size:11px;")
        self.title.setWordWrap(True)
        lay.addWidget(self.title)

        self.canvas = pg.GraphicsLayoutWidget()
        self.canvas.setBackground("#060606")
        self.view = self.canvas.addViewBox()
        self.view.setAspectLocked(True)
        self.view.invertY(True)
        self.view.setMenuEnabled(False)
        self.image_item = pg.ImageItem()
        self.outline_item = pg.ImageItem()
        self.view.addItem(self.image_item)
        self.view.addItem(self.outline_item)
        self.view.sigRangeChanged.connect(self._on_range_changed)
        self.canvas.scene().sigMouseClicked.connect(self._on_mouse_clicked)
        lay.addWidget(self.canvas, stretch=1)

    def set_run_label(self, text):
        self.title.setText(text)

    def set_data(self, dapi, mask, stride):
        self._dapi = np.asarray(dapi)
        self._mask = np.asarray(mask)
        self._stride = int(stride or 1)
        self.render()
        self.reset_view()

    def set_display(self, show_outline=None, outline_width=None, dapi_intensity=None):
        if show_outline is not None:
            self._show_outline = bool(show_outline)
        if outline_width is not None:
            self._outline_width = max(1, int(outline_width))
        if dapi_intensity is not None:
            self._dapi_intensity = float(dapi_intensity)
        self.render()

    def set_outline_color(self, color):
        self.outline_color = color
        self.render()

    def render(self):
        if self._dapi is None:
            self.image_item.clear()
            self.outline_item.clear()
            return
        self.image_item.setImage(dapi_rgb(self._dapi, self._dapi_intensity), autoLevels=False)
        if self._show_outline and self._mask is not None:
            self.outline_item.setImage(
                outline_rgba(self._mask, self.outline_color, self._outline_width),
                autoLevels=False,
            )
        else:
            self.outline_item.clear()

    def reset_view(self):
        self.view.autoRange()

    def get_ranges(self):
        return self.view.viewRange()

    def set_ranges(self, ranges):
        self._sync_guard = True
        try:
            self.view.setRange(xRange=ranges[0], yRange=ranges[1], padding=0)
        finally:
            QtCore.QTimer.singleShot(0, self._release_sync_guard)

    def _release_sync_guard(self):
        self._sync_guard = False

    def _on_range_changed(self, _view, ranges):
        if not self._sync_guard:
            self.view_changed.emit(self.viewer_id, ranges[0], ranges[1])

    def _on_mouse_clicked(self, ev):
        if self.canvas.sceneBoundingRect().contains(ev.scenePos()):
            self.selected.emit(self.viewer_id)
