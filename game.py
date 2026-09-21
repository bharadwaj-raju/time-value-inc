import sys

import pygame

pygame.init()

WIDTH, HEIGHT = 800, 600
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Time Value Inc.")
clock = pygame.time.Clock()

BG_COLOR = (24, 24, 28)
PLAYER_COLOR = (70, 180, 255)
WALL_COLOR = (140, 140, 160)
BORDER_COLOR = (60, 60, 75)


def rect_edges(rect: pygame.Rect):
    return [
        (rect.topleft, rect.topright),
        (rect.topright, rect.bottomright),
        (rect.bottomright, rect.bottomleft),
        (rect.bottomleft, rect.topleft)
    ]

def keys_to_vec(keys):
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


player = Player(WIDTH // 2, HEIGHT // 2, radius=18)

walls = [
    pygame.Rect(120, 100, 160, 40),
    pygame.Rect(520, 100, 160, 40),
    pygame.Rect(220, 260, 40, 180),
    pygame.Rect(540, 260, 40, 180),
    pygame.Rect(340, 360, 120, 40),
]


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

    player.update(dt, walls)

    screen.fill(BG_COLOR)

    for wall in walls:
        pygame.draw.rect(screen, WALL_COLOR, wall, border_radius=4)
        pygame.draw.rect(screen, BORDER_COLOR, wall, width=2, border_radius=4)

    player.draw(screen)

    pygame.display.flip()

pygame.quit()
sys.exit()
