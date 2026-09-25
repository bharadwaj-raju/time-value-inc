import json

import pygame
from PIL import Image

from animation import Animation
from consts import ROOT
from icon import Icon
from level_map import LevelMap
from save import Save

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

    wall_base: pygame.Surface
    wall_laser_gun_base: pygame.Surface
    wall_laser_gun_firing: pygame.Surface
    laser_gun_fire: pygame.Surface

    goal_anim: Animation

    levels: list[LevelMap]
    tutorials: list[LevelMap]

    save: Save

    @classmethod
    def load(cls):
        cls.font128 = pygame.font.Font(FONT_FILE, 128)
        cls.font64 = pygame.font.Font(FONT_FILE, 64)
        cls.font32 = pygame.font.Font(FONT_FILE, 32)
        cls.font16 = pygame.font.Font(FONT_FILE, 16)
        cls.font8 = pygame.font.Font(FONT_FILE, 8)
        cls.player_base = pygame.image.load(
            ROOT / "sprites" / "Sprite-Player-Base.png"
        ).convert_alpha()
        cls.player_eyes = pygame.image.load(
            ROOT / "sprites" / "Sprite-Player-EyesFront.png"
        ).convert_alpha()
        cls.player_shock = pygame.image.load(
            ROOT / "sprites" / "Sprite-Player-Shock.png"
        ).convert_alpha()
        cls.player_happy = pygame.image.load(
            ROOT / "sprites" / "Sprite-Player-Happy.png"
        ).convert_alpha()

        cls.enemy_base = pygame.image.load(
            ROOT / "sprites" / "Sprite-Enemy-Base.png"
        ).convert_alpha()
        cls.enemy_spotted = pygame.image.load(
            ROOT / "sprites" / "Sprite-Enemy-Spotted.png"
        ).convert_alpha()

        cls.wall_base = pygame.image.load(
            ROOT / "sprites/Sprite-Wall.png"
        ).convert_alpha()
        cls.wall_laser_gun_base = pygame.image.load(
            ROOT / "sprites/Sprite-Laser-Gun.png"
        ).convert_alpha()
        cls.wall_laser_gun_firing = pygame.image.load(
            ROOT / "sprites/Sprite-Laser-Gun-Firing.png"
        ).convert_alpha()
        cls.laser_gun_fire = pygame.image.load(
            ROOT / "sprites/Sprite-Laser-Fire.png"
        ).convert_alpha()

        cls.goal_anim = Animation(ROOT / "sprites" / "Sprite-Goal-Glow.png")

        levels_meta = json.loads((ROOT / "levels/meta.json").read_text())
        cls.levels = []
        cls.tutorials = []
        for tut in levels_meta["tutorials"]:
            cls.tutorials.append(
                LevelMap(
                    Image.open(ROOT / "levels" / tut["file"]), tutorial_text=tut["text"]
                )
            )
        for lvl in levels_meta["levels"]:
            cls.levels.append(LevelMap(Image.open(ROOT / "levels" / lvl)))

        cls.save = Save(ROOT / "save.json")

    @classmethod
    def render_text(cls, text, size) -> pygame.Surface:
        font = {
            8: res.font8,
            16: res.font16,
            32: res.font32,
            64: res.font64,
            128: res.font128,
        }[size]
        return font.render(text, antialias=False, color=(255, 255, 255))


res = Resources()
