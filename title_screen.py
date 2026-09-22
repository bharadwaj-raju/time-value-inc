import pygame

from consts import BG_COLOR
from core_game import CoreGameState
from resources import res
from state import State, StateManager


class TitleScreenState(State):
    def __init__(self, mgr: StateManager):
        super().__init__(mgr)
        assert res.font64
        self.timevalue_surf = res.render_text("Time\nValue", 64)
        self.value_surf = res.render_text("Value", 64)
        self.inc_surf = res.render_text("Inc.", 32)
        self.regmark_surf = res.render_text("®", 32)
        self.tagline_surf = res.render_text("“Never heard of us? We can fix that!”", 16)
        self.enter_surf = res.render_text("Press [ENTER] to start", 32)

    def draw(self, surface):
        surface.fill(BG_COLOR)
        logo_offset_y = 128
        surface.blit(
            self.timevalue_surf,
            dest=(surface.width // 2 - self.timevalue_surf.size[0] // 2 - 32, logo_offset_y),
        )
        surface.blit(
            self.inc_surf,
            dest=(
                surface.width // 2 + 24 + 32,
                self.timevalue_surf.size[1] - self.inc_surf.size[1] - 6 + logo_offset_y,
            ),
        )
        surface.blit(
            self.regmark_surf,
            dest=(
                surface.width // 2 + 32,
                logo_offset_y,
            ),
        )

        so_far = self.timevalue_surf.size[1] - self.inc_surf.size[1] - 6 + logo_offset_y + 32
        surface.blit(
            self.tagline_surf,
            dest=(surface.width // 2 - self.tagline_surf.size[0] // 2, so_far + 32)
        )

        so_far += 32 + self.tagline_surf.size[1]
        surface.blit(
            self.enter_surf,
            dest=(surface.width // 2 - self.enter_surf.size[0] // 2, so_far + 128)
        )

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
            self.mgr.change(CoreGameState(self.mgr))
        
