"""Single comparison viewport for Step3.1."""

import numpy as np
import pyqtgraph as pg
from PyQt5 import QtCore, QtGui
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QLabel, QVBoxLayout, QWidget

from loaders.image_io import compose_overlay_rgb, dapi_rgb, mask_fill_rgba, outline_rgba


class CompareViewer(QWidget):
    view_changed = pyqtSignal(str, object, object)
    selected = pyqtSignal(str)

    def __init__(self, viewer_id, outline_color, parent=None):
        super().__init__(parent)
        self.viewer_id = viewer_id
        self.outline_color = outline_color
        self.setObjectName(f"compareViewer{viewer_id}")
        border_hex = QtGui.QColor(*outline_color).name()
        self.setStyleSheet(
            f"QWidget#compareViewer{viewer_id}{{border:1px solid {border_hex};"
            "border-radius:5px;background:#101010;}"
        )
        self._sync_guard = False
        self._dapi = None
        self._mask = None
        self._fusion = None
        self._markers = {}
        self._channel_settings = {}
        self._stride = 1
        self._dapi_intensity = 1.0
        self._fusion_intensity = 1.0
        self._dapi_color = (51, 102, 255)
        self._fusion_color = (255, 51, 51)
        self._show_outline = True
        self._outline_width = 0.5
        self._mask_alpha = 0.0
        self._show_dapi = True
        self._show_fusion = False

        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(2)
        self.title = QLabel(f"Viewer {viewer_id}\nNo run selected")
        self.title.setStyleSheet(
            f"color:rgb({outline_color[0]},{outline_color[1]},{outline_color[2]});"
            "background:#1a1a1a;padding:4px;font-size:11px;font-weight:bold;"
        )
        self.title.setWordWrap(True)
        lay.addWidget(self.title)

        self.canvas = pg.GraphicsLayoutWidget()
        self.canvas.setBackground("#060606")
        self.view = self.canvas.addViewBox()
        self.view.setAspectLocked(True)
        self.view.invertY(True)
        self.view.setMenuEnabled(False)
        self.image_item = pg.ImageItem()
        self.fill_item = pg.ImageItem()
        self.outline_item = pg.ImageItem()
        for item in (self.image_item, self.fill_item, self.outline_item):
            try:
                item.setOpts(axisOrder="row-major")
            except Exception:
                pass
        self.view.addItem(self.image_item)
        self.view.addItem(self.fill_item)
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

    def set_overlay_data(self, fusion=None, markers=None):
        self._fusion = None if fusion is None else np.asarray(fusion)
        self._markers = markers or {}
        self.render()

    def set_display(self, show_outline=None, outline_width=None, dapi_intensity=None,
                    mask_alpha=None, show_dapi=None, show_fusion=None, channel_settings=None):
        if show_outline is not None:
            self._show_outline = bool(show_outline)
        if outline_width is not None:
            self._outline_width = max(0.25, float(outline_width))
        if dapi_intensity is not None:
            self._dapi_intensity = float(dapi_intensity)
        if channel_settings is not None and "__dapi__" in channel_settings:
            self._dapi_color = channel_settings["__dapi__"].get("rgb", self._dapi_color)
        if channel_settings is not None and "__fusion__" in channel_settings:
            self._fusion_intensity = float(channel_settings["__fusion__"].get("intensity", self._fusion_intensity))
            self._fusion_color = channel_settings["__fusion__"].get("rgb", self._fusion_color)
        if mask_alpha is not None:
            self._mask_alpha = float(mask_alpha)
        if show_dapi is not None:
            self._show_dapi = bool(show_dapi)
        if show_fusion is not None:
            self._show_fusion = bool(show_fusion)
        if channel_settings is not None:
            self._channel_settings = channel_settings
        self.render()

    def set_roi_bounds(self, bounds):
        # Retained for API compatibility with the old prototype.  Step3.1 now
        # reloads the actual high-resolution patch instead of cropping overview
        # images in the viewer.
        return

    def set_outline_color(self, color):
        self.outline_color = color
        border_hex = QtGui.QColor(*color).name()
        self.setStyleSheet(
            f"QWidget#{self.objectName()}{{border:1px solid {border_hex};"
            "border-radius:5px;background:#101010;}"
        )
        self.title.setStyleSheet(
            f"color:rgb({color[0]},{color[1]},{color[2]});"
            "background:#1a1a1a;padding:4px;font-size:11px;font-weight:bold;"
        )
        self.render()

    def render(self):
        if self._dapi is None:
            self.image_item.clear()
            self.fill_item.clear()
            self.outline_item.clear()
            return
        dapi = self._dapi
        mask = self._mask
        fusion = self._fusion
        marker_layers = []
        for name, arr in self._markers.items():
            st = self._channel_settings.get(name, {})
            if not st.get("visible", False):
                continue
            marker_layers.append(
                {
                    "array": arr,
                    "color": st.get("rgb", (255, 255, 255)),
                    "alpha": st.get("alpha", 0.65),
                    "p_low": st.get("p_low", 1.0),
                    "p_high": st.get("p_high", 99.5),
                }
            )
        if marker_layers or self._show_fusion:
            rgb = compose_overlay_rgb(dapi, fusion=fusion, marker_layers=marker_layers,
                                      dapi_visible=self._show_dapi, fusion_visible=self._show_fusion,
                                      dapi_intensity=self._dapi_intensity,
                                      fusion_intensity=self._fusion_intensity,
                                      dapi_color=self._dapi_color,
                                      fusion_color=self._fusion_color)
        elif self._show_dapi:
            rgb = dapi_rgb(dapi, self._dapi_intensity, color=self._dapi_color)
        else:
            rgb = np.zeros(dapi.shape + (3,), dtype=np.uint8)
        self.image_item.setImage(rgb, autoLevels=False)
        if mask is not None and self._mask_alpha > 0:
            self.fill_item.setImage(mask_fill_rgba(mask, self.outline_color, self._mask_alpha), autoLevels=False)
        else:
            self.fill_item.clear()
        if self._show_outline and mask is not None:
            self.outline_item.setImage(outline_rgba(mask, self.outline_color, self._outline_width), autoLevels=False)
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
