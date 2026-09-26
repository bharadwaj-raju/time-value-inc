import random
import sys

import pygame

from consts import AREA_HEIGHT, AREA_WIDTH, STATUSBAR_HEIGHT
from resources import res
from state import StateManager, Timer
from title_screen import TitleScreenState

pygame.init()
pygame.mixer.init()

screen = pygame.display.set_mode((AREA_WIDTH, AREA_HEIGHT + STATUSBAR_HEIGHT))
res.load()
pygame.display.set_caption("Time Value Inc.")
clock = pygame.time.Clock()

def tick():
    #res.tick.play()
    tick_timer.duration = random.uniform(0.80, 2.0)

running = True
state_mgr = StateManager()
state_mgr.push(TitleScreenState(state_mgr))
tick_timer = Timer(duration=1.0, repeating=True, callback=tick)
tick_timer.start()
while running:
    # Delta time in seconds
    dt = clock.tick(60) / 1000.0

    for event in pygame.event.get():
        if event.type == pygame.QUIT or event.type == pygame.KEYDOWN and event.key == pygame.K_q:
            running = False
            break
        if event.type == pygame.KEYDOWN and event.key == pygame.K_QUOTE:
            print(state_mgr.stack)
        state_mgr.handle_event(event)

    tick_timer.update(dt)
    state_mgr.update(dt)
    state_mgr.draw(screen)

    pygame.display.flip()

pygame.quit()
sys.exit()
