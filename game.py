import sys
from pathlib import Path
from typing import Self

import pygame
from PIL import Image

pygame.init()

ROOT = Path(__file__).parent
LEVELS_DIR = ROOT / "levels"

WIDTH, HEIGHT = 800, 600
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Time Value Inc.")
clock = pygame.time.Clock()

BG_COLOR = (24, 24, 28)
PLAYER_COLOR = (70, 180, 255)
WALL_COLOR = (140, 140, 160)
BORDER_COLOR = (60, 60, 75)


def rect_edges(rect: pygame.Rect) -> list[tuple[tuple[int, int], tuple[int, int]]]:
    return [
        (rect.topleft, rect.topright),
        (rect.topright, rect.bottomright),
        (rect.bottomright, rect.bottomleft),
        (rect.bottomleft, rect.topleft),
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


class LevelMap:
    TILEMAP_WALL = (0, 0, 0)
    TILEMAP_PLAYER = (255, 0, 0)
    TILEMAP_GOAL = (255, 255, 0)
    TILEMAP_GUARD = (0, 0, 255)

    def __init__(self, im: Image.Image):
        self.im = im
        self.scale_factor = WIDTH // im.width
        self.process()

    @classmethod
    def from_file(cls, filelike) -> Self:
        return cls(Image.open(filelike))

    def process(self):
        self.walls = []
        self.player_start = (0, 0)
        self.goal = None
        guard_tiles = set()
        for y in range(self.im.height):
            for x in range(self.im.width):
                p = self.im.getpixel((x, y))
                if p == LevelMap.TILEMAP_WALL:
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

        self.guard_routes = []
        while guard_tiles:
            tile = guard_tiles.pop()
            route = [tile]
            for other_tile in guard_tiles:
                if (abs(other_tile[0] - tile[0]) == 1) ^ (abs(other_tile[1] - tile[1]) == 1):
                    route.append(other_tile)
            for tile in route[1:]:
                guard_tiles.remove(tile)
            self.guard_routes.append(set(route))


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
        elif self.pos.x + self.radius > WIDTH:
            self.pos.x = WIDTH - self.radius
            self.vel.x = 0

        if self.pos.y - self.radius < 0:
            self.pos.y = self.radius
            self.vel.y = 0
        elif self.pos.y + self.radius > HEIGHT:
            self.pos.y = HEIGHT - self.radius
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


LEVEL_MAPS = [LevelMap.from_file(f) for f in LEVELS_DIR.iterdir()]
LEVEL = LEVEL_MAPS[0]

player = Player(*LEVEL.player_start, radius=18)

running = True
while running:
    # Delta time in seconds
    dt = clock.tick(120) / 1000.0

    for event in pygame.event.get():
        if (
            event.type == pygame.QUIT
            or event.type == pygame.KEYDOWN
            and event.key == pygame.K_ESCAPE
        ):
            running = False

    player.update(dt, LEVEL.walls)

    screen.fill(BG_COLOR)

    for wall in LEVEL.walls:
        pygame.draw.rect(screen, WALL_COLOR, wall, border_radius=4)
        pygame.draw.rect(screen, BORDER_COLOR, wall, width=2, border_radius=4)

    player.draw(screen)

    pygame.display.flip()

pygame.quit()
sys.exit()
