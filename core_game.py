import copy
import math
from collections import deque
from typing import Self

import pygame
import pygame.gfxdraw
from PIL import Image

from consts import AREA_HEIGHT, AREA_WIDTH, BG_COLOR, LEVELS_DIR
from geometry import (
    adjacents_cardinal,
    calculate_sweep_line,
    generate_cone_boundaries,
    keys_to_vec,
    rect_edges,
)
from resources import res
from state import State, StateManager, Timer

PLAYER_COLOR = (70, 180, 255)
GUARD_COLOR = (0, 0, 255)
WALL_COLOR = (140, 140, 160)
BORDER_COLOR = (60, 60, 75)
GUARD_VIS_COLOR = (255, 255, 0, 128)


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
                    start_x = x  # Start tracking a new continuous edge
                elif not has_edge and start_x is not None:
                    # End the continuous edge and scale it to screen coordinates
                    self.wall_edges.append(
                        (
                            (start_x * self.scale_factor, y * self.scale_factor),
                            (x * self.scale_factor, y * self.scale_factor),
                        )
                    )
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
                    self.wall_edges.append(
                        (
                            (x * self.scale_factor, start_y * self.scale_factor),
                            (x * self.scale_factor, y * self.scale_factor),
                        )
                    )
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
    def __init__(self, level: LevelMap):
        super().__init__(*level.player_start, radius=level.scale_factor // 2)
        self.level = level

    def update(self, dt, walls):
        keys = pygame.key.get_pressed()
        direction = keys_to_vec(keys)
        self.vel += direction * self.accel * dt
        super().update(dt, walls)

    def draw(self, surface):
        pygame.gfxdraw.aacircle(
            surface, round(self.pos.x), round(self.pos.y), self.radius, PLAYER_COLOR
        )
        pygame.gfxdraw.filled_circle(
            surface, round(self.pos.x), round(self.pos.y), self.radius, PLAYER_COLOR
        )


class Guard:
    def __init__(self, route: set[tuple[int, int]], level: LevelMap):
        self.route = route
        self.scale_factor = level.scale_factor
        self.radius = level.scale_factor // 2
        self.level = level
        self.last_visited = {tile: 0 for tile in route}
        self.map_pos = next(iter(route))
        self.t = 0
        self.facing = None
        self.update()

    def update(self):
        # try to go to the closest tile which hasn't been stepped on for the longest
        adj = [p for p in adjacents_cardinal(*self.map_pos) if p in self.route]
        next_pos = min(adj, key=lambda p: self.last_visited[p])
        prev_pos_v = pygame.Vector2(self.map_pos)
        next_pos_v = pygame.Vector2(next_pos)
        self.map_pos = next_pos
        self.t += 1
        self.last_visited[next_pos] = self.t
        self.facing = next_pos_v - prev_pos_v
        screen_pos = (
            self.map_pos[0] * self.scale_factor + self.radius,
            self.map_pos[1] * self.scale_factor + self.radius,
        )
        cone_edges = generate_cone_boundaries(
            screen_pos[0],
            screen_pos[1],
            math.atan2(self.facing.y, self.facing.x),
            math.radians(90),
            1000.0,
        )
        self.vis_poly_points = calculate_sweep_line(
            screen_pos[0], screen_pos[1], self.level.wall_edges + cone_edges
        )

    def draw(self, surface):
        screen_pos = (
            self.map_pos[0] * self.scale_factor + self.radius,
            self.map_pos[1] * self.scale_factor + self.radius,
        )
        shape_surf = pygame.Surface((AREA_WIDTH, AREA_HEIGHT), pygame.SRCALPHA)
        pygame.gfxdraw.aapolygon(shape_surf, self.vis_poly_points, GUARD_VIS_COLOR)
        pygame.gfxdraw.filled_polygon(shape_surf, self.vis_poly_points, GUARD_VIS_COLOR)
        surface.blit(shape_surf)
        pygame.draw.circle(
            surface,
            GUARD_COLOR,
            screen_pos,
            self.radius,
        )


LEVEL_MAPS = [LevelMap.from_file(f) for f in LEVELS_DIR.iterdir()]


def render(
    surface, level: LevelMap, player: Player, guards: list[Guard], draw_player=True
):
    player_vis_poly = calculate_sweep_line(player.pos.x, player.pos.y, level.wall_edges)
    surface.fill(BG_COLOR)
    for guard in guards:
        guard.draw(surface)
    if draw_player:
        player.draw(surface)
    if len(player_vis_poly) >= 3:
        fog_surf = pygame.Surface((AREA_WIDTH, AREA_HEIGHT))
        fog_surf.fill((10, 10, 15))
        MASK_COLOR = (255, 0, 255)
        pygame.gfxdraw.filled_polygon(fog_surf, player_vis_poly, MASK_COLOR)

        fog_surf.set_colorkey(MASK_COLOR)

        surface.blit(fog_surf, (0, 0))
    for wall in level.walls:
        pygame.draw.rect(surface, WALL_COLOR, wall, border_radius=4)
        pygame.draw.rect(surface, BORDER_COLOR, wall, width=2, border_radius=4)


class CoreGameState(State):
    def __init__(self, mgr: StateManager):
        super().__init__(mgr)
        self.level = LEVEL_MAPS[0]

        self.player = Player(self.level)
        self.guards = [Guard(route, self.level) for route in self.level.guard_routes]

        self.state_snapshots = deque(maxlen=10)

        self.guard_timer = Timer(duration=0.5, repeating=True, callback=self.guard_step)
        self.guard_timer.start()

        self.snapshot_timer = Timer(
            duration=0.5, repeating=True, callback=self.snapshot
        )
        self.snapshot_timer.start()

        self.debuff = False
        self.end_debuff_timer = Timer(
            duration=1.5, repeating=False, callback=self.end_debuff
        )

        self.repayment_bar_label = res.render_text("REPAYMENT", 16)

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_s:
            self.mgr.push(SnapshotViewState(self.mgr))

    def update(self, dt):
        self.guard_timer.update(dt)
        self.snapshot_timer.update(dt)
        self.end_debuff_timer.update(dt)
        self.player.update(dt / 2 if self.debuff else dt, self.level.walls)

    def draw(self, surface):
        render(surface, self.level, self.player, self.guards)
        surface.blit(
            self.repayment_bar_label,
            dest=(
                AREA_WIDTH - 116 - self.repayment_bar_label.width - 8,
                AREA_HEIGHT + 16,
            ),
        )
        pygame.draw.rect(
            surface, (255, 255, 255), (AREA_WIDTH - 116, AREA_HEIGHT + 16, 100, 16), 2
        )
        if self.debuff:
            pygame.draw.rect(
                surface,
                (255, 255, 255),
                (
                    AREA_WIDTH - 116,
                    AREA_HEIGHT + 16,
                    100
                    * (
                        self.end_debuff_timer.time_left / self.end_debuff_timer.duration
                    ),
                    16,
                ),
            )

    def snapshot(self):
        snap = (copy.deepcopy(self.player), copy.deepcopy(self.guards))
        self.state_snapshots.append(snap)

    def guard_step(self):
        for guard in self.guards:
            guard.update()

    def end_debuff(self):
        self.debuff = False


class SnapshotRestoreEffectState(State):
    def __init__(self, mgr: StateManager):
        super().__init__(mgr)
        assert isinstance(self.mgr.stack[-1], CoreGameState)
        self.core = self.mgr.stack[-1]
        self.draw_player = True
        self.blink_timer = Timer(0.1, repeating=True, callback=self.blink)
        self.end_effect_timer = Timer(0.5, repeating=False, callback=self.end)
        self.blink_timer.start()
        self.end_effect_timer.start()

    def update(self, dt):
        self.blink_timer.update(dt)
        self.end_effect_timer.update(dt)

    def draw(self, surface):
        render(
            surface,
            self.core.level,
            self.core.player,
            self.core.guards,
            draw_player=self.draw_player,
        )

    def blink(self):
        self.draw_player = not self.draw_player

    def end(self):
        self.mgr.pop()


class SnapshotViewState(State):
    def __init__(self, mgr: StateManager):
        super().__init__(mgr)
        assert isinstance(self.mgr.stack[-1], CoreGameState)
        self.core = self.mgr.stack[-1]
        self.selected = len(self.core.state_snapshots) - 1
        self.current_surf = pygame.Surface((AREA_WIDTH, AREA_HEIGHT))
        render(self.current_surf, self.core.level, self.core.player, self.core.guards)
        self.blur_radius = 0
        self.darkening = 0
        self.blurred_surf = None
        self.snapshot_times = []
        for i in range(len(self.core.state_snapshots))[::-1]:
            if i == len(self.core.state_snapshots) - 1:
                self.snapshot_times.append(
                    self.core.snapshot_timer.duration
                    - self.core.snapshot_timer.time_left
                )
            else:
                self.snapshot_times.append(
                    self.snapshot_times[-1] + self.core.snapshot_timer.duration
                )
        self.snapshot_times.reverse()

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.mgr.pop()
            elif event.key == pygame.K_LEFT:
                self.selected = max(0, self.selected - 1)
            elif event.key == pygame.K_RIGHT:
                self.selected = min(
                    len(self.core.state_snapshots) - 1, self.selected + 1
                )
            elif event.key == pygame.K_RETURN:
                player, guards = self.core.state_snapshots[self.selected]
                player = copy.deepcopy(player)
                player.vel = pygame.Vector2(0, 0)
                repayment = round(round(self.snapshot_times[self.selected], 1) * 1.5, 1)
                self.core.player = player
                self.core.guards = copy.deepcopy(guards)
                if self.core.debuff:
                    # debts stack
                    self.core.end_debuff_timer.duration += repayment
                else:
                    self.core.debuff = True
                    self.core.end_debuff_timer.duration = repayment
                    self.core.end_debuff_timer.start()
                self.mgr.pop()
                self.mgr.push(SnapshotRestoreEffectState(self.mgr))

    def update(self, dt):
        if self.blur_radius < 10:
            self.blur_radius += 1
        if self.darkening < 100:
            self.darkening += 10

    def draw(self, surface):
        if self.blurred_surf:
            surface.blit(self.blurred_surf)
        else:
            blurred_surf = pygame.transform.gaussian_blur(
                self.current_surf, radius=self.blur_radius
            )
            surface.blit(blurred_surf)
            if self.blur_radius == 10:
                self.blurred_surf = blurred_surf  # cache :)
        overlay = pygame.Surface((AREA_WIDTH, AREA_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, self.darkening))
        surface.blit(overlay)
        snapshot_previews = []
        for snapshot in self.core.state_snapshots:
            preview_surf = pygame.Surface((AREA_WIDTH, AREA_HEIGHT))
            player, guards = snapshot
            render(preview_surf, self.core.level, player, guards)
            preview_surf = pygame.transform.scale_by(preview_surf, 0.5)
            snapshot_previews.append(preview_surf)
        powered_by_text = res.render_text(
            "Travel back in time, powered by Time Value Inc.!", 16
        )
        surface.blit(
            powered_by_text, dest=(AREA_WIDTH // 2 - powered_by_text.width // 2, 32)
        )
        surface.blit(
            snapshot_previews[self.selected], dest=(AREA_WIDTH // 4, AREA_HEIGHT // 4)
        )
        time_ago = round(self.snapshot_times[self.selected], 1)
        snapshot_info_text = res.render_text(f"{time_ago:.1f}s ago", 32)
        surface.blit(
            snapshot_info_text,
            dest=(
                AREA_WIDTH // 2 - snapshot_info_text.width // 2,
                AREA_HEIGHT // 2 + preview_surf.height // 2,
            ),
        )
        disclaimer_text = res.render_text(
            f"Repayment: Your movement speed will be halved for the next {time_ago * 1.25:.1f} seconds\n\n[ENTER] to confirm      [ESC] to cancel",
            16,
        )
        surface.blit(
            disclaimer_text,
            dest=(
                AREA_WIDTH // 2 - disclaimer_text.width // 2,
                AREA_HEIGHT // 2 + preview_surf.height // 2 + 48,
            ),
        )
