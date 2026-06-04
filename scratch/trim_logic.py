import numpy as np

def line_intersection(p1, p2, p3, p4):
    """
    Find intersection of two line segments p1-p2 and p3-p4.
    Returns point (x,y) or None.
    """
    # https://en.wikipedia.org/wiki/Line%E2%80%93line_intersection
    x1, y1 = p1[:2]; x2, y2 = p2[:2]
    x3, y3 = p3[:2]; x4, y4 = p4[:2]
    
    denom = (x1-x2)*(y3-y4) - (y1-y2)*(x3-x4)
    if abs(denom) < 1e-8:
        return None # parallel
        
    t = ((x1-x3)*(y3-y4) - (y1-y3)*(x3-x4)) / denom
    u = ((x1-x3)*(y1-y2) - (y1-y3)*(x1-x2)) / denom
    
    if 0 <= t <= 1 and 0 <= u <= 1:
        x = x1 + t*(x2-x1)
        y = y1 + t*(y2-y1)
        return (x, y)
    return None

def test():
    # Cross
    p1 = (0, 5); p2 = (10, 5)
    p3 = (5, 0); p4 = (5, 10)
    print("Cross intersection:", line_intersection(p1, p2, p3, p4))
    
    # T-junction
    p1 = (0, 0); p2 = (10, 0)
    p3 = (5, 0); p4 = (5, 10)
    print("T-junction intersection:", line_intersection(p1, p2, p3, p4))
    
    # No intersection
    p1 = (0, 0); p2 = (10, 0)
    p3 = (0, 5); p4 = (10, 5)
    print("Parallel:", line_intersection(p1, p2, p3, p4))

if __name__ == "__main__":
    test()
