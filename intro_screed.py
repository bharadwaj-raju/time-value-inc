import pygame

from consts import BG_COLOR, SCREEN_HEIGHT, SCREEN_WIDTH
from resources import res
from state import State


class IntroScreed(State):
    def __init__(self, mgr):
        super().__init__(mgr)
        self.line = 0
        self.lines = (
            ("Hello. It’s good to see you again.", res.player_happy),
            ("We have a new mission for you.", res.player_eyes),
            (
                "Infiltration again, but our reconnaissance shows that the facility is far more tightly-guarded\nthan anything we’ve done so far.",
                res.player_shock,
            ),
            (
                "Don’t worry! We’re hiring the services of this innovative new firm, Time Value Inc.",
                res.player_eyes,
            ),
            (
                "They develop a bunch of cool time-manipulation tech — time travel and speed control.",
                res.player_eyes,
            ),
            (
                "How are we paying for it? Well, strangely enough, this company wants to be repaid in time itself.",
                res.player_eyes,
            ),
            (
                "When you manipulate time with their products, you’re slowed down for that much time \n(plus a little extra for their profit margin).",
                res.player_eyes,
            ),
            (
                "It’s like that saying, you know? Living on borrowed time? But it’s useful this time!",
                res.player_shock,
            ),
            ("Anyway, let’s get you into training! Off you go!", res.player_shock),
        )
        self.continue_prompt_text = res.render_text(
            "Press [ENTER] to continue", 16
        )


    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            self.line += 1
            if self.line == len(self.lines):
                self.mgr.pop()

    def draw(self, surface):
        surface.fill(BG_COLOR)
        surface.blit(
            res.render_text("\n\n".join(l[0] for l in self.lines[: self.line + 1]), 16),
            dest=(16, 16),
        )
        sprite = pygame.transform.scale(self.lines[self.line][1], (128, 128))
        surface.blit(sprite, dest=(SCREEN_WIDTH // 2 - sprite.width // 2, 256 + 128 + 64))
        surface.blit(
            self.continue_prompt_text,
            dest=(SCREEN_WIDTH // 2 - self.continue_prompt_text.width // 2, SCREEN_HEIGHT - 32),
        )
