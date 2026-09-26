import sys

import PIL
import pygame

from consts import BG_COLOR, SCREEN_HEIGHT, SCREEN_WIDTH
from resources import res
from state import State


def fmtver(ver):
    maj, min, patch, *_ = ver
    return f"{maj}.{min}.{patch}"

class Credits(State):
    def __init__(self, mgr):
        super().__init__(mgr)
        self.lines = (
            "This game is an entry for the PyWeek September 2026 challenge “Borrowed Time”.\nhttps://pyweek.org/42/",
            "I would also like to shout out the Python Discord :)\nhttps://discord.gg/python",
            "Made by Bharadwaj Raju, open source (MIT).\nhttps://github.com/bharadwaj-raju/time-value-inc",
            "Thanks to Nicky Case, and Amit Patel of Red Blob Games\nfor their resources on implementing the visibility and lighting mechanic.\nhttps://ncase.me/sight-and-light/\nhttps://www.redblobgames.com/articles/visibility/",
            "Font is GNU Unifont, licensed under the SIL Open Font License.\nhttps://unifoundry.com/unifont/",
            "Sprites drawn by me in LibreSprite and KolourPaint.",
            f"pygame-ce {fmtver(pygame.vernum)}\nSDL {fmtver(pygame.version.SDL)}\nPillow {PIL.__version__}\nPython {fmtver(sys.version_info)}",
        )
        self.player_sprite = pygame.transform.scale(res.player_shock, (128, 128))
        self.guard_sprite = pygame.transform.scale(res.enemy_spotted, (128, 128))
        self.text = res.render_text("\n\n".join(self.lines), 16)
        self.continue_prompt_text = res.render_text(
            "Press [ENTER] to go back to the title screen", 16
        )

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            self.mgr.pop()

    def draw(self, surface):
        surface.fill(BG_COLOR)
        surface.blit(self.text, dest=(16, 16))
        player_width = self.player_sprite.width 
        guard_width = self.guard_sprite.width
        gap = 64

        total_sprites_width = player_width + gap + guard_width

        start_x = (SCREEN_WIDTH - total_sprites_width) // 2
        sprites_y_pos = 256 + 128 + 64
        surface.blit(
            self.player_sprite,
            dest=(start_x, sprites_y_pos),
        )
        surface.blit(
            self.guard_sprite,
            dest=(start_x + player_width + gap, sprites_y_pos),
        )
        surface.blit(
            self.continue_prompt_text,
            dest=(
                SCREEN_WIDTH // 2 - self.continue_prompt_text.width // 2,
                SCREEN_HEIGHT - 32,
            ),
        )
