import pygame

from consts import ROOT
from icon import Icon

FONT_FILE = ROOT / "unifont-subset.ttf"


class Resources:
    font64: pygame.font.Font | None = None
    font32: pygame.font.Font | None = None
    font16: pygame.font.Font | None = None
    font8: pygame.font.Font | None = None

    backintime_icon = Icon(ROOT / "icons" / "backintime.pbm")
    rewind_icon = Icon(ROOT / "icons" / "rewind.pbm")
    ff_icon = Icon(ROOT / "icons" / "ff.pbm")

    @classmethod
    def load(cls):
        cls.font64 = pygame.font.Font(FONT_FILE, 64)
        cls.font32 = pygame.font.Font(FONT_FILE, 32)
        cls.font16 = pygame.font.Font(FONT_FILE, 16)
        cls.font8 = pygame.font.Font(FONT_FILE, 8)

    @classmethod
    def render_text(cls, text, size) -> pygame.Surface:
        font = {8: res.font8, 16: res.font16, 32: res.font32, 64: res.font64}[size]
        assert font
        return font.render(text, antialias=False, color=(255, 255, 255))


res = Resources()
