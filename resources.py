import pygame

from consts import ROOT

FONT_FILE = ROOT / "unifont-subset.ttf"


class Resources:
    font64: pygame.font.Font | None = None
    font32: pygame.font.Font | None = None
    font16: pygame.font.Font | None = None

    @classmethod
    def load(cls):
        cls.font64 = pygame.font.Font(FONT_FILE, 64)
        cls.font32 = pygame.font.Font(FONT_FILE, 32)
        cls.font16 = pygame.font.Font(FONT_FILE, 16)

    @classmethod
    def render_text(cls, text, size) -> pygame.Surface:
        font = {16: res.font16, 32: res.font32, 64: res.font64}[size]
        assert font
        return font.render(text, antialias=False, color=(255, 255, 255))


res = Resources()
