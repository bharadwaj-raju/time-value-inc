import math
from collections import deque

import pygame
import pygame.gfxdraw

from consts import AREA_HEIGHT, AREA_WIDTH, BG_COLOR, LEVELS_DIR
from geometry import (
    adjacents,
    adjacents_cardinal,
    calculate_sweep_line,
    generate_cone_boundaries,
    keys_to_vec,
    point_in_polygon,
)
from level_map import LevelMap
from resources import res
from state import State, StateManager, Timer

PLAYER_COLOR = (70, 180, 255)
GUARD_COLOR = (0, 0, 255)
WALL_COLOR = (140, 140, 160)
BORDER_COLOR = (60, 60, 75)
GUARD_VIS_COLOR = (255, 255, 0, 128)
GUARD_VIS_ALERT_COLOR = (255, 100, 0, 128)


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

    def snapshot(self):
        return (self.pos.copy(),)

    def load_snapshot(self, snapshot):
        (pos,) = snapshot
        self.pos = pos.copy()

    def update(self, dt, walls):
        keys = pygame.key.get_pressed()
        direction = keys_to_vec(keys)
        self.vel += direction * self.accel * dt
        super().update(dt, walls)

    def draw(self, surface, caught=False, at_goal=False):
        sprite = res.player_eyes
        if self.vel.y < 0:
            sprite = res.player_base
        if at_goal:
            sprite = res.player_happy
        if caught:
            sprite = res.player_shock
        surface.blit(sprite, self.pos - (16, 16))


class Guard:
    def __init__(self, route: set[tuple[int, int]], level: LevelMap):
        self.route = route
        self.scale_factor = level.scale_factor
        self.radius = 16
        self.level = level
        self.last_visited = {tile: 0 for tile in route}
        self.map_pos = next(iter(route))
        self.t = 0
        self.caught = False
        self.update()

    def snapshot(self):
        return (
            self.route,
            self.map_pos,
            self.t,
            self.facing.copy(),
            self.last_visited.copy(),
        )

    def load_snapshot(self, snapshot):
        route, map_pos, t, facing, last_visited = snapshot
        self.route, self.map_pos, self.t, self.facing, self.last_visited = (
            route,
            map_pos,
            t,
            facing.copy(),
            last_visited.copy(),
        )
        self.calculate_vis()

    def update(self, player_pos: tuple[int, int] | None = None):
        # try to go to the closest tile which hasn't been stepped on for the longest
        adj = [p for p in adjacents_cardinal(*self.map_pos) if p in self.route]
        next_pos = min(adj, key=lambda p: self.last_visited[p])
        prev_pos_v = pygame.Vector2(self.map_pos)
        next_pos_v = pygame.Vector2(next_pos)
        self.map_pos = next_pos
        self.t += 1
        self.last_visited[next_pos] = self.t
        self.facing = next_pos_v - prev_pos_v
        self.calculate_vis()
        if player_pos:
            self.check_caught(player_pos)

    def calculate_vis(self):
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

    def check_caught(self, player_pos: tuple[int, int]):
        self.caught = False
        for pos in (
            player_pos,
            *adjacents(*player_pos, by=self.radius // 2),
        ):
            if point_in_polygon(*pos, self.vis_poly_points):
                self.caught = True

    def draw(self, surface):
        screen_pos = (
            self.map_pos[0] * self.scale_factor,
            self.map_pos[1] * self.scale_factor,
        )
        shape_surf = pygame.Surface((AREA_WIDTH, AREA_HEIGHT), pygame.SRCALPHA)
        color = GUARD_VIS_ALERT_COLOR if self.caught else GUARD_VIS_COLOR
        pygame.gfxdraw.aapolygon(shape_surf, self.vis_poly_points, color)
        pygame.gfxdraw.filled_polygon(shape_surf, self.vis_poly_points, color)
        surface.blit(shape_surf)
        surface.blit(
            pygame.transform.rotate(
                res.enemy_spotted if self.caught else res.enemy_base,
                math.degrees(math.atan2(self.facing.y, -self.facing.x)),
            ),
            screen_pos,
        )


LEVEL_MAPS = [LevelMap.from_file(f) for f in LEVELS_DIR.iterdir()]


def render(
    surface, level: LevelMap, player: Player, guards: list[Guard], draw_player=True
):
    player_vis_poly = calculate_sweep_line(player.pos.x, player.pos.y, level.wall_edges)
    surface.fill(BG_COLOR)
    caught = False
    for guard in guards:
        guard.draw(surface)
        if guard.caught:
            caught = True
    if draw_player:
        player.draw(surface, caught=caught)
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

        self.state_snapshots = deque(maxlen=50)

        self.guard_timer = Timer(duration=0.5, repeating=True, callback=self.guard_step)
        self.guard_timer.start()

        self.snapshot_timer = Timer(
            duration=0.5, repeating=True, callback=self.take_snapshot
        )
        self.snapshot_timer.start()

        self.debuff = False
        self.end_debuff_timer = Timer(
            duration=0.0, repeating=False, callback=self.end_debuff
        )

        self.repayment_label = res.render_text("REPAYMENT", 16)

        self.backinttime_key_label = res.render_text("BACK IN TIME\n[B]", 16)
        self.speedup_key_label = res.render_text("SPEEDUP\n[S]", 16)

        self.speedup = False
        self.end_speedup_timer = Timer(
            duration=2.0, repeating=False, callback=self.end_speedup
        )

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_b:
                self.mgr.push(SnapshotViewState(self.mgr))
            elif event.key == pygame.K_s and not (self.debuff or self.speedup):
                self.speedup = True
                self.end_speedup_timer.start()

    def update(self, dt):
        player_dt = (dt / 2) if self.debuff else dt
        enemy_dt = (dt / 2) if self.speedup else dt
        self.guard_timer.update(enemy_dt)
        for guard in self.guards:
            guard.check_caught((int(self.player.pos.x), int(self.player.pos.y)))
            if guard.caught:
                self.mgr.push(CaughtHoldEffectState(self.mgr))
                return
        self.snapshot_timer.update(dt)
        self.end_debuff_timer.update(dt)
        self.end_speedup_timer.update(dt)
        self.player.update(player_dt, self.level.walls)

    def draw_countdown(self, surface, x, y, fraction):
        pygame.draw.rect(surface, (255, 255, 255), (x, y, 100, 16), 2)
        pygame.draw.rect(
            surface,
            (255, 255, 255),
            (
                x,
                y,
                100 * fraction,
                16,
            ),
        )

    def draw(self, surface):
        if any(guard.caught for guard in self.guards):
            return
        render(surface, self.level, self.player, self.guards)
        res.backintime_icon.draw(surface, dest=(32, AREA_HEIGHT + 16), scale=3)
        surface.blit(
            self.backinttime_key_label, dest=(32 + 16 * 3 + 8, AREA_HEIGHT + 16 + 8)
        )
        res.ff_icon.draw(surface, dest=(256, AREA_HEIGHT + 16), scale=3)
        surface.blit(
            self.speedup_key_label, dest=(256 + 16 * 3 + 8, AREA_HEIGHT + 16 + 8)
        )
        surface.blit(
            self.repayment_label,
            dest=(
                AREA_WIDTH - 116 - self.repayment_label.width - 8,
                AREA_HEIGHT + 32 + 4,
            ),
        )
        self.draw_countdown(
            surface,
            AREA_WIDTH - 100 - 16,
            AREA_HEIGHT + 32 + 4,
            0.0
            if not self.debuff or self.end_debuff_timer.duration == 0.0
            else self.end_debuff_timer.time_left / self.end_debuff_timer.duration,
        )
        self.draw_countdown(
            surface,
            256 + 8,
            AREA_HEIGHT + 32 + 8 + 32,
            0.0
            if not self.speedup
            else self.end_speedup_timer.time_left / self.end_speedup_timer.duration,
        )

    def take_snapshot(self):
        snap = (self.player.snapshot(), [g.snapshot() for g in self.guards])
        self.state_snapshots.append(snap)

    def guard_step(self):
        for guard in self.guards:
            guard.update()

    def end_debuff(self):
        self.debuff = False
        self.end_debuff_timer.duration = 0.0

    def end_speedup(self):
        self.speedup = False
        self.debuff = True
        self.end_debuff_timer.duration += self.end_speedup_timer.duration
        self.end_debuff_timer.start()


class CaughtHoldEffectState(State):
    def __init__(self, mgr: StateManager):
        super().__init__(mgr)
        assert isinstance(self.mgr.stack[-1], CoreGameState)
        self.core = self.mgr.stack[-1]
        self.end_effect_timer = Timer(1.0, repeating=False, callback=self.end)
        self.end_effect_timer.start()

    def update(self, dt):
        self.end_effect_timer.update(dt)

    def draw(self, surface):
        render(surface, self.core.level, self.core.player, self.core.guards)

    def end(self):
        self.mgr.pop()
        self.mgr.push(SnapshotViewState(self.mgr, because_caught=True))


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
    def __init__(self, mgr: StateManager, because_caught=False):
        super().__init__(mgr)
        assert isinstance(self.mgr.stack[-1], CoreGameState)
        self.core = self.mgr.stack[-1]
        self.snapshots = self.core.state_snapshots
        self.snapshot_times = []
        for i in range(len(self.snapshots))[::-1]:
            if i == len(self.snapshots) - 1:
                self.snapshot_times.append(
                    self.core.snapshot_timer.duration
                    - self.core.snapshot_timer.time_left
                )
            else:
                self.snapshot_times.append(
                    self.snapshot_times[-1] + self.core.snapshot_timer.duration
                )
        self.snapshot_times.reverse()
        if self.snapshot_times and round(self.snapshot_times[-1], 1) == 0.0:
            self.snapshot_times.pop()
            self.snapshots.pop()
        self.selected = len(self.snapshots) - 1
        self.current_surf = pygame.Surface((AREA_WIDTH, AREA_HEIGHT))
        render(self.current_surf, self.core.level, self.core.player, self.core.guards)
        self.blur_radius = 0
        self.darkening = 0
        self.blurred_surf = None
        self.left_arrow = res.render_text("←", 128)
        self.right_arrow = res.render_text("→", 128)
        self.because_caught = because_caught

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE and not self.because_caught:
                self.mgr.pop()
            elif event.key == pygame.K_LEFT:
                self.selected = max(0, self.selected - 1)
            elif event.key == pygame.K_RIGHT:
                self.selected = min(len(self.snapshots) - 1, self.selected + 1)
            elif event.key == pygame.K_RETURN and self.snapshots:
                player_snap, guards_snap = self.snapshots[self.selected]
                repayment = round(round(self.snapshot_times[self.selected], 1) * 1.5, 1)
                self.core.player.load_snapshot(player_snap)
                self.core.player.vel = pygame.Vector2(0.0, 0.0)
                for guard, guard_snap in zip(self.core.guards, guards_snap):
                    guard.load_snapshot(guard_snap)
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
        if not self.snapshots:
            no_snaps_text = res.render_text(
                "No snapshots yet! They’re taken every half a second, so please wait just a bit.",
                16,
            )
            surface.blit(
                no_snaps_text, dest=(AREA_WIDTH // 2 - no_snaps_text.width // 2, 32)
            )
            return
        snapshot_preview = pygame.Surface((AREA_WIDTH, AREA_HEIGHT))
        player_snap, guards_snap = self.snapshots[self.selected]
        player = Player(self.core.level)
        player.load_snapshot(player_snap)
        guards = [
            Guard(self.core.guards[0].route, self.core.level) for _ in guards_snap
        ]
        for guard, guard_snap in zip(guards, guards_snap):
            guard.load_snapshot(guard_snap)
        render(snapshot_preview, self.core.level, player, guards)
        snapshot_preview = pygame.transform.scale_by(snapshot_preview, 0.5)
        if self.because_caught:
            powered_by_text = res.render_text(
                "Sucks. Luckily, you have Time Value Inc. ® on your side!", 16
            )
        else:
            powered_by_text = res.render_text(
                "Travel back in time, powered by Time Value Inc. ®!", 16
            )
        surface.blit(
            powered_by_text, dest=(AREA_WIDTH // 2 - powered_by_text.width // 2, 32)
        )
        surface.blit(snapshot_preview, dest=(AREA_WIDTH // 4, AREA_HEIGHT // 4))
        if self.selected != 0:
            surface.blit(
                self.left_arrow,
                dest=(
                    AREA_WIDTH // 4 - 128,
                    AREA_HEIGHT // 2 - self.left_arrow.height // 2,
                ),
            )
        if self.selected != len(self.snapshots) - 1:
            surface.blit(
                self.right_arrow,
                dest=(
                    3 * AREA_WIDTH // 4 + 64,
                    AREA_HEIGHT // 2 - self.left_arrow.height // 2,
                ),
            )
        time_ago = round(self.snapshot_times[self.selected], 1)
        snapshot_info_text = res.render_text(f"{time_ago:.1f}s ago", 32)
        surface.blit(
            snapshot_info_text,
            dest=(
                AREA_WIDTH // 2 - snapshot_info_text.width // 2,
                AREA_HEIGHT // 2 + snapshot_preview.height // 2,
            ),
        )
        disclaimer = f"Repayment: Your movement speed will be halved for the next {time_ago * 1.25:.1f} seconds"
        instr = "[ENTER] to confirm"
        if not self.because_caught:
            instr += "      [ESC] to cancel"
        disclaimer_text = res.render_text(
            disclaimer + "\n\n" + instr,
            16,
        )
        surface.blit(
            disclaimer_text,
            dest=(
                AREA_WIDTH // 2 - disclaimer_text.width // 2,
                AREA_HEIGHT // 2 + snapshot_preview.height // 2 + 48,
            ),
        )
