import math
import os
from collections import deque

import pygame
import pygame.gfxdraw

from animation import AnimationPlayer, AnimationPlayStyle
from consts import AREA_HEIGHT, AREA_WIDTH, BG_COLOR, DISABLED_COLOR, STATUSBAR_HEIGHT
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
SPEEDUP_COLOR = (106, 190, 48)
REPAYMENT_COLOR = (251, 242, 54)
BACKINTIME_COLOR = (91, 110, 225)


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

    def get_rect(self) -> pygame.Rect:
        return pygame.Rect(self.pos - (self.radius, self.radius), (self.radius * 2, self.radius * 2))


class Player(MovableEntity):
    def __init__(self, level: LevelMap):
        super().__init__(*level.player_start, radius=16)
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

scale = pygame.transform.scale_by

def render(
    surface,
    level: LevelMap,
    player: Player,
    guards: list[Guard],
    goal_anim: AnimationPlayer,
    draw_player=True,
    firing_lasers=False,
    player_just_restored=False,
    key=None,
    trapdoors_thrown=(),
):
    player_vis_poly = calculate_sweep_line(player.pos.x, player.pos.y, level.wall_edges)
    surface.fill(BG_COLOR)
    caught = False
    for guard in guards:
        guard.draw(surface)
        if guard.caught:
            caught = True
    if draw_player:
        player.draw(surface, caught=caught or player_just_restored)
    if key:
        surface.blit(res.key, key)
        surface.blit(res.lock, level.locked_door)
    if len(player_vis_poly) >= 3:
        fog_surf = pygame.Surface((AREA_WIDTH, AREA_HEIGHT))
        fog_surf.fill((10, 10, 15))
        MASK_COLOR = (255, 0, 255)
        pygame.gfxdraw.filled_polygon(fog_surf, player_vis_poly, MASK_COLOR)

        fog_surf.set_colorkey(MASK_COLOR)

        surface.blit(fog_surf, (0, 0))
    for wall in level.walls:
        surface.blit(res.wall_base, wall)
    for trapdoor in trapdoors_thrown:
        surface.blit(res.wall_base, trapdoor)
    for gun in level.laser_guns:
        surface.blit(
            res.wall_laser_gun_firing if firing_lasers else res.wall_laser_gun_base, gun
        )
    if firing_lasers:
        for laser_danger in level.laser_guns_danger:
            surface.blit(res.laser_gun_fire, laser_danger)
    if level.tutorial_text_marker:
        for tile in level.tutorial_text_tiles:
            pygame.draw.rect(surface, BG_COLOR, (*tile, level.scale_factor, level.scale_factor))
        dest = (level.tutorial_text_marker[0] + 16, level.tutorial_text_marker[1] + 16)
        surface.blit(res.render_text(level.tutorial_text, 16), dest=dest)

    assert level.goal
    goal_anim.draw(
        surface,
        (level.goal[0] * level.scale_factor, level.goal[1] * level.scale_factor),
    )


def mm_ss(t: float) -> str:
    mins, rsecs = divmod(t, 60)
    return f"{int(mins):02d}:{rsecs:04.1f}"


class CoreGameState(State):
    def __init__(self, mgr: StateManager, level: LevelMap):
        super().__init__(mgr)
        self.level = level

        self.t = 0

        self.player = Player(self.level)
        self.guards = [Guard(route, self.level) for route in self.level.guard_routes]

        self.state_snapshots = deque(maxlen=5000)

        self.guard_timer = Timer(duration=0.5, repeating=True, callback=self.guard_step)
        self.guard_timer.start()

        self.snapshot_timer = Timer(
            duration=1.0, repeating=True, callback=self.take_snapshot
        )
        self.snapshot_timer.start()

        self.debuff = False
        self.end_debuff_timer = Timer(
            duration=0.0, repeating=False, callback=self.end_debuff
        )

        self.repayment_label = res.render_text("REPAYMENT", 16, color=DISABLED_COLOR)
        self.repayment_active_label = res.render_text("REPAYMENT", 16, color=REPAYMENT_COLOR)

        self.backinttime_key_label = res.render_text("BACK IN TIME\n[B]", 16)
        self.backinttime_active_key_label = res.render_text("BACK IN TIME\n[B]", 16, color=BACKINTIME_COLOR)
        
        self.speedup_key_label = res.render_text("SPEEDUP\n[S]", 16)
        self.speedup_active_key_label = res.render_text("SPEEDUP\n[S]", 16, color=SPEEDUP_COLOR)
        self.speedup_disabled_key_label = res.render_text("SPEEDUP\n[S]", 16, color=DISABLED_COLOR)

        self.speedup = False
        self.end_speedup_timer = Timer(
            duration=3.0, repeating=False, callback=self.end_speedup
        )

        self.goal_anim = AnimationPlayer(
            res.goal_anim, playstyle=AnimationPlayStyle.PINGPONG
        )

        self.firing_lasers = False
        self.fire_lasers_timer = Timer(
            duration=0.25, repeating=True, callback=self.fire_lasers
        )
        self.fire_lasers_timer.start()

        self.got_key = False
        self.need_key = self.level.key is not None

        self.trapdoors_thrown = []

        assert self.level.goal
        goal_pos = pygame.Vector2(*self.level.goal) * self.level.scale_factor
        goal_size = self.goal_anim.animation.size
        self.goal_rect = pygame.Rect(goal_pos, goal_size)

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_b:
                self.mgr.push(SnapshotViewState(self.mgr))
            elif event.key == pygame.K_s and not (self.debuff or self.speedup):
                self.speedup = True
                self.end_speedup_timer.start()
            elif event.key == pygame.K_i and os.getlogin() == "bharadwaj":
                self.mgr.pop()

    def update(self, dt):
        self.t += dt
        player_dt = (dt / 2) if self.debuff else dt
        enemy_dt = (dt / 2) if self.speedup else dt
        self.guard_timer.update(enemy_dt)
        for guard in self.guards:
            guard.check_caught((int(self.player.pos.x), int(self.player.pos.y)))
            if guard.caught:
                self.mgr.push(CaughtHoldEffectState(self.mgr))
                return
        self.fire_lasers_timer.update(enemy_dt)
        if self.firing_lasers:
            for laser_danger in self.level.laser_guns_danger:
                lx, ly = laser_danger
                lw, lh = self.level.scale_factor, self.level.scale_factor
                lx += self.level.scale_factor // 4
                lw -= self.level.scale_factor // 2
                for pos in (
                    self.player.pos,
                    *adjacents(*self.player.pos, by=16),
                ):
                    if pygame.Rect(lx, ly, lw, lh).collidepoint(*pos):
                        self.mgr.push(CaughtHoldEffectState(self.mgr))
                        return
        player_rect = self.player.get_rect()
        for trigger, trap in self.level.trapdoor_triggers.items():
            trigger_rect = pygame.Rect(*trigger, self.level.scale_factor, self.level.scale_factor)
            if player_rect.colliderect(trigger_rect) and trap not in self.trapdoors_thrown:
                self.trapdoors_thrown.append(trap)
            
        if player_rect.colliderect(self.goal_rect) and (self.got_key or not self.need_key):
            self.mgr.pop()
        if self.need_key:
            key_pos = self.level.key
            assert key_pos
            key_size = res.key.size
            if player_rect.colliderect(pygame.Rect(key_pos, key_size)):
                self.got_key = True
        self.snapshot_timer.update(dt)
        self.end_debuff_timer.update(dt)
        self.end_speedup_timer.update(dt)
        walls = self.level.walls[:]
        if self.need_key and not self.got_key:
            lock_rect = pygame.Rect(*self.level.locked_door, self.level.scale_factor, self.level.scale_factor)  # ty: ignore
            walls.append(lock_rect)
        for trapdoor in self.trapdoors_thrown:
            trapdoor_rect = pygame.Rect(*trapdoor, self.level.scale_factor, self.level.scale_factor)  # ty: ignore[no-matching-overload]
            walls.append(trapdoor_rect)
        self.player.update(player_dt, walls)
        self.goal_anim.update(dt)
        if len(self.state_snapshots) == 0:
            print("taking first snapshot")
            self.take_snapshot()

    def draw_countdown(self, surface, x, y, fraction, color):
        pygame.draw.rect(surface, (255, 255, 255), (x, y, 50, 8), 1)
        pygame.draw.rect(
            surface,
            color,
            (
                x,
                y,
                50 * fraction,
                8,
            ),
        )

    def draw(self, surface):
        if any(guard.caught for guard in self.guards):
            return
        render(
            surface,
            self.level,
            self.player,
            self.guards,
            self.goal_anim,
            firing_lasers=self.firing_lasers,
            key=self.level.key,
            trapdoors_thrown=self.trapdoors_thrown,
        )
        # assert self.level.goal
        # goal_pos = pygame.Vector2(*self.level.goal) * self.level.scale_factor
        # goal_size = self.goal_anim.animation.size
        # player_rect = self.player.get_rect()
        # goal_rect = pygame.Rect(goal_pos, goal_size)
        # pygame.draw.rect(surface, (255, 0, 0), player_rect, width=1)
        # pygame.draw.rect(surface, (0, 255, 0), goal_rect, width=1)
        clock = mm_ss(self.t)
        clock_secs = clock[:-2]
        clock_mils = clock[-2:]
        clock_secs_text = res.render_text(clock_secs, 32)
        clock_mils_text = res.render_text(clock_mils, 32, color=DISABLED_COLOR)
        surface.blit(
            clock_secs_text, dest=(32, AREA_HEIGHT + STATUSBAR_HEIGHT // 2 - clock_secs_text.height // 2 - 2)
        )
        surface.blit(
            clock_mils_text, dest=(32 + clock_secs_text.width, AREA_HEIGHT + STATUSBAR_HEIGHT // 2 - clock_secs_text.height // 2 - 2)
        )
        btns_offset_x = 128 + 32
        res.backintime_icon.draw(
            surface, dest=(btns_offset_x + 32, AREA_HEIGHT + 16), scale=3
        )
        surface.blit(
            self.backinttime_key_label,
            dest=(btns_offset_x + 32 + 16 * 3 + 8, AREA_HEIGHT + 16 + 8),
        )
        ff_color = (255, 255, 255)
        ff_label = self.speedup_key_label
        if self.debuff:
            ff_color = DISABLED_COLOR
            ff_label = self.speedup_disabled_key_label
        if self.speedup:
            ff_color = SPEEDUP_COLOR
            ff_label = self.speedup_active_key_label
        res.ff_icon.draw(surface, dest=(btns_offset_x + 256, AREA_HEIGHT + 16), scale=3, color=ff_color)
        surface.blit(
            ff_label,
            dest=(btns_offset_x + 256 + 16 * 3 + 8, AREA_HEIGHT + 16 + 8),
        )
        if self.speedup:
            self.draw_countdown(
                surface,
                self.player.pos.x - self.player.radius - 10,# - 50//2,
                self.player.pos.y - self.player.radius - 12,
                0.0 if self.end_speedup_timer.duration == 0.0
                else
                self.end_speedup_timer.time_left / self.end_speedup_timer.duration,
                SPEEDUP_COLOR,
            )
        surface.blit(
            self.repayment_label if not self.debuff else self.repayment_active_label,
            dest=(
                AREA_WIDTH - 32 - self.repayment_label.width - 8,
                AREA_HEIGHT + STATUSBAR_HEIGHT // 2 - self.repayment_label.height // 2,
            )
        )
        if self.debuff:
            self.draw_countdown(
                surface,
                self.player.pos.x - self.player.radius - 10,# - 50//2,
                self.player.pos.y - self.player.radius - 12,
                0.0
                if self.end_debuff_timer.duration == 0.0
                else self.end_debuff_timer.time_left / self.end_debuff_timer.duration,
                REPAYMENT_COLOR,
            )
        if self.got_key:
            surface.blit(res.key, dest=(AREA_WIDTH - 32 - self.repayment_label.width - 8 - 40 - 32, AREA_HEIGHT + STATUSBAR_HEIGHT // 2 - res.key.height // 2))

    def take_snapshot(self):
        # got_key is intentionally excluded from snapshotting
        # keys are transported across time with the player, let us say :)
        snap = (
            self.player.snapshot(),
            [g.snapshot() for g in self.guards],
            self.firing_lasers,
            self.fire_lasers_timer.snapshot(),
            self.guard_timer.snapshot(),
            self.trapdoors_thrown.copy()
        )
        self.state_snapshots.append((self.t, snap))

    def load_snapshot(self, snap, penalty=0.0):
        t, (player_snap, guard_snaps, firing_lasers, fire_lasers_timer, guard_step_timer, trapdoors_thrown) = snap
        self.player.load_snapshot(player_snap)
        self.player.vel = pygame.Vector2(0.0, 0.0)
        for guard, guard_snap in zip(self.guards, guard_snaps):
            guard.load_snapshot(guard_snap)
        self.firing_lasers = firing_lasers
        self.fire_lasers_timer.load_snapshot(fire_lasers_timer)
        self.guard_timer.load_snapshot(guard_step_timer)
        self.trapdoors_thrown = trapdoors_thrown.copy()
        self.t = t
        self.speedup = False
        self.end_speedup_timer.stop()
        self.debuff = True
        self.end_debuff_timer.time_left += penalty
        self.end_debuff_timer.duration += penalty
        self.end_debuff_timer.active = True
        state_snapshots_new = [snap for snap in self.state_snapshots if snap[0] <= t]
        self.state_snapshots.clear()
        self.state_snapshots.extend(state_snapshots_new)

    def guard_step(self):
        for guard in self.guards:
            guard.update()

    def end_debuff(self):
        self.debuff = False
        self.end_debuff_timer.duration = 0.0

    def end_speedup(self):
        self.speedup = False
        self.debuff = True
        self.end_debuff_timer.time_left += self.end_speedup_timer.duration
        self.end_debuff_timer.duration += self.end_speedup_timer.duration
        self.end_debuff_timer.active = True

    def fire_lasers(self):
        self.firing_lasers = not self.firing_lasers
        self.fire_lasers_timer.start()


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
        render(
            surface,
            self.core.level,
            self.core.player,
            self.core.guards,
            self.core.goal_anim,
            firing_lasers=self.core.firing_lasers,
            player_just_restored=True,
            key=self.core.level.key,
            trapdoors_thrown=self.core.trapdoors_thrown,
        )

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
        self.end_effect_timer = Timer(0.75, repeating=False, callback=self.end)
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
            self.core.goal_anim,
            draw_player=self.draw_player,
            player_just_restored=True,
            key=self.core.level.key,
            trapdoors_thrown=self.core.trapdoors_thrown,
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
        if self.snapshots and round(self.core.t - self.snapshots[-1][0], 1) == 0.0:
            self.snapshots.pop()
        self.selected = len(self.snapshots) - 1
        self.current_surf = pygame.Surface((AREA_WIDTH, AREA_HEIGHT))
        render(
            self.current_surf,
            self.core.level,
            self.core.player,
            self.core.guards,
            self.core.goal_anim,
            firing_lasers=self.core.firing_lasers,
            key=self.core.level.key,
            trapdoors_thrown=self.core.trapdoors_thrown
        )
        self.blur_radius = 0
        self.darkening = 0
        self.blurred_surf = None
        self.left_arrow = res.render_text("←", 256, color=BACKINTIME_COLOR)
        self.right_arrow = res.render_text("→", 256, color=BACKINTIME_COLOR)
        self.because_caught = because_caught

        self.arrow_animate_delta = 0
        self.arrow_animate_timer = Timer(duration=0.2, repeating=True, callback=self.arrow_animate)
        self.arrow_animate_timer.start()

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE and not self.because_caught:
                self.mgr.pop()
            elif event.key == pygame.K_LEFT:
                self.selected = max(0, self.selected - 1)
            elif event.key == pygame.K_RIGHT:
                self.selected = min(len(self.snapshots) - 1, self.selected + 1)
            elif event.key == pygame.K_RETURN and self.snapshots:
                snap_t, (snap) = self.snapshots[self.selected]
                ago = self.core.t - snap_t
                repayment = round(round(ago, 1) * 1.5, 1)
                self.core.load_snapshot((snap_t, snap), penalty=repayment)
                self.mgr.pop()
                self.mgr.push(SnapshotRestoreEffectState(self.mgr))

    def update(self, dt):
        if self.blur_radius < 10:
            self.blur_radius += 1
        if self.darkening < 100:
            self.darkening += 10
        self.arrow_animate_timer.update(dt)

    def arrow_animate(self):
        self.arrow_animate_delta = 8 if self.arrow_animate_delta == 0 else 0

    def draw(self, surface):
        surface.fill(BG_COLOR)
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
        btns_offset_x = 128 + 32
        res.backintime_icon.draw(
            surface, dest=(btns_offset_x + 32, AREA_HEIGHT + 16), scale=3, color=BACKINTIME_COLOR
        )
        surface.blit(
            self.core.backinttime_active_key_label,
            dest=(btns_offset_x + 32 + 16 * 3 + 8, AREA_HEIGHT + 16 + 8),
        )
        snapshot_preview = pygame.Surface((AREA_WIDTH, AREA_HEIGHT))
        snapshot_state = CoreGameState(self.mgr, self.core.level)
        snapshot_state.load_snapshot(self.snapshots[self.selected])
        snapshot_state.draw(snapshot_preview)
        snap_t = self.snapshots[self.selected][0]
        pygame.draw.rect(snapshot_preview, (255, 255, 255), (*snapshot_state.player.pos - (snapshot_state.player.radius, snapshot_state.player.radius), snapshot_state.player.radius*2, snapshot_state.player.radius*2), width=2)
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
                    AREA_WIDTH // 4 - 128 - 32 - self.arrow_animate_delta,
                    AREA_HEIGHT // 2 - self.left_arrow.height // 2,
                ),
            )
        if self.selected != len(self.snapshots) - 1:
            surface.blit(
                self.right_arrow,
                dest=(
                    3 * AREA_WIDTH // 4 + 32 + self.arrow_animate_delta,
                    AREA_HEIGHT // 2 - self.left_arrow.height // 2,
                ),
            )
        time_ago = round(self.core.t - snap_t, 1)
        snapshot_info_text = res.render_text(mm_ss(snap_t), 32)
        surface.blit(
            snapshot_info_text,
            dest=(
                AREA_WIDTH // 2 - snapshot_info_text.width // 2,
                AREA_HEIGHT // 2 + snapshot_preview.height // 2,
            ),
        )
        disclaimer = f"REPAYMENT: Your movement speed will be halved for the next {time_ago * 1.25:.1f} seconds"
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
