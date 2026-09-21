import sys

import pygame

from consts import AREA_HEIGHT, AREA_WIDTH, STATUSBAR_HEIGHT
from core_game import CoreGameState
from resources import res
from state import StateManager

pygame.init()
res.load()

screen = pygame.display.set_mode((AREA_WIDTH, AREA_HEIGHT + STATUSBAR_HEIGHT))
pygame.display.set_caption("Time Value Inc.")
clock = pygame.time.Clock()

running = True
state_mgr = StateManager()
state_mgr.push(CoreGameState())
while running:
    # Delta time in seconds
    dt = clock.tick(120) / 1000.0

    for event in pygame.event.get():
        if event.type == pygame.QUIT or event.type == pygame.KEYDOWN and event.key == pygame.K_q:
            running = False
        state_mgr.handle_event(event)

    state_mgr.update(dt)
    state_mgr.draw(screen)

    pygame.display.flip()

pygame.quit()
sys.exit()
