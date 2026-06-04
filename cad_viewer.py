from PyQt6.QtWidgets import QWidget, QVBoxLayout
import pyvista as pv
from pyvistaqt import QtInteractor

class CADViewer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        # Initialize PyVista QtInteractor
        self.plotter = QtInteractor(self)
        self.layout.addWidget(self.plotter.interactor)
        
        # Set background color to gray
        self.plotter.set_background("gray")
        
        # Add axes actor (the XYZ triad in the corner) at 1/2 size
        self.plotter.add_axes(viewport=(0, 0, 0.1, 0.1))
        

        
        # Add axes at origin (scales with zoom, no labels)
        self.origin_axes = self.plotter.add_axes_at_origin(line_width=4, labels_off=True)
        self.origin_axes.SetTotalLength(20, 20, 20)
        
        # Set camera to a nice isometric view
        self.plotter.view_isometric()

    def add_mesh(self, mesh, name, color="lightblue"):
        """Add a pyvista mesh to the scene with a given name."""
        self.plotter.add_mesh(mesh, name=name, color=color, show_edges=False, pickable=False)
        self.plotter.reset_camera()
        
    def add_brep_edges(self, edge_points_list, color="black"):
        """Draw true topological edges from CAD modeler"""
        self.brep_edge_color = color
        for i, points in enumerate(edge_points_list):
            if points and len(points) > 1:
                mesh = pv.lines_from_points(points)
                self.plotter.add_mesh(mesh, name=f"brep_edge_{i}", color=color, line_width=3, render_lines_as_tubes=False, pickable=True)
        
    def remove_mesh(self, name):
        """Remove a mesh by name."""
        self.plotter.remove_actor(name)
        
    def clear_all(self):
        self.plotter.clear_actors()
        self.plotter.add_axes(viewport=(0, 0, 0.1, 0.1))
        self.origin_axes = self.plotter.add_axes_at_origin(line_width=4, labels_off=True)
        self.origin_axes.SetTotalLength(20, 20, 20)
        
    def fit_all(self):
        """Reset camera to fit all objects"""
        self.plotter.reset_camera()

    def set_camera_to_plane(self, plane):
        """Rotate camera to face the selected plane orthographically."""
        if plane == "XY":
            self.plotter.view_xy()
        elif plane == "YZ":
            self.plotter.view_yz()
        elif plane == "ZX":
            self.plotter.view_xz()
        self.plotter.render()
        
    def view_front(self):
        self.plotter.view_xz()
        self.plotter.render()
        
    def view_top(self):
        self.plotter.view_xy()
        self.plotter.render()
        
    def view_left(self):
        self.plotter.view_yz(negative=True)
        self.plotter.render()
        
    def view_right(self):
        self.plotter.view_yz()
        self.plotter.render()
        
    def view_iso(self):
        self.plotter.view_isometric()
        self.plotter.render()
        
    def align_camera_to_normal(self, normal, center):
        """Align camera to look directly at the face."""
        nx, ny, nz = normal
        cx, cy, cz = center
        
        # Calculate appropriate UP vector
        up = (0, 1, 0)
        if abs(ny) > 0.99:
            up = (0, 0, 1)
            
        dist = self.plotter.camera.distance
        if dist == 0:
            dist = 50.0
            
        self.plotter.camera.position = (cx + nx * dist, cy + ny * dist, cz + nz * dist)
        self.plotter.camera.focal_point = (cx, cy, cz)
        self.plotter.camera.up = up
        
        self.plotter.enable_parallel_projection()
        self.plotter.render()

    def enable_edge_picking(self, callback):
        """Enable picking on the mesh and return the 3D point."""
        def _on_pick(picked_point):
            if picked_point is not None and len(picked_point) == 3:
                callback(picked_point)
        self.plotter.enable_surface_point_picking(callback=_on_pick, show_message=False, left_clicking=True, show_point=False)

    def enable_interactive_trim(self, callback):
        self.trim_callback = callback
        
        def _on_pick(picked_point):
            if picked_point is not None and len(picked_point) == 3:
                if self.trim_callback:
                    self.trim_callback(picked_point)
                    
        self.plotter.enable_surface_point_picking(callback=_on_pick, show_message=False, left_clicking=True, show_point=False)
        self._trim_right_click_observer = self.plotter.iren.add_observer("RightButtonPressEvent", self._on_trim_right_click)
        self._trim_move_observer = self.plotter.iren.add_observer("MouseMoveEvent", self._on_trim_move)

    def _on_trim_move(self, obj, event):
        click_pos = self.plotter.iren.get_event_position()
        import vtk
        picker = vtk.vtkPropPicker()
        picker.Pick(click_pos[0], click_pos[1], 0, self.plotter.renderer)
        actor = picker.GetActor()
        
        original_color = getattr(self, 'brep_edge_color', 'blue')
        for name, a in self.plotter.actors.items():
            if name.startswith("brep_edge_"):
                if a == actor:
                    a.prop.color = "red"
                else:
                    a.prop.color = original_color
        self.plotter.render()

    def _on_trim_right_click(self, obj, event):
        if hasattr(self, 'trim_callback'):
            cb = self.trim_callback
            self.disable_interactive_trim()
            if cb:
                cb(None)

    def disable_interactive_trim(self):
        if hasattr(self, '_trim_right_click_observer'):
            self.plotter.iren.remove_observer(self._trim_right_click_observer)
            del self._trim_right_click_observer
        if hasattr(self, '_trim_move_observer'):
            self.plotter.iren.remove_observer(self._trim_move_observer)
            del self._trim_move_observer
            
        # Reset color
        original_color = getattr(self, 'brep_edge_color', 'blue')
        for name, a in self.plotter.actors.items():
            if name.startswith("brep_edge_"):
                a.prop.color = original_color
        self.plotter.render()
        
        self.plotter.disable_picking()
        self.trim_callback = None

    def enable_interactive_pad(self, center, normal, initial_distance, callback):
        import numpy as np
        self.interactive_pad_callback = callback
        self.pad_normal = np.array(normal)
        self.pad_center = np.array(center)
        self.pad_distance = initial_distance
        
        self.update_interactive_pad_widget(initial_distance)
        
        self._dragging_pad = False
        self._pad_press_observer = self.plotter.iren.add_observer("LeftButtonPressEvent", self._on_pad_press)
        self._pad_move_observer = self.plotter.iren.add_observer("MouseMoveEvent", self._on_pad_move)
        self._pad_release_observer = self.plotter.iren.add_observer("LeftButtonReleaseEvent", self._on_pad_release)
        
    def _on_pad_press(self, obj, event):
        click_pos = self.plotter.iren.get_event_position()
        import vtk
        
        picker = vtk.vtkPropPicker()
        picker.Pick(click_pos[0], click_pos[1], 0, self.plotter.renderer)
        if picker.GetActor():
            self._dragging_pad = True
            self._last_mouse_y = click_pos[1]
            
    def _on_pad_move(self, obj, event):
        if hasattr(self, '_dragging_pad') and self._dragging_pad:
            click_pos = self.plotter.iren.get_event_position()
            dy = click_pos[1] - self._last_mouse_y
            self._last_mouse_y = click_pos[1]
            
            delta = dy * 0.5  # Sensitivity
            self.pad_distance += delta
            
            self.update_interactive_pad_widget(self.pad_distance)
            if self.interactive_pad_callback:
                self.interactive_pad_callback(self.pad_distance)
                
    def _on_pad_release(self, obj, event):
        if hasattr(self, '_dragging_pad') and self._dragging_pad:
            self._dragging_pad = False
            
    def update_interactive_pad_widget(self, distance):
        self.pad_distance = distance
            
    def disable_interactive_pad(self):
        if hasattr(self, '_pad_press_observer'):
            self.plotter.iren.remove_observer(self._pad_press_observer)
            self.plotter.iren.remove_observer(self._pad_move_observer)
            self.plotter.iren.remove_observer(self._pad_release_observer)
        self.interactive_pad_callback = None
        
    def _get_plane_intersection(self, click_pos, origin, normal):
        import vtk
        import numpy as np
        coordinate = vtk.vtkCoordinate()
        coordinate.SetCoordinateSystemToDisplay()
        coordinate.SetValue(click_pos[0], click_pos[1], 0.0)
        near_pt = np.array(coordinate.GetComputedWorldValue(self.plotter.renderer))
        coordinate.SetValue(click_pos[0], click_pos[1], 1.0)
        far_pt = np.array(coordinate.GetComputedWorldValue(self.plotter.renderer))
        ray_dir = far_pt - near_pt
        normal = np.array(normal)
        origin = np.array(origin)
        denom = np.dot(ray_dir, normal)
        if abs(denom) < 1e-6: return None
        t = np.dot(origin - near_pt, normal) / denom
        return near_pt + t * ray_dir

    def enable_interactive_sketch_line(self, origin, normal, callback):
        self.sketch_origin = origin
        self.sketch_normal = normal
        self.sketch_line_callback = callback
        self.sketch_line_pts = []
        
        self.temp_line_actor = None
        self.temp_point_actor = None
        self.temp_confirmed_lines_actor = None
        
        self._sketch_line_press_observer = self.plotter.iren.add_observer("LeftButtonPressEvent", self._on_sketch_line_press)
        self._sketch_line_right_click_observer = self.plotter.iren.add_observer("RightButtonPressEvent", self._on_sketch_line_press)
        self._sketch_line_move_observer = self.plotter.iren.add_observer("MouseMoveEvent", self._on_sketch_line_move)
        self._sketch_line_keypress_observer = self.plotter.iren.add_observer("KeyPressEvent", self._on_sketch_line_keypress)

    def _on_sketch_line_keypress(self, obj, event):
        key = self.plotter.iren.interactor.GetKeySym()
        if key == "Escape":
            cb = self.sketch_line_callback
            if len(self.sketch_line_pts) >= 2:
                pts = list(self.sketch_line_pts)
                self.disable_interactive_sketch_line()
                if cb:
                    cb(pts)
            else:
                self.disable_interactive_sketch_line()
                # Also reset the bold font on UI since we cancelled
                if cb:
                    # Pass empty list to indicate cancellation
                    cb([])

    def _on_sketch_line_press(self, obj, event):
        click_pos = self.plotter.iren.get_event_position()
        pt = self._get_plane_intersection(click_pos, self.sketch_origin, self.sketch_normal)
        if pt is None: return
        
        # Right click to finish
        if event == "RightButtonPressEvent":
            cb = self.sketch_line_callback
            if len(self.sketch_line_pts) >= 2:
                pts = list(self.sketch_line_pts)
                self.disable_interactive_sketch_line()
                if cb:
                    cb(pts)
            else:
                self.disable_interactive_sketch_line()
                if cb:
                    cb([])
            return
            
        import pyvista as pv
        if len(self.sketch_line_pts) == 0:
            self.sketch_line_pts.append(pt)
            sphere = pv.Sphere(radius=0.5, center=pt)
            self.temp_point_actor = self.plotter.add_mesh(sphere, color='green')
            self.plotter.render()
        else:
            self.sketch_line_pts.append(pt)
            if hasattr(self, 'temp_confirmed_lines_actor') and self.temp_confirmed_lines_actor:
                self.plotter.remove_actor(self.temp_confirmed_lines_actor)
            lines_mesh = pv.lines_from_points(self.sketch_line_pts)
            self.temp_confirmed_lines_actor = self.plotter.add_mesh(lines_mesh, color="green", line_width=4, render_lines_as_tubes=False)
            self.plotter.render()

    def _on_sketch_line_move(self, obj, event):
        if hasattr(self, 'sketch_line_pts') and len(self.sketch_line_pts) >= 1:
            click_pos = self.plotter.iren.get_event_position()
            pt = self._get_plane_intersection(click_pos, self.sketch_origin, self.sketch_normal)
            if pt is None: return
            
            import pyvista as pv
            if self.temp_line_actor:
                self.plotter.remove_actor(self.temp_line_actor)
            
            last_pt = self.sketch_line_pts[-1]
            line = pv.Line(last_pt, pt)
            self.temp_line_actor = self.plotter.add_mesh(line, color='green', line_width=3)
            self.plotter.render()

    def disable_interactive_sketch_line(self):
        if hasattr(self, '_sketch_line_press_observer'):
            self.plotter.iren.remove_observer(self._sketch_line_press_observer)
            self.plotter.iren.remove_observer(self._sketch_line_move_observer)
            if hasattr(self, '_sketch_line_right_click_observer'):
                self.plotter.iren.remove_observer(self._sketch_line_right_click_observer)
            if hasattr(self, '_sketch_line_keypress_observer'):
                self.plotter.iren.remove_observer(self._sketch_line_keypress_observer)
            del self._sketch_line_press_observer
            del self._sketch_line_move_observer
        if hasattr(self, 'temp_line_actor') and self.temp_line_actor:
            self.plotter.remove_actor(self.temp_line_actor)
        if hasattr(self, 'temp_point_actor') and self.temp_point_actor:
            self.plotter.remove_actor(self.temp_point_actor)
        if hasattr(self, 'temp_confirmed_lines_actor') and self.temp_confirmed_lines_actor:
            self.plotter.remove_actor(self.temp_confirmed_lines_actor)
        self.temp_line_actor = None
        self.temp_point_actor = None
        self.temp_confirmed_lines_actor = None
        self.sketch_line_callback = None
        self.plotter.render()
        self.temp_line_actor = None
        self.temp_point_actor = None
        self.sketch_line_callback = None
        self.plotter.render()
        
    def highlight_edges(self, edges_points_list):
        """Draw red lines along the points for multiple edges"""
        if hasattr(self, 'highlighted_actor_names'):
            for name in self.highlighted_actor_names:
                self.plotter.remove_actor(name)
        self.highlighted_actor_names = []
        
        import pyvista as pv
        for i, points in enumerate(edges_points_list):
            if points and len(points) > 1:
                name = f"highlighted_edge_{i}"
                mesh = pv.lines_from_points(points)
                self.plotter.add_mesh(mesh, name=name, color="red", line_width=5, render_lines_as_tubes=True)
                self.highlighted_actor_names.append(name)
        self.plotter.render()

    def highlight_faces(self, face_stl_paths):
        """Draw red surfaces for multiple faces"""
        if hasattr(self, 'highlighted_actor_names'):
            for name in self.highlighted_actor_names:
                self.plotter.remove_actor(name)
        self.highlighted_actor_names = []
        
        import pyvista as pv
        for i, stl_path in enumerate(face_stl_paths):
            if stl_path:
                try:
                    name = f"highlighted_face_{i}"
                    mesh = pv.read(stl_path)
                    # Compute normals and slightly offset the face to prevent Z-fighting with the original model
                    mesh.compute_normals(inplace=True)
                    mesh.points += mesh.point_normals * 0.05
                    self.plotter.add_mesh(mesh, name=name, color="red")
                    self.highlighted_actor_names.append(name)
                except Exception as e:
                    print(f"Failed to load face STL {stl_path}: {e}")
        self.plotter.render()
