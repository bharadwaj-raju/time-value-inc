import pygame

from animation import Animation
from consts import ROOT
from icon import Icon

FONT_FILE = ROOT / "unifont-subset.ttf"


class Resources:
    font128: pygame.font.Font
    font64: pygame.font.Font
    font32: pygame.font.Font
    font16: pygame.font.Font
    font8: pygame.font.Font

    backintime_icon = Icon(ROOT / "icons" / "backintime.pbm")
    rewind_icon = Icon(ROOT / "icons" / "rewind.pbm")
    ff_icon = Icon(ROOT / "icons" / "ff.pbm")

    player_base: pygame.Surface
    player_eyes: pygame.Surface
    player_shock: pygame.Surface
    player_happy: pygame.Surface

    enemy_base: pygame.Surface
    enemy_spotted: pygame.Surface

    goal_anim: Animation

    @classmethod
    def load(cls):
        cls.font128 = pygame.font.Font(FONT_FILE, 128)
        cls.font64 = pygame.font.Font(FONT_FILE, 64)
        cls.font32 = pygame.font.Font(FONT_FILE, 32)
        cls.font16 = pygame.font.Font(FONT_FILE, 16)
        cls.font8 = pygame.font.Font(FONT_FILE, 8)
        cls.player_base = pygame.image.load(ROOT / "sprites" / "Sprite-Player-Base.png").convert_alpha()
        cls.player_eyes = pygame.image.load(ROOT / "sprites" / "Sprite-Player-EyesFront.png").convert_alpha()
        cls.player_shock = pygame.image.load(ROOT / "sprites" / "Sprite-Player-Shock.png").convert_alpha()
        cls.player_happy = pygame.image.load(ROOT / "sprites" / "Sprite-Player-Happy.png").convert_alpha()

        cls.enemy_base = pygame.image.load(ROOT / "sprites" / "Sprite-Enemy-Base.png").convert_alpha()
        cls.enemy_spotted = pygame.image.load(ROOT / "sprites" / "Sprite-Enemy-Spotted.png").convert_alpha()

        cls.goal_anim = Animation(ROOT / "sprites" / "Sprite-Goal-Glow.png")

    @classmethod
    def render_text(cls, text, size) -> pygame.Surface:
        font = {8: res.font8, 16: res.font16, 32: res.font32, 64: res.font64, 128: res.font128}[size]
        return font.render(text, antialias=False, color=(255, 255, 255))


res = Resources()
