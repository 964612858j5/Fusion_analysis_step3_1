"""Step3.1 standalone multi-method segmentation comparator."""

import os

from PyQt5 import QtGui, QtWidgets
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QFileDialog,
    QCheckBox,
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSlider,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from configs.defaults import VIEWER_COLORS
from loaders.project_loader import ProjectLoader
from ui.compare_viewer import CompareViewer
from workers.compare_loader import RunLoadWorker


class Step31ComparePage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Step3.1 - Multi-method Segmentation Comparator")
        self._project_dir = ""
        self._loader = None
        self._rois = []
        self._runs = []
        self._run_by_id = {}
        self._workers = {}
        self._sync_enabled = True
        self._selected_viewer = "A"
        self._outline_width = 1
        self._dapi_intensity = 1.0
        self._outline_colors = {
            key: self._hex_to_rgb(value) for key, value in VIEWER_COLORS.items()
        }
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)

        top = QHBoxLayout()
        top.addWidget(QLabel("Project directory:"))
        self.project_edit = QLineEdit()
        self.project_edit.setPlaceholderText("Select project directory containing roi_index.json")
        top.addWidget(self.project_edit, stretch=2)
        browse = QPushButton("Browse")
        browse.clicked.connect(self._browse_project)
        top.addWidget(browse)
        top.addWidget(QLabel("ROI:"))
        self.roi_combo = QComboBox()
        self.roi_combo.currentIndexChanged.connect(self._on_roi_changed)
        top.addWidget(self.roi_combo, stretch=1)
        self.load_btn = QPushButton("Load")
        self.load_btn.clicked.connect(self._load_selected_runs)
        top.addWidget(self.load_btn)
        root.addLayout(top)

        run_row = QHBoxLayout()
        self.run_combos = {}
        for viewer_id in ("A", "B", "C", "D"):
            run_row.addWidget(QLabel(f"Viewer {viewer_id}:"))
            combo = QComboBox()
            self.run_combos[viewer_id] = combo
            run_row.addWidget(combo, stretch=1)
        root.addLayout(run_row)

        split = QSplitter(Qt.Horizontal)
        split.addWidget(self._make_control_panel())
        split.addWidget(self._make_viewer_grid())
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)
        root.addWidget(split, stretch=1)

        self.status = QLabel("No project loaded")
        self.status.setStyleSheet("color:#aaa;font-size:11px;")
        root.addWidget(self.status)

    def _make_control_panel(self):
        panel = QWidget()
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(0, 0, 4, 0)
        lay.setSpacing(8)

        view_box = QGroupBox("View Controls")
        view_lay = QVBoxLayout(view_box)
        self.sync_chk = QCheckBox("Sync zoom/pan")
        self.sync_chk.setChecked(True)
        self.sync_chk.toggled.connect(self._set_sync_enabled)
        view_lay.addWidget(self.sync_chk)
        reset_all = QPushButton("Reset all")
        reset_all.clicked.connect(self._reset_all)
        view_lay.addWidget(reset_all)
        reset_current = QPushButton("Reset current")
        reset_current.clicked.connect(self._reset_current)
        view_lay.addWidget(reset_current)
        lay.addWidget(view_box)

        mask_box = QGroupBox("Mask Controls")
        mask_lay = QVBoxLayout(mask_box)
        self.outline_chk = QCheckBox("Show outline")
        self.outline_chk.setChecked(True)
        self.outline_chk.toggled.connect(self._update_display_controls)
        mask_lay.addWidget(self.outline_chk)
        width_row = QHBoxLayout()
        width_row.addWidget(QLabel("Outline width:"))
        self.width_slider = QSlider(Qt.Horizontal)
        self.width_slider.setRange(1, 5)
        self.width_slider.setValue(1)
        self.width_slider.valueChanged.connect(self._update_display_controls)
        width_row.addWidget(self.width_slider)
        mask_lay.addLayout(width_row)
        color_btn = QPushButton("Set current outline color")
        color_btn.clicked.connect(self._choose_current_color)
        mask_lay.addWidget(color_btn)
        lay.addWidget(mask_box)

        display_box = QGroupBox("Display Controls")
        display_lay = QVBoxLayout(display_box)
        dapi_row = QHBoxLayout()
        dapi_row.addWidget(QLabel("DAPI intensity:"))
        self.dapi_slider = QSlider(Qt.Horizontal)
        self.dapi_slider.setRange(10, 300)
        self.dapi_slider.setValue(100)
        self.dapi_slider.valueChanged.connect(self._update_display_controls)
        dapi_row.addWidget(self.dapi_slider)
        display_lay.addLayout(dapi_row)
        lay.addWidget(display_box)

        lay.addStretch()
        return panel

    def _make_viewer_grid(self):
        grid_w = QWidget()
        grid = QGridLayout(grid_w)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(4)
        self.viewers = {}
        positions = {"A": (0, 0), "B": (0, 1), "C": (1, 0), "D": (1, 1)}
        for viewer_id, pos in positions.items():
            viewer = CompareViewer(viewer_id, self._outline_colors[viewer_id])
            viewer.view_changed.connect(self._on_view_changed)
            viewer.selected.connect(self._on_viewer_selected)
            self.viewers[viewer_id] = viewer
            grid.addWidget(viewer, *pos)
        return grid_w

    def _browse_project(self):
        path = QFileDialog.getExistingDirectory(self, "Select project directory", self.project_edit.text() or os.getcwd())
        if path:
            self.project_edit.setText(path)
            self._load_project(path)

    def _load_project(self, path=None):
        self._project_dir = os.path.abspath(path or self.project_edit.text().strip())
        if not self._project_dir:
            return
        self._loader = ProjectLoader(self._project_dir)
        self._rois = self._loader.rois()
        self.roi_combo.blockSignals(True)
        self.roi_combo.clear()
        for roi in self._rois:
            self.roi_combo.addItem(f"{roi.display_name} ({roi.roi_id})", roi)
        self.roi_combo.blockSignals(False)
        print(f"[Step3.1] project loaded={self._project_dir}")
        print(f"[Step3.1] available rois={len(self._rois)}")
        self.status.setText(f"Loaded {len(self._rois)} ROI(s).")
        if self._rois:
            self.roi_combo.setCurrentIndex(0)
            self._on_roi_changed(0)

    def _on_roi_changed(self, _idx):
        roi = self.roi_combo.currentData()
        if roi is None or self._loader is None:
            return
        self._runs = self._loader.runs_for_roi(roi)
        self._run_by_id = {run.run_id: run for run in self._runs}
        print(f"[Step3.1] selected roi_id={roi.roi_id}")
        print(f"[Step3.1] available runs={len(self._runs)}")
        for combo in self.run_combos.values():
            combo.clear()
            combo.addItem("(none)", None)
            for run in self._runs:
                combo.addItem(run.label, run.run_id)
        for i, viewer_id in enumerate(("A", "B", "C", "D"), start=0):
            if i + 1 < self.run_combos[viewer_id].count():
                self.run_combos[viewer_id].setCurrentIndex(i + 1)
        self.status.setText(f"{roi.display_name}: {len(self._runs)} segmentation run(s).")

    def _load_selected_runs(self):
        if self._loader is None or self.project_edit.text().strip() != self._project_dir:
            self._load_project(self.project_edit.text().strip())
        roi = self.roi_combo.currentData()
        if roi is None:
            QMessageBox.warning(self, "Step3.1", "Select a ROI first.")
            return
        for viewer_id, combo in self.run_combos.items():
            run_id = combo.currentData()
            if not run_id:
                self.viewers[viewer_id].set_run_label(f"Viewer {viewer_id}\nNo run selected")
                continue
            run = self._run_by_id.get(run_id)
            if run is None:
                continue
            if run.roi_id != roi.roi_id:
                QMessageBox.warning(self, "Step3.1", "Selected runs must belong to the same ROI.")
                return
            self._start_run_load(viewer_id, run)

    def _start_run_load(self, viewer_id, run):
        if not os.path.exists(run.dapi_ome) or not os.path.exists(run.mask_ome):
            QMessageBox.warning(
                self,
                "Step3.1",
                f"Run {run.run_id} is missing DAPI or mask OME output.",
            )
            return
        label = f"{run.display_name}\n{run.created_at}"
        if run.cell_count is not None:
            label += f"\ncells={run.cell_count:,}"
        self.viewers[viewer_id].set_run_label(label + "\nloading...")
        print(f"[Viewer{viewer_id}] run_id={run.run_id}")
        print(f"[Viewer{viewer_id}] method={run.method}")
        print(f"[Viewer{viewer_id}] dapi={run.dapi_ome}")
        print(f"[Viewer{viewer_id}] mask={run.mask_ome}")
        worker = RunLoadWorker(viewer_id, run.dapi_ome, run.mask_ome, self)
        worker.loaded.connect(lambda vid, dapi, mask, stride, r=run, label=label: self._on_run_loaded(vid, r, label, dapi, mask, stride))
        worker.failed.connect(self._on_run_failed)
        self._workers[viewer_id] = worker
        worker.start()

    def _on_run_loaded(self, viewer_id, run, label, dapi, mask, stride):
        self.viewers[viewer_id].set_run_label(label)
        self.viewers[viewer_id].set_data(dapi, mask, stride)
        self._update_display_controls()
        self.status.setText(f"Loaded {viewer_id}: {run.run_id}")

    def _on_run_failed(self, viewer_id, error):
        self.viewers[viewer_id].set_run_label(f"Viewer {viewer_id}\nLoad failed")
        print(f"[Viewer{viewer_id}] load failed:\n{error}")
        QMessageBox.warning(self, "Step3.1", f"Viewer {viewer_id} failed to load.\n\n{error[:1200]}")

    def _set_sync_enabled(self, enabled):
        self._sync_enabled = bool(enabled)
        print(f"[Sync] enabled={self._sync_enabled}")

    def _on_view_changed(self, source_id, x_range, y_range):
        if not self._sync_enabled:
            return
        for viewer_id, viewer in self.viewers.items():
            if viewer_id != source_id:
                viewer.set_ranges((x_range, y_range))
        print("[Sync] zoom propagated")
        print("[Sync] pan propagated")

    def _on_viewer_selected(self, viewer_id):
        self._selected_viewer = viewer_id
        self.status.setText(f"Selected viewer {viewer_id}")

    def _reset_all(self):
        for viewer in self.viewers.values():
            viewer.reset_view()

    def _reset_current(self):
        self.viewers[self._selected_viewer].reset_view()

    def _update_display_controls(self):
        show_outline = self.outline_chk.isChecked()
        outline_width = self.width_slider.value()
        dapi_intensity = self.dapi_slider.value() / 100.0
        for viewer in self.viewers.values():
            viewer.set_display(show_outline, outline_width, dapi_intensity)

    def _choose_current_color(self):
        cur = QtGui.QColor(*self._outline_colors[self._selected_viewer])
        color = QtWidgets.QColorDialog.getColor(cur, self, f"Viewer {self._selected_viewer} outline color")
        if not color.isValid():
            return
        self._outline_colors[self._selected_viewer] = (color.red(), color.green(), color.blue())
        self.viewers[self._selected_viewer].set_outline_color(self._outline_colors[self._selected_viewer])

    @staticmethod
    def _hex_to_rgb(value):
        color = QtGui.QColor(value)
        return (color.red(), color.green(), color.blue())
