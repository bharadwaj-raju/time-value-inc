import pygame

from consts import BG_COLOR, SCREEN_HEIGHT, SCREEN_WIDTH
from resources import res
from state import State


class LevelDoneState(State):
    def __init__(self, mgr, extra_message=""):
        super().__init__(mgr)
        self.well_done_text = res.render_text("Well done!", 32)
        self.continue_prompt_text = res.render_text("Press [ENTER] to continue", 16)
        self.sprite = pygame.transform.scale(res.player_happy, (128, 128))
        self.extra_msg_text = res.render_text(extra_message, 16)

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
            self.mgr.pop()

    def draw(self, surface):
        surface.fill(BG_COLOR)
        surface.blit(self.well_done_text, (SCREEN_WIDTH // 2 - self.well_done_text.width // 2, 64))
        surface.blit(self.extra_msg_text, (SCREEN_WIDTH // 2 - self.extra_msg_text.width // 2, 128))
        surface.blit(self.continue_prompt_text, (SCREEN_WIDTH // 2 - self.continue_prompt_text.width // 2, SCREEN_HEIGHT - 64))
        surface.blit(self.sprite, (SCREEN_WIDTH // 2 - self.sprite.width // 2, SCREEN_HEIGHT // 2 - self.sprite.height // 2))

class WantResetState(State):
    def __init__(self, mgr):
        super().__init__(mgr)
        self.finished_text = res.render_text("The mission is over, you can go home.\n\nWait, what? You had fun? You want to do it again?\n\nI guess I could talk to the Time Value Inc. folks and send you back in time…\n\nIf you really want to erase your progress and start again, press [ENTER].\nOtherwise, [ESC].", 16)

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN:
                res.save.last_stage = "title-screen"
                res.save.save()
                self.mgr.pop()
                self.mgr.pop()
            elif event.key == pygame.K_ESCAPE:
                self.mgr.pop()  # self
                self.mgr.pop()  # level manager

    def draw(self, surface):
        surface.fill(BG_COLOR)
        surface.blit(self.finished_text, (16, 16))
