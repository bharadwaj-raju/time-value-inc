import collections
import functools
import math
import operator
import sys
from itertools import groupby
from pathlib import Path
from typing import Self

import pygame
from PIL import Image

pygame.init()

ROOT = Path(__file__).parent
LEVELS_DIR = ROOT / "levels"

AREA_WIDTH, AREA_HEIGHT = 800, 600
STATUSBAR_HEIGHT = 100
screen = pygame.display.set_mode((AREA_WIDTH, AREA_HEIGHT + STATUSBAR_HEIGHT))
pygame.display.set_caption("Time Value Inc.")
clock = pygame.time.Clock()

BG_COLOR = (24, 24, 28)
PLAYER_COLOR = (70, 180, 255)
GUARD_COLOR = (0, 0, 255)
WALL_COLOR = (140, 140, 160)
BORDER_COLOR = (60, 60, 75)


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

class LevelMap:
    TILEMAP_WALL = (0, 0, 0)
    TILEMAP_PLAYER = (255, 0, 0)
    TILEMAP_GOAL = (255, 255, 0)
    TILEMAP_GUARD = (0, 0, 255)

    def __init__(self, im: Image.Image):
        self.im = im
        self.scale_factor = AREA_WIDTH // im.width
        self.process()

    @classmethod
    def from_file(cls, filelike) -> Self:
        return cls(Image.open(filelike))

    def process(self):
        self.walls = []
        self.player_start = (0, 0)
        self.goal = None
        guard_tiles = set()
        wall_tiles = set()
        for y in range(self.im.height):
            for x in range(self.im.width):
                p = self.im.getpixel((x, y))
                if p == LevelMap.TILEMAP_WALL:
                    wall_tiles.add((x, y))
                    self.walls.append(
                        pygame.Rect(
                            x * self.scale_factor,
                            y * self.scale_factor,
                            self.scale_factor,
                            self.scale_factor,
                        )
                    )
                elif p == LevelMap.TILEMAP_PLAYER:
                    self.player_start = (x * self.scale_factor, y * self.scale_factor)
                elif p == LevelMap.TILEMAP_GUARD:
                    guard_tiles.add((x, y))

        self.wall_edges = []
        
        # 1. Merge Horizontal Edges
        for y in range(self.im.height + 1):
            start_x = None
            for x in range(self.im.width + 1):
                # An edge exists if one side is a wall and the other is empty
                is_wall_below = (x, y) in wall_tiles
                is_wall_above = (x, y - 1) in wall_tiles
                has_edge = is_wall_below ^ is_wall_above
                
                if has_edge and start_x is None:
                    start_x = x # Start tracking a new continuous edge
                elif not has_edge and start_x is not None:
                    # End the continuous edge and scale it to screen coordinates
                    self.wall_edges.append((
                        (start_x * self.scale_factor, y * self.scale_factor),
                        (x * self.scale_factor, y * self.scale_factor)
                    ))
                    start_x = None
                    
        # 2. Merge Vertical Edges
        for x in range(self.im.width + 1):
            start_y = None
            for y in range(self.im.height + 1):
                is_wall_right = (x, y) in wall_tiles
                is_wall_left = (x - 1, y) in wall_tiles
                has_edge = is_wall_right ^ is_wall_left
                
                if has_edge and start_y is None:
                    start_y = y
                elif not has_edge and start_y is not None:
                    self.wall_edges.append((
                        (x * self.scale_factor, start_y * self.scale_factor),
                        (x * self.scale_factor, y * self.scale_factor)
                    ))
                    start_y = None

        # Add screen borders to edges so rays always hit a boundary
        border_rect = pygame.Rect(0, 0, AREA_WIDTH, AREA_HEIGHT)
        self.wall_edges.extend(rect_edges(border_rect))

        self.guard_routes = []
        while guard_tiles:
            tile = guard_tiles.pop()
            route = {tile}
            while True:
                route_next_iter = route.copy()
                for other_tile in guard_tiles:
                    if any(other_tile in adjacents_cardinal(*tile) for tile in route):
                        route_next_iter.add(other_tile)
                if len(route_next_iter) == len(route):
                    break
                route = route_next_iter
            for tile in route:
                guard_tiles.discard(tile)
            self.guard_routes.append(set(route))
        print(len(self.guard_routes))


class MovableEntity:
    def __init__(self, x, y, radius=20):
        self.pos = pygame.Vector2(x, y)
        self.vel = pygame.Vector2(0, 0)
        self.radius = radius

        self.accel = 2400.0
        self.friction = 8.0
        self.max_speed = 350.0

    def resolve_wall_collision(self, rect):
        """Clamp circle position against an axis-aligned bounding box."""
        # Find closest point on rect to the circle center
        closest_x = max(rect.left, min(self.pos.x, rect.right))
        closest_y = max(rect.top, min(self.pos.y, rect.bottom))

        diff = self.pos - pygame.Vector2(closest_x, closest_y)
        dist_sq = diff.length_squared()

        # Check collision
        if dist_sq < self.radius * self.radius:
            dist = diff.length()
            if dist != 0:
                normal = diff / dist
                overlap = self.radius - dist
                self.pos += normal * overlap

                # Zero out velocity into the wall surface
                vel_dot = self.vel.dot(normal)
                if vel_dot < 0:
                    self.vel -= normal * vel_dot
            else:
                # Center is exactly on/inside rect boundary
                self.pos.x += self.radius
                self.vel.x = 0

    def update(self, dt, walls):
        self.vel -= self.vel * self.friction * dt

        if self.vel.length() > self.max_speed:
            self.vel.scale_to_length(self.max_speed)

        self.pos.x += self.vel.x * dt
        for wall in walls:
            self.resolve_wall_collision(wall)

        self.pos.y += self.vel.y * dt
        for wall in walls:
            self.resolve_wall_collision(wall)

        if self.pos.x - self.radius < 0:
            self.pos.x = self.radius
            self.vel.x = 0
        elif self.pos.x + self.radius > AREA_WIDTH:
            self.pos.x = AREA_WIDTH - self.radius
            self.vel.x = 0

        if self.pos.y - self.radius < 0:
            self.pos.y = self.radius
            self.vel.y = 0
        elif self.pos.y + self.radius > AREA_HEIGHT:
            self.pos.y = AREA_HEIGHT - self.radius
            self.vel.y = 0


class Player(MovableEntity):
    def update(self, dt, walls):
        keys = pygame.key.get_pressed()
        direction = keys_to_vec(keys)
        self.vel += direction * self.accel * dt
        super().update(dt, walls)

    def draw(self, surface):
        pygame.draw.circle(
            surface, PLAYER_COLOR, (round(self.pos.x), round(self.pos.y)), self.radius
        )


class Guard(MovableEntity):
    def __init__(self, route: set[tuple[int, int]], level: LevelMap):
        self.route = route
        self.scale_factor = level.scale_factor
        self.level = level
        self.last_visited = {tile: 0 for tile in route}
        self.map_pos = next(iter(route))
        start_screen_pos = (
            self.map_pos[0] * level.scale_factor,
            self.map_pos[1] * level.scale_factor,
        )
        super().__init__(*start_screen_pos, radius=level.scale_factor // 2)
        self.t = 0
        self.facing = None

    def update(self, dt, walls):
        # try to go to the closest tile which hasn't been stepped on for the longest
        adj = [p for p in adjacents_cardinal(*self.map_pos) if p in self.route]
        next_pos = min(adj, key=lambda p: self.last_visited[p])
        prev_pos_v = pygame.Vector2(self.map_pos)
        next_pos_v = pygame.Vector2(next_pos)
        self.map_pos = next_pos
        self.t += 1
        self.last_visited[next_pos] = self.t
        self.facing = next_pos_v - prev_pos_v

    def draw(self, surface):
        screen_pos = (
            self.map_pos[0] * self.scale_factor + self.radius,
            self.map_pos[1] * self.scale_factor + self.radius,
        )
        pygame.draw.circle(
            surface,
            GUARD_COLOR,
            screen_pos,
            self.radius,
        )

        points = calculate_sweep_line(screen_pos[0], screen_pos[1], self.level.wall_edges)

        pygame.draw.polygon(surface, (0, 255, 255, 128), points)


LEVEL_MAPS = [LevelMap.from_file(f) for f in LEVELS_DIR.iterdir()]
LEVEL = LEVEL_MAPS[0]

player = Player(*LEVEL.player_start, radius=LEVEL.scale_factor // 2)
guards = [Guard(route, LEVEL) for route in LEVEL.guard_routes]

GUARD_STEP_EVENT = pygame.USEREVENT + 1
pygame.time.set_timer(GUARD_STEP_EVENT, 500)

running = True
t = 0.0
while running:
    # Delta time in seconds
    dt = clock.tick(120) / 1000.0
    t += dt

    for event in pygame.event.get():
        if (
            event.type == pygame.QUIT
            or event.type == pygame.KEYDOWN
            and event.key == pygame.K_ESCAPE
        ):
            running = False
        if event.type == GUARD_STEP_EVENT:
            for guard in guards:
                guard.update(dt, LEVEL.walls)

    player.update(dt, LEVEL.walls)

    screen.fill(BG_COLOR)

    for wall in LEVEL.walls:
        pygame.draw.rect(screen, WALL_COLOR, wall, border_radius=4)
        pygame.draw.rect(screen, BORDER_COLOR, wall, width=2, border_radius=4)

    player.draw(screen)
    for guard in guards:
        guard.draw(screen)

    pygame.display.flip()

pygame.quit()
sys.exit()
