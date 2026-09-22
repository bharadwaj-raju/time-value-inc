import math
from itertools import groupby

import pygame


def lerp(a, b, t):
    return a + (b - a) * t

def point_in_polygon(x, y, poly):
    """
    Checks if a point (x, y) is inside a polygon defined by a sequence of points.
    poly: list of (x, y) tuples/lists -> [(x1,y1), (x2,y2), ...]
    """
    n = len(poly)
    inside = False
    p1x, p1y = poly[0]
    
    for i in range(n + 1):
        p2x, p2y = poly[i % n]
        if y > min(p1y, p2y) and y <= max(p1y, p2y) and x <= max(p1x, p2x):
            if p1y != p2y:
                xints = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
            if p1x == p2x or x <= xints:
                inside = not inside
        p1x, p1y = p2x, p2y
        
    return inside

def generate_cone_boundaries(origin_x, origin_y, facing_angle, fov_radians, view_distance):
    edges = []
    half_fov = fov_radians / 2.0
    start_angle = facing_angle - half_fov
    end_angle = facing_angle + half_fov
    
    # 1. The anchor point (placed 0.5 pixels BEHIND the guard)
    # This ensures the raycaster's origin is strictly inside the closed cone.
    back_dist = 0.5
    back_angle = facing_angle + math.pi
    anchor_pt = (
        origin_x + math.cos(back_angle) * back_dist,
        origin_y + math.sin(back_angle) * back_dist
    )
    
    # 2. The far corners
    left_far = (
        origin_x + view_distance * math.cos(start_angle),
        origin_y + view_distance * math.sin(start_angle)
    )
    right_far = (
        origin_x + view_distance * math.cos(end_angle),
        origin_y + view_distance * math.sin(end_angle)
    )
    
    # 3. Left boundary wall
    edges.append((anchor_pt, left_far))
    
    # 4. Far arc walls
    arc_resolution = 8
    prev_pt = left_far
    for i in range(1, arc_resolution + 1):
        theta = start_angle + (fov_radians * (i / arc_resolution))
        arc_pt = (
            origin_x + view_distance * math.cos(theta),
            origin_y + view_distance * math.sin(theta)
        )
        edges.append((prev_pt, arc_pt))
        prev_pt = arc_pt
        
    # 5. Right boundary wall (closing the polygon)
    edges.append((prev_pt, anchor_pt))
    
    return edges

def rect_edges(rect: pygame.Rect) -> list[tuple[tuple[int, int], tuple[int, int]]]:
    return [
        (rect.topleft, rect.topright),
        (rect.topright, rect.bottomright),
        (rect.bottomright, rect.bottomleft),
        (rect.bottomleft, rect.topleft),
    ]


def rect_endpoints(rect: pygame.Rect) -> list[tuple[int, int]]:
    return [
        rect.topleft,
        rect.topright,
        rect.topright,
        rect.bottomright,
        rect.bottomright,
        rect.bottomleft,
        rect.bottomleft,
        rect.topleft,
    ]


def keys_to_vec(keys) -> pygame.Vector2:
    input_dir = pygame.Vector2(0, 0)
    if keys[pygame.K_LEFT]:
        input_dir.x -= 1
    if keys[pygame.K_RIGHT]:
        input_dir.x += 1
    if keys[pygame.K_UP]:
        input_dir.y -= 1
    if keys[pygame.K_DOWN]:
        input_dir.y += 1

    if input_dir.length_squared() > 0:
        input_dir = input_dir.normalize()

    return input_dir


def adjacents_cardinal(x, y):
    return [(x + 1, y), (x, y + 1), (x - 1, y), (x, y - 1)]


# thanks Nicky Case :D
def ray_intersect(ray, segment):
    r_px, r_py = ray[0]
    r_dx = ray[1][0] - r_px
    r_dy = ray[1][1] - r_py
    
    s_px, s_py = segment[0]
    s_dx = segment[1][0] - s_px
    s_dy = segment[1][1] - s_py
    
    denom = s_dx * r_dy - s_dy * r_dx
    
    # Are they parallel? (Check against a tiny epsilon instead of exact 0)
    if abs(denom) < 1e-8:
        return None

    # T2 is the scalar along the line segment
    T2 = (r_dx * (s_py - r_py) + r_dy * (r_px - s_px)) / denom
    
    # T1 is the scalar along the ray.
    # To prevent ZeroDivisionError, use the axis with the larger delta
    if abs(r_dx) > abs(r_dy):
        T1 = (s_px + s_dx * T2 - r_px) / r_dx
    else:
        T1 = (s_py + s_dy * T2 - r_py) / r_dy

    # Epsilon bounds check
    # T1 > -1e-6: The intersection is in front of the ray (or exactly at origin)
    # T2 between -1e-6 and 1 + 1e-6: The intersection is on the segment
    epsilon = 1e-6
    if T1 > -epsilon and -epsilon <= T2 <= 1.0 + epsilon:
        # Return the exact intersection point and distance (T1)
        return ((r_px + r_dx * T1, r_py + r_dy * T1), T1)
        
    return None



def calculate_sweep_line(origin_x, origin_y, edges):
    endpoints = []
    active_segments = set()

    # 1. Setup Endpoints and the -PI/PI Seam
    for edge in edges:
        p1, p2 = edge
        dx1, dy1 = p1[0] - origin_x, p1[1] - origin_y
        dx2, dy2 = p2[0] - origin_x, p2[1] - origin_y

        a1 = math.atan2(dy1, dx1)
        a2 = math.atan2(dy2, dx2)

        # Determine winding order (counter-clockwise)
        d_angle = (a2 - a1) % (2 * math.pi)
        if d_angle < math.pi:
            start_p, end_p, start_a, end_a = p1, p2, a1, a2
        else:
            start_p, end_p, start_a, end_a = p2, p1, a2, a1

        endpoints.append((start_p, edge, start_a, True))
        endpoints.append((end_p, edge, end_a, False))

        # If the segment crosses the -PI/PI seam, it starts active
        if start_a > end_a:
            active_segments.add(edge)

    # 2. Sort rotationally, breaking ties by distance
    endpoints.sort(key=lambda e: (round(e[2], 5), math.hypot(e[0][0] - origin_x, e[0][1] - origin_y)))

    points = []
    origin = (origin_x, origin_y)

    # 3. Sweep the line
    for exact_angle, group in groupby(endpoints, key=lambda e: round(e[2], 5)):
        group_list = list(group)
        real_angle = group_list[0][2]
        ray = (origin, (origin_x + math.cos(real_angle), origin_y + math.sin(real_angle)))

        def get_closest(ray=ray):
            closest_pt, min_dist = None, float('inf')
            for s in active_segments:
                intersect = ray_intersect(ray, s)
                if intersect and intersect[1] < min_dist:
                    closest_pt, min_dist = intersect
            return closest_pt

        # Raycast BEFORE state change
        p_old = get_closest()
        if p_old: 
            points.append(p_old)

        # Update active segments
        for ep in group_list:
            if ep[3]: 
                active_segments.add(ep[1])
            else: 
                active_segments.discard(ep[1])

        # Raycast AFTER state change
        p_new = get_closest()
        if p_new: 
            points.append(p_new)

    return points

