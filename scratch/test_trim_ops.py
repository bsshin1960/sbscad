import numpy as np

def distance_point_to_segment(p, a, b):
    p = np.array(p)
    a = np.array(a)
    b = np.array(b)
    ab = b - a
    ab_sq = np.dot(ab, ab)
    if ab_sq == 0:
        return np.linalg.norm(p - a)
    t = np.dot(p - a, ab) / ab_sq
    t = max(0, min(1, t))
    proj = a + t * ab
    return np.linalg.norm(p - proj), t

def line_intersection(p1, p2, p3, p4):
    x1, y1 = p1[:2]; x2, y2 = p2[:2]
    x3, y3 = p3[:2]; x4, y4 = p4[:2]
    denom = (x1-x2)*(y3-y4) - (y1-y2)*(x3-x4)
    if abs(denom) < 1e-8:
        return None, None
    t = ((x1-x3)*(y3-y4) - (y1-y3)*(x3-x4)) / denom
    u = ((x1-x3)*(y1-y2) - (y1-y3)*(x1-x2)) / denom
    if -1e-6 <= t <= 1+1e-6 and -1e-6 <= u <= 1+1e-6:
        x = x1 + t*(x2-x1)
        y = y1 + t*(y2-y1)
        return (x, y, 0.0), t
    return None, None

def test_trim(operations, click_pt):
    # 1. Collect all segments
    segments = []
    for op_idx, op in enumerate(operations):
        pts = op["params"]["points"]
        for i in range(len(pts) - 1):
            segments.append({
                "op_idx": op_idx,
                "seg_idx": i,
                "p1": pts[i],
                "p2": pts[i+1]
            })
            
    # 2. Find closest segment to click_pt
    min_dist = float('inf')
    target_seg = None
    target_t = 0
    for seg in segments:
        dist, t = distance_point_to_segment(click_pt, seg["p1"], seg["p2"])
        if dist < min_dist:
            min_dist = dist
            target_seg = seg
            target_t = t
            
    if not target_seg or min_dist > 5.0: # threshold
        print("No segment found near click")
        return operations

    print(f"Target: op={target_seg['op_idx']}, seg={target_seg['seg_idx']}, t={target_t}")
    
    # 3. Find intersections with target segment
    t_intersections = []
    for seg in segments:
        if seg == target_seg:
            continue
        pt, t_int = line_intersection(target_seg["p1"], target_seg["p2"], seg["p1"], seg["p2"])
        if pt is not None:
            t_intersections.append((t_int, pt))
            
    # 4. Find bounds to trim
    t_min = 0.0
    t_max = 1.0
    for t_int, pt in t_intersections:
        if t_int < target_t and t_int > t_min:
            t_min = t_int
        if t_int > target_t and t_int < t_max:
            t_max = t_int
            
    print(f"Trim bounds: t_min={t_min}, t_max={t_max}")
    
    # Calculate points
    p1 = np.array(target_seg["p1"])
    p2 = np.array(target_seg["p2"])
    pt_min = tuple(p1 + t_min * (p2 - p1))
    pt_max = tuple(p1 + t_max * (p2 - p1))
    
    # 5. Modify operations
    new_ops = []
    for i, op in enumerate(operations):
        if i == target_seg["op_idx"]:
            pts = op["params"]["points"]
            seg_i = target_seg["seg_idx"]
            
            # First part
            pts1 = pts[:seg_i+1] + [pt_min]
            # Avoid duplicate points
            if np.linalg.norm(np.array(pts1[-1]) - np.array(pts1[-2])) > 1e-5:
                new_ops.append({"type": op["type"], "params": {"plane": op["params"]["plane"], "points": pts1}})
            elif len(pts1) > 2: # still a valid polyline
                new_ops.append({"type": op["type"], "params": {"plane": op["params"]["plane"], "points": pts1[:-1]}})
                
            # Second part
            pts2 = [pt_max] + pts[seg_i+1:]
            if np.linalg.norm(np.array(pts2[0]) - np.array(pts2[1])) > 1e-5:
                new_ops.append({"type": op["type"], "params": {"plane": op["params"]["plane"], "points": pts2}})
            elif len(pts2) > 2:
                new_ops.append({"type": op["type"], "params": {"plane": op["params"]["plane"], "points": pts2[1:]}})
        else:
            new_ops.append(op)
            
    return new_ops

ops = [
    {"type": "sketch_line", "params": {"plane": "XY", "points": [(0,5,0), (10,5,0)]}},
    {"type": "sketch_line", "params": {"plane": "XY", "points": [(5,0,0), (5,10,0)]}}
]
print("Initial:", ops)
ops = test_trim(ops, (7.5, 5, 0)) # click right side of cross
print("After Trim:", ops)
