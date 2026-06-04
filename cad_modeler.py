import numpy_patch
import cadquery as cq

# Patch CadQuery HashCode issue for newer OCP versions
if not hasattr(cq.Shape, '_patched_hash'):
    cq.Shape.hashCode = lambda self: hash(self.wrapped)
    cq.Shape.__hash__ = lambda self: hash(self.wrapped)
    cq.Shape._patched_hash = True

import tempfile
import os

class CustomNearestEdgeSelector(cq.Selector):
    def __init__(self, pnt):
        self.pnt = cq.Vector(tuple(float(v) for v in pnt))
    def filter(self, objectList):
        if not objectList: return []
        best_edge = None
        min_dist = float('inf')
        for e in objectList:
            try:
                d = min((e.positionAt(t) - self.pnt).Length for t in (0.0, 0.25, 0.5, 0.75, 1.0))
            except:
                d = (e.Center() - self.pnt).Length
            if d < min_dist:
                min_dist = d
                best_edge = e
        return [best_edge] if best_edge else []

class CustomMultipleEdgesSelector(cq.Selector):
    def __init__(self, pnts):
        self.pnts = [cq.Vector(tuple(float(v) for v in pnt)) for pnt in pnts]
    def filter(self, objectList):
        if not objectList: return []
        selected_edges = []
        for pnt in self.pnts:
            best_edge = None
            min_dist = float('inf')
            for e in objectList:
                try:
                    d = min((e.positionAt(t) - pnt).Length for t in (0.0, 0.25, 0.5, 0.75, 1.0))
                except:
                    d = (e.Center() - pnt).Length
                if d < min_dist:
                    min_dist = d
                    best_edge = e
            if best_edge and best_edge not in selected_edges:
                selected_edges.append(best_edge)
        return selected_edges

class CADModeler:
    def __init__(self):
        self.operations = []
        self.redo_stack = []
        self.result_shape = None
        
    def add_operation(self, op_type, **kwargs):
        self.operations.append({"type": op_type, "params": kwargs})
        self.redo_stack = []  # Clear redo stack when a new operation is performed
        self.rebuild()
        
    def undo(self):
        if not self.operations:
            return None
        op = self.operations.pop()
        self.redo_stack.append(op)
        self.rebuild()
        return op
        
    def redo(self):
        if not self.redo_stack:
            return None
        op = self.redo_stack.pop()
        self.operations.append(op)
        self.rebuild()
        return op
        
    def save_project(self, filepath):
        import json
        try:
            with open(filepath, 'w') as f:
                json.dump(self.operations, f)
            return True
        except Exception as e:
            print("Save error:", e)
            return False

    def load_project(self, filepath):
        import json
        try:
            with open(filepath, 'r') as f:
                self.operations = json.load(f)
            self.rebuild()
            return True
        except Exception as e:
            print("Load error:", e)
            return False
            
    def rebuild(self):
        if not self.operations:
            self.result_shape = None
            return

        current_wp = None
        has_3d = False
        last_op_was_3d = False
        current_plane = "XY"
        
        for op in self.operations:
            t = op["type"]
            p = op["params"]
            prev_wp = current_wp
            
            try:
                # --- Plane Context Switching ---
                if t.startswith("sketch_"):
                    plane = p.get("plane", "XY")
                    
                    if isinstance(plane, dict) and plane.get("type") == "Face":
                        pt = plane.get("point")
                        if pt and has_3d and current_wp is not None:
                            current_wp = current_wp.faces(cq.selectors.NearestToPointSelector(pt)).workplane()
                        current_plane = "Face"
                    else:
                        if current_wp is None or last_op_was_3d or current_plane != plane:
                            current_wp = cq.Workplane(plane, obj=current_wp.val() if has_3d else None)
                        current_plane = plane
                        
                    last_op_was_3d = False

                # --- Sketching ---
                if t == "sketch_rect":
                    current_wp = current_wp.rect(p["width"], p["height"])
                elif t == "sketch_circle":
                    current_wp = current_wp.circle(p["radius"])
                elif t == "sketch_line":
                    if "points" in p and len(p["points"]) > 0:
                        local_pts = []
                        for pt in p["points"]:
                            if len(pt) == 3:
                                vec = cq.Vector(pt[0], pt[1], pt[2])
                                local_pt = current_wp.plane.toLocalCoords(vec)
                                local_pts.append((local_pt.x, local_pt.y))
                            else:
                                local_pts.append(pt)
                                
                        if len(local_pts) > 0:
                            current_wp = current_wp.moveTo(local_pts[0][0], local_pts[0][1])
                            for pt in local_pts[1:]:
                                current_wp = current_wp.lineTo(pt[0], pt[1])
                
                # --- 3D Features ---
                elif t == "pad":
                    current_wp = current_wp.extrude(p["distance"])
                    has_3d = True
                    last_op_was_3d = True
                elif t == "shaft":
                    current_wp = current_wp.revolve(360, (0,0,0), (0,1,0))
                    has_3d = True
                    last_op_was_3d = True
                    
                # --- Dress-up Features ---
                elif t == "fillet":
                    if has_3d:
                        if "points" in p and p["points"]:
                            current_wp = current_wp.edges(CustomMultipleEdgesSelector(p["points"])).fillet(p["radius"])
                        elif "point" in p and p["point"]: # legacy support
                            current_wp = current_wp.edges(CustomNearestEdgeSelector(p["point"])).fillet(p["radius"])
                        else:
                            current_wp = current_wp.edges().fillet(p["radius"])
                elif t == "chamfer":
                    if has_3d:
                        if "points" in p and p["points"]:
                            current_wp = current_wp.edges(CustomMultipleEdgesSelector(p["points"])).chamfer(p["distance"])
                        elif "point" in p and p["point"]: # legacy support
                            current_wp = current_wp.edges(CustomNearestEdgeSelector(p["point"])).chamfer(p["distance"])
                        else:
                            current_wp = current_wp.edges().chamfer(p["distance"])
                    last_op_was_3d = True
            except Exception as e:
                print(f"Rebuild Error on '{t}': {e}")
                current_wp = prev_wp # Rollback failed operation

        self.last_wp = current_wp
        self.result_shape = current_wp

    def get_active_plane_transform(self):
        if hasattr(self, 'last_wp') and self.last_wp and self.last_wp.plane:
            origin = self.last_wp.plane.origin
            z_dir = self.last_wp.plane.zDir
            return (origin.x, origin.y, origin.z), (z_dir.x, z_dir.y, z_dir.z)
        return (0, 0, 0), (0, 0, 1)

    def get_shape_stl(self, filepath):
        if self.result_shape:
            cq.exporters.export(self.result_shape.val(), filepath, 'STL')
            return True
        return False
            
    def export_stl(self, filepath):
        if self.result_shape:
            # cadquery exporter
            cq.exporters.export(self.result_shape.val(), filepath, 'STL')
            return True
        return False
        
    def import_step(self, filepath):
        try:
            shape = cq.importers.importStep(filepath)
            self.result_shape = shape
            # Clear operations since we are starting from an imported solid
            self.operations = []
            self.redo_stack = []
            return True
        except Exception as e:
            print("Import STEP Error:", e)
            return False

    def export_step(self, filepath):
        try:
            if self.result_shape:
                cq.exporters.export(self.result_shape.val(), filepath, 'STEP')
                return True
            return False
        except Exception as e:
            print("Export STEP Error:", e)
            return False
        
    def get_nearest_edge_points(self, point):
        try:
            if not self.result_shape:
                return []
            import numpy as np
            nearest_edge = self.result_shape.edges(CustomNearestEdgeSelector(point)).val()
            if not nearest_edge:
                return []
            
            points = []
            for t in np.linspace(0, 1, 50):
                pt = nearest_edge.positionAt(t)
                points.append((pt.x, pt.y, pt.z))
            return points
        except Exception as e:
            print("Edge selection error:", e)
            return []

    def get_nearest_face_stl(self, point, out_filepath):
        try:
            if not self.result_shape:
                return False
            face = self.result_shape.faces(cq.selectors.NearestToPointSelector(point)).val()
            if not face:
                return False
            cq.exporters.export(face, out_filepath, 'STL')
            return True
        except Exception as e:
            print("Face selection error:", e)
            return False
            
    def get_face_normal_and_center(self, point):
        try:
            if not self.result_shape: return None, None
            face = self.result_shape.faces(cq.selectors.NearestToPointSelector(point)).val()
            if not face: return None, None
            
            geom_type = face.geomType()
            if geom_type == "PLANE":
                center = face.Center()
                normal = face.normalAt(center)
                return (normal.x, normal.y, normal.z), (center.x, center.y, center.z)
            return None, None
        except Exception as e:
            print("Normal error:", e)
            return None, None
            
    def get_all_edges_points(self):
        try:
            if not self.result_shape:
                return []
            import numpy as np
            points_list = []
            
            all_edges = []
            try:
                # Some operations without solid bodies might fail when getting edges
                all_edges.extend(self.result_shape.edges().vals())
            except:
                pass
                
            if hasattr(self.result_shape, 'ctx') and self.result_shape.ctx:
                all_edges.extend(self.result_shape.ctx.pendingEdges)
                for w in self.result_shape.ctx.pendingWires:
                    all_edges.extend(w.Edges())
                    
            for e in all_edges:
                pts = []
                for t in np.linspace(0, 1, 100):
                    pt = e.positionAt(t)
                    pts.append((pt.x, pt.y, pt.z))
                points_list.append(pts)
            return points_list
        except Exception as e:
            print("GetAllEdges Error:", e)
            return []
