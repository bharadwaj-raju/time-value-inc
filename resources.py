import pygame

from consts import ROOT

FONT_FILE = ROOT / "unifont-subset.ttf"

class Resources:
    font = None

    @classmethod
    def load(cls):
        cls.font = pygame.font.Font(FONT_FILE, 24)

res = Resources()
