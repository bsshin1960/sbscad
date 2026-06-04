import sys
import tempfile
import os
from PyQt6.QtWidgets import (
    QMainWindow, QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QTreeView, QDockWidget, QToolBar, QMenu, QMenuBar, QStatusBar,
    QInputDialog, QMessageBox, QLabel, QComboBox, QFileDialog,
    QDialog, QDoubleSpinBox, QPushButton, QFrame, QRadioButton, QButtonGroup
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction, QStandardItemModel, QStandardItem
from cad_viewer import CADViewer
from cad_modeler import CADModeler
import pyvista as pv
import re

class PlaneButton(QWidget):
    def __init__(self, text, callback, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        self.label = QLabel()
        html = ""
        for char in text:
            if char == 'X': html += "<font color='#FF5555'><b>X</b></font>"
            elif char == 'Y': html += "<font color='#22CC22'><b>Y</b></font>"
            elif char == 'Z': html += "<font color='#5555FF'><b>Z</b></font>"
            else: html += f"<b>{char}</b>"
        self.label.setText(html)
        self.label.setStyleSheet("font-size: 14px; background: transparent;")
        layout.addWidget(self.label)
        self.text_val = text
        self.callback = callback
        self.is_active = False
        self.update_style()
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
    def update_style(self):
        if self.is_active:
            self.setStyleSheet("QWidget { background-color: white; border: 2px solid #555; border-radius: 4px; } QLabel { color: black; }")
        else:
            self.setStyleSheet("QWidget { background-color: lightgray; border: 1px solid #aaa; border-radius: 4px; } QWidget:hover { background-color: #ccc; } QLabel { color: black; }")
            
    def mousePressEvent(self, event):
        self.callback(self.text_val)

class SelectionModeWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.btn_edge = QRadioButton("Edge")
        self.btn_face = QRadioButton("Face")
        self.btn_edge.setChecked(True)
        layout.addWidget(self.btn_edge)
        layout.addWidget(self.btn_face)
        
    def currentText(self):
        return "Face" if self.btn_face.isChecked() else "Edge"
        
    def setCurrentText(self, text):
        if text == "Face":
            self.btn_face.setChecked(True)
        else:
            self.btn_edge.setChecked(True)

class RevolveDialog(QDialog):
    def __init__(self, parent=None, title="Revolve", default_angle=360.0, on_ok=None, on_cancel=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        self.angle = default_angle
        self.axis = "Y"
        self.on_ok = on_ok
        self.on_cancel = on_cancel
        
        layout = QVBoxLayout(self)
        
        # Angle
        angle_layout = QHBoxLayout()
        angle_layout.addWidget(QLabel("Angle (deg):"))
        self.angle_spin = QDoubleSpinBox()
        self.angle_spin.setRange(0.1, 360.0)
        self.angle_spin.setValue(self.angle)
        angle_layout.addWidget(self.angle_spin)
        layout.addLayout(angle_layout)
        
        # Axis
        axis_layout = QHBoxLayout()
        axis_layout.addWidget(QLabel("Axis:"))
        self.radio_x = QRadioButton("X-Axis")
        self.radio_y = QRadioButton("Y-Axis")
        self.radio_y.setChecked(True)
        axis_layout.addWidget(self.radio_x)
        axis_layout.addWidget(self.radio_y)
        layout.addLayout(axis_layout)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("OK")
        btn_cancel = QPushButton("Cancel")
        btn_ok.clicked.connect(self.accept)
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)
        
    def accept(self):
        self.angle = self.angle_spin.value()
        self.axis = "X" if self.radio_x.isChecked() else "Y"
        super().accept()
        if self.on_ok: self.on_ok(self.angle, self.axis)
        
    def reject(self):
        super().reject()
        if self.on_cancel: self.on_cancel()

class NonModalInputDialog(QDialog):
    def __init__(self, parent=None, title="Input", labels=["Value:"], defaults=[0.0], on_ok=None, on_cancel=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        
        layout = QVBoxLayout(self)
        self.spinboxes = []
        for label, default in zip(labels, defaults):
            hlayout = QHBoxLayout()
            hlayout.addWidget(QLabel(label))
            spinbox = QDoubleSpinBox()
            spinbox.setRange(0.1, 10000.0)
            spinbox.setDecimals(2)
            spinbox.setValue(default)
            hlayout.addWidget(spinbox)
            layout.addLayout(hlayout)
            self.spinboxes.append(spinbox)
            
        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("OK")
        btn_cancel = QPushButton("Cancel")
        btn_ok.clicked.connect(self.accept)
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)
        
        self.on_ok = on_ok
        self.on_cancel = on_cancel
        
    def accept(self):
        values = [sb.value() for sb in self.spinboxes]
        super().accept()
        if self.on_ok: self.on_ok(values)
            
    def reject(self):
        super().reject()
        if self.on_cancel: self.on_cancel()

class InteractivePadDialog(QDialog):
    def __init__(self, parent=None, initial_distance=10.0, callback=None, on_ok=None, on_cancel=None):
        super().__init__(parent)
        self.setWindowTitle("Interactive Pad")
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        
        layout = QVBoxLayout(self)
        
        hlayout = QHBoxLayout()
        hlayout.addWidget(QLabel("Distance:"))
        self.spinbox = QDoubleSpinBox()
        self.spinbox.setRange(-10000.0, 10000.0)
        self.spinbox.setValue(initial_distance)
        hlayout.addWidget(self.spinbox)
        layout.addLayout(hlayout)
        
        btn_layout = QHBoxLayout()
        self.btn_ok = QPushButton("OK")
        self.btn_cancel = QPushButton("Cancel")
        btn_layout.addWidget(self.btn_ok)
        btn_layout.addWidget(self.btn_cancel)
        layout.addLayout(btn_layout)
        
        self.callback = callback
        self.on_ok = on_ok
        self.on_cancel = on_cancel
        
        self.spinbox.valueChanged.connect(self._on_value_changed)
        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)
        self._updating = False

    def _on_value_changed(self, val):
        if not self._updating and self.callback:
            self.callback(val)
            
    def set_distance(self, val):
        self._updating = True
        self.spinbox.setValue(val)
        self._updating = False
        
    def accept(self):
        self.on_cancel = None
        if self.on_ok: self.on_ok(self.spinbox.value())
        super().accept()
        
    def reject(self):
        if self.on_cancel: 
            self.on_cancel()
            self.on_cancel = None
        super().reject()
        
    def closeEvent(self, event):
        if self.on_cancel: 
            self.on_cancel()
            self.on_cancel = None
        super().closeEvent(event)

class CADMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Smart CAD")
        self.resize(1200, 800)

        self.modeler = CADModeler()
        self.part_body = None
        self.current_plane = "XYZ"
        self.operations = []
        self.init_viewport()
        self.init_menu()
        self.init_tree_view()

        self.setStatusBar(QStatusBar(self))
        self.help_label = QLabel()
        self.help_label.setStyleSheet("background-color: #222; color: #FFF; font-size: 13px; padding: 5px; font-weight: bold;")
        self.statusBar().addPermanentWidget(self.help_label, 1)
        self.statusBar().setStyleSheet("background-color: #222;")
        self.set_help("프로그램이 시작되었습니다.")
        
    def showEvent(self, event):
        super().showEvent(event)
        if hasattr(self, 'right_dock'):
            self.resizeDocks([self.dock, self.right_dock], [180, 80], Qt.Orientation.Horizontal)
        else:
            self.resizeDocks([self.dock], [180], Qt.Orientation.Horizontal)

    def set_help(self, msg):
        self.help_label.setText(msg)

    def show_warning(self, title, text):
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setWindowTitle(title)
        msg.setText(text)
        msg.setWindowModality(Qt.WindowModality.NonModal)
        msg.show()
        if not hasattr(self, '_msg_boxes'): self._msg_boxes = []
        self._msg_boxes.append(msg)

    def clear_tool_options(self):
        for i in reversed(range(self.tool_options_layout.count())):
            item = self.tool_options_layout.itemAt(i)
            if item.widget():
                item.widget().setParent(None)

    def show_tool_options(self, title, labels, defaults, on_ok, on_cancel):
        self.clear_tool_options()
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 5, 0, 0)
        
        layout.addWidget(QLabel(f"<b>{title}</b>"))
        
        spinboxes = []
        for label_text, default_val in zip(labels, defaults):
            layout.addWidget(QLabel(label_text))
            sb = QDoubleSpinBox()
            sb.setRange(-10000, 10000)
            sb.setMinimumWidth(60)
            sb.setValue(default_val)
            layout.addWidget(sb)
            spinboxes.append(sb)
            
        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("OK")
        cancel_btn = QPushButton("Cancel")
        ok_btn.setMinimumWidth(40)
        cancel_btn.setMinimumWidth(40)
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)
        
        def handle_ok():
            vals = [sb.value() for sb in spinboxes]
            self.clear_tool_options()
            if on_ok: on_ok(vals)
            
        def handle_cancel():
            self.clear_tool_options()
            if on_cancel: on_cancel()
            
        ok_btn.clicked.connect(handle_ok)
        cancel_btn.clicked.connect(handle_cancel)
        
        self.tool_options_layout.addWidget(widget)

    def show_revolve_options(self, title, on_ok, on_cancel):
        self.clear_tool_options()
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 5, 0, 0)
        
        layout.addWidget(QLabel(f"<b>{title}</b>"))
        
        layout.addWidget(QLabel("Angle (deg):"))
        sb = QDoubleSpinBox()
        sb.setRange(-360, 360)
        sb.setMinimumWidth(60)
        sb.setValue(360.0)
        layout.addWidget(sb)
        
        layout.addWidget(QLabel("Axis of Revolution:"))
        axis_group = QButtonGroup(widget)
        radio_x = QRadioButton("X Axis")
        radio_y = QRadioButton("Y Axis")
        radio_x.setChecked(True)
        axis_group.addButton(radio_x)
        axis_group.addButton(radio_y)
        layout.addWidget(radio_x)
        layout.addWidget(radio_y)
        
        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("OK")
        cancel_btn = QPushButton("Cancel")
        ok_btn.setMinimumWidth(40)
        cancel_btn.setMinimumWidth(40)
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)
        
        def handle_ok():
            angle = sb.value()
            axis = "X" if radio_x.isChecked() else "Y"
            self.clear_tool_options()
            if on_ok: on_ok(angle, axis)
            
        def handle_cancel():
            self.clear_tool_options()
            if on_cancel: on_cancel()
            
        ok_btn.clicked.connect(handle_ok)
        cancel_btn.clicked.connect(handle_cancel)
        
        self.tool_options_layout.addWidget(widget)

    def set_active_tool(self, active_action=None):
        if active_action is None:
            self.clear_tool_options()
        for action in self.tool_actions:
            if action.isCheckable():
                action.setChecked(action == active_action)
            
        # If we switch to another tool or clear tools, cancel any pending interactive operations
        if hasattr(self, 'pending_operation') and self.pending_operation:
            self.pending_operation = None
            self.set_help("명령이 취소되었습니다.")
            
        # Also cancel interactive sketch if active and we switch tools
        if active_action != self.action_line and hasattr(self.viewport, 'disable_interactive_sketch_line'):
            if getattr(self.viewport, 'sketch_line_callback', None) is not None:
                self.viewport.disable_interactive_sketch_line()

        # Cancel interactive trim
        if hasattr(self.viewport, 'disable_interactive_trim') and getattr(self.viewport, 'trim_callback', None):
            self.viewport.disable_interactive_trim()

    def init_menu(self):
        self.action_line = QAction("Line", self)
        self.action_line.setCheckable(True)
        self.action_line.triggered.connect(self.cmd_line)
        self.action_circle = QAction("Circle", self)
        self.action_circle.setCheckable(True)
        self.action_circle.triggered.connect(self.cmd_circle)
        self.action_rect = QAction("Rectangle", self)
        self.action_rect.setCheckable(True)
        self.action_rect.triggered.connect(self.cmd_rect)
        
        self.action_pad = QAction("Extrude", self)
        self.action_pad.setCheckable(True)
        self.action_pad.triggered.connect(self.cmd_pad)
        self.action_extrucut = QAction("ExtruCut", self)
        self.action_extrucut.setCheckable(True)
        self.action_extrucut.triggered.connect(self.cmd_extrucut)
        self.action_revolve = QAction("Revolve", self)
        self.action_revolve.setCheckable(True)
        self.action_revolve.triggered.connect(self.cmd_revolve)
        self.action_revolcut = QAction("RevolCut", self)
        self.action_revolcut.setCheckable(True)
        self.action_revolcut.triggered.connect(self.cmd_revolcut)
        self.action_fillet = QAction("Round", self)
        self.action_fillet.setCheckable(True)
        self.action_fillet.triggered.connect(self.cmd_fillet)
        self.action_chamfer = QAction("Chamfer", self)
        self.action_chamfer.setCheckable(True)
        self.action_chamfer.triggered.connect(self.cmd_chamfer)
        
        self.action_trim_nearest = QAction("Trim Nearest", self)
        self.action_trim_nearest.setCheckable(True)
        self.action_trim_nearest.triggered.connect(self.cmd_trim_nearest)

        self.tool_actions = [
            self.action_line, self.action_circle, self.action_rect,
            self.action_pad, self.action_extrucut, self.action_revolve, self.action_revolcut, self.action_fillet, self.action_chamfer,
            self.action_trim_nearest
        ]

        menubar = self.menuBar()

        # File Menu
        file_menu = menubar.addMenu("File")
        new_action = QAction("New", self)
        new_action.triggered.connect(self.new_model)
        file_menu.addAction(new_action)
        
        open_action = QAction("Open", self)
        open_action.triggered.connect(self.cmd_open)
        file_menu.addAction(open_action)
        
        save_action = QAction("Save", self)
        save_action.triggered.connect(self.cmd_save)
        file_menu.addAction(save_action)
        
        import_menu = file_menu.addMenu("Import")
        import_step_action = QAction("Step", self)
        import_step_action.triggered.connect(self.cmd_import_step)
        import_menu.addAction(import_step_action)
        
        export_menu = file_menu.addMenu("Export")
        export_step_action = QAction("Step", self)
        export_step_action.triggered.connect(self.cmd_export_step)
        export_menu.addAction(export_step_action)
        
        export_snapshot_action = QAction("Snapshot (Image)", self)
        export_snapshot_action.triggered.connect(self.cmd_export_snapshot)
        export_menu.addAction(export_snapshot_action)
        
        close_action = QAction("Close", self)
        close_action.triggered.connect(self.cmd_close)
        file_menu.addAction(close_action)
        
        action_exit = QAction("Exit", self)
        action_exit.triggered.connect(self.close)
        file_menu.addAction(action_exit)

        # Edit Menu
        edit_menu = menubar.addMenu("Edit")
        action_undo = QAction("Undo", self)
        action_undo.setShortcut("Ctrl+Z")
        action_undo.triggered.connect(self.cmd_undo)
        edit_menu.addAction(action_undo)
        
        action_redo = QAction("Redo", self)
        action_redo.setShortcut("Ctrl+Y")
        action_redo.triggered.connect(self.cmd_redo)
        edit_menu.addAction(action_redo)

        trim_menu = edit_menu.addMenu("Trim")
        trim_menu.addAction(self.action_trim_nearest)

        insert_menu = menubar.addMenu("Insert")
        
        sketch_menu = insert_menu.addMenu("Sketch")
        sketch_menu.addAction(self.action_line)
        sketch_menu.addAction(self.action_circle)
        sketch_menu.addAction(self.action_rect)
        
        pad_menu = insert_menu.addMenu("Solid")
        pad_menu.addAction(self.action_pad)
        pad_menu.addAction(self.action_revolve)
        pad_menu.addAction(self.action_extrucut)
        pad_menu.addAction(self.action_revolcut)
        pad_menu.addAction(self.action_fillet)
        pad_menu.addAction(self.action_chamfer)

        view_menu = menubar.addMenu("View")
        self.view_menu = view_menu
        action_reset = QAction("Reset View", self)
        action_reset.triggered.connect(lambda: self.viewport.plotter.reset_camera())
        view_menu.addAction(action_reset)
        
        view_menu.addSeparator()

        action_front = QAction("Front", self)
        action_front.triggered.connect(self.viewport.view_front)
        view_menu.addAction(action_front)
        
        action_top = QAction("Top", self)
        action_top.triggered.connect(self.viewport.view_top)
        view_menu.addAction(action_top)

        action_left = QAction("Left", self)
        action_left.triggered.connect(self.viewport.view_left)
        view_menu.addAction(action_left)

        action_right = QAction("Right", self)
        action_right.triggered.connect(self.viewport.view_right)
        view_menu.addAction(action_right)

        action_iso = QAction("Iso", self)
        action_iso.triggered.connect(self.viewport.view_iso)
        view_menu.addAction(action_iso)

        self.view_menu.addSeparator()
        
        self.right_dock = QDockWidget("Tools", self)
        self.right_dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self.right_dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetFloatable | QDockWidget.DockWidgetFeature.DockWidgetMovable)
        
        tools_widget = QWidget()
        tools_widget.setMinimumWidth(90)
        dock_layout = QVBoxLayout(tools_widget)
        dock_layout.setContentsMargins(2, 2, 2, 2)
        dock_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        # --- Sketch Plane & Selection Area ---
        top_layout = QVBoxLayout()
        
        plane_layout = QVBoxLayout()
        plane_layout.addWidget(QLabel("Sketch:"))
        
        self.plane_group = QButtonGroup(self)
        
        self.plane_btns = {}
        planes = ["XYZ", "XY", "YZ", "ZX", "Face"]
        
        for p in planes:
            btn = PlaneButton(p, self.on_plane_changed)
            if p == "XYZ":
                btn.is_active = True
                btn.update_style()
            self.plane_btns[p] = btn
            plane_layout.addWidget(btn)
        top_layout.addLayout(plane_layout)
        
        sel_layout = QVBoxLayout()
        sel_layout.addWidget(QLabel("Selection:"))
        self.selection_mode_combo = SelectionModeWidget()
        sel_layout.addWidget(self.selection_mode_combo)
        top_layout.addLayout(sel_layout)
        
        dock_layout.addLayout(top_layout)
        dock_layout.addWidget(QFrame(frameShape=QFrame.Shape.HLine))
        
        active_tool_css = """
        QToolButton {
            border: 2px solid transparent;
            border-radius: 3px;
        }
        QToolButton:checked {
            color: #0044cc;
            background-color: #e0e0e0;
            border: 2px solid #0044cc;
            border-radius: 3px;
        }
        """
        
        sketch_dock_toolbar = QToolBar("Sketch")
        sketch_dock_toolbar.setStyleSheet(active_tool_css)
        sketch_dock_toolbar.setOrientation(Qt.Orientation.Vertical)
        sketch_dock_toolbar.addAction(self.action_line)
        sketch_dock_toolbar.addAction(self.action_circle)
        sketch_dock_toolbar.addAction(self.action_rect)
        sketch_dock_toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        dock_layout.addWidget(sketch_dock_toolbar)
        
        dock_layout.addWidget(QFrame(frameShape=QFrame.Shape.HLine))
        
        feat_dock_toolbar = QToolBar("Feature")
        feat_dock_toolbar.setStyleSheet(active_tool_css)
        feat_dock_toolbar.setOrientation(Qt.Orientation.Vertical)
        feat_dock_toolbar.addAction(self.action_pad)
        feat_dock_toolbar.addAction(self.action_revolve)
        feat_dock_toolbar.addAction(self.action_extrucut)
        feat_dock_toolbar.addAction(self.action_revolcut)
        feat_dock_toolbar.addAction(self.action_fillet)
        feat_dock_toolbar.addAction(self.action_chamfer)
        feat_dock_toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        dock_layout.addWidget(feat_dock_toolbar)
        
        dock_layout.addWidget(QFrame(frameShape=QFrame.Shape.HLine))
        
        edit_dock_toolbar = QToolBar("Edit")
        edit_dock_toolbar.setStyleSheet(active_tool_css)
        edit_dock_toolbar.setOrientation(Qt.Orientation.Vertical)
        edit_dock_toolbar.addAction(self.action_trim_nearest)
        edit_dock_toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        dock_layout.addWidget(edit_dock_toolbar)
        
        dock_layout.addWidget(QFrame(frameShape=QFrame.Shape.HLine))
        self.tool_options_layout = QVBoxLayout()
        dock_layout.addLayout(self.tool_options_layout)
        dock_layout.addStretch()
        
        self.right_dock.setWidget(tools_widget)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.right_dock)
        self.right_dock.show()
        
        self.view_menu.addAction(self.right_dock.toggleViewAction())

    def init_tree_view(self):
        self.dock = QDockWidget("Specification Tree", self)
        self.dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self.view_menu.addAction(self.dock.toggleViewAction())

        self.tree_view = QTreeView()
        self.tree_model = QStandardItemModel()
        self.tree_model.setHorizontalHeaderLabels(['PartBody'])
        self.tree_view.setModel(self.tree_model)
        self.tree_view.selectionModel().selectionChanged.connect(self.on_tree_selection)
        self.tree_model.itemChanged.connect(self.on_tree_item_changed)

        self.root_node = self.tree_model.invisibleRootItem()
        self.part_body = QStandardItem("Part1")
        
        self.planes = QStandardItem("Origin Planes")
        self.planes.appendRow(QStandardItem("XY Plane"))
        self.planes.appendRow(QStandardItem("YZ Plane"))
        self.planes.appendRow(QStandardItem("ZX Plane"))
        
        self.part_body.appendRow(self.planes)
        self.root_node.appendRow(self.part_body)
        
        self.tree_view.expandAll()
        self.tree_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree_view.customContextMenuRequested.connect(self.on_tree_context_menu)
        self.dock.setWidget(self.tree_view)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.dock)

    def on_tree_context_menu(self, position):
        index = self.tree_view.indexAt(position)
        if not index.isValid(): return
        item = self.tree_model.itemFromIndex(index)
        if not item: return
        parent = item.parent()
        if parent == self.part_body:
            row = item.row()
            op_index = row - 1
            if 0 <= op_index < len(self.modeler.operations):
                menu = QMenu()
                delete_action = QAction("Delete Feature", self)
                delete_action.triggered.connect(lambda: self.delete_feature(row, op_index))
                menu.addAction(delete_action)
                menu.exec(self.tree_view.viewport().mapToGlobal(position))

    def delete_feature(self, row, op_index):
        self.part_body.removeRow(row)
        self.modeler.operations.pop(op_index)
        self.modeler.rebuild()
        self.update_view()
        self.set_help("해당 피처가 삭제되었습니다.")

    def on_tree_selection(self, selected, deselected):
        indexes = selected.indexes()
        if indexes:
            item = self.tree_model.itemFromIndex(indexes[0])
            if item:
                text = item.text()
                if text in ["XY Plane", "YZ Plane", "ZX Plane"]:
                    plane = text.split(" ")[0]
                    self.on_plane_changed(plane)

    def on_tree_item_changed(self, item):
        self.tree_model.itemChanged.disconnect(self.on_tree_item_changed)
        try:
            parent = item.parent()
            if parent == self.part_body:
                row = item.row()
                op_index = row - 1
                if 0 <= op_index < len(self.modeler.operations):
                    new_text = item.text()
                    op = self.modeler.operations[op_index]
                    t = op["type"]
                    
                    changed = False
                    if t == "sketch_rect":
                        m = re.search(r"Rect ([\d\.]+)x([\d\.]+)", new_text)
                        if m:
                            op["params"]["width"] = float(m.group(1))
                            op["params"]["height"] = float(m.group(2))
                            changed = True
                    elif t == "sketch_circle":
                        m = re.search(r"R=([\d\.]+)", new_text)
                        if m:
                            op["params"]["radius"] = float(m.group(1))
                            changed = True
                    elif t == "pad":
                        m = re.search(r"Pad \(([-]?[\d\.]+)mm\)", new_text)
                        if m:
                            op["params"]["distance"] = float(m.group(1))
                            changed = True
                    elif t == "fillet":
                        m = re.search(r"R=([\d\.]+)", new_text)
                        if m:
                            op["params"]["radius"] = float(m.group(1))
                            changed = True
                    elif t == "chamfer":
                        m = re.search(r"D=([\d\.]+)", new_text)
                        if m:
                            op["params"]["distance"] = float(m.group(1))
                            changed = True
                            
                    if changed:
                        self.modeler.rebuild()
                        self.update_view()
                        self.set_help("모델 트리의 수치가 변경되어 형상을 업데이트했습니다.")
        finally:
            self.tree_model.itemChanged.connect(self.on_tree_item_changed)

    def init_viewport(self):
        self.viewport = CADViewer(self)
        self.setCentralWidget(self.viewport)
        self.viewport.enable_edge_picking(self.on_element_picked)
        self.selected_points = []
        self.selected_faces_stls = []
        self.pending_operation = None

    def on_element_picked(self, point):
        if point is None: return
        
        # Convert numpy ndarray to standard python float tuple for JSON serialization
        pt = (float(point[0]), float(point[1]), float(point[2]))
        
        modifiers = QApplication.keyboardModifiers()
        is_ctrl = bool(modifiers & Qt.KeyboardModifier.ControlModifier)
        
        if not is_ctrl:
            self.selected_points = []
            for f in getattr(self, 'selected_faces_stls', []):
                if os.path.exists(f): os.unlink(f)
            self.selected_faces_stls = []
            self.viewport.highlight_edges([]) # clear highlights
            
        mode = self.selection_mode_combo.currentText()
        
        if mode == "Edge":
            self.selected_points.append(pt)
            all_edge_points = []
            for p in self.selected_points:
                edge_pts = self.modeler.get_nearest_edge_points(p)
                if edge_pts:
                    all_edge_points.append(edge_pts)
            if all_edge_points:
                self.viewport.highlight_edges(all_edge_points)
                self.set_help(f"총 {len(self.selected_points)}개의 선이 선택되었습니다.")
                
                # If there's a pending operation, apply it immediately
                if getattr(self, 'pending_operation', None):
                    op = self.pending_operation
                    self.pending_operation = None
                    if op["type"] == "fillet":
                        self.modeler.add_operation("fillet", radius=op["radius"], points=self.selected_points.copy())
                        self.update_tree(f"EdgeFillet (R={op['radius']})")
                        self.selected_points = []
                        self.update_view()
                        self.set_help(f"방금 라운드(R={op['radius']})를 실행했습니다.")
                    elif op["type"] == "chamfer":
                        self.modeler.add_operation("chamfer", distance=op["distance"], points=self.selected_points.copy())
                        self.update_tree(f"Chamfer (D={op['distance']})")
                        self.selected_points = []
                        self.update_view()
                        self.set_help(f"방금 모따기(D={op['distance']})를 실행했습니다.")
                    self.set_active_tool(None)
            else:
                self.set_help("선을 찾을 수 없습니다.")
        elif mode == "Face":
            if self.current_plane == "Face":
                normal, center = self.modeler.get_face_normal_and_center(pt)
                if normal:
                    self.selected_sketch_face_pt = pt
                    self.viewport.align_camera_to_normal(normal, center)
                    self.set_help("선택한 면이 스케치 평면으로 지정되었습니다. 정면으로 뷰가 정렬되었습니다.")
            
            temp_file = tempfile.NamedTemporaryFile(suffix=".stl", delete=False)
            temp_file.close()
            success = self.modeler.get_nearest_face_stl(pt, temp_file.name)
            if success and os.path.getsize(temp_file.name) > 84:
                self.selected_faces_stls.append(temp_file.name)
                self.viewport.highlight_faces(self.selected_faces_stls)
                if self.current_plane != "Face":
                    self.set_help(f"총 {len(self.selected_faces_stls)}개의 면이 선택되었습니다.")
            else:
                if os.path.exists(temp_file.name): os.unlink(temp_file.name)
                self.set_help("면을 찾을 수 없습니다.")

    def update_tree(self, op_name):
        item = QStandardItem(op_name)
        self.part_body.appendRow(item)
        self.tree_view.expandAll()

    def update_view(self):
        self.viewport.clear_all()
        self.viewport.highlighted_actor_names = []
        for f in getattr(self, 'selected_faces_stls', []):
            if os.path.exists(f): os.unlink(f)
        self.selected_faces_stls = []
        if self.modeler.result_shape:
            # Export to temp STL and load with PyVista
            temp_file = tempfile.NamedTemporaryFile(suffix=".stl", delete=False)
            temp_file.close()
            has_solid = False
            try:
                success = self.modeler.export_stl(temp_file.name)
                if success and os.path.getsize(temp_file.name) > 84:
                    mesh = pv.read(temp_file.name)
                    self.viewport.add_mesh(mesh, "model", color="#B0C4DE")
                    has_solid = True
                    
                # Add B-Rep Edges
                brep_edges = self.modeler.get_all_edges_points()
                if brep_edges:
                    self.viewport.add_brep_edges(brep_edges, color="black" if has_solid else "blue")
            except Exception as e:
                print(f"Error updating view: {e}")
            finally:
                if os.path.exists(temp_file.name):
                    os.unlink(temp_file.name)
            
            self.viewport.plotter.render()

    # --- Commands ---
    def new_model(self):
        self.modeler = CADModeler()
        self.part_body.removeRows(1, self.part_body.rowCount() - 1)
        self.update_view()

    def on_plane_changed(self, plane):
        self.current_plane = plane
        for p, btn in self.plane_btns.items():
            btn.is_active = (p == plane)
            btn.update_style()
        self.set_help(f"스케치 평면이 {plane}로 변경되었습니다.")
        
        # If Sketch: Face is selected, auto-switch selection mode to Face
        if plane == "Face" and hasattr(self, 'selection_mode_combo'):
            self.selection_mode_combo.setCurrentText("Face")
        self.viewport.set_camera_to_plane(plane)

    def cmd_open(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Open Project", "", "CAD Files (*.cad)")
        if file_path:
            if self.modeler.load_project(file_path):
                self.update_view()
                # Rebuild tree view
                while self.part_body.rowCount() > 1:
                    self.part_body.removeRow(1)
                for op in self.modeler.operations:
                    self.update_tree(op['type'])
                self.set_help("프로젝트를 성공적으로 불러왔습니다.")
            else:
                self.show_warning("오류", "프로젝트를 불러오는데 실패했습니다.")

    def cmd_close(self):
        self.modeler.operations = []
        self.modeler.redo_stack = []
        self.modeler.rebuild()
        self.update_view()
        while self.part_body.rowCount() > 1:
            self.part_body.removeRow(1)
        self.set_help("현재 모델을 닫았습니다.")

    def cmd_trim_nearest(self):
        if not self.current_plane:
            self.set_help("먼저 스케치 평면을 선택해주세요 (Top/Front/Right).")
            return
            
        self.set_active_tool(None)
        self.set_help("자를 선을 클릭하세요. 우클릭 시 취소됩니다.")
        
        def on_trim_click(pt):
            if pt is None:
                self.set_help("자르기가 취소되었습니다.")
                self.set_active_tool(None)
                return
                
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(0, lambda: process_trim(pt))
            
        def process_trim(pt):
            try:
                # 1. Disable the picking BEFORE geometry changes to prevent VTK segfaults
                self.viewport.disable_interactive_trim()
                
                # 2. Modify geometry
                success = self.modeler.trim_sketch_nearest(pt)
                if success:
                    self.update_view()
                    self.set_help("선이 잘렸습니다. 계속해서 자를 선을 클릭하세요.")
                else:
                    self.set_help("클릭한 위치 근처에 자를 선이 없습니다.")
                    
                # 3. Re-enable picking
                self.viewport.enable_interactive_trim(on_trim_click)
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.set_help(f"오류가 발생했습니다: {e}")
                self.viewport.enable_interactive_trim(on_trim_click)
                
        self.viewport.enable_interactive_trim(on_trim_click)

    def cmd_undo(self):
        op = self.modeler.undo()
        if op:
            self.update_view()
            if self.part_body.rowCount() > 1:
                self.part_body.removeRow(self.part_body.rowCount() - 1)
            self.set_help("실행 취소(Undo) 완료.")
        else:
            self.set_help("취소할 작업이 없습니다.")

    def cmd_redo(self):
        op = self.modeler.redo()
        if op:
            self.update_view()
            self.update_tree(op["type"])
            self.set_help("다시 실행(Redo) 완료.")
        else:
            self.set_help("다시 실행할 작업이 없습니다.")

    def cmd_save(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Project", "", "CAD Files (*.cad)")
        if file_path:
            if not file_path.lower().endswith('.cad'):
                file_path += '.cad'
            if self.modeler.save_project(file_path):
                self.set_help("프로젝트가 성공적으로 저장되었습니다.")
            else:
                self.show_warning("오류", "프로젝트 저장에 실패했습니다.")

    def cmd_import_step(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Import STEP", "", "STEP Files (*.step *.stp)")
        if file_path:
            success = self.modeler.import_step(file_path)
            if success:
                self.update_view()
                self.update_tree("Import STEP")
                self.set_help("STEP 파일이 성공적으로 불러와졌습니다.")
            else:
                self.show_warning("오류", "STEP 파일을 불러오는데 실패했습니다.")

    def cmd_export_step(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Export STEP", "", "STEP Files (*.step *.stp)")
        if file_path:
            if not file_path.lower().endswith(('.step', '.stp')):
                file_path += '.step'
            success = self.modeler.export_step(file_path)
            if success:
                self.set_help("STEP 파일이 성공적으로 저장되었습니다.")
            else:
                self.show_warning("오류", "STEP 파일 저장에 실패했습니다. 모델이 있는지 확인하세요.")

    def cmd_export_snapshot(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Snapshot", "", "PNG Image (*.png);;JPEG Image (*.jpg);;BMP Image (*.bmp)")
        if file_path:
            try:
                self.viewport.plotter.screenshot(file_path)
                self.set_help(f"스냅샷이 저장되었습니다: {file_path}")
            except Exception as e:
                self.show_warning("오류", f"스냅샷 저장에 실패했습니다:\n{str(e)}")

    def get_plane_param(self):
        if self.current_plane == "Face":
            if not getattr(self, 'selected_sketch_face_pt', None):
                self.set_active_tool(None)
                self.show_warning("안내", "스케치 평면(Face)을 3D 화면에서 먼저 클릭하여 지정해주세요.")
                return None
            return {"type": "Face", "point": self.selected_sketch_face_pt}
        elif self.current_plane == "XYZ":
            self.set_active_tool(None)
            self.show_warning("안내", "XYZ 좌표계는 3D 뷰잉 모드입니다.\n스케치를 하려면 먼저 XY, YZ, ZX 또는 Face 평면을 선택해주세요.")
            return None
        return self.current_plane

    def cmd_rect(self):
        plane_param = self.get_plane_param()
        if not plane_param: return
        self.set_active_tool(self.action_rect)
        
        def on_ok(values):
            w, h = values
            self.modeler.add_operation("sketch_rect", width=w, height=h, plane=plane_param)
            self.update_tree(f"Sketch (Rect {w}x{h} on {self.current_plane})")
            self.modeler.rebuild()
            self.update_view()
            self.set_help(f"방금 {self.current_plane} 평면에 사각형 스케치({w}x{h})를 생성했습니다.")
            self.set_active_tool(None)
            
        def on_cancel():
            self.set_active_tool(None)
            
        self.show_tool_options("Sketch Rectangle", ["Width (X):", "Height (Y):"], [10.0, 10.0], on_ok, on_cancel)

    def cmd_circle(self):
        plane_param = self.get_plane_param()
        if not plane_param: return
        self.set_active_tool(self.action_circle)
        
        def on_ok(values):
            r = values[0]
            self.modeler.add_operation("sketch_circle", radius=r, plane=plane_param)
            self.update_tree(f"Sketch (Circle R={r} on {self.current_plane})")
            self.modeler.rebuild()
            self.update_view()
            self.set_help(f"방금 {self.current_plane} 평면에 반지름 {r}mm 원 스케치를 생성했습니다.")
            self.set_active_tool(None)
            
        def on_cancel():
            self.set_active_tool(None)
            
        self.show_tool_options("Sketch Circle", ["Radius:"], [5.0], on_ok, on_cancel)
            
    def cmd_line(self):
        plane_param = self.get_plane_param()
        if not plane_param: return
        
        origin, normal = self.modeler.get_active_plane_transform()
        
        if hasattr(self.viewport, 'disable_interactive_pad'):
            self.viewport.disable_interactive_pad()
            
        self.set_active_tool(self.action_line)
            
        def on_line_drawn(pts):
            self.set_active_tool(None)
            
            if not pts or len(pts) < 2:
                self.set_help("스케치가 취소되었습니다.")
                return
                
            self.modeler.add_operation("sketch_line", points=pts, plane=plane_param)
            self.update_tree(f"Sketch (Line on {self.current_plane})")
            self.update_view()
            self.set_active_tool(None)
            self.set_help("선 스케치가 완료되었습니다.")
            
        self.viewport.enable_interactive_sketch_line(origin, normal, on_line_drawn)
        self.set_help("점들을 클릭하여 선을 그리고, 마우스 우클릭으로 마칩니다.")

    def cmd_pad(self):
        self.set_active_tool(self.action_pad)
        initial_distance = 10.0
        self.modeler.add_operation("pad", distance=initial_distance)
        success = self.modeler.rebuild()
        if not success:
            self.set_help("오류: 닫힌 형상(Close Line)이 아니거나 스케치가 유효하지 않습니다.")
            self.modeler.undo()
            self.update_view()
            self.set_active_tool(None)
            return
            
        self.update_view()
        
        center, normal = self.modeler.get_active_plane_transform()
        
        def on_distance_changed(d):
            if d == 0: return
            self.modeler.operations[-1]["params"]["distance"] = d
            self.modeler.rebuild()
            self.update_view()
            if hasattr(self, 'interactive_pad_dialog') and self.interactive_pad_dialog:
                self.interactive_pad_dialog.set_distance(d)
            self.viewport.update_interactive_pad_widget(d)
                
        def on_ok(d):
            self.viewport.disable_interactive_pad()
            self.set_active_tool(None)
            if d == 0:
                self.modeler.operations.pop()
                self.show_warning("안내", "돌출 두께는 0이 될 수 없습니다.")
                self.modeler.rebuild()
                self.update_view()
                return
            self.update_tree(f"Pad ({d}mm)")
            self.set_help(f"방금 {d}mm 두께로 돌출시켰습니다.")
            self.interactive_pad_dialog = None
            
        def on_cancel():
            self.viewport.disable_interactive_pad()
            self.set_active_tool(None)
            self.modeler.operations.pop()
            self.modeler.rebuild()
            self.update_view()
            self.interactive_pad_dialog = None

        self.interactive_pad_dialog = InteractivePadDialog(
            self, initial_distance, on_distance_changed, on_ok, on_cancel)
            
        self.viewport.enable_interactive_pad(center, normal, initial_distance, on_distance_changed)
        self.interactive_pad_dialog.show()
            
    def cmd_extrucut(self):
        self.set_active_tool(self.action_extrucut)
        def on_ok(values):
            d = values[0]
            self.modeler.add_operation("extru_cut", distance=d)
            success = self.modeler.rebuild()
            if not success:
                self.set_help("오류: 유효한 스케치가 없거나 닫힌 선(Close Line)이 아닙니다.")
                self.modeler.undo()
                self.update_view()
            else:
                self.update_tree(f"ExtruCut ({d}mm)")
                self.update_view()
                self.set_help(f"돌출 컷({d}mm)을 적용했습니다.")
            self.set_active_tool(None)
        self.active_dialog = NonModalInputDialog(None, "Extrude Cut", ["Distance:"], [10.0], on_ok, lambda: self.set_active_tool(None))
        QTimer.singleShot(100, self.active_dialog.show)

    def cmd_revolve(self):
        self.set_active_tool(self.action_revolve)
        def on_ok(angle, axis):
            self.modeler.add_operation("revolve", angle=angle, axis=axis)
            success = self.modeler.rebuild()
            if not success:
                self.set_help("오류: 유효한 스케치가 없거나 닫힌 선(Close Line)이 아닙니다.")
                self.modeler.undo()
                self.update_view()
            else:
                self.update_tree(f"Revolve ({axis}-Axis, {angle}deg)")
                self.update_view()
                self.set_help(f"스케치를 {axis}축을 중심으로 {angle}도 회전했습니다.")
            self.set_active_tool(None)
        self.active_dialog = RevolveDialog(None, title="Revolve", on_ok=on_ok, on_cancel=lambda: self.set_active_tool(None))
        QTimer.singleShot(100, self.active_dialog.show)

    def cmd_revolcut(self):
        self.set_active_tool(self.action_revolcut)
        def on_ok(angle, axis):
            self.modeler.add_operation("revol_cut", angle=angle, axis=axis)
            success = self.modeler.rebuild()
            if not success:
                self.set_help("오류: 유효한 스케치가 없거나 닫힌 선(Close Line)이 아닙니다.")
                self.modeler.undo()
                self.update_view()
            else:
                self.update_tree(f"RevolCut ({axis}-Axis, {angle}deg)")
                self.update_view()
                self.set_help(f"스케치를 {axis}축을 중심으로 회전 컷({angle}도) 적용했습니다.")
            self.set_active_tool(None)
        self.active_dialog = RevolveDialog(None, title="RevolCut", on_ok=on_ok, on_cancel=lambda: self.set_active_tool(None))
        QTimer.singleShot(100, self.active_dialog.show)

    def cmd_fillet(self):
        self.set_active_tool(self.action_fillet)
        def on_ok(values):
            r = values[0]
            if getattr(self, 'selected_points', []):
                self.modeler.add_operation("fillet", radius=r, points=self.selected_points.copy())
                self.update_tree(f"EdgeFillet (R={r})")
                self.selected_points = []
                self.update_view()
                self.set_help(f"선택한 모서리에 라운드(R={r}) 처리를 했습니다.")
            else:
                self.pending_operation = {"type": "fillet", "radius": r}
                self.selection_mode_combo.setCurrentText("Edge")
                self.set_help(f"라운드(R={r})를 적용할 선(Edge)을 화면에서 클릭하세요.")
            self.set_active_tool(None)
        self.active_dialog = NonModalInputDialog(None, "Edge Fillet", ["Radius:"], [2.0], on_ok, lambda: self.set_active_tool(None))
        QTimer.singleShot(100, self.active_dialog.show)
            
    def cmd_chamfer(self):
        self.set_active_tool(self.action_chamfer)
        def on_ok(values):
            d = values[0]
            if getattr(self, 'selected_points', []):
                self.modeler.add_operation("chamfer", distance=d, points=self.selected_points.copy())
                self.update_tree(f"Chamfer (D={d})")
                self.selected_points = []
                self.update_view()
                self.set_help(f"선택한 모서리에 모따기(D={d}) 처리를 했습니다.")
            else:
                self.pending_operation = {"type": "chamfer", "distance": d}
                self.selection_mode_combo.setCurrentText("Edge")
                self.set_help(f"모따기(D={d})를 적용할 선(Edge)을 화면에서 클릭하세요.")
            self.set_active_tool(None)
        self.active_dialog = NonModalInputDialog(None, "Chamfer", ["Distance:"], [2.0], on_ok, lambda: self.set_active_tool(None))
        QTimer.singleShot(100, self.active_dialog.show)

    def cmd_fit_all(self):
        self.viewport.fit_all()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = CADMainWindow()
    window.showMaximized()
    sys.exit(app.exec())
