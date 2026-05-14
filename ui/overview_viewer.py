"""V7-style preview viewer with a draggable ROI rectangle."""

import numpy as np
import pyqtgraph as pg
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QLabel, QVBoxLayout, QWidget

from loaders.image_io import dapi_rgb


class OverviewViewer(QWidget):
    roi_changed = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._dapi = None
        self._roi = None
        self._drag_start = None
        self._rect_item = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(2, 2, 2, 2)
        lay.setSpacing(2)
        self.title = QLabel("Preview / ROI")
        self.title.setStyleSheet("color:#ddd;background:#222;padding:4px;font-size:11px;")
        lay.addWidget(self.title)
        self.canvas = pg.GraphicsLayoutWidget()
        self.canvas.setBackground("#060606")
        self.view = self.canvas.addViewBox()
        self.view.setAspectLocked(True)
        self.view.invertY(True)
        self.view.setMenuEnabled(False)
        self.image_item = pg.ImageItem()
        self.view.addItem(self.image_item)
        self.canvas.scene().sigMouseClicked.connect(self._on_clicked)
        self.canvas.viewport().installEventFilter(self)
        lay.addWidget(self.canvas, stretch=1)

    def set_data(self, dapi):
        self._dapi = np.asarray(dapi)
        self.image_item.setImage(dapi_rgb(self._dapi), autoLevels=False)
        self.view.autoRange()
        self.title.setText("Preview / ROI - drag to select zoom region")

    def set_roi(self, bounds):
        self._roi = bounds
        self._draw_roi()
        self.roi_changed.emit(bounds)

    def clear_roi(self):
        self._roi = None
        if self._rect_item is not None:
            self.view.removeItem(self._rect_item)
            self._rect_item = None
        self.roi_changed.emit(None)

    def eventFilter(self, obj, event):
        if obj is self.canvas.viewport():
            if event.type() == QtCore.QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                self._drag_start = self._img_pos(event.pos())
                return True
            if event.type() == QtCore.QEvent.MouseMove and self._drag_start is not None and event.buttons() & Qt.LeftButton:
                self._update_drag_roi(self._drag_start, self._img_pos(event.pos()), emit=False)
                return True
            if event.type() == QtCore.QEvent.MouseButtonRelease and event.button() == Qt.LeftButton and self._drag_start is not None:
                start = self._drag_start
                self._drag_start = None
                self._update_drag_roi(start, self._img_pos(event.pos()), emit=True)
                return True
            if event.type() == QtCore.QEvent.MouseButtonDblClick:
                self.view.autoRange()
                return True
            if event.type() == QtCore.QEvent.Wheel:
                delta = event.angleDelta().y()
                factor = 1.15 ** (delta / 120.0)
                pos = self._img_pos(event.pos())
                vr = self.view.viewRange()
                self.view.setRange(
                    xRange=[pos.x() + (vr[0][0] - pos.x()) / factor, pos.x() + (vr[0][1] - pos.x()) / factor],
                    yRange=[pos.y() + (vr[1][0] - pos.y()) / factor, pos.y() + (vr[1][1] - pos.y()) / factor],
                    padding=0,
                )
                return True
        return super().eventFilter(obj, event)

    def _img_pos(self, viewport_pos):
        return self.image_item.mapFromScene(self.canvas.mapToScene(viewport_pos))

    def _on_clicked(self, ev):
        if ev.button() == Qt.RightButton:
            self.clear_roi()

    def _update_drag_roi(self, p0, p1, emit):
        if self._dapi is None:
            return
        x0 = int(max(0, min(p0.x(), p1.x())))
        y0 = int(max(0, min(p0.y(), p1.y())))
        x1 = int(min(self._dapi.shape[1], max(p0.x(), p1.x())))
        y1 = int(min(self._dapi.shape[0], max(p0.y(), p1.y())))
        if x1 - x0 < 8 or y1 - y0 < 8:
            return
        self._roi = (y0, y1, x0, x1)
        self._draw_roi()
        if emit:
            self.roi_changed.emit(self._roi)

    def _draw_roi(self):
        if self._roi is None:
            return
        y0, y1, x0, x1 = self._roi
        rect = QtCore.QRectF(x0, y0, x1 - x0, y1 - y0)
        if self._rect_item is None:
            self._rect_item = QtWidgets.QGraphicsRectItem(rect)
            self._rect_item.setPen(pg.mkPen("#f0a030", width=2))
            self._rect_item.setBrush(QtGui.QColor(240, 160, 48, 45))
            self.view.addItem(self._rect_item)
        else:
            self._rect_item.setRect(rect)
